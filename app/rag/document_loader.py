import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_HEADING_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    title: str
    relative_path: str
    content_hash: str
    text: str


class DocumentLoader:
    def __init__(
        self,
        knowledge_dir: str,
        max_file_bytes: int,
        max_corpus_bytes: int,
    ) -> None:
        self._root = Path(knowledge_dir).resolve()
        self._max_file_bytes = max_file_bytes
        self._max_corpus_bytes = max_corpus_bytes

    def load(self) -> Sequence[KnowledgeDocument]:
        if not self._root.is_dir():
            return ()

        paths = sorted(
            p for p in self._root.rglob("*")
            if self._is_eligible(p)
        )

        documents: list[KnowledgeDocument] = []
        total_bytes = 0
        for path in paths:
            self._validate_path_safety(path)
            file_bytes = path.stat().st_size
            if file_bytes > self._max_file_bytes:
                raise ValueError(
                    f"Knowledge file exceeds per-file limit: {file_bytes} > {self._max_file_bytes}"
                )
            total_bytes += file_bytes
            if total_bytes > self._max_corpus_bytes:
                raise ValueError(
                    "Knowledge corpus exceeds total limit: "
                    f"{total_bytes} > {self._max_corpus_bytes}"
                )
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                raise ValueError(f"Cannot read knowledge file: {path}") from exc

            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            relative = str(path.relative_to(self._root))
            title = self._derive_title(text, path)

            documents.append(
                KnowledgeDocument(
                    title=title,
                    relative_path=relative,
                    content_hash=content_hash,
                    text=text,
                )
            )

        return tuple(documents)

    def _is_eligible(self, path: Path) -> bool:
        parts = path.parts
        for part in parts:
            if part.startswith("."):
                return False
        if path.is_symlink():
            return False
        if not path.is_file():
            return False
        suffix = path.suffix.lower()
        return suffix in (".md", ".txt")

    def _validate_path_safety(self, path: Path) -> None:
        resolved = path.resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError(f"Knowledge file escapes root directory: {path}")

    @staticmethod
    def _derive_title(text: str, path: Path) -> str:
        if path.suffix.lower() == ".md":
            match = _HEADING_PATTERN.search(text)
            if match is not None:
                return match.group(1).strip()
        return path.stem
