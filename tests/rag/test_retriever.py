# Author: Huang Qijun
# Email: 2692341798@qq.com

import tempfile
from pathlib import Path

import pytest

from app.core.config import Settings
from app.rag.index_manager import IndexManager
from app.rag.retriever import FTS5Retriever, NoOpRetriever


def _settings(index_path: str, knowledge_dir: str) -> Settings:
    return Settings(
        DEEPSEEK_API_KEY=" ",
        _env_file=None,
        RAG_ENABLED="true",
        RAG_KNOWLEDGE_DIR=knowledge_dir,
        RAG_INDEX_PATH=index_path,
        RAG_CHUNK_SIZE="1000",
        RAG_CHUNK_OVERLAP="150",
        RAG_TOP_K="4",
        RAG_CONTEXT_MAX_CHARS="4000",
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def _build_retriever(
    knowledge_dir: Path, docs: list[tuple[str, str]]
) -> FTS5Retriever:
    for name, content in docs:
        _write(knowledge_dir / name, content)

    index_path = str(knowledge_dir.parent / "index.sqlite3")
    settings = _settings(index_path, str(knowledge_dir))
    IndexManager(settings).ensure_index()
    return FTS5Retriever(settings)


@pytest.mark.asyncio
async def test_retrieves_relevant_chunks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        retriever = await _build_retriever(
            knowledge,
            [
                ("sleep.md", "# Sleep\nGood sleep improves health and mood."),
                ("exercise.md", "# Exercise\nRegular exercise boosts energy."),
                ("water.md", "# Water\nStay hydrated throughout the day."),
            ],
        )

        chunks = await retriever.retrieve("how to sleep better")
        assert len(chunks) > 0

        texts = " ".join(c.text for c in chunks)
        assert "sleep" in texts.lower()


@pytest.mark.asyncio
async def test_no_match_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        retriever = await _build_retriever(
            knowledge,
            [("sleep.md", "# Sleep\nGood sleep is important.")],
        )

        chunks = await retriever.retrieve("xylophone zydeco quadrillion")
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_blank_query_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        retriever = await _build_retriever(
            knowledge,
            [("a.md", "# A\nContent.")],
        )

        assert len(await retriever.retrieve("")) == 0
        assert len(await retriever.retrieve("   ")) == 0


@pytest.mark.asyncio
async def test_stop_word_only_query_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        retriever = await _build_retriever(
            knowledge,
            [("a.md", "# A\nContent.")],
        )

        chunks = await retriever.retrieve("the and of for with")
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_respects_top_k_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        docs = []
        for i in range(10):
            docs.append(
                (f"doc_{i}.md", f"# Topic {i}\nSleep is important for topic {i}.")
            )

        index_path = str(root / "index.sqlite3")
        settings = _settings(index_path, str(knowledge))
        for name, content in docs:
            _write(knowledge / name, content)
        IndexManager(settings).ensure_index()

        top2_settings = Settings(
            DEEPSEEK_API_KEY=" ",
            _env_file=None,
            RAG_ENABLED="true",
            RAG_KNOWLEDGE_DIR=str(knowledge),
            RAG_INDEX_PATH=index_path,
            RAG_CHUNK_SIZE="1000",
            RAG_CHUNK_OVERLAP="150",
            RAG_TOP_K="2",
            RAG_CONTEXT_MAX_CHARS="4000",
        )
        retriever = FTS5Retriever(top2_settings)
        chunks = await retriever.retrieve("sleep")

        assert len(chunks) <= 2


@pytest.mark.asyncio
async def test_chunks_have_expected_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        knowledge = root / "knowledge"
        retriever = await _build_retriever(
            knowledge,
            [("sleep.md", "# Sleep Tips\nRegular sleep improves health.")],
        )

        chunks = await retriever.retrieve("sleep")

        assert len(chunks) == 1
        chunk = chunks[0]
        assert isinstance(chunk.chunk_id, str)
        assert len(chunk.chunk_id) > 0
        assert chunk.title == "Sleep Tips"
        assert chunk.path == "sleep.md"
        assert chunk.ordinal == 0
        assert isinstance(chunk.text, str)
        assert len(chunk.text) > 0


@pytest.mark.asyncio
async def test_noop_retriever_always_returns_empty() -> None:
    retriever = NoOpRetriever()
    assert len(await retriever.retrieve("anything")) == 0
    assert len(await retriever.retrieve("")) == 0
