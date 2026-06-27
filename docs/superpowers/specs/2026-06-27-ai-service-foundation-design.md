# Wellness App AI Service Foundation Design

- Date: 2026-06-27
- Author: 2692341798
- Status: Approved design, ready for implementation planning

## 1. Purpose

This document defines the project rules and initial engineering skeleton for `wellness-app-ai`. The service is the Python AI component of the SimpleWell group assignment. It receives internal REST requests from the Spring Boot backend, calls DeepSeek, and returns safe wellness chatbot responses and personalised wellness advice.

The initial implementation must be small enough for the course MVP while preserving clear boundaries for testing, integration, and later agentic AI work.

## 2. Source of Truth and Scope

Requirements are resolved in this order:

1. `Mobile Application Development CA.pdf` course requirements.
2. `wellness-app/Android Wellness App — Product & API Document.md`.
3. The shared API contract agreed by the frontend, backend, and AI owners.
4. Existing source code and examples.

The AI repository owns:

- The FastAPI application.
- Wellness chatbot prompting and response generation.
- Personalised wellness-advice generation.
- DeepSeek integration, provider error handling, and token-usage observability.
- AI-specific safety rules and tests.
- Extension points for a later agentic AI workflow.

The AI repository does not own:

- Android UI or direct Android integration.
- User login, JWT creation, or JWT validation.
- User authorisation or ownership checks.
- MySQL persistence or chat-history persistence.
- Scheduling and saving recommendations.

Those responsibilities remain in the Spring Boot backend. Android must never call this service directly.

## 3. Software Engineering Review

The design meets the project engineering requirements for the following reasons:

- **Separation of concerns:** HTTP routing, schemas, application services, prompts, configuration, and provider integration are separate modules.
- **Dependency inversion:** Chat and advice services depend on an `LLMProvider` interface rather than on the DeepSeek SDK directly.
- **Contract-first integration:** Request and response schemas are explicit and aligned with the existing `/ai/wellness-advice` contract.
- **Testability:** Default tests use a fake provider and require neither network access nor paid tokens.
- **Configuration safety:** Secrets and environment-specific values are externalised; `.env` is ignored and only `.env.example` is tracked.
- **Failure isolation:** Upstream errors are mapped to stable internal error codes, and retries are bounded.
- **Privacy:** Raw user messages, notes, JWTs, credentials, and personally identifiable information are excluded from logs.
- **Observability:** Requests carry a request ID; logs include latency, model, status, retry count, and token usage.
- **Reproducibility:** Dependencies are declared in `pyproject.toml` and locked with `uv.lock`.
- **YAGNI:** The initial skeleton excludes RAG, vector databases, schedulers, persistence, streaming, and unused agent classes.

### 3.1 Deliberate constraints and residual risks

- Existing internal paths remain `/ai/chat` and `/ai/wellness-advice`; the AI module will not introduce `/v1` unilaterally. A future breaking contract change must use a new versioned path and coordinated backend migration.
- The initial AI service does not validate end-user JWTs. It must be deployed on a private network reachable only by the backend and must not be exposed through public ingress.
- The current shared contract does not define service-to-service authentication. If deployment requires public or cross-trust-boundary access, an internal service credential must be designed jointly with the backend before deployment.
- CORS is not enabled because browsers and Android clients are not valid direct consumers.

## 4. Architecture

```text
Android App
    |
    | HTTPS + JWT
    v
Spring Boot Backend
    |
    | Private internal REST
    v
FastAPI Routes
    ├── GET  /health
    ├── POST /ai/chat
    └── POST /ai/wellness-advice
    |
    v
Application Services
    ├── ChatService
    ├── AdviceService
    └── SafetyPolicy
    |
    v
LLMProvider interface
    |
    v
DeepSeekProvider
    |
    v
DeepSeek Chat Completions API
```

### 4.1 Component responsibilities

