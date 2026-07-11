# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AIHR BOSS 招聘 Agent —— 基于开源 AI 客服系统 [AI-CS](https://github.com/2930134478/AI-CS) 二次开发，面向蓝领/服务业招聘场景。当前核心目标是辅助操作 BOSS 直聘完成候选人搜索、筛选和沟通。

项目包含三个独立服务，本地开发时需全部启动：

| 服务 | 语言/框架 | 端口 | 职责 |
|------|----------|------|------|
| `backend/` | Go 1.24 + Gin + GORM | :8080 | REST API + WebSocket + RAG + 业务逻辑 |
| `frontend/` | Next.js 16 (React 19, Tailwind CSS 4, Radix UI) | :3000 | 营销首页、访客聊天小窗、客服工作台、招聘 Agent 页面 |
| `agent-service/` | Python 3 + FastAPI + LangGraph | :8090 | 招聘 Agent 工作流 + BOSS 浏览器自动化 |

## Git 提交规范

- commit message 使用**中文**，简明扼要描述本次提交做了什么
- 格式：`<类型>: <中文描述>`
- 类型：`feat`（新功能）、`fix`（修复）、`refactor`（重构）、`docs`（文档）、`chore`（杂项）
- 示例：
  - `feat: 添加知识库测试页面知识库选择功能`
  - `fix: 修复 fetchMessages 缺少认证 header 导致 403`
  - `docs: 更新 CLAUDE.md 项目架构说明`
- `git push` 前先确认 commit message 能准确说明改动内容

## 启动命令

### 一键启停（推荐本地开发）

```powershell
# 后台启动全部三个服务
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1

# 跳过 Agent 服务（Python 环境未就绪时使用）
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -NoAgent

# 弹窗模式（每个服务一个 PowerShell 窗口）
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Window

# 停止所有服务
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

脚本自动检测 `$env:TEMP\codex-go-1.24.1\go\bin\go.exe` 或系统 PATH 中的 Go。日志写入 `.dev/logs/`。

### 手动启动

```powershell
# 1. 后端（需 MySQL 已运行）
cd backend && go run .

# 2. 前端
cd frontend && npm run dev

# 3. Agent 服务（需先创建虚拟环境）
cd agent-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

首次访问：`http://localhost:3000/agent/login`，默认账号 `admin / 123456`（登录后建议立即改密码）。

### Docker 部署

```bash
# 开发构建
docker-compose up -d --build

# 生产（预构建镜像）
docker-compose -f docker-compose.prod.yml up -d

# 附带 Milvus 向量库
docker-compose -f docker-compose.yml -f docker-compose.milvus.yml up -d
```

## 配置体系

`.env` 是**唯一配置源**。`backend/main.go` 启动时依次检查 `{工作目录}/.env` → `{上级目录}/.env`。Docker 和本地开发读取同一份 `.env`。

### 必填项

- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` — MySQL 连接
- `MYSQL_ROOT_PASSWORD` — Docker 部署时 MySQL 容器 root 密码
- `ADMIN_PASSWORD` — 管理员密码，启动时自动创建/同步 `admin` 账号
- `ADMIN_USERNAME` — 管理员用户名（默认 `admin`）
- `ENCRYPTION_KEY` — 64 位十六进制加密密钥（`openssl rand -hex 32`）

### 重要可选配置

- `RECRUITMENT_AGENT_URL=http://127.0.0.1:8090` — Python Agent 服务地址；留空时 Go 后端用本地规则兜底
- `SYSTEM_LOG_MIN_LEVEL=info` — 结构化日志最低落库级别（debug/info/warn/error/none）
- `MILVUS_HOST` / `MILVUS_PORT` — 向量库连接
- `MILVUS_DISABLED=true` — 跳过 Milvus（RAG 不可用但服务正常启动）
- `MILVUS_REQUIRED=true` — 强依赖，连接失败则启动退出
- `SERPER_API_KEY` 或 `SERPER_MCP_URL` — 联网搜索（至少配一种）
- `REDIS_URL` — 多实例 WebSocket 广播（单实例无需配置）
- `IP2REGION_DISABLED=true` — 关闭访客 IP 地理位置解析

