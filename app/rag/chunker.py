# Author: Huang Qijun
# Email: 2692341798@qq.com

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.document_loader import KnowledgeDocument


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    title: str
    relative_path: str
    ordinal: int
    text: str


class TextChunker:
    def __init__(self, max_chunk_size: int, overlap: int, min_content: int = 40) -> None:
        self._max_chunk_size = max_chunk_size
        self._overlap = overlap
        self._min_content = min_content

    def chunk(self, documents: Sequence[KnowledgeDocument]) -> Sequence[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for doc in documents:
            doc_chunks = self._chunk_one(doc)
            chunks.extend(doc_chunks)
        return tuple(chunks)

    def _chunk_one(self, doc: KnowledgeDocument) -> list[DocumentChunk]:
        sections = self._split_by_headings(doc.text)
        chunks: list[DocumentChunk] = []
        ordinal = 0
        for heading, body in sections:
            sub_chunks = self._split_long_section(body, heading)
            for text in sub_chunks:
                if len(text.strip()) < self._min_content:
                    continue
                chunk_id = self._make_chunk_id(doc.relative_path, ordinal)
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        title=doc.title,
                        relative_path=doc.relative_path,
                        ordinal=ordinal,
                        text=text.strip(),
                    )
                )
                ordinal += 1
        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        lines = text.splitlines(keepends=True)
        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_body: list[str] = []

        for line in lines:
            if line.startswith("#"):
                if current_body:
                    sections.append((current_heading, "".join(current_body)))
                current_heading = line.strip()
                current_body = []
            else:
                current_body.append(line)

        if current_body:
            sections.append((current_heading, "".join(current_body)))
        elif current_heading and not sections:
            sections.append((current_heading, ""))

        if not sections:
            sections.append(("", text))

        return sections

    def _split_long_section(self, body: str, heading: str) -> list[str]:
        prefix = f"{heading}\n" if heading else ""
        if len(prefix) + len(body) <= self._max_chunk_size:
            return [prefix + body] if body.strip() else []

        paragraphs = body.split("\n\n")
        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            candidate = f"{current}\n\n{para}" if current else para
            if len(prefix) + len(candidate) <= self._max_chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(prefix + current)
                if len(prefix) + len(para) > self._max_chunk_size:
                    sub = self._split_oversized(para, prefix)
                    chunks.extend(sub)
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(prefix + current)

        return chunks

    def _split_oversized(self, text: str, prefix: str) -> list[str]:
        step = self._max_chunk_size - self._overlap - len(prefix)
        if step <= 0:
            step = self._max_chunk_size - len(prefix)
            if step <= 0:
                step = self._max_chunk_size

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + step, len(text))
            chunks.append(prefix + text[start:end])
            if end >= len(text):
                break
            start = end - self._overlap
            if start <= 0:
                start = step
        return chunks

    @staticmethod
    def _make_chunk_id(relative_path: str, ordinal: int) -> str:
        raw = f"{relative_path}:{ordinal}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
