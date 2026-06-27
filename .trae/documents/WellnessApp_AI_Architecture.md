# Wellness App AI — 架构文档

> **版本**: v0.1.0 | **Author**: 2692341798 | **更新日期**: 2026-06-27  
> 本文档定义 SimpleWell AI 模块的分层架构、模块职责、数据流和关键设计决策。

---

## 目录

- [1. 系统定位与边界](#1-系统定位与边界)
- [2. 分层架构](#2-分层架构)
- [3. 模块职责](#3-模块职责)
- [4. 数据流](#4-数据流)
- [5. Provider 适配器设计](#5-provider-适配器设计)
- [6. 安全架构](#6-安全架构)
- [7. 错误处理架构](#7-错误处理架构)
- [8. 配置管理](#8-配置管理)
- [9. 设计决策记录](#9-设计决策记录)

---

## 1. 系统定位与边界

### 1.1 在 SimpleWell 中的位置

```text
┌──────────────┐     HTTPS + JWT     ┌──────────────────────┐     内部 REST      ┌─────────────────┐      HTTPS       ┌──────────┐
│  Android App  │ ──────────────────▶ │  Spring Boot Backend │ ─────────────────▶ │  FastAPI (本服务) │ ───────────────▶ │ DeepSeek │
└──────────────┘                     └──────────────────────┘                    └─────────────────┘                  └──────────┘
```

### 1.2 本模块负责

- FastAPI 应用程序与服务启动
- Wellness 聊天 prompting 与回复生成
- 个性化 Wellness 建议生成
- DeepSeek 集成、Provider 错误处理、Token 用量观测
- AI 安全规则与测试
- 后续 Agentic AI 工作流的扩展点

### 1.3 本模块不负责（由 Spring Boot 负责）

- Android UI 或直接 Android 集成
- 用户登录、JWT 创建与校验
- 用户鉴权与所有权检查
- MySQL 持久化、聊天历史持久化
- 定时推荐与调度

---

## 2. 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Routes (薄层)                        │
│  GET /health         POST /ai/chat    POST /ai/wellness-advice│
│  仅解析输入 → 调用一个 Service → 返回 Response Model          │
├─────────────────────────────────────────────────────────────┤
│                    Application Services                      │
│  ChatService          AdviceService        SafetyPolicy     │
│  编排安全策略 → 调用 Provider → 验证/Strip 结果               │
│  依赖 LLMProvider 接口，不依赖 DeepSeek SDK                   │
├─────────────────────────────────────────────────────────────┤
│                    LLMProvider 接口 (Protocol)                │
│  generate_chat()            generate_advice()                │
│  异步 Protocol，服务层仅依赖此接口                             │
├─────────────────────────────────────────────────────────────┤
│                    DeepSeekProvider (适配器)                   │
│  唯一知道 OpenAI SDK 的模块                                   │
│  负责：SDK 构造、重试、解析、错误映射、Token 提取、日志脱敏     │
├─────────────────────────────────────────────────────────────┤
│                    DeepSeek Chat Completions API              │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 依赖方向

```
Routes → Services → LLMProvider (Protocol) ← DeepSeekProvider
                    ↑                            ↑
              Prompts (versioned)          Core (Config/Logging/Exceptions)
```

- **路由不包含** prompt 逻辑、provider 逻辑、重试逻辑
- **服务不依赖** DeepSeek SDK，仅依赖 `LLMProvider` 协议
- **Provider 是唯一**了解 OpenAI SDK 和 DeepSeek API 细节的模块

---

## 3. 模块职责

### 3.1 `app/api/routes/` — HTTP 路由层

| 文件 | 职责 |
|------|------|
| `health.py` | `GET /health` — 进程存活检查 |
| `chat.py` | `POST /ai/chat` — 接收聊天请求，调用 ChatService |
| `advice.py` | `POST /ai/wellness-advice` — 接收建议请求，调用 AdviceService |

路由层规则：
- 解析 HTTP 输入（FastAPI 自动校验 Schema）
- 调用一个应用服务
- 返回声明的响应模型
- **不含** prompt、provider、重试、JSON 解析、安全逻辑

### 3.2 `app/services/` — 应用服务层

| 文件 | 职责 |
|------|------|
| `safety.py` | `SafetyPolicy` — 确定性危机短语匹配，返回固定升级消息 |
| `chat.py` | `ChatService` — 先执行安全策略，安全通过后调用 Provider，验证结果 |
| `advice.py` | `AdviceService` — 空日志走确定性路径，有数据调 Provider，严格验证 JSON |

### 3.3 `app/providers/` — Provider 适配层

| 文件 | 职责 |
|------|------|
| `base.py` | `LLMProvider` 异步 Protocol — 定义 `generate_chat` / `generate_advice` 最小契约 |
| `deepseek.py` | `DeepSeekProvider` — OpenAI 兼容适配器，包含重试、错误映射、Token 观测 |

### 3.4 `app/prompts/` — 提示词层

| 文件 | 职责 |
|------|------|
| `chat.py` | `CHAT_SYSTEM_PROMPT` (v1) — Wellness Chat 系统提示词 |
| `advice.py` | `ADVICE_SYSTEM_PROMPT` (v1) — Wellness Advice 系统提示词 + JSON 输出指令 |

提示词变更必须同步更新测试。

### 3.5 `app/schemas/` — Schema 层

| 文件 | 职责 |
|------|------|
| `common.py` | `ErrorResponse` — 统一错误信封 |
| `chat.py` | `ChatRequest`, `ChatResponse`, `ChatProviderResult` 及内部模型 |
| `advice.py` | `AdviceRequest`, `AdviceResponse`, `AdvicePayload`, `AdviceProviderResult` |

### 3.6 `app/core/` — 基础设施层

| 文件 | 职责 |
|------|------|
| `config.py` | `Settings` — Pydantic Settings，11 个环境变量，含边界验证 |
| `exceptions.py` | `AppError` + `ErrorCode` — 10 种稳定错误码 + 命名构造器 |
| `logging.py` | 隐私安全 JSON 日志 + ContextVar 管理 Request ID |

---

## 4. 数据流

### 4.1 Chat 请求流程

```text
Spring Boot POST /ai/chat
  ↓
Chat Route → 自动校验 ChatRequest Schema (422 失败则直接返回)
  ↓
ChatService.generate()
  ├── SafetyPolicy.evaluate(message + history)
  │   └── 命中危机词汇？ → 返回固定升级消息 (200 OK, 不调 Provider)
  └── 安全通过
      ├── 构建 Provider 消息 (System Prompt + History + User Message)
      ├── LLMProvider.generate_chat()
      │   └── DeepSeekProvider → DeepSeek API (含重试/错误映射)
      ├── Strip & 验证回复内容
      └── 返回 ChatResponse { reply, requestId }
```

### 4.2 Advice 请求流程

```text
Spring Boot POST /ai/wellness-advice
  ↓
Advice Route → 自动校验 AdviceRequest Schema
  ↓
AdviceService.generate()
  ├── logs 为空？
  │   └── 是 → 返回稳定文本 (200 OK, 不调 Provider)
  └── 否
      ├── 序列化 wellness logs 为 JSON
      ├── 构建 Provider 消息 (System Prompt + Logs JSON)
      ├── LLMProvider.generate_advice()
      │   └── DeepSeekProvider → DeepSeek API (JSON mode, 含重试/错误映射)
      ├── 验证 JSON → AdvicePayload (adviceText)
      │   └── 无效？→ 额外一次重新生成 (最多 1 次)
      ├── Strip & 验证 adviceText
      └── 返回 AdviceResponse { adviceText, requestId }
```

---

## 5. Provider 适配器设计

### 5.1 DeepSeekProvider 关键设计点

| 能力 | 实现 |
|------|------|
| SDK 构造 | `AsyncOpenAI(api_key, base_url, timeout, max_retries=0)` — 禁用 SDK 内置重试 |
| Thinking 模式 | `extra_body={"thinking": {"type": "disabled"}}` — 降低延迟和成本 |
| Model | `deepseek-v4-flash` (chat/advice), `deepseek-v4-pro` (agent 预留) |
| 重试 | 自行实现异步 attempt 循环，指数退避 + jitter |
| 错误映射 | 9 种 HTTP 状态/异常 → 稳定 `AppError` 构造器 |
| JSON 输出 | Advice 使用 `response_format={"type": "json_object"}`，Pydantic 验证 |
| 截断检测 | 检查 `finish_reason == "length"` → `AI_INVALID_RESPONSE` |
| 可测试性 | client/sleep/random/clock 全部可注入 |

### 5.2 重试策略

```
retryable: connection error, timeout, 429, 500, 503
non-retryable: 400, 401, 402, 422

delay = min(base * 2^attempt + random(), remaining_budget)
Retry-After honored only within timeout budget
```

---

## 6. 安全架构

### 6.1 多层安全防护

```text
Layer 1 (Pre-Provider): SafetyPolicy — 确定性关键词匹配
  ↓ 未命中
Layer 2 (Prompt): System Prompt 约束 — 通用 Wellness 范围
  ↓
Layer 3 (Post-Provider): 输出验证 — Strip, 非空检查, Schema 验证
```

### 6.2 隐私保护

| 保护措施 | 实现位置 |
|----------|---------|
| `userId` 不发送给 DeepSeek | Services 构建 Provider 请求时不包含 |
| 日志白名单字段 | `app/core/logging.py` — 仅允许 `event/request_id/method/path/status/latency_ms/model/retry_count/tokens` |
| 不记录生文本 | Provider 和 Service 均不 log 消息/提示词/回复 |
| `.env` 不提交 | `.gitignore` 排除 |

---

## 7. 错误处理架构

### 7.1 错误流转

```text
Pydantic ValidationError → RequestValidationError handler → ErrorResponse (422)
AppError (任何层级抛出) → AppError handler → ErrorResponse (status_code)
Exception (未预期) → unexpected handler → ErrorResponse (500, 隐藏细节)
```

### 7.2 错误码映射表

| 来源 | → | ErrorCode | HTTP |
|------|---|-----------|------|
| Pydantic 校验失败 | → | `VALIDATION_ERROR` | 422 |
| DeepSeek 429 | → | `AI_RATE_LIMITED` | 429 |
| 空/截断/无效 JSON 输出 | → | `AI_INVALID_RESPONSE` | 502 |
| DeepSeek 400/422 拒绝 | → | `AI_PROVIDER_REQUEST_REJECTED` | 502 |
| API Key 缺失 | → | `AI_PROVIDER_NOT_CONFIGURED` | 503 |
| DeepSeek 401 | → | `AI_PROVIDER_AUTH_FAILED` | 503 |
| DeepSeek 402 | → | `AI_PROVIDER_QUOTA_EXHAUSTED` | 503 |
| DeepSeek 500/503/连接失败 | → | `AI_PROVIDER_UNAVAILABLE` | 503 |
| 超时 | → | `AI_PROVIDER_TIMEOUT` | 504 |
| 未预期异常 | → | `INTERNAL_ERROR` | 500 |

---

## 8. 配置管理

- **单一配置源**：Pydantic `Settings` + `.env` 文件
- **启动无需 Key**：`DEEPSEEK_API_KEY` 可为空，`/health` 始终可用
- **边界验证**：`timeout` (1-120s)、`max_retries` (0-5) 启动时即校验
- **无 `os.getenv` 散落**：所有配置通过注入的 `Settings` 实例访问
- **模型名可配置**：支持未来模型迁移而无需改动业务代码

---

## 9. 设计决策记录

| 决策 | 理由 |
|------|------|
| 不使用 `deepseek-chat` / `deepseek-reasoner` | DeepSeek 已于 2026-07-24 宣告退役 |
| CORS 未启用 | 浏览器/Android 不是合法直连消费者 |
| 无 `/v1` 路径前缀 | 等待与 Spring Boot 侧协商版控方案 |
| 不使用 LangChain/LangGraph | 未批准 Agent 用例，避免过度抽象 |
| 无 RAG/向量数据库 | 课程 MVP 范围外 |
| Thinking 模式禁用 | 低延迟、低成本（Chat/Advice 场景不需要思考过程） |
| `max_retries=0` on SDK | 所有重试由本适配器自行管理，确保可控和可测 |

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-27 | v0.1.0 | 初始版本 |
