# wellness-app-ai

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/fastapi-0.115%2B-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/deepseek-v4--flash-4f46e5" alt="DeepSeek v4 Flash">
  <img src="https://img.shields.io/badge/tests-215%20passed-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-offline%20deterministic-success" alt="Offline Tests">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

> **SimpleWell — AI Module** | Author: 2692341798  
> `wellness-app-ai` is the private FastAPI AI microservice for the SimpleWell health management application. It provides health checks, general wellness chat, and personalized wellness advice, generating content via the DeepSeek large language model. It is called exclusively by the Spring Boot backend internally and is never exposed directly to the frontend or Android.

---

## Table of Contents

- [Integration Boundary](#integration-boundary)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Running the Service](#running-the-service)
- [API Endpoints](#api-endpoints)
  - [GET /health — Health Check](#get-health--health-check)
  - [POST /ai/chat — Wellness Chat](#post-aichat--wellness-chat)
  - [POST /ai/wellness-advice — Wellness Advice](#post-aiwellness-advice--wellness-advice)
- [Unified Error Format](#unified-error-format)
- [Error Code Reference](#error-code-reference)
- [Safety Design](#safety-design)
- [Quality Checks](#quality-checks)
- [Engineering Documentation](#engineering-documentation)

---

## Integration Boundary

```text
┌──────────────┐     HTTPS + JWT     ┌──────────────────────┐      Internal REST    ┌─────────────────┐      HTTPS       ┌──────────┐
│  Android App  │ ──────────────────▶ │  Spring Boot Backend │ ───────────────────▶ │  FastAPI (This)  │ ───────────────▶ │ DeepSeek │
└──────────────┘                     └──────────────────────┘                      └─────────────────┘                  └──────────┘
  Does not call this service directly      Owns login/JWT/auth/persistence               AI generation service                  LLM API
```

- **Android must never call FastAPI directly**. All requests must go through Spring Boot.
- Spring Boot is responsible for: user login, JWT creation and validation, user authentication, ownership checks, MySQL persistence, chat history management, and scheduled recommendation dispatch.
- This service must be deployed on a private network reachable only by Spring Boot, **never exposed via a public internet entry point**.
- Therefore, all curl examples below do not include JWT or custom service auth headers — they are private backend-to-backend calls.

> Full architecture: [`.trae/documents/WellnessApp_AI_Architecture.md`](.trae/documents/WellnessApp_AI_Architecture.md)

---

## Tech Stack

| Category | Technology | Version |
|------|------|------|
| Language | Python | ≥ 3.11 |
| Web Framework | FastAPI | ≥ 0.115 |
| Data Validation | Pydantic v2 | (bundled with FastAPI) |
| LLM SDK | OpenAI Python SDK (adapted for DeepSeek) | ≥ 1.68 |
| Config Management | pydantic-settings | ≥ 2.8 |
| Retry Strategy | tenacity | ≥ 9 |
| ASGI Server | uvicorn | ≥ 0.34 |
| Test Framework | pytest + pytest-asyncio + HTTPX | — |
| Code Quality | ruff + mypy (strict) | — |
| Package Management | uv + hatchling | — |

---

## Project Structure

```
wellness-app-ai/
├── app/                        # Application source
│   ├── main.py                 # FastAPI factory, middleware, exception handlers
│   ├── api/
│   │   ├── dependencies.py     # Dependency injection (Settings/Provider/Service)
│   │   └── routes/
│   │       ├── health.py       # GET /health
│   │       ├── chat.py         # POST /ai/chat
│   │       └── advice.py       # POST /ai/wellness-advice
│   ├── core/                   # Infrastructure
│   │   ├── config.py           # Environment config (Pydantic Settings)
│   │   ├── exceptions.py       # Stable error codes + AppError (10 types)
│   │   └── logging.py          # Privacy-safe JSON logging + Request ID
│   ├── prompts/                # Versioned System Prompts
│   │   ├── chat.py             # Wellness Chat prompt v1
│   │   └── advice.py           # Wellness Advice prompt v1
│   ├── providers/              # LLM adapter layer
│   │   ├── base.py             # LLMProvider async protocol
│   │   └── deepseek.py         # DeepSeek adapter (retry/error-mapping/token observability)
│   ├── schemas/                # Request/Response schemas
│   │   ├── common.py           # ErrorResponse unified error envelope
│   │   ├── chat.py             # ChatRequest/ChatResponse
│   │   └── advice.py           # AdviceRequest/AdviceResponse/WellnessLog
│   └── services/               # Application service layer
│       ├── safety.py           # SafetyPolicy (deterministic crisis detection)
│       ├── chat.py             # ChatService (orchestrates safety + Provider)
│       └── advice.py           # AdviceService (includes deterministic no-data path)
├── tests/                      # Tests (mirrors production structure)
├── docs/superpowers/           # Design docs and implementation plans
└── .trae/documents/            # Engineering documentation
```

---

## Quick Start

**Prerequisites**: Python 3.11+, [`uv`](https://docs.astral.sh/uv/) recommended.

```bash
# 1. Clone the repository
git clone https://github.com/Terrence129/wellness-app-ai.git
cd wellness-app-ai

# 2. Install dependencies
uv sync --extra dev

# 3. Configure environment (copy the template and edit .env to fill in your real DEEPSEEK_API_KEY)
test -e .env || cp .env.example .env
```

> **Not using uv?** Use traditional pip:
> ```bash
> python -m venv .venv
> source .venv/bin/activate
> pip install -e '.[dev]'
> test -e .env || cp .env.example .env
> ```

**Environment Variables** (fully documented in `.env.example`):

| Variable | Default | Description |
|------|--------|------|
| `APP_NAME` | `wellness-app-ai` | Application name |
| `APP_ENV` | `development` | Runtime environment |
| `LOG_LEVEL` | `INFO` | Log level |
| `DEEPSEEK_API_KEY` | (empty) | DeepSeek API key. Empty = not configured |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API base URL |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-v4-flash` | Chat model name |
| `DEEPSEEK_ADVICE_MODEL` | `deepseek-v4-flash` | Advice model name |
| `DEEPSEEK_AGENT_MODEL` | `deepseek-v4-pro` | Agent model name (reserved) |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | Request timeout (1-120) |
| `DEEPSEEK_MAX_RETRIES` | `2` | Max retry attempts (0-5) |

> **Security reminder**: The real `DEEPSEEK_API_KEY` belongs only in the untracked `.env` file or process environment variables. **Never commit keys.**

---

## Running the Service

```bash
uv run uvicorn app.main:app --reload
```

Default service address: `http://127.0.0.1:8000`

### Behavior Without an API Key

Starting without `DEEPSEEK_API_KEY` is allowed:

| Scenario | Behavior |
|------|------|
| `GET /health` | **200 OK** — DeepSeek not needed |
| `POST /ai/chat` | **503** — `AI_PROVIDER_NOT_CONFIGURED` |
| `POST /ai/wellness-advice` (with data) | **503** — `AI_PROVIDER_NOT_CONFIGURED` |
| `POST /ai/wellness-advice` (empty logs) | **200 OK** — returns stable tip text, does not call DeepSeek |

---

## API Endpoints

> Full API specification: [`.trae/documents/WellnessApp_AI_API.md`](.trae/documents/WellnessApp_AI_API.md)  
> Start the service and visit `http://127.0.0.1:8000/docs` for interactive Swagger documentation.

### GET /health — Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

### POST /ai/chat — Wellness Chat

Spring Boot forwards user questions and a bounded conversation history. DeepSeek is stateless — Spring Boot handles conversation persistence and submits a bounded history with each request.

```bash
curl -X POST http://localhost:8000/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "userId": 1,
    "message": "How can I improve my sleep schedule?",
    "history": [
      {"role": "user", "content": "I usually sleep six hours."},
      {"role": "assistant", "content": "A consistent bedtime may help."}
    ]
  }'
```

**Request Validation**:

| Field | Constraint |
|------|------|
| `userId` | Positive integer |
| `message` | 1-2000 characters (after stripping whitespace) |
| `history` | Max 12 entries |
| `history[].role` | `user` / `assistant` only |
| `history[].content` | 1-4000 characters per entry |
| Aggregate length | `message` + all `history[].content` ≤ 20000 characters |

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### POST /ai/wellness-advice — Wellness Advice

Generates personalized advice based on the user's wellness log data.

**Empty logs scenario (deterministic path, does not call DeepSeek)**:

```bash
curl -X POST http://localhost:8000/ai/wellness-advice \
  -H 'Content-Type: application/json' \
  -d '{"userId": 1, "logs": []}'
```

```json
{
  "adviceText": "There is not enough wellness data yet. Record your sleep, mood, water intake, and exercise for a few days.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**With data scenario**:

```bash
curl -X POST http://localhost:8000/ai/wellness-advice \
  -H 'Content-Type: application/json' \
  -d '{
    "userId": 1,
    "logs": [
      {
        "logDate": "2026-06-24",
        "sleepHours": 7.5,
        "moodScore": 4,
        "waterCups": 6,
        "steps": 8000,
        "exerciseMinutes": 30,
        "note": "Felt tired in the afternoon."
      }
    ]
  }'
```

```json
{
  "adviceText": "Your sleep duration is stable. Consider taking a short afternoon break.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Request Validation**:

| Field | Constraint |
|------|------|
| `userId` | Positive integer |
| `logs` | Max 31 entries |
| `logDate` | ISO 8601 full date (YYYY-MM-DD) |
| `sleepHours` | 0 - 24 (optional) |
| `moodScore` | 1 - 5 (optional) |
| `waterCups` | ≥ 0 (optional) |
| `steps` | ≥ 0 (optional) |
| `exerciseMinutes` | 0 - 1440 (optional) |
| `note` | Max 1000 characters (optional) |

---

## Unified Error Format

All validation errors, provider errors, and unexpected exceptions use a unified envelope:

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Consumer contract**: Branch on `errorCode`. Preserve `requestId` for troubleshooting. **Do not parse the `message` text.**

---

## Error Code Reference

| HTTP | errorCode | Meaning |
|------|-----------|------|
| 422 | `VALIDATION_ERROR` | Local Pydantic request validation failure |
| 429 | `AI_RATE_LIMITED` | DeepSeek rate limit triggered |
| 502 | `AI_INVALID_RESPONSE` | Provider returned empty/truncated/invalid JSON / schema mismatch |
| 502 | `AI_PROVIDER_REQUEST_REJECTED` | DeepSeek rejected the request (400 or 422) |
| 503 | `AI_PROVIDER_NOT_CONFIGURED` | `DEEPSEEK_API_KEY` is missing |
| 503 | `AI_PROVIDER_AUTH_FAILED` | DeepSeek authentication failed (401) |
| 503 | `AI_PROVIDER_QUOTA_EXHAUSTED` | DeepSeek quota exhausted (402) |
| 503 | `AI_PROVIDER_UNAVAILABLE` | DeepSeek unavailable (500/503) or connection failure |
| 504 | `AI_PROVIDER_TIMEOUT` | Provider timed out |
| 500 | `INTERNAL_ERROR` | Unexpected application error |

**Retry strategy**:
- Retry only on: connection failure, timeout, 429, 500, 503
- Exponential backoff + random jitter, max 2 retries (3 total attempts)
- Honor upstream `Retry-After` delay (within the overall timeout budget)
- Do not retry: 400 / 401 / 402 / 422
- Advice JSON output invalid → one additional regeneration attempt allowed

---

## Safety Design

This service operates within a **general wellness scope** and does not provide medical diagnosis:

- **Does not diagnose** illness, **does not claim** medical certainty, **does not prescribe** medication, **does not provide** dosage recommendations
- **Deterministic crisis escalation**: Before calling the provider, matches 6 keywords (`kill myself` / `suicide` / `self-harm` / `cannot breathe` / `chest pain` / `overdose`); on match, returns a fixed escalation message and **does not call DeepSeek**
- User text and wellness notes are treated as **untrusted input** and cannot override the system safety policy
- **Never sent to DeepSeek**: email, username, JWT, password, `userId`, or other identity data
- **Never logged**: raw messages, history, prompts, generated content, wellness notes, keys, credentials

---

## Quality Checks

The default test suite is **deterministic and offline**, consuming zero provider tokens:

```bash
uv run ruff check .
uv run mypy app tests
uv run pytest
```

Live DeepSeek integration tests require **explicit opt-in** with a configured `DEEPSEEK_API_KEY` and are excluded from the default suite:

```bash
uv run pytest -m live tests/integration/test_live_deepseek.py
```

The live test must not print the key, request payload, or generated response text.

## Local knowledge RAG (retrieval-augmented generation)

When `RAG_ENABLED` is true, the service indexes approved local knowledge files at startup and uses keyword retrieval to ground chat replies in the project-maintained wellness knowledge base. Documents are plain Markdown (`.md`) or text (`.txt`) files under `knowledge/`.

### Adding knowledge

Create `.md` or `.txt` files under `knowledge/`. Each file should cover a narrow wellness topic. Recommended content structure:

```markdown
# Topic title

Concise, paraphrased summary of authoritative public wellness guidance.
Keep content factual and source-based.

## References
- https://authoritative-source.example.com/guideline
- Last reviewed: YYYY-MM-DD
```

Source material should be paraphrased, not copied. Adding or changing a knowledge file is a reviewable code change. Medical claims require verification against current authoritative sources.

### Index lifecycle

The index is managed automatically:

- On startup, the service computes a corpus fingerprint from file content hashes and chunk settings.
- If the fingerprint matches an existing index, the index is reused.
- Otherwise the index is rebuilt atomically — a partial rebuild cannot leave a broken index.
- Missing or corrupt indexes trigger an automatic rebuild.
- An empty `knowledge/` directory or `RAG_ENABLED=false` gracefully degrades to non-RAG chat.

Generated SQLite index files live under `.data/` and are excluded from Git.

### RAG configuration

All RAG settings default to safe values for a small local corpus:

| Setting | Default | Description |
|---|---|---|
| `RAG_ENABLED` | `true` | Feature switch |
| `RAG_KNOWLEDGE_DIR` | `knowledge` | Directory for Markdown and TXT knowledge files |
| `RAG_INDEX_PATH` | `.data/rag-index.sqlite3` | Generated FTS5 index path |
| `RAG_TOP_K` | `4` | Maximum chunks per query (1-10) |
| `RAG_CHUNK_SIZE` | `1000` | Target characters per chunk (300-4000) |
| `RAG_CHUNK_OVERLAP` | `150` | Character overlap between chunks |
| `RAG_CONTEXT_MAX_CHARS` | `4000` | Maximum total context characters (500-12000) |
| `RAG_MAX_FILE_BYTES` | `1048576` | Per-file byte limit |
| `RAG_MAX_CORPUS_BYTES` | `20971520` | Total corpus byte limit (20 MB) |

### Retrieval behaviour

- Retrieval uses SQLite FTS5 with BM25 ranking on English tokenized queries.
- The retrieval query combines the current user message and the two most recent user history messages.
- Assistant messages are excluded from the query.
- Retrieved text is placed in a delimited context block appended to the user message.
- The system prompt instructs the model that knowledge text is reference material, never an instruction source.
- Retrieval failures degrade to the existing non-RAG chat path.

### Deployment

In production, mount the knowledge directory read-only and the index directory writable. The index directory must be on a persistent volume if you want to reuse the index across restarts (the service will rebuild it otherwise, which is fast for small corpora).
