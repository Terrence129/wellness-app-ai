<!--
Author: Huang Qijun
Email: 2692341798@qq.com
-->

# Local Wellness Knowledge RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, failure-tolerant SQLite FTS5 RAG pipeline that grounds `/ai/chat` in approved English wellness documents without changing its HTTP contract.

**Architecture:** A focused `app/rag/` package loads, chunks, fingerprints, indexes, and retrieves local knowledge through a `Retriever` protocol. `ChatService` performs safety checks first, then retrieves bounded context and passes it separately through the provider boundary; bootstrap failures select a no-op retriever so the existing chat path remains available.

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, standard-library SQLite FTS5, pytest, Ruff, mypy, existing OpenAI-compatible DeepSeek adapter.

---

## File Map

- Create `app/rag/models.py`: immutable document, chunk, and retrieval value objects.
- Create `app/rag/base.py`: asynchronous `Retriever` protocol and `NoOpRetriever`.
- Create `app/rag/loader.py`: bounded, deterministic Markdown/TXT loading.
- Create `app/rag/chunker.py`: heading/paragraph-aware deterministic chunking.
- Create `app/rag/sqlite.py`: corpus fingerprinting, atomic FTS5 index lifecycle, safe BM25 retrieval.
- Create `app/rag/bootstrap.py`: initialize the production retriever and degrade safely.
- Create `app/rag/__init__.py`: package marker only.
- Modify `app/core/config.py`: validated RAG settings.
- Modify `app/main.py`: initialize one retriever during application creation.
- Modify `app/api/dependencies.py`: inject the app-owned retriever into `ChatService`.
- Modify `app/services/chat.py`: safety-first query construction and retrieval fallback.
- Modify `app/providers/base.py`: add bounded knowledge context to chat generation.
- Modify `app/providers/deepseek.py`: render delimited knowledge context.
- Modify `app/prompts/chat.py`: versioned RAG safety instructions.
- Modify `tests/fakes.py`: fake retriever and provider knowledge-call recording.
- Create `tests/rag/test_loader.py`, `tests/rag/test_chunker.py`, `tests/rag/test_sqlite.py`, and `tests/rag/test_bootstrap.py`.
- Modify chat, provider, configuration, API, documentation, and hygiene tests.
- Create `knowledge/README.md` and a small set of reviewed English wellness summaries.
- Modify `.env.example`, `.gitignore`, and `README.md`.

## Task 1: RAG types, protocol, and configuration

**Files:**
- Create: `app/rag/__init__.py`
- Create: `app/rag/models.py`
- Create: `app/rag/base.py`
- Modify: `app/core/config.py`
- Modify: `tests/core/test_config.py`
- Modify: `tests/fakes.py`

- [ ] **Step 1: Add failing configuration and protocol tests**

Add tests asserting the documented defaults, environment aliases, bounds, and the cross-field rules:

```python
def test_rag_defaults_are_bounded() -> None:
    settings = Settings(_env_file=None)
    assert settings.rag_enabled is True
    assert settings.rag_knowledge_dir == Path("knowledge")
    assert settings.rag_index_path == Path(".data/rag-index.sqlite3")
    assert settings.rag_top_k == 4
    assert settings.rag_chunk_size == 1000
    assert settings.rag_chunk_overlap == 150
    assert settings.rag_context_max_chars == 4000


@pytest.mark.parametrize(
    "values",
    [
        {"RAG_CHUNK_SIZE": 500, "RAG_CHUNK_OVERLAP": 500},
        {"RAG_MAX_FILE_BYTES": 21, "RAG_MAX_CORPUS_BYTES": 20},
    ],
)
def test_rag_cross_field_validation_rejects_invalid_limits(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
```

Also test that `NoOpRetriever.retrieve("sleep")` returns an empty tuple and that `FakeRetriever` records queries without storing unrelated request identity.

- [ ] **Step 2: Verify the focused tests fail**

