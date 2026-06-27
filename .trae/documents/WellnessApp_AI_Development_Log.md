# Wellness App AI — Development Log

> **Author**: 2692341798 | **Repository**: `wellness-app-ai`  
> Append-only log recording the AI module's development plan, key decisions, and change history.

---

## Table of Contents

- [Development Plan](#development-plan)
- [Change Records](#change-records)

---

## Development Plan

### Phase 1: AI Service Foundation (Completed ✅)

**Branch**: `codex/ai-service-foundation`

| Task | Description | Status |
|------|------|------|
| Task 1 | Project metadata and offline test toolchain | ✅ |
| Task 2 | Configuration management + stable error types | ✅ |
| Task 3 | Request ID + exception handlers + Health route | ✅ |
| Task 4 | Chat/Advice data schemas | ✅ |
| Task 5 | LLMProvider protocol + offline Fake | ✅ |
| Task 6 | Safety policy + Chat service | ✅ |
| Task 7 | Deterministic empty-data behavior + Advice service | ✅ |
| Task 8 | DeepSeek adapter (retry/error-mapping/token observability) | ✅ |
| Task 9 | Dependency injection + HTTP routes | ✅ |
| Task 10 | Privacy logging + Live tests | ✅ |
| Task 11 | AGENTS.md + README.md | ✅ |
| Task 12 | Final quality verification + runtime acceptance | ✅ |

### Phase 2: To Be Planned

| Candidate Feature | Priority | Notes |
|----------|--------|------|
| SSE streaming responses | High | Improve user experience with token-by-token delivery |
| Live integration test optimization | Medium | Increase real-scenario coverage |
| Spring Boot integration testing | Medium | End-to-end verification |
| Performance optimization | Low | If needed |

---

## Change Records

### 2026-06-27 — v0.1.0 Initial Release

**Commit**: `feat(ai): establish wellness AI service foundation`

**Contents**:
- 58 files, 5847 lines of code
- 3 API endpoints: `GET /health`, `POST /ai/chat`, `POST /ai/wellness-advice`
- Four-layer architecture: Routes → Services → LLMProvider Protocol → DeepSeekProvider
- Deterministic safety policy: 6 crisis keywords → fixed escalation message
- DeepSeek adapter: exponential backoff retries, 10 error codes, token usage observability
- 215 offline tests (FakeLLMProvider)
- Live smoke tests (`@pytest.mark.live`)

**Quality Gates**:
- ruff check: zero issues
- mypy strict (app): zero issues
- pytest: 215 passed, 2 deselected

**Architecture Decisions**:
- Use `deepseek-v4-flash`, not the retired `deepseek-chat` / `deepseek-reasoner`
- CORS not enabled (browser/Android does not connect directly)
- Thinking mode disabled (low latency)
- SDK built-in retries disabled (`max_retries=0`), self-managed by this adapter
- No RAG / Agent framework / vector database introduced

**Engineering Documentation**:
- README.md complete technical documentation
- `.trae/documents/WellnessApp_AI_API.md` API documentation
- `.trae/documents/WellnessApp_AI_Architecture.md` Architecture document
- `.trae/documents/WellnessApp_AI_PRD.md` Product requirements document
- `.trae/documents/WellnessApp_AI_Development_Log.md` This file

### 2026-06-27 — Live Test Completion

**Commit**: Completed `tests/integration/test_live_deepseek.py`

**Contents**:
- Chat smoke test: sends `"Give one short general wellness tip."`
- Advice smoke test: sends one basic wellness log
- Marked `@pytest.mark.live`, excluded by default
- Only executes when `DEEPSEEK_API_KEY` is present
- Does not print keys / payloads / response text

### 2026-06-27 — Security Fix: Leaked API Key Removal

**Commit**: Fixed real DeepSeek API key in `.env.example`

**Issue**: `.env.example` contained a real `sk-11ed7b...` key → blocked by GitHub Push Protection
**Fix**: Replaced with placeholder `your-deepseek-api-key` → `git commit --amend` → `git push --force-with-lease`
**Recommendation**: Revoke the old key in the DeepSeek dashboard and regenerate

### 2026-06-27 — Documentation Upgrade: README + Engineering Docs

**Commit**: Upgraded README.md + created `.trae/documents/` engineering documentation system

**Contents**:
- README.md additions: project badges, ASCII architecture diagram, table of contents navigation, tech stack table, environment variables table, safety design section
- New documents: API doc, architecture doc, PRD, development log
