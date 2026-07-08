<!--
Author: Huang Qijun
Email: 2692341798@qq.com
-->

# Wellness App AI — Product Requirements Document (PRD)

> **Version**: v0.1.0 | **Author**: 2692341798 | **Last Updated**: 2026-06-27  
> This document defines the product requirements scope, core features, and acceptance criteria for the SimpleWell AI module.

---

## Table of Contents

- [1. Product Overview](#1-product-overview)
- [2. Requirements Source and Priority](#2-requirements-source-and-priority)
- [3. Core Features](#3-core-features)
- [4. Non-Functional Requirements](#4-non-functional-requirements)
- [5. Safety and Compliance Requirements](#5-safety-and-compliance-requirements)
- [6. Out-of-Scope Features (Deferred)](#6-out-of-scope-features-deferred)
- [7. Acceptance Criteria](#7-acceptance-criteria)

---

## 1. Product Overview

### 1.1 Product Name

**SimpleWell AI Module** (`wellness-app-ai`)

### 1.2 Product Positioning

SimpleWell is a mobile health management application. The AI module is its private backend microservice component responsible for calling the DeepSeek large language model to provide end users with:

- **General wellness chat**: Answer everyday health questions about sleep, diet, exercise, mental health, etc.
- **Personalized wellness advice**: Generate targeted suggestions based on the user's recorded wellness log data (sleep, mood, water intake, steps, exercise)

### 1.3 Target Users

- **Indirect users**: End users of the SimpleWell Android app (relayed through the Spring Boot backend)
- **Direct caller**: Spring Boot backend

### 1.4 Technical Architecture Positioning

```text
Android App → Spring Boot → FastAPI AI Service → DeepSeek
```

The AI module is the third layer of the four-tier architecture, transparent to end users.

---

## 2. Requirements Source and Priority

Requirement resolution priority (highest to lowest):

1. `Mobile Application Development CA.pdf` course requirements
2. `wellness-app/Android Wellness App — Product & API Document.md` product document
3. Shared API contract agreed upon by the Android / Spring Boot / AI teams
4. Existing source code and examples

---

## 3. Core Features

### 3.1 Health Check

| Attribute | Value |
|------|-----|
| Priority | P0 |
| Endpoint | `GET /health` |
| Depends on DeepSeek | No |
| Requires API Key | No |

**Description**: Confirm the FastAPI process is running. Response is simple, stable, and does not expose configuration information.

**Acceptance Criteria**:
- Returns `200 OK` normally even without an API key
- Response is `{"status":"ok","service":"wellness-app-ai"}`
- Every response includes the `X-Request-ID` request tracing header

### 3.2 Wellness Chat

| Attribute | Value |
|------|-----|
| Priority | P0 |
| Endpoint | `POST /ai/chat` |
| Depends on DeepSeek | Yes |
| Requires API Key | Yes |

**Description**: Spring Boot forwards user questions and bounded conversation history; the AI service returns a wellness-related chat reply.

**Core Requirements**:
- Supports multi-turn conversation history (max 12 entries)
- Response scope limited to general wellness (sleep, diet, exercise, stress management, etc.)
- Returns a fixed escalation message on crisis language without calling DeepSeek
- `userId` is not sent to DeepSeek
- All input undergoes strict schema validation

**Acceptance Criteria**:
- Normal conversation returns `200 OK` with `reply` and `requestId`
- Crisis language match returns fixed escalation message without calling the provider
- 402/401/timeout etc. return corresponding error codes
- Without an API key, returns `503 AI_PROVIDER_NOT_CONFIGURED`
- Aggregate text > 20000 characters returns `422 VALIDATION_ERROR`

### 3.3 Wellness Advice

| Attribute | Value |
|------|-----|
| Priority | P0 |
| Endpoint | `POST /ai/wellness-advice` |
| Depends on DeepSeek | Yes when data is present, No when logs are empty |
| Requires API Key | Required when data is present |

**Description**: Generates personalized advice based on the user's daily wellness logs.

**Core Requirements**:
- Empty logs follow a deterministic path, returning a fixed tip text (no DeepSeek call, no API key needed)
- With data, calls DeepSeek requiring strict JSON output (only `adviceText`)
- Invalid JSON, truncation, or empty content is rejected and mapped to `AI_INVALID_RESPONSE`
- Invalid JSON allows one additional regeneration attempt

**Acceptance Criteria**:
- Empty logs return `200 OK` with fixed tip text, no provider call
- Normal request with data returns `200 OK` with `adviceText` and `requestId`
- Invalid provider response returns `502 AI_INVALID_RESPONSE`
- More than 31 log entries returns `422 VALIDATION_ERROR`

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Target |
|------|------|
| Chat average latency | < 5s (P95) |
| Advice average latency | < 8s (P95) |
| Health response time | < 50ms |
| Concurrency support | Single-process uvicorn, Spring Boot controls concurrency |

### 4.2 Reliability

| Metric | Target |
|------|------|
| Retry strategy | Connection failure/timeout/429/500/503 → max 2 retries |
| Graceful degradation | Without API key, only AI endpoints are unavailable; `/health` is always available |
| Error handling | All exceptions mapped to 10 stable error codes |

### 4.3 Observability

| Metric | Requirement |
|------|------|
| Request ID | Each request generates/echoes a UUID, propagated to response headers and body |
| Logging | JSON format, allowlisted fields (event/request_id/method/path/status/latency_ms/model/retry_count/tokens) |
| Token usage | Record prompt_tokens and completion_tokens for each provider call |

### 4.4 Testability

| Requirement | Implementation |
|------|------|
| Offline tests | All default tests do not initiate network requests (FakeLLMProvider + socket blocking) |
| Live tests | Optional keyed smoke tests (`@pytest.mark.live`) |
| Dependency injection | Services/Provider are injectable, supporting test doubles |

### 4.5 Deployment

- Requires Python 3.11+
- Private network reachable only by Spring Boot
- Must not be exposed to the public internet
- `.env` excluded from version control

---

## 5. Safety and Compliance Requirements

### 5.1 Wellness Safety

| Requirement | Implementation |
|------|------|
| General wellness scope | System Prompt + SafetyPolicy |
| No diagnosis, no treatment | System Prompt defines clear boundaries |
| Crisis escalation | 6 keywords → fixed escalation message, no LLM call |
| User input is untrusted | User text cannot override the System Prompt |

### 5.2 Data Privacy

| Requirement | Implementation |
|------|------|
| No user identity sent to DeepSeek | email/username/JWT/userId all excluded |
| No raw content logged | Log allowlist, only structured metadata permitted |
| No key leakage | `.env.example` contains no real key, `.gitignore` excludes `.env` |

---

## 6. Out-of-Scope Features (Deferred)

| Feature | Reason for Deferral |
|------|---------|
| SSE streaming responses | First version prioritizes stable, controllable non-streaming responses |
| RAG + knowledge base | Outside course MVP scope |
| Function Calling / Agent tools | No approved use case |
| Scheduled recommendations | Handled by Spring Boot scheduling |
| Recommendation and conversation persistence | Handled by Spring Boot's MySQL |
| Service-to-service authentication | Not needed for current private network deployment; to be designed uniformly later |
| CORS support | Browsers/Android are not legitimate direct consumers |
| API versioning (`/v1`) | Pending negotiation with Spring Boot side |

---

## 7. Acceptance Criteria

### 7.1 Functional Acceptance

- [x] `GET /health` returns `200 OK` without key
- [x] `POST /ai/chat` returns normal reply with key
- [x] `POST /ai/chat` returns `503 AI_PROVIDER_NOT_CONFIGURED` without key
- [x] `POST /ai/chat` crisis language triggers fixed escalation
- [x] `POST /ai/wellness-advice` empty logs returns `200 OK` without key
- [x] `POST /ai/wellness-advice` with data and key returns advice
- [x] `POST /ai/wellness-advice` with data without key returns `503`
- [x] All validation failures return `422 VALIDATION_ERROR`
- [x] All provider exceptions mapped to corresponding error codes

### 7.2 Quality Acceptance

- [x] ruff check: zero issues
- [x] mypy strict: zero issues
- [x] pytest: 215 passed (offline)
- [x] README documentation completeness tests passing
- [x] AGENTS.md repository rules tests passing

### 7.3 Architecture Acceptance

- [x] No RAG / vector database dependencies
- [x] No agent framework
- [x] No persistence code
- [x] No scheduler
- [x] No CORS
- [x] No `deepseek-chat` / `deepseek-reasoner` aliases
- [x] No JWT handling
- [x] Largest single file 344 lines (< 500 line warning threshold)

---

## Change Log

| Date | Version | Changes |
|------|------|------|
| 2026-06-27 | v0.1.0 | Initial version, based on architecture design spec and 12 task implementation results |
