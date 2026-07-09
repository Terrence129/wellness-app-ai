<!--
Author: Huang Qijun
Email: 2692341798@qq.com
-->

# Wellness App AI — API Documentation

> **Version**: v0.1.0 | **Author**: 2692341798 | **Last Updated**: 2026-06-27  
> This document defines the complete HTTP interface contract for the SimpleWell AI module. It is the shared API specification agreed upon by the Android, Spring Boot, and AI teams.

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. General Conventions](#2-general-conventions)
- [3. GET /health — Health Check](#3-get-health--health-check)
- [4. POST /ai/chat — Wellness Chat](#4-post-aichat--wellness-chat)
- [5. POST /ai/wellness-advice — Wellness Advice](#5-post-aiwellness-advice--wellness-advice)
- [6. Unified Error Format](#6-unified-error-format)
- [7. Error Code Reference](#7-error-code-reference)
- [8. Request Validation Rules Summary](#8-request-validation-rules-summary)

---

## 1. Overview

`wellness-app-ai` is the private AI service component of SimpleWell. It receives internal REST requests from the Spring Boot backend, calls the DeepSeek large language model, and returns safe wellness chat replies and personalized wellness advice.

**Integration architecture**:

```text
Android App → Spring Boot Backend → FastAPI (This Service) → DeepSeek
```

- Android is **prohibited** from calling FastAPI directly
- Spring Boot handles authentication, authorization, and persistence
- This service must be deployed on a private network with no public internet exposure

**Base URL**: `http://127.0.0.1:8000` (development environment)

**Swagger Docs**: Start the service and visit `http://127.0.0.1:8000/docs`

---

## 2. General Conventions

### Request Headers

| Header | Required | Description |
|--------|------|------|
| `Content-Type` | Yes | `application/json` |
| `X-Request-ID` | No | Client request tracing ID. Must be a valid UUID format, otherwise the server generates a new ID |

### Response Headers

| Header | Description |
|--------|------|
| `X-Request-ID` | Tracing ID for this request |
| `Content-Type` | `application/json` |

### Naming Conventions

- Request/response JSON fields use **camelCase** (e.g. `userId`, `requestId`)
- Pydantic automatically handles `snake_case` ↔ `camelCase` mapping
- Route prefix is uniformly `/ai/`

---

## 3. GET /health — Health Check

### Basic Information

| Item | Value |
|----|-----|
| Method | `GET` |
| Path | `/health` |
| Calls DeepSeek | No |
| Requires API Key | No |

### Response `200 OK`

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

### Notes

- Only confirms that the FastAPI process is running
- Does not expose configuration values, model credentials, dependency versions, or environment variables
- Returns 200 normally even without an API key

---

## 4. POST /ai/chat — Wellness Chat

### Basic Information

| Item | Value |
|----|-----|
| Method | `POST` |
| Path | `/ai/chat` |
| Calls DeepSeek | Yes (unless safety policy is triggered) |
| Requires API Key | Yes (returns 503 without a key) |

### Request Body

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

### Field Descriptions

| Field | Type | Required | Description |
|------|------|------|------|
| `userId` | integer | Yes | User ID, positive integer. **Not sent to DeepSeek** — for Spring Boot tracing only |
| `message` | string | Yes | Current user message, 1-2000 characters (after stripping whitespace) |
| `history` | array | No | Conversation history, max 12 entries |
| `history[].role` | string | Yes | Role, limited to `"user"` or `"assistant"` |
| `history[].content` | string | Yes | History message content, 1-4000 characters |

**Aggregate constraint**: `message` + all `history[].content` total length ≤ 20,000 characters.

### Fields Prohibited for Callers

- `role`: `"system"` or `"tool"` — rejected by validation
- Do not attempt to inject system prompts, function calls, or tool messages

### Response `200 OK`

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Description |
|------|------|------|
| `reply` | string | AI-generated wellness reply, at least 1 character |
| `requestId` | string | Tracing ID, consistent with the `X-Request-ID` response header |

### Safety Behavior

1. **Deterministic crisis detection runs first**: Matches 6 keywords (`kill myself`, `suicide`, `self-harm`, `cannot breathe`, `chest pain`, `overdose`), case-insensitive
2. On match, returns a **fixed escalation message** and **does not call DeepSeek**
3. DeepSeek is stateless: Spring Boot handles conversation persistence and submits a bounded history with each request

---

## 5. POST /ai/wellness-advice — Wellness Advice

### Basic Information

| Item | Value |
|----|-----|
| Method | `POST` |
| Path | `/ai/wellness-advice` |
| Calls DeepSeek | Yes when data is present, No when logs are empty |
| Requires API Key | Required when data is present (returns 503 without a key), not required for empty logs |

### Request Body — Empty Logs

```json
{
  "userId": 1,
  "logs": []
}
```

### Request Body — With Data

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

### Field Descriptions

| Field | Type | Required | Constraints | Description |
|------|------|------|------|------|
| `userId` | integer | Yes | Positive integer | User ID, **not sent to DeepSeek** |
| `logs` | array | No | Max 31 entries | Daily wellness logs |
| `logs[].logDate` | string | Yes | ISO 8601 full date (YYYY-MM-DD) | Log date |
| `logs[].sleepHours` | number | No | 0 - 24 | Sleep duration (hours) |
| `logs[].moodScore` | integer | No | 1 - 5 | Mood rating |
| `logs[].waterCups` | integer | No | ≥ 0 | Cups of water |
| `logs[].steps` | integer | No | ≥ 0 | Step count |
| `logs[].exerciseMinutes` | integer | No | 0 - 1440 | Exercise duration (minutes) |
| `logs[].note` | string | No | ≤ 1000 characters | User note |

### Empty Logs Behavior (Deterministic Path)

When `logs` is empty, the service **does not call DeepSeek** and directly returns a stable fixed text.

### Response `200 OK` — Empty Logs

```json
{
  "adviceText": "There is not enough wellness data yet. Record your sleep, mood, water intake, and exercise for a few days.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response `200 OK` — With Data

```json
{
  "adviceText": "Your sleep duration is stable. Consider taking a short afternoon break.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Description |
|------|------|------|
| `adviceText` | string | AI-generated personalized wellness advice, at least 1 character |
| `requestId` | string | Tracing ID, consistent with the `X-Request-ID` response header |

### Provider Behavior

- DeepSeek is instructed to return JSON containing only the `adviceText` field
- The service rejects empty text, truncation, invalid JSON, or schema-incompatible output
- Invalid JSON output allows one additional regeneration attempt (does not increase transport retry count)

---

## 6. Unified Error Format

All validation errors, provider errors, and unexpected exceptions use the following unified envelope:

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Consumer Contract

- **Branch on `errorCode`** — do not parse the `message` text
- **Preserve `requestId`** for troubleshooting
- `success` is always `false`

---

## 7. Error Code Reference

| HTTP | errorCode | Meaning | Retry |
|------|-----------|------|------|
| 422 | `VALIDATION_ERROR` | Local Pydantic request validation failure | No |
| 429 | `AI_RATE_LIMITED` | DeepSeek rate limit triggered | Yes (max 2) |
| 502 | `AI_INVALID_RESPONSE` | Provider returned empty/truncated/invalid JSON / schema mismatch | No* |
| 502 | `AI_PROVIDER_REQUEST_REJECTED` | DeepSeek rejected the request (400/422) | No |
| 503 | `AI_PROVIDER_NOT_CONFIGURED` | `DEEPSEEK_API_KEY` is missing | No |
| 503 | `AI_PROVIDER_AUTH_FAILED` | DeepSeek authentication failed (401) | No |
| 503 | `AI_PROVIDER_QUOTA_EXHAUSTED` | DeepSeek quota exhausted (402) | No |
| 503 | `AI_PROVIDER_UNAVAILABLE` | DeepSeek unavailable (500/503) or connection failure | Yes (max 2) |
| 504 | `AI_PROVIDER_TIMEOUT` | Provider timed out | Yes (max 2) |
| 500 | `INTERNAL_ERROR` | Unexpected application error — implementation details hidden | No |

> \* Advice JSON output regenrates once on invalid output (not a transport retry)

### Retry Strategy

| Trigger | Retry | Strategy |
|----------|------|------|
| Connection failure, timeout | Max 2 retries | Exponential backoff + random jitter |
| 429 (Rate Limited) | Max 2 retries | Honor `Retry-After` header |
| 500, 503 | Max 2 retries | Exponential backoff + random jitter |
| 400, 401, 402, 422 | Do not retry | Return mapped error directly |

- Overall timeout budget controlled by `DEEPSEEK_TIMEOUT_SECONDS` (default 30s, range 1-120s)
- `Retry-After` delay is honored only within the overall timeout budget
- SDK built-in retries are disabled (SDK `max_retries` is set to 0)

---

## 8. Request Validation Rules Summary

### Chat

| Field | Rule | Violation Response |
|------|------|-----------|
| `userId` | Positive integer (>0) | 422 `VALIDATION_ERROR` |
| `message` | 1-2000 characters (after strip) | 422 `VALIDATION_ERROR` |
| `history` | Max 12 entries | 422 `VALIDATION_ERROR` |
| `history[].role` | `user` / `assistant` only | 422 `VALIDATION_ERROR` |
| `history[].content` | 1-4000 characters | 422 `VALIDATION_ERROR` |
| Aggregate text length | ≤ 20000 characters | 422 `VALIDATION_ERROR` |

### Advice

| Field | Rule | Violation Response |
|------|------|-----------|
| `userId` | Positive integer (>0) | 422 `VALIDATION_ERROR` |
| `logs` | Max 31 entries | 422 `VALIDATION_ERROR` |
| `logs[].logDate` | ISO 8601 full date | 422 `VALIDATION_ERROR` |
| `logs[].sleepHours` | 0-24 (optional) | 422 `VALIDATION_ERROR` |
| `logs[].moodScore` | 1-5 integer (optional) | 422 `VALIDATION_ERROR` |
| `logs[].waterCups` | ≥ 0 integer (optional) | 422 `VALIDATION_ERROR` |
| `logs[].steps` | ≥ 0 integer (optional) | 422 `VALIDATION_ERROR` |
| `logs[].exerciseMinutes` | 0-1440 integer (optional) | 422 `VALIDATION_ERROR` |
| `logs[].note` | ≤ 1000 characters (optional) | 422 `VALIDATION_ERROR` |

---

## Change Log

| Date | Version | Changes |
|------|------|------|
| 2026-06-27 | v0.1.0 | Initial version: 3 endpoints, 10 error codes, complete validation rules |