Run: `uv run pytest tests/core/test_config.py tests/rag/test_base.py -q`

Expected: collection/import failure because `app.rag` and RAG settings do not exist.

- [ ] **Step 3: Implement the minimal types and validated settings**

Define frozen, slotted dataclasses `KnowledgeDocument`, `DocumentChunk`, and `RetrievedChunk`. Define:

```python
@runtime_checkable
class Retriever(Protocol):
    async def retrieve(self, query: str) -> Sequence[RetrievedChunk]: ...


class NoOpRetriever:
    async def retrieve(self, query: str) -> Sequence[RetrievedChunk]:
        return ()
```

Add the eight documented `RAG_*` fields to `Settings`, using `Path`, Pydantic bounds, and an `@model_validator(mode="after")` that rejects overlap greater than or equal to chunk size and per-file bytes greater than corpus bytes. Every project-owned public class/function receives the required author docstring.

- [ ] **Step 4: Run focused tests and static checks**

Run: `uv run pytest tests/core/test_config.py tests/rag/test_base.py -q && uv run mypy app/rag app/core/config.py tests/fakes.py`

Expected: all selected tests pass and mypy reports success.

## Task 2: Safe deterministic document loading

**Files:**
- Create: `app/rag/loader.py`
- Create: `tests/rag/test_loader.py`

- [ ] **Step 1: Write loader tests using `tmp_path`**

Cover sorted recursive `.md`/`.txt` discovery, first-heading title extraction, filename fallback, hidden paths, unsupported suffixes, symlinks, invalid UTF-8, root escape, per-file limit, and aggregate limit. Assert invalid eligible files fail the entire load with a typed `KnowledgeLoadError`; do not assert raw content in exception strings.

```python
def test_load_documents_is_sorted_and_extracts_titles(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("Hydration guidance", encoding="utf-8")
    (tmp_path / "a.md").write_text("# Sleep Basics\n\nKeep a schedule.", encoding="utf-8")
    documents = load_documents(tmp_path, max_file_bytes=1024, max_corpus_bytes=4096)
    assert [(doc.relative_path.as_posix(), doc.title) for doc in documents] == [
        ("a.md", "Sleep Basics"),
        ("b.txt", "b"),
    ]
```

- [ ] **Step 2: Verify loader tests fail**

Run: `uv run pytest tests/rag/test_loader.py -q`

Expected: import failure because `app.rag.loader` does not exist.

- [ ] **Step 3: Implement `load_documents`**

Use `Path.rglob`, `lstat`, `resolve`, `relative_to`, `read_bytes`, and explicit byte accounting. Ignore hidden path components and symlinks before opening files. Decode UTF-8 strictly. Derive the first Markdown ATX heading with a compiled expression and otherwise use `path.stem`. Return an immutable sequence in relative-path order. Convert filesystem and decode failures to `KnowledgeLoadError` with safe category-only messages.

- [ ] **Step 4: Run loader tests and lint**

Run: `uv run pytest tests/rag/test_loader.py -q && uv run ruff check app/rag/loader.py tests/rag/test_loader.py`

Expected: all selected tests pass and Ruff reports no errors.

## Task 3: Deterministic paragraph-aware chunking

**Files:**
- Create: `app/rag/chunker.py`
- Create: `tests/rag/test_chunker.py`

- [ ] **Step 1: Write chunking tests**

Cover empty/short documents, heading propagation, paragraph packing, oversized-section windows, configured overlap, minimum content, stable IDs, and deterministic ordinals.

```python
def test_chunk_ids_and_output_are_deterministic() -> None:
    document = KnowledgeDocument(
        title="Sleep",
        relative_path=Path("sleep.md"),
        content="# Sleep\n\n" + "rest " * 300,
        content_sha256="a" * 64,
    )
    first = chunk_documents((document,), chunk_size=300, overlap=50)
    second = chunk_documents((document,), chunk_size=300, overlap=50)
    assert first == second
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert all(len(chunk.text) <= 300 for chunk in first)
```

