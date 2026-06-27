# Wellness App AI — 产品需求文档 (PRD)

> **版本**: v0.1.0 | **Author**: 2692341798 | **更新日期**: 2026-06-27  
> 本文档定义 SimpleWell AI 模块的产品需求范围、核心功能和验收标准。

---

## 目录

- [1. 产品概述](#1-产品概述)
- [2. 需求来源与优先级](#2-需求来源与优先级)
- [3. 核心功能](#3-核心功能)
- [4. 非功能性需求](#4-非功能性需求)
- [5. 安全合规需求](#5-安全合规需求)
- [6. 不在本版本的特性（延后）](#6-不在本版本的特性延后)
- [7. 验收标准](#7-验收标准)

---

## 1. 产品概述

### 1.1 产品名称

**SimpleWell AI Module** (`wellness-app-ai`)

### 1.2 产品定位

SimpleWell 是一个移动端健康管理应用。AI 模块是其私有后端微服务组件，负责调用 DeepSeek 大模型，为终端用户提供：

- **通用 Wellness 聊天**：回答睡眠、饮食、运动、心理健康等日常健康问题
- **个性化健康建议**：基于用户记录的健康日志数据（睡眠、心情、饮水、步数、运动）生成针对性建议

### 1.3 目标用户

- **间接用户**：SimpleWell Android App 的终端用户（通过 Spring Boot 后端中转）
- **直接调用方**：Spring Boot 后端

### 1.4 技术架构定位

```text
Android App → Spring Boot → FastAPI AI Service → DeepSeek
```

AI 模块是四层架构的第三层，对终端用户透明。

---

## 2. 需求来源与优先级

需求解析优先级（从高到低）：

1. `Mobile Application Development CA.pdf` 课程要求
2. `wellness-app/Android Wellness App — Product & API Document.md` 产品文档
3. Android / Spring Boot / AI 三方约定的共享 API 契约
4. 现有源代码与示例

---

## 3. 核心功能

### 3.1 Health Check — 健康检查

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 端点 | `GET /health` |
| 依赖 DeepSeek | 否 |
| 需要 API Key | 否 |

**需求描述**：确认 FastAPI 进程正在运行。响应简单、稳定、不暴露配置信息。

**验收标准**：
- 无 API Key 时可正常返回 `200 OK`
- 响应为 `{"status":"ok","service":"wellness-app-ai"}`
- 每个响应包含 `X-Request-ID` 请求追踪头

### 3.2 Wellness Chat — 聊天

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 端点 | `POST /ai/chat` |
| 依赖 DeepSeek | 是 |
| 需要 API Key | 是 |

**需求描述**：Spring Boot 转发用户问题和有界对话历史，AI 服务返回 Wellness 相关的聊天回复。

**核心要求**：
- 支持多轮对话历史（最多 12 条）
- 回答范围限定为通用 Wellness（睡眠、饮食、运动、压力管理等）
- 遇到危机语言时返回固定升级消息而不调用 DeepSeek
- `userId` 不发送给 DeepSeek
- 所有输入经过严格 Schema 校验

**验收标准**：
- 正常对话返回 `200 OK`，含 `reply` 和 `requestId`
- 危机语言命中后返回固定升级消息，不调用 Provider
- 402/401/超时等异常返回对应错误码
- 无 API Key 时返回 `503 AI_PROVIDER_NOT_CONFIGURED`
- 聚合文本 > 20000 字符返回 `422 VALIDATION_ERROR`

### 3.3 Wellness Advice — 健康建议

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 端点 | `POST /ai/wellness-advice` |
| 依赖 DeepSeek | 有数据时是，空日志时否 |
| 需要 API Key | 有数据时需要 |

**需求描述**：基于用户每日健康日志生成个性化建议。

**核心要求**：
- 空日志时走确定性路径，返回固定提示文本（不调用 DeepSeek，无需 API Key）
- 有数据时调用 DeepSeek，要求严格 JSON 输出（仅含 `adviceText`）
- 无效 JSON、截断、空内容被拒绝并映射为 `AI_INVALID_RESPONSE`
- 无效 JSON 额外允许一次重新生成

**验收标准**：
- 空日志返回 `200 OK`，文本为固定提示，不调用 Provider
- 有数据的正常请求返回 `200 OK`，含 `adviceText` 和 `requestId`
- 无效 Provider 响应返回 `502 AI_INVALID_RESPONSE`
- 日志超过 31 条返回 `422 VALIDATION_ERROR`

---

## 4. 非功能性需求

### 4.1 性能

| 指标 | 目标 |
|------|------|
| Chat 平均延迟 | < 5s（P95） |
| Advice 平均延迟 | < 8s（P95） |
| Health 响应时间 | < 50ms |
| 并发支持 | 单进程 uvicorn，Spring Boot 控制并发 |

### 4.2 可靠性

| 指标 | 目标 |
|------|------|
| 重试策略 | 连接失败/超时/429/500/503 → 最多 2 次重试 |
| 优雅降级 | 无 API Key 时仅 AI 端点不可用，`/health` 始终可用 |
| 错误处理 | 所有异常映射为 10 种稳定错误码 |

### 4.3 可观测性

| 指标 | 要求 |
|------|------|
| Request ID | 每个请求生成/回显 UUID，透传至响应头和 Body |
| 日志 | JSON 格式，白名单字段（event/request_id/method/path/status/latency_ms/model/retry_count/tokens） |
| Token 用量 | 每次 Provider 调用记录 prompt_tokens 和 completion_tokens |

### 4.4 可测试性

| 要求 | 实现 |
|------|------|
| 离线测试 | 所有默认测试不发起网络请求（FakeLLMProvider + socket 阻断） |
| Live 测试 | 可选的有 Key 的烟雾测试（`@pytest.mark.live`） |
| 依赖注入 | Services/Provider 均可注入，支持测试替身 |

### 4.5 部署

- 必需 Python 3.11+
- 仅通过 Spring Boot 可达的私有网络
- 不得暴露公网入口
- `.env` 排除在版本控制之外

---

## 5. 安全合规需求

### 5.1 Wellness 安全

| 需求 | 实现 |
|------|------|
| 通用 Wellness 范围 | System Prompt + SafetyPolicy |
| 不诊断、不处治 | System Prompt 明确边界 |
| 危机升级 | 6 个关键词 → 固定升级消息，不调 LLM |
| 用户输入不可信 | 用户文本不能覆盖 System Prompt |

### 5.2 数据隐私

| 需求 | 实现 |
|------|------|
| 不发送用户身份到 DeepSeek | email/username/JWT/userId 全部排除 |
| 不记录原始内容 | 日志白名单，仅允许结构化元数据 |
| 密钥不外泄 | `.env.example` 不含真实 Key，`.gitignore` 排除 `.env` |

---

## 6. 不在本版本的特性（延后）

| 特性 | 延后理由 |
|------|---------|
| SSE 流式响应 | 首版优先稳定、可控的非流式响应 |
| RAG + 知识库 | 超出课程 MVP 范围 |
| Function Calling / Agent 工具 | 无批准用例 |
| 定时推荐 | 由 Spring Boot 负责调度 |
| 推荐与对话持久化 | 由 Spring Boot 的 MySQL 负责 |
| 服务间认证 | 当前私有网络部署无需，后续统一设计 |
| CORS 支持 | 浏览器/Android 不是合法直连消费者 |
| API 版本化 (`/v1`) | 待与 Spring Boot 侧协商 |

---

## 7. 验收标准

### 7.1 功能验收

- [x] `GET /health` 无 Key 返回 `200 OK`
- [x] `POST /ai/chat` 有 Key 返回正常回复
- [x] `POST /ai/chat` 无 Key 返回 `503 AI_PROVIDER_NOT_CONFIGURED`
- [x] `POST /ai/chat` 危机语言触发固定升级
- [x] `POST /ai/wellness-advice` 空日志无 Key 返回 `200 OK`
- [x] `POST /ai/wellness-advice` 有数据有 Key 返回建议
- [x] `POST /ai/wellness-advice` 有数据无 Key 返回 `503`
- [x] 所有校验失败返回 `422 VALIDATION_ERROR`
- [x] 所有 Provider 异常映射为对应错误码

### 7.2 质量验收

- [x] ruff check：零问题
- [x] mypy strict：零问题
- [x] pytest：215 passed（离线）
- [x] README 文档完整性测试通过
- [x] AGENTS.md 仓库规则测试通过

### 7.3 架构验收

- [x] 无 RAG / 向量数据库依赖
- [x] 无 Agent 框架
- [x] 无持久化代码
- [x] 无调度器
- [x] 无 CORS
- [x] 无 `deepseek-chat` / `deepseek-reasoner` 别名
- [x] 无 JWT 处理
- [x] 单文件最大 344 行（< 500 行警戒线）

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-27 | v0.1.0 | 初始版本，基于架构设计 Spec 和 12 个 Task 实现结果 |