### 前端构建时变量

以下 `NEXT_PUBLIC_*` 变量在 `docker build` 时注入，本地 `npm run dev` 时从 `.env` 读取：

- `NEXT_PUBLIC_API_BASE_URL` — 前端调用后端的基地址（同域反向代理时留空）
- `NEXT_PUBLIC_BACKEND_HOST` / `NEXT_PUBLIC_BACKEND_PORT` — 开发代理目标
- `NEXT_PUBLIC_SITE_URL` — 站点绝对地址，用于 SEO

## 后端架构

### 分层模式

```
router/router.go     → 路由注册（同时挂在 / 和 /api 两个前缀）
controller/          → 请求参数提取、响应封装，不写业务逻辑
service/             → 业务逻辑、编排、外部调用
repository/          → 数据库 CRUD（GORM）
models/              → GORM 模型定义（= 数据库表结构）
infra/               → 基础设施：DB连接、Milvus、Redis、文件存储、GeoIP、搜索
middleware/          → TraceID、结构化日志、CORS、认证
websocket/           → Hub 模式：连接管理、消息广播、Redis Pub/Sub
```

### 依赖注入（`backend/main.go`）

`main()` 是唯一的组装入口。初始化顺序：

1. 加载 `.env` → 初始化 GeoIP
2. 连接 MySQL → AutoMigrate 所有 model（`RecruitmentRequirement`, `RecruitmentCandidate`, `RecruitmentTimelineEvent` 等）
3. 创建 Repository → 创建 SystemLogService
4. 初始化默认 admin 账号
5. 创建 Gin 引擎 → 注册中间件（TraceID → StructuredHTTPLogger → Logger → CORS）
6. 初始化 Milvus（可选降级） → VectorStore → 嵌入服务 → RAG
7. 初始化联网搜索（MCP 优先，Serper HTTP API 兜底）
8. 创建所有 Service → 创建 WebSocket Hub → 启动 Hub goroutine
9. 创建所有 Controller → 注入 Router
10. `r.Run(addr)` 启动 HTTP 服务

**添加新功能时遵循此模式**：定义 model → 写 repository → 写 service → 写 controller → 在 main() 组装 → 在 router 注册路由。

### 认证机制

- 登录接口 `/login` 验证用户名密码，返回 `{user_id, username, role}`
- 前端将 `user_id` 存入 `localStorage`，后续所有请求通过 `X-User-Id` header 传递
- `middleware.RequireAuth()` 从 header 解析 `user_id` 注入 `gin.Context`
- 用户角色：`admin`（全权限）、`agent`（客服，默认仅 `chat` 权限）
- 权限粒度：`User.Permissions` 字段为 JSON 数组字符串（如 `["chat","knowledge"]`）

### 路由结构

所有路由由 `router.RegisterRoutes()` 统一注册，自动同时挂在 `/` 和 `/api` 两个前缀下。路由按业务模块分组：

| 前缀 | 模块 | 说明 |
|------|------|------|
| `/login`, `/logout` | Auth | 登录登出 |
| `/conversation/*`, `/conversations/*` | Conversation | 对话管理 |
| `/messages/*` | Message | 消息收发、文件上传 |
| `/admin/*` | Admin | 用户管理（CRUD） |
| `/agent/profile/*` | Profile | 个人信息、头像 |
| `/agent/ai-config/*` | AI Config | AI 模型配置 |
| `/agent/embedding-config` | Embedding | 向量模型配置（平台级） |
| `/agent/prompts` | Prompt | 提示词配置（平台级） |
| `/faqs/*` | FAQ | 常见问题管理 |
| `/documents/*` | Document | 文档管理（含向量/混合检索） |
| `/knowledge-bases/*` | KnowledgeBase | 知识库管理 |
| `/import/*` | Import | 文档批量导入 |
| `/visitor/*` | Visitor | 访客端接口（无需登录） |
| `/agent/analytics/*` | Analytics | 数据报表 |
| `/agent/logs/*` | SystemLog | 日志中心 |
| `/agent/recruitment/*` | Recruitment | 招聘需求、候选人、时间线、Agent 运行 |
| `/agent/boss-assistant/*` | BossAssistant | BOSS 桌面助手检测/配置 |
| `/health`, `/health/metrics` | Health | 健康检查 |
| `/ws` | WebSocket | WebSocket 连接 |

