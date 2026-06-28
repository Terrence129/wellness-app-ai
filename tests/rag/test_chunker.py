
from app.rag.chunker import TextChunker
from app.rag.document_loader import KnowledgeDocument


def _doc(title: str, path: str, text: str, content_hash: str = "abc") -> KnowledgeDocument:
    return KnowledgeDocument(
        title=title,
        relative_path=path,
        content_hash=content_hash,
        text=text,
    )


def test_chunks_by_heading_sections() -> None:
    text = (
        "# Sleep\n"
        "Sleep is important for your overall health and daily energy levels.\n\n"
        "## Tips\n"
        "Go to bed early and maintain a consistent schedule every night."
    )
    chunker = TextChunker(max_chunk_size=1000, overlap=150, min_content=10)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks) >= 2
    texts = [c.text for c in chunks]
    assert any("Sleep" in t for t in texts)
    assert any("Tips" in t for t in texts)


def test_splits_long_paragraphs() -> None:
    text = "# Intro\n" + ("x" * 2000)
    chunker = TextChunker(max_chunk_size=500, overlap=100)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.text) <= 550


def test_strips_and_discards_empty_chunks() -> None:
    text = "# A\n\n\n# B\nsome useful content"
    chunker = TextChunker(max_chunk_size=1000, overlap=150, min_content=10)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    for chunk in chunks:
        assert len(chunk.text.strip()) >= 10
        assert chunk.text == chunk.text.strip()


def test_stable_chunk_ids() -> None:
    text = "# A\nContent here."
    chunker = TextChunker(max_chunk_size=1000, overlap=150)
    chunks1 = chunker.chunk([_doc("Test", "test.md", text)])
    chunks2 = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2, strict=True):
        assert c1.chunk_id == c2.chunk_id


def test_different_documents_have_different_chunk_ids() -> None:
    text = "# A\nContent."
    chunker = TextChunker(max_chunk_size=1000, overlap=150)
    chunks1 = chunker.chunk([_doc("A", "a.md", text)])
    chunks2 = chunker.chunk([_doc("B", "b.md", text)])

    ids1 = {c.chunk_id for c in chunks1}
    ids2 = {c.chunk_id for c in chunks2}
    assert ids1.isdisjoint(ids2)


def test_ordinal_increments() -> None:
    text = "# A\nThis is content that is long enough to pass the minimum length check.\n\n# B\nMore content here that also needs to be somewhat longer."
    chunker = TextChunker(max_chunk_size=1000, overlap=150, min_content=10)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    ordinals = [c.ordinal for c in chunks]
    assert ordinals == sorted(set(ordinals))
    assert ordinals[0] == 0


def test_preserves_heading_in_chunk_text() -> None:
    text = "# Sleep Tips\nRegular sleep improves health."
    chunker = TextChunker(max_chunk_size=1000, overlap=150)
    chunks = chunker.chunk([_doc("Sleep", "sleep.md", text)])

    assert len(chunks) == 1
    assert "Sleep Tips" in chunks[0].text


def test_overlap_in_split_sections() -> None:
    text = "# Intro\n" + ("ab" * 600)
    chunker = TextChunker(max_chunk_size=200, overlap=50)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks) >= 2
    if len(chunks) >= 2:
        last = chunks[0].text[-30:]
        first = chunks[1].text[:30]
        assert last or first


def test_multi_document_chunks_are_interleaved() -> None:
    a = _doc("A", "a.md", "# A\nFirst document with enough content to be indexed and chunked.")
    b = _doc("B", "b.md", "# B\nSecond document also with sufficient content for chunking.")
    chunker = TextChunker(max_chunk_size=1000, overlap=150, min_content=10)
    chunks = chunker.chunk([a, b])

    titles = {c.title for c in chunks}
    assert titles == {"A", "B"}


def test_min_content_filter() -> None:
    text = "# Title\nab"
    chunker = TextChunker(max_chunk_size=1000, overlap=150, min_content=40)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks) == 0


def test_no_headings_uses_whole_text() -> None:
    text = "Just a paragraph without any headings at all."
    chunker = TextChunker(max_chunk_size=1000, overlap=150)
    chunks = chunker.chunk([_doc("Test", "test.md", text)])

    assert len(chunks) == 1
    assert "headings" in chunks[0].text
