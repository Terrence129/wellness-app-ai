# Wellness App AI — API 接口文档

> **版本**: v0.1.0 | **Author**: 2692341798 | **更新日期**: 2026-06-27  
> 本文档定义 SimpleWell AI 模块的全部 HTTP 接口契约，是 Android / Spring Boot / AI 三方的共享 API 规范。

---

## 目录

- [1. 概述](#1-概述)
- [2. 通用约定](#2-通用约定)
- [3. GET /health — 健康检查](#3-get-health--健康检查)
- [4. POST /ai/chat — Wellness 聊天](#4-post-aichat--wellness-聊天)
- [5. POST /ai/wellness-advice — 健康建议](#5-post-aiwellness-advice--健康建议)
- [6. 统一错误格式](#6-统一错误格式)
- [7. 错误码参考](#7-错误码参考)
- [8. 请求校验规则汇总](#8-请求校验规则汇总)

---

## 1. 概述

`wellness-app-ai` 是 SimpleWell 的私有 AI 服务组件。它接收 Spring Boot 后端的内部 REST 请求，调用 DeepSeek 大模型，返回安全的 Wellness 聊天回复和个性化健康建议。

**集成架构**：

```text
Android App → Spring Boot Backend → FastAPI (本服务) → DeepSeek
```

- Android **禁止**直接调用 FastAPI
- Spring Boot 负责认证、鉴权、持久化
- 本服务需部署在私有网络中，不暴露公网入口

**Base URL**：`http://127.0.0.1:8000`（开发环境）

**Swagger 文档**：启动服务后访问 `http://127.0.0.1:8000/docs`

---

## 2. 通用约定

### 请求头

| Header | 必填 | 说明 |
|--------|------|------|
| `Content-Type` | 是 | `application/json` |
| `X-Request-ID` | 否 | 客户端请求追踪 ID。需为有效 UUID 格式，否则服务端生成新 ID |

### 响应头

| Header | 说明 |
|--------|------|
| `X-Request-ID` | 本次请求的追踪 ID |
| `Content-Type` | `application/json` |

### 命名约定

- 请求/响应 JSON 字段使用 **camelCase**（如 `userId`、`requestId`）
- Pydantic 自动完成 `snake_case` ↔ `camelCase` 映射
- 路由前缀统一为 `/ai/`

---

## 3. GET /health — 健康检查

### 基本信息

| 项 | 值 |
|----|-----|
| 方法 | `GET` |
| 路径 | `/health` |
| 调用 DeepSeek | 否 |
| 需要 API Key | 否 |

### 响应 `200 OK`

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

### 说明

- 仅确认 FastAPI 进程正在运行
- 不暴露配置值、模型凭据、依赖版本或环境变量
- 无 API Key 时仍可正常返回 200

---

## 4. POST /ai/chat — Wellness 聊天

### 基本信息

| 项 | 值 |
|----|-----|
| 方法 | `POST` |
| 路径 | `/ai/chat` |
| 调用 DeepSeek | 是（除非命中安全策略） |
| 需要 API Key | 是（无 Key 返回 503） |

### 请求体

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

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userId` | integer | 是 | 用户 ID，正整数。**不发送给 DeepSeek**，仅供 Spring Boot 追踪 |
| `message` | string | 是 | 当前用户消息，1-2000 字符（去除前后空白后） |
| `history` | array | 否 | 对话历史，最多 12 条 |
| `history[].role` | string | 是 | 角色，仅限 `"user"` 或 `"assistant"` |
| `history[].content` | string | 是 | 历史消息内容，1-4000 字符 |

**聚合约束**：`message` + 所有 `history[].content` 总长度 ≤ 20,000 字符。

### 调用方禁止提供的字段

- `role`: `"system"` 或 `"tool"` — 校验拒绝
- 不得尝试注入 system prompt、function call 或 tool 消息

### 响应 `200 OK`

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `reply` | string | AI 生成的 Wellness 回复，至少 1 字符 |
| `requestId` | string | 与响应头 `X-Request-ID` 一致的追踪 ID |

### 安全行为

1. **首先执行确定性危机检测**：匹配 6 个关键词 (`kill myself`, `suicide`, `self-harm`, `cannot breathe`, `chest pain`, `overdose`)，不区分大小写
2. 命中后返回 **固定升级消息**，**不调用 DeepSeek**
3. DeepSeek 无状态：Spring Boot 负责对话持久化，每次请求提交有界历史

---

## 5. POST /ai/wellness-advice — 健康建议

### 基本信息

| 项 | 值 |
|----|-----|
| 方法 | `POST` |
| 路径 | `/ai/wellness-advice` |
| 调用 DeepSeek | 有数据时是，空日志时否 |
| 需要 API Key | 有数据时需要（无 Key 返回 503），空日志不需要 |

### 请求体 — 空日志

```json
{
  "userId": 1,
  "logs": []
}
```

### 请求体 — 有数据

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

### 字段说明

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `userId` | integer | 是 | 正整数 | 用户 ID，**不发送给 DeepSeek** |
| `logs` | array | 否 | 最多 31 条 | 每日健康日志 |
| `logs[].logDate` | string | 是 | ISO 8601 完整日期 (YYYY-MM-DD) | 日志日期 |
| `logs[].sleepHours` | number | 否 | 0 - 24 | 睡眠时长（小时） |
| `logs[].moodScore` | integer | 否 | 1 - 5 | 心情评分 |
| `logs[].waterCups` | integer | 否 | ≥ 0 | 饮水杯数 |
| `logs[].steps` | integer | 否 | ≥ 0 | 步数 |
| `logs[].exerciseMinutes` | integer | 否 | 0 - 1440 | 运动时长（分钟） |
| `logs[].note` | string | 否 | ≤ 1000 字符 | 用户备注 |

### 空日志行为（确定性路径）

当 `logs` 为空时，服务**不调用 DeepSeek**，直接返回稳定固定文本。

### 响应 `200 OK` — 空日志

```json
{
  "adviceText": "There is not enough wellness data yet. Record your sleep, mood, water intake, and exercise for a few days.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 响应 `200 OK` — 有数据

```json
{
  "adviceText": "Your sleep duration is stable. Consider taking a short afternoon break.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `adviceText` | string | AI 生成的个性化健康建议，至少 1 字符 |
| `requestId` | string | 与响应头 `X-Request-ID` 一致的追踪 ID |

### Provider 行为

- DeepSeek 被指示返回仅含 `adviceText` 字段的 JSON
- 服务拒绝空文本、截断、无效 JSON 或 Schema 不兼容的输出
- JSON 输出无效时允许额外一次重新生成（不增加传输重试次数）

---

## 6. 统一错误格式

所有校验错误、Provider 错误及未预期异常均使用如下统一信封：

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 消费方约定

- **以 `errorCode` 为分支依据**，不要解析 `message` 文本
- **保留 `requestId`** 供问题排查
- `success` 始终为 `false`

---

## 7. 错误码参考

| HTTP | errorCode | 含义 | 重试 |
|------|-----------|------|------|
| 422 | `VALIDATION_ERROR` | 本地 Pydantic 请求校验失败 | 否 |
| 429 | `AI_RATE_LIMITED` | DeepSeek 触发限流 | 是（最多 2 次） |
| 502 | `AI_INVALID_RESPONSE` | Provider 返回空/截断/无效 JSON/不符合 Schema | 否* |
| 502 | `AI_PROVIDER_REQUEST_REJECTED` | DeepSeek 拒绝请求 (400/422) | 否 |
| 503 | `AI_PROVIDER_NOT_CONFIGURED` | `DEEPSEEK_API_KEY` 缺失 | 否 |
| 503 | `AI_PROVIDER_AUTH_FAILED` | DeepSeek 鉴权失败 (401) | 否 |
| 503 | `AI_PROVIDER_QUOTA_EXHAUSTED` | DeepSeek 配额耗尽 (402) | 否 |
| 503 | `AI_PROVIDER_UNAVAILABLE` | DeepSeek 不可用 (500/503) 或连接失败 | 是（最多 2 次） |
| 504 | `AI_PROVIDER_TIMEOUT` | Provider 超时未完成 | 是（最多 2 次） |
| 500 | `INTERNAL_ERROR` | 未预期的应用错误，隐藏了实现细节 | 否 |

> \* Advice JSON 输出在无效时会额外重生成一次（不是传输重试）

### 重试策略

| 触发条件 | 重试 | 策略 |
|----------|------|------|
| 连接失败、超时 | 最多 2 次重试 | 指数退避 + 随机抖动 |
| 429 (Rate Limited) | 最多 2 次重试 | 尊重 `Retry-After` 头 |
| 500, 503 | 最多 2 次重试 | 指数退避 + 随机抖动 |
| 400, 401, 402, 422 | 不重试 | 直接返回映射错误 |

- 总超时预算由 `DEEPSEEK_TIMEOUT_SECONDS` 控制（默认 30s，范围 1-120s）
- `Retry-After` 延迟仅在总超时预算内被尊重
- 不复用 SDK 内置重试（SDK 的 `max_retries` 设为 0）

---

## 8. 请求校验规则汇总

### Chat

| 字段 | 规则 | 违反时返回 |
|------|------|-----------|
| `userId` | 正整数 (>0) | 422 `VALIDATION_ERROR` |
| `message` | 1-2000 字符（strip 后） | 422 `VALIDATION_ERROR` |
| `history` | 最多 12 条 | 422 `VALIDATION_ERROR` |
| `history[].role` | 仅 `user` / `assistant` | 422 `VALIDATION_ERROR` |
| `history[].content` | 1-4000 字符 | 422 `VALIDATION_ERROR` |
| 聚合文本长度 | ≤ 20000 字符 | 422 `VALIDATION_ERROR` |

### Advice

| 字段 | 规则 | 违反时返回 |
|------|------|-----------|
| `userId` | 正整数 (>0) | 422 `VALIDATION_ERROR` |
| `logs` | 最多 31 条 | 422 `VALIDATION_ERROR` |
| `logs[].logDate` | ISO 8601 完整日期 | 422 `VALIDATION_ERROR` |
| `logs[].sleepHours` | 0-24（可选） | 422 `VALIDATION_ERROR` |
| `logs[].moodScore` | 1-5 整数（可选） | 422 `VALIDATION_ERROR` |
| `logs[].waterCups` | ≥ 0 整数（可选） | 422 `VALIDATION_ERROR` |
| `logs[].steps` | ≥ 0 整数（可选） | 422 `VALIDATION_ERROR` |
| `logs[].exerciseMinutes` | 0-1440 整数（可选） | 422 `VALIDATION_ERROR` |
| `logs[].note` | ≤ 1000 字符（可选） | 422 `VALIDATION_ERROR` |

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-27 | v0.1.0 | 初始版本：3 个端点、10 种错误码、完整校验规则 |
