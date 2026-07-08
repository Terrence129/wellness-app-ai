# Author: Huang Qijun
# Email: 2692341798@qq.com

import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Sequence

from app.core.config import Settings
from app.rag.chunker import DocumentChunk, TextChunker
from app.rag.document_loader import DocumentLoader, KnowledgeDocument

_LOGGER = logging.getLogger("wellness_app")
_SCHEMA_VERSION = 1


class IndexBuildResult:
    def __init__(
        self,
        reused: bool,
        file_count: int,
        chunk_count: int,
        elapsed_ms: float,
    ) -> None:
        self.reused = reused
        self.file_count = file_count
        self.chunk_count = chunk_count
        self.elapsed_ms = elapsed_ms


class IndexManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index_path = settings.rag_index_path

    def ensure_index(self) -> IndexBuildResult:
        import time
        started = time.monotonic()

        loader = DocumentLoader(
            knowledge_dir=self._settings.rag_knowledge_dir,
            max_file_bytes=self._settings.rag_max_file_bytes,
            max_corpus_bytes=self._settings.rag_max_corpus_bytes,
        )
        documents = loader.load()

        if not documents:
            elapsed = (time.monotonic() - started) * 1000
            return IndexBuildResult(reused=False, file_count=0, chunk_count=0, elapsed_ms=elapsed)

        chunker = TextChunker(
            max_chunk_size=self._settings.rag_chunk_size,
            overlap=self._settings.rag_chunk_overlap,
        )
        chunks = chunker.chunk(documents)

        fingerprint = self._compute_fingerprint(documents, chunker)

        if self._can_reuse(fingerprint):
            elapsed = (time.monotonic() - started) * 1000
            return IndexBuildResult(
                reused=True,
                file_count=len(documents),
                chunk_count=len(chunks),
                elapsed_ms=elapsed,
            )

        self._build_atomic(documents, chunks, fingerprint)
        elapsed = (time.monotonic() - started) * 1000
        return IndexBuildResult(
            reused=False,
            file_count=len(documents),
            chunk_count=len(chunks),
            elapsed_ms=elapsed,
        )

    def _can_reuse(self, fingerprint: str) -> bool:
        if not os.path.isfile(self._index_path):
            return False
        try:
            connection = sqlite3.connect(f"file:{self._index_path}?mode=ro", uri=True)
            try:
                row = connection.execute(
                    "SELECT 1 FROM rag_meta WHERE key = 'schema_version' AND value = ?",
                    (str(_SCHEMA_VERSION),),
                ).fetchone()
                if row is None:
                    return False
                row = connection.execute(
                    "SELECT 1 FROM rag_meta WHERE key = 'fingerprint' AND value = ?",
                    (fingerprint,),
                ).fetchone()
                return row is not None
            finally:
                connection.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return False

    def _build_atomic(
        self,
        documents: Sequence[KnowledgeDocument],
        chunks: Sequence[DocumentChunk],
        fingerprint: str,
    ) -> None:
        os.makedirs(os.path.dirname(self._index_path) or ".", exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".sqlite3",
            prefix="rag-index-",
            dir=os.path.dirname(self._index_path) or ".",
        )
        os.close(tmp_fd)
        try:
            connection = sqlite3.connect(tmp_path)
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks
                    USING fts5(
                        chunk_id UNINDEXED,
                        title,
                        relative_path UNINDEXED,
                        ordinal UNINDEXED,
                        chunk_text,
                        tokenize='porter unicode61'
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rag_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT OR REPLACE INTO rag_meta(key, value) VALUES(?, ?)",
                    ("schema_version", str(_SCHEMA_VERSION)),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO rag_meta(key, value) VALUES(?, ?)",
                    ("fingerprint", fingerprint),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO rag_meta(key, value) VALUES(?, ?)",
                    ("file_count", str(len(documents))),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO rag_meta(key, value) VALUES(?, ?)",
                    ("chunk_count", str(len(chunks))),
                )
                rows = [
                    (chunk.chunk_id, chunk.title, chunk.relative_path, chunk.ordinal, chunk.text)
                    for chunk in chunks
                ]
                connection.executemany(
                    """
                    INSERT INTO rag_chunks(chunk_id, title, relative_path, ordinal, chunk_text)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                connection.commit()
            finally:
                connection.close()

            self._validate_index(tmp_path, len(chunks))
            shutil.move(tmp_path, self._index_path)
        except Exception:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
            raise

    @staticmethod
    def _validate_index(path: str, expected_chunk_count: int) -> None:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT value FROM rag_meta WHERE key = 'chunk_count'"
            ).fetchone()
            actual = int(row[0]) if row else 0
            if actual != expected_chunk_count:
                raise ValueError(
                    f"Index chunk count mismatch: expected {expected_chunk_count}, got {actual}"
                )
        finally:
            connection.close()

    def _compute_fingerprint(
        self, documents: Sequence[KnowledgeDocument], chunker: TextChunker
    ) -> str:
        parts: list[str] = []
        parts.append(f"schema={_SCHEMA_VERSION}")
        parts.append(f"chunk_size={self._settings.rag_chunk_size}")
        parts.append(f"overlap={self._settings.rag_chunk_overlap}")
        for doc in documents:
            parts.append(f"{doc.relative_path}:{doc.content_hash}")
        raw = "\n".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