- [ ] **Step 2: Verify chunking tests fail**

Run: `uv run pytest tests/rag/test_chunker.py -q`

Expected: import failure because `app.rag.chunker` does not exist.

- [ ] **Step 3: Implement `chunk_documents`**

Normalize line endings, split Markdown sections at ATX headings, pack paragraphs without exceeding `chunk_size`, and use overlapping character windows only for a section that cannot be packed. Prefix applicable heading text while respecting the hard size bound. Drop chunks below 40 non-whitespace characters. Compute stable IDs with SHA-256 over relative path, content hash, and ordinal.

- [ ] **Step 4: Run focused checks**

Run: `uv run pytest tests/rag/test_chunker.py -q && uv run mypy app/rag/chunker.py tests/rag/test_chunker.py`

Expected: tests pass and mypy reports success.

## Task 4: Atomic SQLite FTS5 index and BM25 retrieval

**Files:**
- Create: `app/rag/sqlite.py`
- Create: `tests/rag/test_sqlite.py`

- [ ] **Step 1: Write index lifecycle and retrieval tests**

Using only temporary directories, cover first build, unchanged fingerprint reuse, content/settings/schema rebuild, corruption recovery, failed replacement preserving the prior file, safe punctuation/quote input, stop-word-only input, BM25 ordering, deterministic ties, Top-K, and aggregate context limits. Skip with an explicit reason only if the runtime SQLite library genuinely lacks FTS5.

```python
@pytest.mark.asyncio
async def test_retrieve_ranks_relevant_chunks_and_respects_limits(tmp_path: Path) -> None:
    retriever = build_sqlite_retriever(
        documents=_documents_for_sleep_and_hydration(),
        index_path=tmp_path / "rag.sqlite3",
        chunk_size=300,
        overlap=50,
        top_k=1,
        context_max_chars=500,
    )
    results = await retriever.retrieve('sleep schedule" OR hydration')
    assert len(results) == 1
    assert "sleep" in results[0].text.lower()
    assert len(results[0].text) <= 500
```

- [ ] **Step 2: Verify SQLite tests fail**

Run: `uv run pytest tests/rag/test_sqlite.py -q`

Expected: import failure because `app.rag.sqlite` does not exist.

- [ ] **Step 3: Implement fingerprinting and atomic build**

Compute a canonical SHA-256 fingerprint from schema version, chunk settings, relative paths, and document hashes. Create metadata and FTS5 tables in a sibling temporary database, insert all chunks in one transaction, validate row count and metadata, close all connections, then call `os.replace`. Reuse only a readable database with matching schema and fingerprint. On corruption, rebuild once. Ensure a failed build or replacement does not delete an existing valid index.

- [ ] **Step 4: Implement safe async retrieval**

Normalize ASCII/English alphanumeric tokens, lowercase, remove duplicates and a small constant stop-word set, quote each token, and join them with `OR`. Execute blocking SQLite work with `asyncio.to_thread` and a short-lived read-only connection. Order by `bm25(chunks)`, then relative path and ordinal. Stop before `top_k` or `context_max_chars`; never interpolate unescaped query syntax into SQL or FTS expressions.

- [ ] **Step 5: Run lifecycle tests and checks**

Run: `uv run pytest tests/rag/test_sqlite.py -q && uv run ruff check app/rag/sqlite.py tests/rag/test_sqlite.py && uv run mypy app/rag/sqlite.py tests/rag/test_sqlite.py`

Expected: all tests pass, including quote/punctuation injection cases, and both static checks succeed.

## Task 5: Bootstrap, application state, and dependency injection

**Files:**
- Create: `app/rag/bootstrap.py`
- Create: `tests/rag/test_bootstrap.py`
- Modify: `app/main.py`
- Modify: `app/api/dependencies.py`
- Modify: `tests/api/test_chat.py`

- [ ] **Step 1: Add bootstrap and DI tests**

