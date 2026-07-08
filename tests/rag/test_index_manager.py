# Author: Huang Qijun
# Email: 2692341798@qq.com

import os
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.rag.index_manager import IndexManager


def _settings(index_path: str, knowledge_dir: str) -> Settings:
    return Settings(
        DEEPSEEK_API_KEY=" ",
        _env_file=None,
        RAG_ENABLED="true",
        RAG_KNOWLEDGE_DIR=knowledge_dir,
        RAG_INDEX_PATH=index_path,
        RAG_CHUNK_SIZE="1000",
        RAG_CHUNK_OVERLAP="150",
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_builds_index_from_knowledge_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "index.sqlite3")
        _write(knowledge / "sleep.md", "# Sleep\nGood sleep is important for health.")
        _write(knowledge / "water.md", "# Water\nDrink enough water daily.")

        settings = _settings(index_path, str(knowledge))
        result = IndexManager(settings).ensure_index()

        assert result.file_count == 2
        assert result.chunk_count > 0
        assert result.reused is False
        assert os.path.isfile(index_path)


def test_reuses_index_when_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "index.sqlite3")
        _write(knowledge / "a.md", "# A\nContent A.")

        settings = _settings(index_path, str(knowledge))
        manager = IndexManager(settings)

        result1 = manager.ensure_index()
        assert result1.reused is False

        result2 = manager.ensure_index()
        assert result2.reused is True


def test_rebuilds_when_file_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "index.sqlite3")
        _write(knowledge / "a.md", "# A\nContent A.")

        settings = _settings(index_path, str(knowledge))
        manager = IndexManager(settings)

        result1 = manager.ensure_index()
        assert result1.reused is False

        _write(knowledge / "a.md", "# A\nContent B.")
        result2 = manager.ensure_index()
        assert result2.reused is False


def test_rebuilds_when_chunk_settings_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "index.sqlite3")
        _write(knowledge / "a.md", "# A\n" + ("x" * 2000))

        settings1 = _settings(index_path, str(knowledge))
        IndexManager(settings1).ensure_index()

        settings2 = _settings(index_path, str(knowledge))
        settings2 = Settings(
            DEEPSEEK_API_KEY=" ",
            _env_file=None,
            RAG_ENABLED="true",
            RAG_KNOWLEDGE_DIR=str(knowledge),
            RAG_INDEX_PATH=index_path,
            RAG_CHUNK_SIZE="500",
            RAG_CHUNK_OVERLAP="100",
        )
        result = IndexManager(settings2).ensure_index()
        assert result.reused is False


def test_empty_knowledge_dir_returns_no_chunks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "empty"
        knowledge.mkdir()
        index_path = str(Path(tmp) / "index.sqlite3")

        settings = _settings(index_path, str(knowledge))
        result = IndexManager(settings).ensure_index()

        assert result.file_count == 0
        assert result.chunk_count == 0


def test_recovers_from_corrupt_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "index.sqlite3")
        _write(knowledge / "a.md", "# A\nContent.")

        settings = _settings(index_path, str(knowledge))

        Path(index_path).write_text("not a valid sqlite database")

        result = IndexManager(settings).ensure_index()
        assert result.reused is False
        assert result.file_count == 1


def test_missing_index_builds_new() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        knowledge = Path(tmp) / "knowledge"
        index_path = str(Path(tmp) / "nonexistent" / "index.sqlite3")
        _write(knowledge / "a.md", "# A\nContent.")

        settings = _settings(index_path, str(knowledge))
        result = IndexManager(settings).ensure_index()

        assert result.file_count == 1
        assert os.path.isfile(index_path)