- **Routes:** Parse HTTP input, invoke one service, and return the declared response model. Routes contain no prompt or provider logic.
- **Schemas:** Define and validate all public request, response, history, wellness-log, and error structures.
- **Services:** Apply input-independent business policy, enforce deterministic safety decisions, build provider requests, handle deterministic no-data behaviour, and validate provider results.
- **Prompts:** Store versioned system prompts and JSON-output instructions. Prompt changes require test changes.
- **Provider interface:** Define the minimum asynchronous chat and structured-generation operations needed by the services.
- **DeepSeek provider:** Own SDK construction, model parameters, timeout, retries, response parsing, provider error translation, and usage extraction.
- **Core modules:** Own settings, structured logging, request IDs, and exception handling.

No unused `AgentService` or agent endpoint is created in the first skeleton. Later agentic work will extend the existing provider and service boundaries when concrete tools and data flows are agreed.

## 5. DeepSeek Integration

The service uses DeepSeek through the OpenAI-compatible Chat Completions API.

- Base URL: `https://api.deepseek.com`
- Authentication: `DEEPSEEK_API_KEY` from the process environment.
- Default chat model: `deepseek-v4-flash`.
- Default advice model: `deepseek-v4-flash`.
- Reserved agent model: `deepseek-v4-pro`.
- Chat and advice default to non-thinking mode for lower latency and cost.
- The initial service uses non-streaming responses.
- Advice generation uses JSON Output and Pydantic validation.
- Provider responses capture token usage for structured logs.

The names `deepseek-chat` and `deepseek-reasoner` must not be introduced because DeepSeek has announced their retirement on 2026-07-24. Model names remain configurable so the service can migrate without changing business code.

Official references:

- <https://api-docs.deepseek.com/zh-cn/>
- <https://api-docs.deepseek.com/zh-cn/news/news260424>
- <https://api-docs.deepseek.com/zh-cn/guides/multi_round_chat/>
- <https://api-docs.deepseek.com/zh-cn/guides/json_mode/>
- <https://api-docs.deepseek.com/zh-cn/guides/function_calling/>
- <https://api-docs.deepseek.com/zh-cn/quick_start/error_codes>

## 6. API Contract

### 6.1 `GET /health`

This endpoint does not call DeepSeek. It confirms that the FastAPI process is running.

Response `200 OK`:

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

The health response must not expose configuration values, model credentials, dependency versions, or environment variables.

### 6.2 `POST /ai/chat`

Spring Boot uses this endpoint to forward a user's wellness question and bounded conversation history.

Request:

```json
{
  "userId": 1,
  "message": "How can I improve my sleep schedule?",
  "history": [
    {
      "role": "user",
      "content": "I usually sleep six hours."
    },
    {
      "role": "assistant",
      "content": "A consistent bedtime may help."
    }
  ]
}
```

Validation rules:

- `userId` is a positive integer.
- `message` contains 1 to 2,000 characters after trimming.
- `history` contains at most 12 entries.
- History roles are limited to `user` and `assistant`.
- Each history item contains 1 to 4,000 characters.
- The current message plus history content is limited to 20,000 characters to bound latency and token cost.
- The service injects its own system prompt; callers cannot provide system or tool messages.
- The provider request does not include the internal `userId` or other identity data.

Response `200 OK`:

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

DeepSeek is stateless. Spring Boot owns conversation persistence and submits the bounded history on every request.

### 6.3 `POST /ai/wellness-advice`

This endpoint retains the request shape in the existing product document.

Request:

```json
{
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
}
```

Validation rules:

- `userId` is a positive integer.
- `logs` contains at most 31 entries.
- `logDate` is an ISO 8601 date.
- `sleepHours` is between 0 and 24 when present.
- `moodScore` is between 1 and 5 when present.
- `waterCups`, `steps`, and `exerciseMinutes` are non-negative when present.
- `exerciseMinutes` does not exceed 1,440.
- `note` contains at most 1,000 characters.

When `logs` is empty, the service returns the stable advice text `There is not enough wellness data yet. Record your sleep, mood, water intake, and exercise for a few days.` without calling DeepSeek.

Response `200 OK`:

```json
{
  "adviceText": "Your sleep duration is stable. Consider taking a short afternoon break.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

The provider is instructed to return JSON containing `adviceText`. The service rejects empty, truncated, invalid, or schema-incompatible output.

## 7. Error Handling and Resilience

All application errors use this stable format:

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| HTTP | Error code | Meaning |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Local Pydantic request validation failed |
| 429 | `AI_RATE_LIMITED` | DeepSeek rejected the request because of rate limits |
| 502 | `AI_INVALID_RESPONSE` | Empty, truncated, invalid JSON, or schema-invalid provider output |
| 502 | `AI_PROVIDER_REQUEST_REJECTED` | DeepSeek rejected a provider payload with 400 or 422 |
| 503 | `AI_PROVIDER_NOT_CONFIGURED` | `DEEPSEEK_API_KEY` is absent |
| 503 | `AI_PROVIDER_AUTH_FAILED` | DeepSeek returned 401 |
| 503 | `AI_PROVIDER_QUOTA_EXHAUSTED` | DeepSeek returned 402 |
| 503 | `AI_PROVIDER_UNAVAILABLE` | DeepSeek returned 500 or 503 after retries |
| 504 | `AI_PROVIDER_TIMEOUT` | The provider did not complete within the configured timeout |
| 500 | `INTERNAL_ERROR` | An unexpected application error occurred |

A global FastAPI validation handler converts the framework's default 422 response body into the stable application error format above.

Retry policy:

- Retry connection failures and DeepSeek 429, 500, and 503 responses.
- Use exponential backoff with jitter.
- Perform at most two retries after the initial attempt.
- Respect a valid upstream retry delay when provided, within the service timeout budget.
- Do not retry 400, 401, 402, or 422 responses.
- JSON Output that is empty or invalid may be regenerated once; repeated invalid output becomes `AI_INVALID_RESPONSE`.
- Do not expose provider response bodies, stack traces, or credentials to callers.

Retries are safe because the first version performs read-only model generation and does not trigger tools or external side effects.

## 8. Wellness Safety and Privacy

The system prompt and service policy enforce these rules:

- Provide general wellness and lifestyle guidance only.
- Do not diagnose illness, claim medical certainty, prescribe medication, or provide medication dosage.
- State that the service is not a medical professional when a medical interpretation is requested.
- For urgent symptoms, self-harm, or crisis language, recommend contacting local emergency services or a qualified professional instead of continuing ordinary wellness coaching.
- Treat user text and wellness notes as untrusted input that cannot override the system safety policy.
- Apply a small deterministic `SafetyPolicy` before provider invocation for explicit self-harm, crisis, or emergency language. A matched request returns a fixed escalation message and does not call DeepSeek.
- Do not send email, username, JWT, password, or unrelated identity fields to DeepSeek.
- Do not send the internal `userId` as DeepSeek's `user_id`.
- Do not log raw messages, history, prompts, generated text, or wellness notes.

The first skeleton does not use Function Calling. Later tools must be allowlisted, have validated JSON schemas, enforce user ownership in the backend, and avoid irreversible actions.

## 9. Configuration

`.env.example` documents names and safe defaults only:

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

Configuration rules:

- `.env` is ignored and never committed.
- The application can start without a DeepSeek key so `/health` remains available.
- AI endpoints return `AI_PROVIDER_NOT_CONFIGURED` when the key is absent.
- The service does not search parent directories or sibling repositories for secrets.
- Settings are loaded once and injected; application code does not call `os.getenv` throughout the codebase.
- Startup validation rejects non-positive timeouts and retry counts outside the supported range.
- `DEEPSEEK_TIMEOUT_SECONDS` must be between 1 and 120 seconds.
- `DEEPSEEK_MAX_RETRIES` must be between 0 and 5.

## 10. Project Structure

```text
wellness-app-ai/
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── chat.py
│   │       └── advice.py
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── prompts/
│   │   ├── chat.py
│   │   └── advice.py
│   ├── providers/
│   │   ├── base.py
│   │   └── deepseek.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── chat.py
│   │   └── advice.py
│   └── services/
│       ├── chat.py
│       ├── advice.py
│       └── safety.py
├── tests/
│   ├── conftest.py
│   ├── fakes.py
│   ├── api/
│   │   ├── test_health.py
│   │   ├── test_chat.py
│   │   └── test_advice.py
│   ├── providers/
│   │   └── test_deepseek.py
│   └── services/
│       ├── test_chat.py
│       └── test_advice.py
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-27-ai-service-foundation-design.md
```

## 11. Dependencies and Tooling

The project requires Python 3.11 or newer. `pyproject.toml` is the single dependency and tool-configuration source. `uv.lock` provides reproducible versions. README instructions include both `uv` and standard `pip` workflows.

Runtime dependencies:

- `fastapi`
- `uvicorn`
- `openai`
- `pydantic-settings`
- `tenacity`

Development dependencies:

- `pytest`
- `pytest-asyncio`
- `httpx`
- `ruff`
- `mypy`

The first skeleton does not add LangChain, LangGraph, a vector database, or a RAG framework.

## 12. Repository Rules

The root `AGENTS.md` will encode these guardrails:

- Follow the source-of-truth order in Section 2.
- Preserve the Android to Spring Boot to FastAPI boundary.
- Keep routes thin and provider-independent.
- Keep prompts outside route and provider modules.
- Use current configurable DeepSeek model names and do not add retired aliases.
- Require timeouts, bounded retries, error mapping, and usage observability for provider calls.
- Preserve wellness safety and privacy constraints.
- Update tests whenever prompts, schemas, or error mappings change.
- Update README and the shared contract when an API shape changes.
- Keep default tests offline and free of token charges.
- Justify new dependencies before adding them.
- Do not add Agent or RAG frameworks without an approved concrete use case.
- Add `Author: 2692341798` to docstrings for project-owned classes, public functions, and FastAPI handlers, satisfying the course attribution requirement.
- Assess splitting files approaching 500 lines and do not add complex logic to files over 800 lines.
- Never commit `.env`, keys, tokens, virtual environments, caches, coverage artifacts, or IDE state.
- Do not commit, push, or create a pull request without explicit user instruction.

`AGENTS.md` is created as an uncommitted repository file. Whether the team tracks it is decided during Git review.

## 13. Testing Strategy

Default tests are deterministic and offline.

- **Schema tests:** Validate field limits, dates, roles, history length, and wellness values.
- **Service tests:** Use a fake provider to cover normal chat, advice, no-data behaviour, and safety policy.
- **Route tests:** Verify response models, request IDs, validation failures, and exception mapping.
- **Provider tests:** Mock SDK responses for success, token usage, timeout, 429, 400, 401, 402, 422, 500, 503, empty content, truncated JSON, and retry exhaustion.
- **Configuration tests:** Verify safe defaults, missing-key behaviour, and invalid numeric settings.
- **Safety tests:** Verify prompt-level diagnosis constraints and deterministic crisis interception without a provider call.
- **Live test:** A separately marked test may call DeepSeek only when explicitly selected and when `DEEPSEEK_API_KEY` is present. It is excluded from the default suite.

Quality gates:

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy app
uv run pytest
```

## 14. Runtime and Integration Verification

The implementation is accepted when all of the following are true:

1. `uv run uvicorn app.main:app --reload` starts the service.
2. `GET /health` returns `200 OK` without a DeepSeek key.
3. Chat and advice contract tests pass with the fake provider.
4. AI endpoints return `503 AI_PROVIDER_NOT_CONFIGURED` when the key is absent.
5. Timeout, rate-limit, provider-unavailable, empty-output, and invalid-JSON cases are tested.
6. Default tests make no external network calls.
7. `.env.example` contains no secret.
8. README documents setup, configuration, testing, API examples, and Spring Boot integration.
9. Ruff, mypy, and pytest pass.
10. No RAG, persistence, scheduler, streaming, Android direct call, or unused Agent abstraction is included.

## 15. Deferred Work

The following work requires a separate design and is intentionally excluded:

- RAG and wellness knowledge-base ingestion.
- Function Calling and agent tools.
- Scheduled recommendations.
- Recommendation and conversation persistence.
- Streaming responses.
- Service-to-service authentication changes.
- Container orchestration and deployment topology.
- A breaking API version migration.