### WebSocket 架构

- 端点：`/ws?conversation_id=<id>`
- Hub 模式：一个 goroutine 循环处理 register / unregister / broadcast 三个 channel
- 每个 conversation 可有多客户端（访客 + 多个客服）
- 消息类型：`new_message`、`conversation_update`、`visitor_status_update`
- 广播范围：`scope: "conversation"`（单对话）或 `scope: "all_agents"`（所有客服）
- 多实例：配置 Redis 后自动启用 Pub/Sub，跨实例同步广播，带回环保护（`FromRemote` 标记）
- 连接/断开回调：自动更新访客在线状态、生成客服加入/离开系统消息

### 结构化日志

- `middleware.StructuredHTTPLogger` 将每个 HTTP 请求写入 `system_logs` 表
- 落库级别：`SYSTEM_LOG_MIN_LEVEL` 环境变量（默认 `info`），可通过前端「日志中心」页面动态覆盖（写入 `app_settings` 表）
- 分类：`http`、`vector`、`ai` 等
- 每个请求带 `X-Trace-Id`，便于链路追踪

## 前端架构

### 技术栈

- **框架**: Next.js 16 (App Router) + React 19
- **样式**: Tailwind CSS 4 + `tailwind-merge` + `class-variance-authority`
- **组件**: Radix UI (Checkbox, Dialog, Switch, Toast, Tooltip 等) + `lucide-react` 图标
- **动画**: `framer-motion`
- **构建**: Turbopack (`next dev --turbopack`)

### 目录结构

```
frontend/
├── app/                      # Next.js App Router 页面
│   ├── page.tsx              # 营销首页
│   ├── layout.tsx            # 根布局
│   ├── chat/page.tsx         # 访客聊天小窗（iframe 嵌入模式）
│   ├── agent/                # 客服工作台（需登录）
│   │   ├── login/            # 登录页
│   │   ├── dashboard/        # 工作台首页
│   │   ├── recruitment/      # ★ 招聘 Agent 页面（核心新功能）
│   │   ├── conversations/    # 对话列表
│   │   ├── chat/[id]/        # 对话详情
│   │   ├── knowledge/        # 知识库管理
│   │   ├── faqs/             # FAQ 管理
│   │   ├── prompts/          # 提示词配置
│   │   ├── settings/         # 系统设置
│   │   ├── analytics/        # 数据报表
│   │   ├── logs/             # 日志中心
│   │   └── users/            # 用户管理
│   └── api/agent/prompts/    # 前端 API 路由（代理层）
├── components/
│   ├── ui/                   # shadcn/ui 风格的通用组件
│   ├── dashboard/            # 工作台专用组件
│   ├── visitor/              # 访客聊天小窗组件
│   ├── layout/               # 布局组件
│   ├── marketing/            # 营销首页组件
│   └── recruitment/          # 招聘模块专用组件（RegionSelect）
├── features/
│   ├── agent/                # 客服端业务逻辑
│   │   ├── services/         # API 调用层（按模块拆分）
│   │   ├── hooks/            # 自定义 hooks
│   │   └── types.ts          # 共享类型定义
│   └── visitor/              # 访客端业务逻辑
├── hooks/                    # 通用 hooks
├── lib/                      # 工具函数
│   ├── config.ts             # API URL 构造、认证 header
│   └── chat-embed.ts         # 聊天小窗嵌入式脚本
└── public/widget.js          # 可嵌入第三方网站的访客小窗脚本
```

