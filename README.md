# wellness-app-ai

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/fastapi-0.115%2B-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/deepseek-v4--flash-4f46e5" alt="DeepSeek v4 Flash">
  <img src="https://img.shields.io/badge/tests-215%20passed-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-offline%20deterministic-success" alt="Offline Tests">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

> **SimpleWell 小组作业 — AI 模块** | Author: 2692341798  
> `wellness-app-ai` 是 SimpleWell 健康管理应用的私有 FastAPI AI 微服务。它提供健康检查、通用 Wellness 聊天、个性化健康建议，通过 DeepSeek 大模型生成内容。仅由 Spring Boot 后端内部调用，不直接面向前端或 Android。

---

## 目录

- [集成边界](#集成边界)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [运行服务](#运行服务)
- [API 接口](#api-接口)
  - [GET /health — 健康检查](#get-health--健康检查)
  - [POST /ai/chat — Wellness 聊天](#post-aichat--wellness-聊天)
  - [POST /ai/wellness-advice — 健康建议](#post-aiwellness-advice--健康建议)
- [统一错误格式](#统一错误格式)
- [错误码参考](#错误码参考)
- [安全设计](#安全设计)
- [质量检查](#质量检查)
- [工程文档](#工程文档)

---

## 集成边界

```text
┌──────────────┐     HTTPS + JWT     ┌──────────────────────┐     内部 REST      ┌─────────────────┐      HTTPS       ┌──────────┐
│  Android App  │ ──────────────────▶ │  Spring Boot Backend │ ─────────────────▶ │  FastAPI (本服务) │ ───────────────▶ │ DeepSeek │
└──────────────┘                     └──────────────────────┘                    └─────────────────┘                  └──────────┘
  不直接调用本服务                          拥有登录/JWT/鉴权/持久化                          AI 生成服务                         大模型 API
```

- **Android 禁止直接调用 FastAPI**。必须通过 Spring Boot 中转。
- Spring Boot 负责：用户登录、JWT 创建与校验、用户鉴权、所有权检查、MySQL 持久化、聊天历史管理、定时推荐调度。
- 本服务需部署在仅 Spring Boot 可达的私有网络中，**不得通过公网入口暴露**。
- 因此以下所有 curl 示例均不含 JWT 或自创的服务认证头 — 它们是私有的后端间调用。

> 完整架构见 [`.trae/documents/WellnessApp_AI_Architecture.md`](.trae/documents/WellnessApp_AI_Architecture.md)

---

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | ≥ 3.11 |
| Web 框架 | FastAPI | ≥ 0.115 |
| 数据验证 | Pydantic v2 | (内置于 FastAPI) |
| LLM SDK | OpenAI Python SDK (适配 DeepSeek) | ≥ 1.68 |
| 配置管理 | pydantic-settings | ≥ 2.8 |
| 重试策略 | tenacity | ≥ 9 |
| ASGI 服务器 | uvicorn | ≥ 0.34 |
| 测试框架 | pytest + pytest-asyncio + HTTPX | — |
| 代码质量 | ruff + mypy (strict) | — |
| 包管理 | uv + hatchling | — |

---

## 项目结构

```
wellness-app-ai/
├── app/                        # 应用源码
│   ├── main.py                 # FastAPI 工厂、中间件、异常处理器
│   ├── api/
│   │   ├── dependencies.py     # 依赖注入（Settings/Provider/Service）
│   │   └── routes/
│   │       ├── health.py       # GET /health
│   │       ├── chat.py         # POST /ai/chat
│   │       └── advice.py       # POST /ai/wellness-advice
│   ├── core/                   # 基础设施
│   │   ├── config.py           # 环境配置（Pydantic Settings）
│   │   ├── exceptions.py       # 稳定错误码 + AppError（10 种）
│   │   └── logging.py          # 隐私安全 JSON 日志 + Request ID
│   ├── prompts/                # 版本化 System Prompt
│   │   ├── chat.py             # Wellness Chat 提示词 v1
│   │   └── advice.py           # Wellness Advice 提示词 v1
│   ├── providers/              # LLM 适配层
│   │   ├── base.py             # LLMProvider 异步协议
│   │   └── deepseek.py         # DeepSeek 适配器（重试/错误映射/TOKEN 观测）
│   ├── schemas/                # 请求/响应 Schema
│   │   ├── common.py           # ErrorResponse 统一错误信封
│   │   ├── chat.py             # ChatRequest/ChatResponse
│   │   └── advice.py           # AdviceRequest/AdviceResponse/WellnessLog
│   └── services/               # 应用服务层
│       ├── safety.py           # SafetyPolicy（确定性危机检测）
│       ├── chat.py             # ChatService（编排安全+Provider）
│       └── advice.py           # AdviceService（含空数据确定性路径）
├── tests/                      # 测试（镜像生产结构）
├── docs/superpowers/           # 设计文档与实现计划
└── .trae/documents/            # 工程文档
```

---

## 快速开始

**前置要求**：Python 3.11+，推荐使用 [`uv`](https://docs.astral.sh/uv/)。

```bash
# 1. 克隆仓库
git clone https://github.com/Terrence129/wellness-app-ai.git
cd wellness-app-ai

# 2. 安装依赖
uv sync --extra dev

# 3. 配置环境（复制模板后编辑 .env 填入真实 DEEPSEEK_API_KEY）
test -e .env || cp .env.example .env
```

> **不使用 uv？** 用传统 pip 方式：
> ```bash
> python -m venv .venv
> source .venv/bin/activate
> pip install -e '.[dev]'
> test -e .env || cp .env.example .env
> ```

**环境变量说明**（`.env.example` 完整文档）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_NAME` | `wellness-app-ai` | 应用名称 |
| `APP_ENV` | `development` | 运行环境 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DEEPSEEK_API_KEY` | (空) | DeepSeek API 密钥。空值 = 未配置 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-v4-flash` | Chat 模型名 |
| `DEEPSEEK_ADVICE_MODEL` | `deepseek-v4-flash` | Advice 模型名 |
| `DEEPSEEK_AGENT_MODEL` | `deepseek-v4-pro` | Agent 模型名（预留） |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | 请求超时（1-120） |
| `DEEPSEEK_MAX_RETRIES` | `2` | 最大重试次数（0-5） |

> **安全提醒**：真实 `DEEPSEEK_API_KEY` 仅放入未追踪的 `.env` 或进程环境变量中。**绝不提交密钥。**

---

## 运行服务

```bash
uv run uvicorn app.main:app --reload
```

服务默认地址：`http://127.0.0.1:8000`

### 无 API Key 的行为

允许不配置 `DEEPSEEK_API_KEY` 启动：

| 场景 | 行为 |
|------|------|
| `GET /health` | **200 OK** — 无需 DeepSeek |
| `POST /ai/chat` | **503** — `AI_PROVIDER_NOT_CONFIGURED` |
| `POST /ai/wellness-advice` (有数据) | **503** — `AI_PROVIDER_NOT_CONFIGURED` |
| `POST /ai/wellness-advice` (空日志) | **200 OK** — 返回稳定提示文本，不调用 DeepSeek |

---

## API 接口

> 完整的接口规范见 [`.trae/documents/WellnessApp_AI_API.md`](.trae/documents/WellnessApp_AI_API.md)  
> 启动服务后访问 `http://127.0.0.1:8000/docs` 可看到交互式 Swagger 文档。

### GET /health — 健康检查

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "service": "wellness-app-ai"
}
```

### POST /ai/chat — Wellness 聊天

Spring Boot 转发用户问题和有界对话历史。DeepSeek 无状态，Spring Boot 负责对话持久化并每次请求提交有界历史。

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

**请求校验**：

| 字段 | 约束 |
|------|------|
| `userId` | 正整数 |
| `message` | 1-2000 字符（去除前后空白后） |
| `history` | 最多 12 条 |
| `history[].role` | 仅 `user` / `assistant` |
| `history[].content` | 每条 1-4000 字符 |
| 总长度 | `message` + 所有 `history[].content` ≤ 20000 字符 |

```json
{
  "reply": "Try moving your bedtime earlier in small, consistent steps.",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

### POST /ai/wellness-advice — 健康建议

基于用户的健康日志数据生成个性化建议。

**空日志场景（确定性路径，不调用 DeepSeek）**：

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

**有数据场景**：

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

**请求校验**：

| 字段 | 约束 |
|------|------|
| `userId` | 正整数 |
| `logs` | 最多 31 条 |
| `logDate` | ISO 8601 完整日期 (YYYY-MM-DD) |
| `sleepHours` | 0 - 24（可选） |
| `moodScore` | 1 - 5（可选） |
| `waterCups` | ≥ 0（可选） |
| `steps` | ≥ 0（可选） |
| `exerciseMinutes` | 0 - 1440（可选） |
| `note` | 最多 1000 字符（可选） |

---

## 统一错误格式

所有校验错误、Provider 错误和未预期异常均使用统一信封：

```json
{
  "success": false,
  "message": "The AI provider is temporarily unavailable.",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**消费方约定**：以 `errorCode` 为分支依据，`requestId` 供排查保留，**不解析 `message` 文本**。

---

## 错误码参考

| HTTP | errorCode | 含义 |
|------|-----------|------|
| 422 | `VALIDATION_ERROR` | 本地 Pydantic 请求校验失败 |
| 429 | `AI_RATE_LIMITED` | DeepSeek 触发限流 |
| 502 | `AI_INVALID_RESPONSE` | Provider 返回空/截断/无效 JSON/不符合 Schema |
| 502 | `AI_PROVIDER_REQUEST_REJECTED` | DeepSeek 拒绝请求（400 或 422） |
| 503 | `AI_PROVIDER_NOT_CONFIGURED` | `DEEPSEEK_API_KEY` 缺失 |
| 503 | `AI_PROVIDER_AUTH_FAILED` | DeepSeek 鉴权失败（401） |
| 503 | `AI_PROVIDER_QUOTA_EXHAUSTED` | DeepSeek 配额耗尽（402） |
| 503 | `AI_PROVIDER_UNAVAILABLE` | DeepSeek 不可用（500/503）或连接失败 |
| 504 | `AI_PROVIDER_TIMEOUT` | Provider 超时未完成 |
| 500 | `INTERNAL_ERROR` | 未预期的应用程序错误 |

**重试策略**：
- 仅对连接失败、超时、429、500、503 进行重试
- 指数退避 + 随机抖动，最多重试 2 次（共 3 次尝试）
- 尊重上游 `Retry-After` 延迟（在总超时预算内）
- 不重试 400 / 401 / 402 / 422
- Advice JSON 输出无效时额外允许一次重新生成

---

## 安全设计

本服务遵循 **通用 Wellness 范围**，不提供医疗诊断：

- **不诊断**疾病，**不声称**医学确定性，**不处方**药物，**不提供**剂量建议
- **确定性危机升级**：在调用 Provider 前，匹配 6 个关键词 (`kill myself` / `suicide` / `self-harm` / `cannot breathe` / `chest pain` / `overdose`)，命中后返回固定升级消息，**不调用 DeepSeek**
- 用户文本和健康笔记被视为**不可信输入**，不能覆盖系统安全策略
- **不向 DeepSeek 发送**：邮箱、用户名、JWT、密码、`userId` 及其他身份数据
- **日志中不记录**：原始消息、历史、提示词、生成内容、健康笔记、密钥、凭据

---

## 质量检查

默认测试套件是**确定性、离线**的，不消耗任何 Provider Token：

```bash
uv run ruff check .
uv run mypy app tests
uv run pytest
```

Live DeepSeek 集成测试需**显式选择**并配置 `DEEPSEEK_API_KEY`，从默认套件中被排除：

```bash
uv run pytest -m live tests/integration/test_live_deepseek.py
```

Live 测试**不会打印** Key、请求 payload 或生成响应文本。

---

## 工程文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 仓库规则 | `AGENTS.md` | 仓库级编码规范与约束 |
| API 接口文档 | [`.trae/documents/WellnessApp_AI_API.md`](.trae/documents/WellnessApp_AI_API.md) | 完整 API 规范、请求/响应、校验规则 |
| 架构文档 | [`.trae/documents/WellnessApp_AI_Architecture.md`](.trae/documents/WellnessApp_AI_Architecture.md) | 分层架构设计、模块职责、数据流 |
| 产品需求 | [`.trae/documents/WellnessApp_AI_PRD.md`](.trae/documents/WellnessApp_AI_PRD.md) | AI 模块产品范围与需求 |
| 开发日志 | [`.trae/documents/WellnessApp_AI_Development_Log.md`](.trae/documents/WellnessApp_AI_Development_Log.md) | 开发计划与变更记录 |
| 架构设计 Spec | `docs/superpowers/specs/` | 设计阶段技术规格 |
| 实现计划 | `docs/superpowers/plans/` | 12 个 Task 的红-绿-重构步骤 |

---

<p align="center">
  <sub>Built with FastAPI + DeepSeek · Author: 2692341798 · SimpleWell AI Module</sub>
</p>
