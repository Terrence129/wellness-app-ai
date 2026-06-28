import os
import tempfile
from pathlib import Path

import pytest

from app.rag.document_loader import DocumentLoader


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_loads_md_and_txt_in_sorted_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "b.md", "# Beta\nContent B")
        _write(root / "a.txt", "Content A")
        _write(root / "c.MD", "# Gamma\nContent C")

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        docs = loader.load()

        assert len(docs) == 3
        assert [d.relative_path for d in docs] == ["a.txt", "b.md", "c.MD"]
        assert docs[0].title == "a"
        assert docs[1].title == "Beta"
        assert docs[2].title == "Gamma"


def test_ignores_hidden_and_non_regular_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "visible.md", "# V")
        (root / ".hidden").mkdir()
        _write(root / ".hidden" / "nope.md", "# Nope")
        _write(root / ".secret.txt", "secret")
        subdir = root / "sub"
        subdir.mkdir()
        _write(subdir / "ok.md", "# OK")

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        docs = loader.load()

        paths = {d.relative_path for d in docs}
        assert paths == {"visible.md", "sub/ok.md"}


def test_validate_path_safety_rejects_escaped_paths() -> None:
    loader = DocumentLoader("/app/knowledge", 1_000_000, 10_000_000)
    with pytest.raises(ValueError):
        loader._validate_path_safety(Path("/etc/passwd").resolve())


def test_title_from_first_heading_fallback_to_filename() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "with_h1.md", "# Sleep Tips\nSome text\n## Sub\nMore")
        _write(root / "no_h1.md", "Just text no heading")
        _write(root / "empty.txt", "")

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        docs = loader.load()

        titles = {d.relative_path: d.title for d in docs}
        assert titles["with_h1.md"] == "Sleep Tips"
        assert titles["no_h1.md"] == "no_h1"
        assert titles["empty.txt"] == "empty"


def test_rejects_file_over_size_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "big.md", "x" * 200)

        loader = DocumentLoader(str(root), max_file_bytes=100, max_corpus_bytes=10_000)
        with pytest.raises(ValueError, match="per-file"):
            loader.load()


def test_rejects_corpus_over_total_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "a.md", "x" * 150)
        _write(root / "b.md", "y" * 150)

        loader = DocumentLoader(str(root), max_file_bytes=1000, max_corpus_bytes=200)
        with pytest.raises(ValueError, match="corpus.*total"):
            loader.load()


def test_rejects_invalid_utf8() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "bad.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x80\x81\x82")

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        with pytest.raises(ValueError, match="Cannot read"):
            loader.load()


def test_empty_directory_returns_no_documents() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        loader = DocumentLoader(tmp, 1_000_000, 10_000_000)
        assert loader.load() == ()


def test_content_hash_is_stable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "a.md", "Hello world")

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        hash1 = loader.load()[0].content_hash
        hash2 = loader.load()[0].content_hash
        assert hash1 == hash2


def test_content_hash_changes_with_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "a.md", "Hello world")
        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        hash1 = loader.load()[0].content_hash

        _write(root / "a.md", "Hello world!")
        hash2 = loader.load()[0].content_hash
        assert hash1 != hash2


def test_symlinks_are_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "real.md", "# real")
        symlink = root / "link.md"
        os.symlink(str(root / "real.md"), str(symlink))

        loader = DocumentLoader(str(root), 1_000_000, 10_000_000)
        docs = loader.load()
        paths = {d.relative_path for d in docs}
        assert paths == {"real.md"}