### 前端 API 调用模式

所有 API 调用遵循以下模式：

```typescript
// frontend/lib/config.ts
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${API_PREFIX}${path}`; // 例：/api/agent/recruitment/requirements
}
export function getAgentHeaders(): Record<string, string> {
  const id = window.localStorage.getItem("agent_user_id");
  return id ? { "X-User-Id": id } : {};
}

// frontend/features/agent/services/recruitmentApi.ts
export async function fetchRecruitmentRequirements(): Promise<RecruitmentRequirement[]> {
  const res = await fetch(apiUrl("/agent/recruitment/requirements"), {
    cache: "no-store",
    headers: getAgentHeaders(),
  });
  if (!res.ok) throw await parseApiError(res, "获取招聘需求失败");
  return res.json();
}
```

### Next.js 开发代理

`next.config.ts` 中配置了 `rewrites()`：开发模式下将 `/api/*`、`/agent/*` 等后端路径代理到 Go 后端（`NEXT_PUBLIC_BACKEND_HOST:NEXT_PUBLIC_BACKEND_PORT`）。生产环境由 Nginx 处理。

## 招聘 Agent 系统

### 数据模型（三张核心表）

```
RecruitmentRequirement（招聘需求）
  ├── ID, Title, Role, JobCategory, Location
  ├── SearchKeyword, EducationRequirement, AgeRequirement
  ├── RecommendedFilters, SortPreference
  ├── FilterViewed14Days, FilterExchanged30Days
  ├── BatchSize, Tags, MustHave, NiceHave, Description
  ├── Status (active/paused/closed), OwnerID
  └── CreatedAt, UpdatedAt

RecruitmentCandidate（候选人）
  ├── ID, RequirementID (FK), OwnerID
  ├── Name, Source, CurrentRole, Location, Tags, Profile
  ├── MatchScore, MatchReason (Agent 评分结果)
  ├── ContactStatus (new/contacted/replied/consented/group_invited/rejected)
  ├── ConsentToContact, PrivateContact
  ├── GroupStatus (not_invited/invited/joined/not_joined)
  ├── LastMessage, NextAction
  └── CreatedAt, UpdatedAt

RecruitmentTimelineEvent（沟通时间线）
  ├── ID, CandidateID (FK), OwnerID
  ├── EventType, Title, Content
  ├── FromStatus, ToStatus
  └── CreatedAt
```

### Go 后端 → Python Agent 通信链路

```
前端招聘页
  → POST /agent/recruitment/candidates/:id/agent-run
  → RecruitmentController.RunAgent()
  → RecruitmentService.RunAgent()
  → RecruitmentAgentClient.Run()  ──HTTP──→  Python /v1/recruitment/run
  → 返回 score/draft/next_action 写入 candidate 记录
  → 创建 timeline event ("agent_run")
  → 前端展示 Agent 结果
```

### RecruitmentAgentClient 行为

- 通过 `RECRUITMENT_AGENT_URL` 环境变量配置 Python 服务地址
- 超时 25 秒，失败返回 error（Go 后端不会 fallback 到本地规则——fallback 在 service 层处理）
- 请求体包含完整的 requirement + candidate + knowledge_context
- `thread_id` 格式：`candidate-{candidate_id}`
- 从 DB 中已发布的 RAG 文档加载 `knowledge_context`（最多 5 篇、每篇截断 1200 字符、总计不超过 4000 字符）

### 本地规则兜底（Python Agent 未配置时）

`RecruitmentService.RunAgent()` 中：如果 `agent.Enabled()` 为 false，调用 `buildLocalRecruitmentAgentResult()`：

1. **评分** (`scoreCandidate`)：基于关键词 token 匹配
   - Role 匹配：+30 分
   - Location 匹配：+15 分
   - MustHave 匹配：每个词 +12 分（上限 35）
   - NiceHave 匹配：每个词 +6 分（上限 18）
   - Tags 匹配：每个词 +8 分（上限 24）
   - 总分上限 100
2. **话术** (`buildRecruitmentDraft`)：模板拼装——"你好，我这边有一个{地点}的{岗位}机会..."
3. **下一步动作**：根据 ContactStatus 和 ConsentToContact 判断
4. `requires_human_approval` 始终为 `true`

### LangGraph 状态流（Python 端）

```
normalize_context → score_match → draft_message → request_human_approval → END
```

- `normalize_context`：清洗字段（trim 字符串）
- `score_match`：调用 `heuristic_score()`（规则匹配，逻辑与 Go 端 `scoreCandidate` 一致），配置了 LLM 时暂未使用 LLM 评分
- `draft_message`：优先调用 LLM（Kimi 等 OpenAI 兼容 API），失败则用 `fallback_draft()` 模板
- `request_human_approval`：始终返回 `requires_human_approval=true`

**Checkpoint**：默认内存模式；设置 `AGENT_CHECKPOINT_DB=path/to/checkpoint.db` 启用 SQLite 持久化。

### BOSS 浏览器自动化

`agent-service/app/boss_browser.py` 使用 DrissionPage 操作本地 Chrome/Edge：

- 打开/复用 BOSS 直聘搜索页 (`zhipin.com/web/chat/search`)
- 自动填写：城市、职位类别、关键词、学历范围（含拖拽滑块）、年龄、更多筛选（专业要求含三级选择+搜索）、推荐筛选
- 自动点击搜索按钮
- 页面文本快照（用于判断登录状态和搜索结果）

**重要限制**：
- 不保存 BOSS 账号/密码/cookie
- 需人工先登录 BOSS
- 稳定性依赖 BOSS 页面 DOM 结构
- BOSS 搜索在 iframe 中，大部分操作通过注入 JavaScript 完成（`run_js_bool` 函数）
- Go 后端通过 `BossAssistantController` 暴露 `/agent/boss-assistant/*` 接口，委托 Python 服务执行浏览器操作

### 候选人状态机

```
new → contacted → replied → consented → group_invited → joined
  ↓        ↓         ↓
rejected  rejected  rejected
```

每个状态变更自动创建 timeline event，记录 `from_status` → `to_status`。

## AI 客服系统（原始 AI-CS 功能）

### AI 对话回复流程

`AIService` 负责生成 AI 客服回复：

1. 加载对话上下文（最近 N 条消息）
2. 按需执行 RAG 检索（从已发布文档中搜索相关内容）
3. 按需执行联网搜索（通过 Serper MCP 或 HTTP API）
4. 调用 `AIProviderFactory` 创建对应的 AI Provider（OpenAI 兼容协议）
5. 流式返回生成结果，通过 WebSocket 推送给访客

### 知识库 RAG

- 向量库：Milvus（可选，支持降级）
- 嵌入模型：从 `EmbeddingConfig`（平台级配置）读取 API 信息，`EmbeddingFactory` 创建具体实现
- 文档流程：上传 → 分块 → 向量化 → 存入 Milvus
- 检索：向量检索 + 混合检索（向量 + 关键词）
- 配置热更新：修改嵌入配置后立即生效，无需重启

### 访客聊天小窗

- 嵌入方式：iframe (`/chat`) 或 `widget.js` 脚本
- 模式切换：AI 模式 / 人工模式
- 自动收集：IP、浏览器、OS、语言、地理位置（ip2region 离线库）
- 埋点：小窗打开事件写入 `widget_open_events` 表

## 依赖版本要求

| 依赖 | 版本 |
|------|------|
| Go | 1.24+ |
| Node.js | 20.9+ |
| MySQL | 8.0+ |
| Python | 3.10+（agent-service） |
| Redis | 可选（多实例 WebSocket） |
| Milvus | 可选（知识库 RAG） |

## 常用开发命令

```bash
# Go 后端
cd backend && go run .                    # 启动
cd backend && go test ./...               # 运行所有测试
cd backend && go vet ./...                # 静态分析
cd backend && go mod tidy                 # 整理依赖

# 前端
cd frontend && npm run dev                # 开发模式（Turbopack）
cd frontend && npm run build              # 生产构建
cd frontend && npm run lint               # ESLint

# Docker
docker-compose up -d --build              # 构建并启动
docker-compose logs -f backend            # 查看后端日志
docker-compose exec backend sh            # 进入后端容器
```

## 重要文件索引

**后端核心**：
- `backend/main.go` — 启动入口，DI 组装（必读）
- `backend/router/router.go` — 全部路由注册（添加路由时改这里）
- `backend/middleware/middleware.go` — 认证、CORS、TraceID、结构化日志
- `backend/service/recruitment_service.go` — 招聘核心业务 + 本地规则兜底
- `backend/service/recruitment_agent_client.go` — 调用 Python Agent 的 HTTP 客户端
- `backend/controller/recruitment_controller.go` — 招聘 API 控制器
- `backend/service/ai_service.go` — AI 对话生成
- `backend/websocket/hub.go` — WebSocket Hub
- `backend/infra/db.go` — 数据库连接初始化
- `backend/infra/milvus.go` — Milvus 客户端初始化

**Agent 服务**：
- `agent-service/app/main.py` — FastAPI 入口和路由
- `agent-service/app/recruitment_agent.py` — LangGraph 状态图：normalize→score→draft→approval
- `agent-service/app/boss_browser.py` — DrissionPage BOSS 浏览器自动化
- `agent-service/app/schemas.py` — Pydantic 数据模型

**前端核心**：
- `frontend/app/agent/recruitment/page.tsx` — 招聘 Agent 主页面（最复杂的前端页面）
- `frontend/features/agent/services/recruitmentApi.ts` — 招聘 API 调用
- `frontend/lib/config.ts` — `apiUrl()` 和 `getAgentHeaders()`
- `frontend/next.config.ts` — 开发代理 rewrites
- `frontend/app/agent/layout.tsx` — 工作台布局（侧边栏导航）

**基础设施**：
- `.env.example` — 完整配置参考（含中文注释）
- `scripts/start-dev.ps1` / `scripts/stop-dev.ps1` — 本地启停
- `docker-compose.yml` — Docker 开发部署
- `docker-compose.prod.yml` — Docker 生产部署（预构建镜像）
- `docker-compose.milvus.yml` — Milvus 附加服务
- `docs/recruitment-agent-langgraph-architecture.md` — Agent 架构文档

## 故障排查

### 前端启动内存泄漏（Turbopack + Tailwind CSS 4）

**日期**: 2026-07-02

**现象**:
- `npm run dev` 后 Node.js 内存持续增长，最终系统卡死
- 进程崩溃后残留 `.next/dev/lock` 和端口占用，无法重启
- `.next` 缓存膨胀至 308MB

**根因**: Turbopack 在 Windows 上的文件监听 + Tailwind CSS 4 自动扫描整棵项目树（含 `.next` 和 `node_modules`），形成恶性循环。

**修复**:

1. 删除 `.next` 缓存目录（含残留 lock 文件）
2. `frontend/app/globals.css` 添加 `@source` 指令，限制 Tailwind 扫描范围：

```css
@import "tailwindcss";
@source "../app";
@source "../components";
@source "../features";
@source "../hooks";
@source "../lib";
@source "../utils";
```

**前端源文件目录清单**: `app/`, `components/`, `features/`, `hooks/`, `lib/`, `utils/` — 添加新目录时同步更新 `globals.css`。

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
