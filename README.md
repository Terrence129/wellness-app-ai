# wellness-app-ai

`wellness-app-ai` is the private FastAPI AI service for the SimpleWell application. It provides a health check, general wellness chat, and personalised wellness advice through DeepSeek. It is an internal backend component, not a client-facing API.

## Integration boundary

The supported request path is:

```text
Android app -> Spring Boot backend -> private FastAPI service -> DeepSeek
```

Android must call Spring Boot and must never call FastAPI directly. Spring Boot owns login, JWT handling, user authorisation, ownership checks, persistence, and bounded chat history. This service must run on a private network reachable only by Spring Boot and must not be exposed through public ingress. The private backend-to-backend examples below therefore contain no JWT or invented service-auth header.

## Requirements and setup

- Python 3.11 or newer.
- [`uv`](https://docs.astral.sh/uv/) is the primary environment and package manager.

Using `uv`:

```bash
uv sync --extra dev
test -e .env || cp .env.example .env
```

Alternatively, using Python and pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
test -e .env || cp .env.example .env
```

`.env.example` documents every supported setting and its safe development default:

```dotenv
APP_NAME=wellness-app-ai
APP_ENV=development
LOG_LEVEL=INFO

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash
DEEPSEEK_ADVICE_MODEL=deepseek-v4-flash
DEEPSEEK_AGENT_MODEL=deepseek-v4-pro
DEEPSEEK_TIMEOUT_SECONDS=30
DEEPSEEK_MAX_RETRIES=2
```

Put the real `DEEPSEEK_API_KEY` only in the untracked `.env` file or process environment. Never commit secrets. Model names, the provider timeout, and the bounded retry count remain configurable.

## Run the service

Start the development server from the repository root:

```bash
uv run uvicorn app.main:app --reload
```

The default address is `http://127.0.0.1:8000`.

The application may start without `DEEPSEEK_API_KEY`. In that configuration:

- `GET /health` still returns `200 OK` because it never calls DeepSeek.
- `POST /ai/chat` returns `503` with `AI_PROVIDER_NOT_CONFIGURED`.
- `POST /ai/wellness-advice` with non-empty `logs` returns `503` with `AI_PROVIDER_NOT_CONFIGURED`.
- `POST /ai/wellness-advice` with empty `logs` returns `200 OK` with the stable no-data advice and does not call DeepSeek.

## API examples

### Health

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

### Wellness chat

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

Successful response:

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Wellness advice

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

Successful response:

```json
{
  "adviceText": "Your sleep duration is stable. Consider taking a short afternoon break.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

An empty-log request uses the deterministic no-data path:

```bash
curl -X POST http://localhost:8000/ai/wellness-advice \
  -H 'Content-Type: application/json' \
  -d '{"userId": 1, "logs": []}'
```

It returns `200 OK` with `There is not enough wellness data yet. Record your sleep, mood, water intake, and exercise for a few days.` even when no provider key is configured.

## Stable error envelope

Validation, provider, and unexpected application failures use one stable response shape:

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

Consumers should branch on `errorCode`, retain `requestId` for support, and not parse `message`. The defined codes are `VALIDATION_ERROR`, `AI_RATE_LIMITED`, `AI_INVALID_RESPONSE`, `AI_PROVIDER_REQUEST_REJECTED`, `AI_PROVIDER_NOT_CONFIGURED`, `AI_PROVIDER_AUTH_FAILED`, `AI_PROVIDER_QUOTA_EXHAUSTED`, `AI_PROVIDER_UNAVAILABLE`, `AI_PROVIDER_TIMEOUT`, and `INTERNAL_ERROR`.

## Quality checks

The default test suite is deterministic, offline, and incurs no provider token charges:

```bash
uv run ruff check .
uv run mypy app tests
uv run pytest
```

The live DeepSeek integration test is opt-in. It requires deliberate network access and a non-empty `DEEPSEEK_API_KEY`; it is excluded from the default suite. Run it explicitly with:

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
