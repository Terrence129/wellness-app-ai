import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.config import Settings

_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our",
        "their", "mine", "yours", "hers", "ours", "theirs",
        "this", "that", "these", "those", "am", "at", "by", "for",
        "with", "about", "against", "between", "into", "through",
        "during", "before", "after", "above", "below", "to", "from",
        "in", "out", "on", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "of", "and", "or", "but",
        "if", "because", "as", "until", "while", "what", "which",
        "who", "whom",
    }
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    title: str
    path: str
    ordinal: int
    text: str


@runtime_checkable
class Retriever(Protocol):
    async def retrieve(self, query: str) -> Sequence[RetrievedChunk]:
        ...


class NoOpRetriever:
    async def retrieve(self, query: str) -> Sequence[RetrievedChunk]:
        return ()


class FTS5Retriever:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._top_k = settings.rag_top_k
        self._context_max_chars = settings.rag_context_max_chars

    async def retrieve(self, query: str) -> Sequence[RetrievedChunk]:
        if not query.strip():
            return ()

        tokens = self._tokenize(query)
        if not tokens:
            return ()

        fts_query = self._build_fts_query(tokens)
        try:
            connection = sqlite3.connect(f"file:{self._settings.rag_index_path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                cursor = connection.execute(
                    """
                    SELECT
                        chunk_id,
                        title,
                        relative_path,
                        ordinal,
                        chunk_text,
                        bm25(rag_chunks, 0, 0, 0) AS score
                    FROM rag_chunks
                    WHERE rag_chunks MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (fts_query, self._top_k),
                )
                rows = cursor.fetchall()
            finally:
                connection.close()
        except sqlite3.OperationalError:
            return ()

        results: list[RetrievedChunk] = []
        total_chars = 0
        for row in rows:
            text = row["chunk_text"]
            if not isinstance(text, str):
                continue
            chunk = RetrievedChunk(
                chunk_id=row["chunk_id"],
                title=row["title"] or "",
                path=row["relative_path"] or "",
                ordinal=row["ordinal"],
                text=text,
            )
            results.append(chunk)
            total_chars += len(text)
            if total_chars >= self._context_max_chars:
                break

        self._apply_deterministic_tiebreak(results)
        if total_chars > self._context_max_chars and len(results) > 1:
            results = self._trim_to_budget(results)

        return tuple(results)

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        lowered = query.lower()
        tokens = _TOKEN_PATTERN.findall(lowered)
        unique: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token not in _STOP_WORDS and token not in seen:
                seen.add(token)
                unique.append(token)
        return unique

    @staticmethod
    def _build_fts_query(tokens: list[str]) -> str:
        quoted = (f'"{token}"' for token in tokens)
        return " OR ".join(quoted)

    @staticmethod
    def _apply_deterministic_tiebreak(chunks: list[RetrievedChunk]) -> None:
        chunks.sort(key=lambda c: (c.path, c.ordinal))

    def _trim_to_budget(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        kept: list[RetrievedChunk] = []
        total = 0
        for chunk in chunks:
            total += len(chunk.text)
            if total > self._context_max_chars and kept:
                break
            kept.append(chunk)
        return kept
