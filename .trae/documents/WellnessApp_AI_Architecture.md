# Wellness App AI — Architecture Document

> **Version**: v0.1.0 | **Author**: 2692341798 | **Last Updated**: 2026-06-27  
> This document defines the layered architecture, module responsibilities, data flows, and key design decisions for the SimpleWell AI module.

---

## Table of Contents

- [1. System Positioning and Boundaries](#1-system-positioning-and-boundaries)
- [2. Layered Architecture](#2-layered-architecture)
- [3. Module Responsibilities](#3-module-responsibilities)
- [4. Data Flows](#4-data-flows)
- [5. Provider Adapter Design](#5-provider-adapter-design)
- [6. Safety Architecture](#6-safety-architecture)
- [7. Error Handling Architecture](#7-error-handling-architecture)
- [8. Configuration Management](#8-configuration-management)
- [9. Design Decision Records](#9-design-decision-records)

---

## 1. System Positioning and Boundaries

### 1.1 Position Within SimpleWell

```text
┌──────────────┐     HTTPS + JWT     ┌──────────────────────┐      Internal REST    ┌─────────────────┐      HTTPS       ┌──────────┐
│  Android App  │ ──────────────────▶ │  Spring Boot Backend │ ───────────────────▶ │  FastAPI (This)  │ ───────────────▶ │ DeepSeek │
└──────────────┘                     └──────────────────────┘                      └─────────────────┘                  └──────────┘
```

### 1.2 What This Module Owns

- FastAPI application and service startup
- Wellness chat prompting and reply generation
- Personalized wellness advice generation
- DeepSeek integration, provider error handling, token usage observability
- AI safety rules and testing
- Extension points for future agentic AI workflows

### 1.3 What This Module Does NOT Own (Handled by Spring Boot)

- Android UI or direct Android integration
- User login, JWT creation and validation
- User authentication and ownership checks
- MySQL persistence, chat history persistence
- Scheduled recommendations and dispatch

---

## 2. Layered Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Routes (Thin Layer)                  │
│  GET /health         POST /ai/chat    POST /ai/wellness-advice│
│  Parse input only → call one Service → return Response Model │
├─────────────────────────────────────────────────────────────┤
│                    Application Services                      │
│  ChatService          AdviceService        SafetyPolicy     │
│  Orchestrate safety → call Provider → validate/strip result │
│  Depend on LLMProvider interface, not DeepSeek SDK           │
├─────────────────────────────────────────────────────────────┤
│                    LLMProvider Interface (Protocol)          │
│  generate_chat()            generate_advice()                │
│  Async Protocol — services depend only on this interface     │
├─────────────────────────────────────────────────────────────┤
│                    DeepSeekProvider (Adapter)                │
│  The only module aware of the OpenAI SDK                     │
│  Handles: SDK construction, retries, parsing, error mapping, │
│           token extraction, log sanitization                 │
├─────────────────────────────────────────────────────────────┤
│                    DeepSeek Chat Completions API              │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Dependency Direction

```
Routes → Services → LLMProvider (Protocol) ← DeepSeekProvider
                    ↑                            ↑
              Prompts (versioned)          Core (Config/Logging/Exceptions)
```

- **Routes contain no** prompt logic, provider logic, or retry logic
- **Services depend only** on the `LLMProvider` protocol, not the DeepSeek SDK
- **Provider is the only** module that knows the OpenAI SDK and DeepSeek API details

---

## 3. Module Responsibilities

### 3.1 `app/api/routes/` — HTTP Route Layer

| File | Responsibility |
|------|------|
| `health.py` | `GET /health` — Process liveness check |
| `chat.py` | `POST /ai/chat` — Accept chat requests, call ChatService |
| `advice.py` | `POST /ai/wellness-advice` — Accept advice requests, call AdviceService |

Route layer rules:
- Parse HTTP input (FastAPI auto-validates schemas)
- Call one application service
- Return the declared response model
- **Contains no** prompt, provider, retry, JSON parsing, or safety logic

### 3.2 `app/services/` — Application Service Layer

| File | Responsibility |
|------|------|
| `safety.py` | `SafetyPolicy` — Deterministic crisis phrase matching, returns fixed escalation message |
| `chat.py` | `ChatService` — Runs safety first, calls provider if safe, validates result |
| `advice.py` | `AdviceService` — Empty logs → deterministic path; with data → calls provider, strict JSON validation |

### 3.3 `app/providers/` — Provider Adapter Layer

| File | Responsibility |
|------|------|
| `base.py` | `LLMProvider` async Protocol — Defines minimum contract for `generate_chat` / `generate_advice` |
| `deepseek.py` | `DeepSeekProvider` — OpenAI-compatible adapter with retries, error mapping, token observability |

### 3.4 `app/prompts/` — Prompt Layer

| File | Responsibility |
|------|------|
| `chat.py` | `CHAT_SYSTEM_PROMPT` (v1) — Wellness Chat system prompt |
| `advice.py` | `ADVICE_SYSTEM_PROMPT` (v1) — Wellness Advice system prompt + JSON output instructions |

Prompt changes must update tests synchronously.

### 3.5 `app/schemas/` — Schema Layer

| File | Responsibility |
|------|------|
| `common.py` | `ErrorResponse` — Unified error envelope |
| `chat.py` | `ChatRequest`, `ChatResponse`, `ChatProviderResult`, and inner models |
| `advice.py` | `AdviceRequest`, `AdviceResponse`, `AdvicePayload`, `AdviceProviderResult` |

### 3.6 `app/core/` — Infrastructure Layer

| File | Responsibility |
|------|------|
| `config.py` | `Settings` — Pydantic Settings, 11 env vars with bounded validation |
| `exceptions.py` | `AppError` + `ErrorCode` — 10 stable error codes + named constructors |
| `logging.py` | Privacy-safe JSON logging + ContextVar-managed Request ID |

---

## 4. Data Flows

### 4.1 Chat Request Flow

```text
Spring Boot POST /ai/chat
  ↓
Chat Route → Auto-validate ChatRequest schema (return 422 on failure)
  ↓
ChatService.generate()
  ├── SafetyPolicy.evaluate(message + history)
  │   └── Crisis keyword match? → Return fixed escalation message (200 OK, no provider call)
  └── Safety passed
      ├── Build provider messages (System Prompt + History + User Message)
      ├── LLMProvider.generate_chat()
      │   └── DeepSeekProvider → DeepSeek API (with retries/error mapping)
      ├── Strip & validate reply content
      └── Return ChatResponse { reply, requestId }
```

### 4.2 Advice Request Flow

```text
Spring Boot POST /ai/wellness-advice
  ↓
Advice Route → Auto-validate AdviceRequest schema
  ↓
AdviceService.generate()
  ├── logs empty?
  │   └── Yes → Return stable text (200 OK, no provider call)
  └── No
      ├── Serialize wellness logs as JSON
      ├── Build provider messages (System Prompt + Logs JSON)
      ├── LLMProvider.generate_advice()
      │   └── DeepSeekProvider → DeepSeek API (JSON mode, with retries/error mapping)
      ├── Validate JSON → AdvicePayload (adviceText)
      │   └── Invalid? → One additional regeneration attempt (max 1)
      ├── Strip & validate adviceText
      └── Return AdviceResponse { adviceText, requestId }
```

---

## 5. Provider Adapter Design

### 5.1 DeepSeekProvider Key Design Points

| Capability | Implementation |
|------|------|
| SDK construction | `AsyncOpenAI(api_key, base_url, timeout, max_retries=0)` — SDK built-in retries disabled |
| Thinking mode | `extra_body={"thinking": {"type": "disabled"}}` — reduces latency and cost |
| Model | `deepseek-v4-flash` (chat/advice), `deepseek-v4-pro` (agent, reserved) |
| Retries | Self-implemented async attempt loop, exponential backoff + jitter |
| Error mapping | 9 HTTP status/exception types → stable `AppError` constructors |
| JSON output | Advice uses `response_format={"type": "json_object"}`, Pydantic validation |
| Truncation detection | Checks `finish_reason == "length"` → `AI_INVALID_RESPONSE` |
| Testability | client/sleep/random/clock all injectable |

### 5.2 Retry Strategy

```
retryable: connection error, timeout, 429, 500, 503
non-retryable: 400, 401, 402, 422

delay = min(base * 2^attempt + random(), remaining_budget)
Retry-After honored only within timeout budget
```

---

## 6. Safety Architecture

### 6.1 Multi-Layer Safety Protection

```text
Layer 1 (Pre-Provider): SafetyPolicy — Deterministic keyword matching
  ↓ No match
Layer 2 (Prompt): System Prompt constraints — General wellness scope
  ↓
Layer 3 (Post-Provider): Output validation — Strip, non-empty check, schema validation
```

### 6.2 Privacy Protection

| Protection Measure | Implementation Location |
|----------|---------|
| `userId` not sent to DeepSeek | Services exclude it when building provider requests |
| Log field allowlist | `app/core/logging.py` — Only permits `event/request_id/method/path/status/latency_ms/model/retry_count/tokens` |
| No raw content logging | Provider and Service never log messages/prompts/replies |
| `.env` excluded from version control | `.gitignore` |

---

## 7. Error Handling Architecture

### 7.1 Error Flow

```text
Pydantic ValidationError → RequestValidationError handler → ErrorResponse (422)
AppError (thrown at any layer) → AppError handler → ErrorResponse (status_code)
Exception (unexpected) → unexpected handler → ErrorResponse (500, details hidden)
```

### 7.2 Error Code Mapping Table

| Source | → | ErrorCode | HTTP |
|------|---|-----------|------|
| Pydantic validation failure | → | `VALIDATION_ERROR` | 422 |
| DeepSeek 429 | → | `AI_RATE_LIMITED` | 429 |
| Empty/truncated/invalid JSON output | → | `AI_INVALID_RESPONSE` | 502 |
| DeepSeek 400/422 rejection | → | `AI_PROVIDER_REQUEST_REJECTED` | 502 |
| API Key missing | → | `AI_PROVIDER_NOT_CONFIGURED` | 503 |
| DeepSeek 401 | → | `AI_PROVIDER_AUTH_FAILED` | 503 |
| DeepSeek 402 | → | `AI_PROVIDER_QUOTA_EXHAUSTED` | 503 |
| DeepSeek 500/503/connection failure | → | `AI_PROVIDER_UNAVAILABLE` | 503 |
| Timeout | → | `AI_PROVIDER_TIMEOUT` | 504 |
| Unexpected exception | → | `INTERNAL_ERROR` | 500 |

---

## 8. Configuration Management

- **Single config source**: Pydantic `Settings` + `.env` file
- **Startup without key**: `DEEPSEEK_API_KEY` can be empty, `/health` always available
- **Bounded validation**: `timeout` (1-120s), `max_retries` (0-5) validated at startup
- **No scattered `os.getenv`**: All config accessed through injected `Settings` instance
- **Configurable model names**: Supports future model migrations without code changes

---

## 9. Design Decision Records

| Decision | Rationale |
|------|------|
| Not using `deepseek-chat` / `deepseek-reasoner` | DeepSeek announced retirement effective 2026-07-24 |
| CORS not enabled | Browsers/Android are not legitimate direct consumers |
| No `/v1` path prefix | Pending versioning negotiation with Spring Boot side |
| Not using LangChain/LangGraph | No approved agent use case — avoids unnecessary abstraction |
| No RAG/vector database | Outside course MVP scope |
| Thinking mode disabled | Low latency, low cost (Chat/Advice scenarios don't need reasoning traces) |
| `max_retries=0` on SDK | All retries self-managed by this adapter, ensuring controllability and testability |

---

## Change Log

| Date | Version | Changes |
|------|------|------|
| 2026-06-27 | v0.1.0 | Initial version |