Test `ready`, `empty`, `disabled`, and `degraded` states; verify failures log only metadata and return `NoOpRetriever`. Test that one retriever is stored on `application.state`, reused by chat dependencies, and does not alter `/health`.

```python
def test_disabled_rag_uses_noop_without_loading(tmp_path: Path) -> None:
    settings = Settings(RAG_ENABLED=False, RAG_KNOWLEDGE_DIR=tmp_path, _env_file=None)
    result = initialize_retriever(settings)
    assert result.state == "disabled"
    assert isinstance(result.retriever, NoOpRetriever)
```

- [ ] **Step 2: Verify bootstrap tests fail**

Run: `uv run pytest tests/rag/test_bootstrap.py tests/api/test_chat.py -q`

Expected: failures because bootstrap and retriever injection do not exist.

- [ ] **Step 3: Implement safe initialization**

Create a frozen `RagInitialization` containing state, retriever, file count, chunk count, index reuse, and elapsed milliseconds. `initialize_retriever(settings)` selects `disabled` without I/O, `empty` for no eligible documents, `ready` after successful build/reuse, and `degraded` after a caught loader/index/SQLite/filesystem error. Log only approved metadata and exception class.

- [ ] **Step 4: Wire application state and dependencies**

Initialize RAG once in `create_app`, assign `application.state.retriever`, and change `get_chat_service` to accept and pass the app retriever. Add a typed `get_retriever(request)` dependency. Existing provider lazy construction and advice dependency must remain unchanged.

- [ ] **Step 5: Run focused application tests**

Run: `uv run pytest tests/rag/test_bootstrap.py tests/api/test_health.py tests/api/test_chat.py -q`

Expected: selected tests pass and health response remains exactly `{"status":"ok","service":"wellness-app-ai"}`.

## Task 6: Safety-first retrieval and provider context

**Files:**
- Modify: `app/services/chat.py`
- Modify: `app/providers/base.py`
- Modify: `app/providers/deepseek.py`
- Modify: `app/prompts/chat.py`
- Modify: `tests/fakes.py`
- Modify: `tests/services/test_chat.py`
- Modify: `tests/providers/test_base.py`
- Modify: `tests/providers/test_deepseek.py`
- Modify: `tests/api/test_chat.py`

- [ ] **Step 1: Add failing service tests**

Assert crisis requests call neither retriever nor provider; retrieval queries contain the stripped current message plus at most the last two user messages and no assistant messages; retriever errors produce empty context; results are bounded and passed separately; public response JSON remains unchanged.

```python
@pytest.mark.asyncio
async def test_crisis_short_circuits_retriever_and_provider() -> None:
    retriever = FakeRetriever(error=AssertionError("retriever must not be called"))
    provider = FakeLLMProvider(error=AssertionError("provider must not be called"))
    response = await ChatService(provider, SafetyPolicy(), retriever).generate(
        ChatRequest(userId=1, message="I want to kill myself"), "request-crisis"
    )
    assert response.reply == CRISIS_RESPONSE
    assert retriever.queries == []
    assert provider.chat_calls == []
```

- [ ] **Step 2: Add failing provider prompt tests**

Assert `LLMProvider.generate_chat` and fakes accept `knowledge_context`; no-context calls preserve the original message sequence; context calls insert one system message with explicit delimiters and rules containing `reference`, `not instructions`, `ignore`, `diagnosis`, and `prescription`; raw context never appears in logs.

- [ ] **Step 3: Verify service/provider tests fail**

Run: `uv run pytest tests/services/test_chat.py tests/providers/test_base.py tests/providers/test_deepseek.py -q`

Expected: signature and constructor failures before implementation.

- [ ] **Step 4: Implement retrieval orchestration**

Extend `ChatService(provider, safety_policy, retriever)` and call safety first. Build a capped query from current message and reverse-scanned user history, retrieve once, catch retrieval-boundary exceptions with metadata-only `rag_retrieval_failed` logging, and pass `knowledge_context=tuple(results)` to the provider. Preserve existing response validation.

