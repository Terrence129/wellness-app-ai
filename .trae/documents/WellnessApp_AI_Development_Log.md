# Wellness App AI — 开发日志

> **Author**: 2692341798 | **仓库**: `wellness-app-ai`  
> 仅追加 (Append-only) 日志，记录 AI 模块的开发计划、关键决策和变更历史。

---

## 目录

- [开发计划](#开发计划)
- [变更记录](#变更记录)

---

## 开发计划

### 阶段 1：AI 服务基础（已完成 ✅）

**分支**: `codex/ai-service-foundation`

| Task | 描述 | 状态 |
|------|------|------|
| Task 1 | 项目元数据和离线测试工具链 | ✅ |
| Task 2 | 配置管理 + 稳定错误类型 | ✅ |
| Task 3 | Request ID + 异常处理器 + Health 路由 | ✅ |
| Task 4 | Chat/Advice 数据 Schema | ✅ |
| Task 5 | LLMProvider 协议 + 离线 Fake | ✅ |
| Task 6 | 安全策略 + Chat 服务 | ✅ |
| Task 7 | 确定性空数据行为 + Advice 服务 | ✅ |
| Task 8 | DeepSeek 适配器（重试/错误映射/Token 观测） | ✅ |
| Task 9 | 依赖注入 + HTTP 路由 | ✅ |
| Task 10 | 隐私日志 + Live 测试 | ✅ |
| Task 11 | AGENTS.md + README.md | ✅ |
| Task 12 | 最终质量验证 + 运行时验收 | ✅ |

### 阶段 2：待规划

| 候选特性 | 优先级 | 备注 |
|----------|--------|------|
| SSE 流式响应 | 高 | 提升用户体验，逐字推送 |
| Live 集成测试优化 | 中 | 增加更多真实场景覆盖 |
| Spring Boot 集成联调 | 中 | 端到端验证 |
| 性能优化 | 低 | 如有必要 |

---

## 变更记录

### 2026-06-27 — v0.1.0 初始版本

**提交**: `feat(ai): establish wellness AI service foundation`

**内容**:
- 58 个文件，5847 行代码
- 3 个 API 端点：`GET /health`、`POST /ai/chat`、`POST /ai/wellness-advice`
- 四层架构：Routes → Services → LLMProvider Protocol → DeepSeekProvider
- 确定性安全策略：6 个危机关键词 → 固定升级消息
- DeepSeek 适配器：指数退避重试、10 种错误码、Token 用量观测
- 215 个离线测试（FakeLLMProvider）
- Live 烟雾测试（`@pytest.mark.live`）

**质量门禁**:
- ruff check: 零问题
- mypy strict (app): 零问题  
- pytest: 215 passed, 2 deselected

**架构决策**:
- 使用 `deepseek-v4-flash`，不使用 retired 的 `deepseek-chat` / `deepseek-reasoner`
- CORS 未启用（浏览器/Android 不直连）
- Thinking 模式禁用（低延迟）
- SDK 内置重试禁用（`max_retries=0`），由本适配器自行管理
- 不引入 RAG / Agent 框架 / 向量数据库

**工程文档**:
- README.md 完整技术文档
- `.trae/documents/WellnessApp_AI_API.md` API 接口文档
- `.trae/documents/WellnessApp_AI_Architecture.md` 架构文档
- `.trae/documents/WellnessApp_AI_PRD.md` 产品需求文档
- `.trae/documents/WellnessApp_AI_Development_Log.md` 本文件

### 2026-06-27 — 补全 Live 测试

**提交**: 补全 `tests/integration/test_live_deepseek.py`

**内容**:
- Chat 烟雾测试：发送 `"Give one short general wellness tip."`
- Advice 烟雾测试：发送一条基础健康日志
- 标记 `@pytest.mark.live`，默认排除
- 仅当 `DEEPSEEK_API_KEY` 存在时才执行
- 不打印 Key / payload / 响应文本

### 2026-06-27 — 安全修复：移除泄露的 API Key

**提交**: 修正 `.env.example` 中的真实 DeepSeek API Key

**问题**：`.env.example` 包含真实 `sk-11ed7b...` Key → GitHub Push Protection 拦截
**修复**：替换为占位符 `your-deepseek-api-key` → `git commit --amend` → `git push --force-with-lease`
**建议**：在 DeepSeek 后台撤销旧 Key，重新生成

### 2026-06-27 — 文档升级：README + 工程文档

**提交**: 升级 README.md + 创建 `.trae/documents/` 工程文档体系

**内容**:
- README.md 新增：项目徽章、ASCII 架构图、目录导航、技术栈表、环境变量表、安全设计章节
- 新增 API 文档、架构文档、PRD、开发日志