- [ ] **Step 5: Implement prompt and provider changes**

Update the protocol and adapters to accept `Sequence[RetrievedChunk]`. Increment `CHAT_PROMPT_VERSION` to `wellness-chat-rag-v2`. When context is non-empty, insert a second system message produced by a pure prompt-rendering function with numbered `<knowledge_chunk>` delimiters. State that chunks are references rather than instructions, cannot change roles or invoke tools, are not complete medical guidance, and cannot override safety. Do not include paths or scores in the provider prompt.

- [ ] **Step 6: Run service/provider/API checks**

Run: `uv run pytest tests/services/test_chat.py tests/providers/test_base.py tests/providers/test_deepseek.py tests/api/test_chat.py -q`

Expected: all selected tests pass and existing API assertions still match exactly.

## Task 7: Curated starter knowledge and operator documentation

**Files:**
- Create: `knowledge/README.md`
- Create: `knowledge/sleep.md`
- Create: `knowledge/physical-activity.md`
- Create: `knowledge/hydration.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `tests/test_documentation.py`
- Modify: `tests/test_repository_hygiene.py`

- [ ] **Step 1: Verify authoritative sources before authoring content**

Use current primary public-health sources only. Record direct URLs and review date `2026-06-28`; paraphrase concise general-wellness guidance and exclude diagnosis, medication, and dosage. Suitable source organizations are WHO, CDC, NHS, or an equivalent national public-health authority.

- [ ] **Step 2: Add failing documentation and hygiene tests**

Assert README documents `knowledge/`, startup indexing, failure degradation, read-only/writable deployment paths, and all `RAG_*` settings. Assert `.env.example` contains every setting and `.gitignore` excludes `.data/`, `*.sqlite3-wal`, `*.sqlite3-shm`, and temporary rebuild databases.

- [ ] **Step 3: Write the starter knowledge corpus**

Each file must include topic title, scope note, concise project-authored guidance, `Sources`, and `Last reviewed: 2026-06-28`. `knowledge/README.md` defines accepted formats, English-only first-version policy, source review requirements, prohibited private data, and the rebuild-on-restart lifecycle.

- [ ] **Step 4: Update runtime and operator documentation**

Add the exact RAG defaults to `.env.example`, ignore generated SQLite artifacts, and document how to add knowledge, trigger rebuilds, disable RAG, mount `knowledge/` read-only, mount `.data/` writable, and recognize metadata-only `ready/empty/disabled/degraded` states. State explicitly that the chat API shape does not change.

- [ ] **Step 5: Run documentation and hygiene tests**

Run: `uv run pytest tests/test_documentation.py tests/test_repository_hygiene.py -q`

Expected: all selected tests pass and no generated index is present in Git status.

## Task 8: Full regression verification and plan bookkeeping

**Files:**
- Modify: `docs/superpowers/plans/2026-06-28-local-knowledge-rag.md`

- [ ] **Step 1: Run formatting and static analysis**

Run: `uv run ruff check . && uv run mypy app tests`

Expected: both commands exit zero with no findings.

- [ ] **Step 2: Run the complete offline test suite**

Run: `uv run pytest`

Expected: all non-live tests pass; the configured live DeepSeek marker remains excluded.

- [ ] **Step 3: Run repository safety checks**

Run: `git diff --check && git status --short --branch && find .data -type f -maxdepth 2 2>/dev/null || true`

Expected: no whitespace errors; `.env`, caches, `.DS_Store`, and generated SQLite files are not staged or modified by the implementation; status contains only intended source, knowledge, test, and documentation files plus pre-existing untracked local files.

- [ ] **Step 4: Mark completed plan checkboxes without committing**

Update only the checkboxes for steps whose commands actually succeeded. Do not create commits, push, or open a pull request because the user authorized development and subagents, not Git publication.
