<div align="center">

# 🤖 智能运维 Agent 平台

**基于 LLM 的自然语言运维助手 · 多工具编排 · 反幻觉校验**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4-42b883?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-3178c6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![MySQL](https://img.shields.io/badge/MySQL-5.7-4479a1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.2-1c3c34?logo=langchain&logoColor=white)](https://www.langchain.com/)

</div>

---

## 📖 目录

- [✨ 功能特性](#-功能特性)
- [🛠️ 技术栈](#️-技术栈)
- [🏗️ 系统架构](#️-系统架构)
- [📁 目录结构](#-目录结构)
- [⚙️ 环境变量配置](#️-环境变量配置)
- [🚀 快速开始](#-快速开始)
- [💡 使用指南](#-使用指南)
- [🔌 API 接口](#-api-接口)
- [🗄️ 数据库设计](#️-数据库设计)
- [🧩 核心模块](#-核心模块)
- [🔒 安全约束](#-安全约束)
- [📦 部署说明](#-部署说明)
- [❓ 常见问题](#-常见问题)

---

## ✨ 功能特性

<div align="center">

| 功能 | 说明 |
|:---:|---|
| 🔐 **用户鉴权** | 注册 / 登录 / JWT，bcrypt 密码哈希，接口级鉴权 |
| 💬 **多轮对话** | 历史消息持久化 MySQL，最近 20 条注入上下文 |
| 📂 **会话管理** | 新建 / 切换 / 重命名 / 软删除，按用户隔离 |
| 🎯 **意图识别** | LLM 分类 chat / weather / nl2sql / diagnose，置信度 < 0.6 回退 chat |
| 🔧 **多工具编排** | 天气查询、NL2SQL、SQL 生成、故障诊断，循环上限 3 次 |
| 🧠 **RAG 故障诊断** | Chroma 向量库语义检索 + 关键词降级，支持模糊描述命中 |
| ⚡ **流式输出** | SSE 逐 token 推送，首字延迟 2~5s，支持工具调用日志实时展示 |
| 📋 **可查询数据表** | 前端展示 servers/metrics/alerts 表结构，辅助用户提问 |
| 🛡️ **反幻觉校验** | 数值来源回溯，工具失败如实告知，不通过自动重试 |
| 📊 **工具日志** | 每次调用记录名称 / 参数 / 结果 / 耗时，前端可折叠查看 |
| 🎨 **Markdown 渲染** | 表格 / 加粗 / 行内代码安全渲染（无 v-html，防 XSS） |
| 🔐 **输入校验** | Pydantic Field 限制用户名/密码/消息长度，防超长输入 |
| 🎨 **Vue 3 前端** | Element Plus + Pinia + Vue Router，登录守卫 + Token 持久化 |

</div>

---

## 🛠️ 技术栈

### 后端

| 类别 | 技术 | 用途 |
|---|---|---|
| Web 框架 | **FastAPI** | 异步路由 + 依赖注入鉴权 |
| ORM | **SQLAlchemy 2.x** + **PyMySQL** | MySQL 操作 |
| 鉴权 | **python-jose** (JWT) + **bcrypt** | Token 签发校验 + 密码哈希 |
| 校验 | **Pydantic v2** | 请求体 / 工具结果 Schema |
| LLM 编排 | **LangChain** | Prompt 模板、`@tool`、`ToolMessage` |
| LLM 接入 | **langchain-openai** → 硅基流动 | OpenAI 兼容接口（对话 + 嵌入） |
| 向量检索 | **langchain-chroma** + **chromadb** | 故障知识库 RAG 语义检索 |
| 外部工具 | **高德天气 API** + **SQLite** | 实时天气 + 运维数据查询 |
| SQL 安全 | **sqlparse** | NL2SQL 语法解析 + 黑名单拦截 |
| 配置 | **python-dotenv** | 加载 `.env` |

### 前端

| 类别 | 技术 | 用途 |
|---|---|---|
| 框架 | **Vue 3** + **Vite** | 单页应用构建 |
| 语言 | **TypeScript** | 类型安全 |
| 路由 | **Vue Router 4** | 页面路由 + 登录守卫 |
| 状态管理 | **Pinia** | 用户 / 会话 / 消息状态 |
| UI 组件库 | **Element Plus** | 表单、对话框、消息提示 |
| HTTP 客户端 | **Axios** | 请求封装 + 拦截器 |
| 代码规范 | **ESLint** + **Prettier** | 代码检查与格式化 |

### 数据库

- **MySQL 5.7**：用户 / 会话 / 消息 / 工具日志持久化
- **SQLite**：NL2SQL 示例运维数据库

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    浏览器 (Vue 3 SPA)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │Vue Router│ │  Pinia   │ │  Axios   │ │  Element Plus  │ │
│  │ /login   │ │ userStore│ │ 拦截器   │ │  聊天组件       │ │
│  │ /chat    │ │sessionStr│ │注入 JWT  │ │                │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │  Authorization: Bearer <jwt>
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI (controller.py)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Auth: register / login / me  (JWT + bcrypt)          │  │
│  │  Session: create / list / messages / rename / delete  │  │
│  │  Chat: POST /api/chat  →  Agent 编排                   │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 Agent Orchestrator (agent.py)                 │
│                                                              │
│  1. IntentClassifier  →  意图识别                            │
│  2. load_chat_history  →  从 MySQL 拉取最近 20 条上下文       │
│  3. Prompt = system + history + input                        │
│  4. LLM.bind_tools(registry.all_tools())                     │
│     ┌──────────────┬──────────────┬──────────────┐          │
│     │ get_weather  │ nl2sql_query │ generate_sql │          │
│     │  高德 API    │ SQLite 执行  │  仅生成 SQL  │          │
│     └──────────────┴──────────────┴──────────────┘          │
│     ┌──────────────┐                                         │
│     │diagnose_fault│  Chroma RAG 语义检索 + fault_kb.json 降级 │
│     └──────────────┘                                         │
│  5. 多工具循环（上限 3 次）+ 写 tool_call_logs               │
│  6. OutputValidator  →  反幻觉校验（不通过重试 1 次）        │
│  7. 持久化 messages 表                                        │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              MySQL 5.7  (agent_ops 数据库)                    │
│   users  │  sessions  │  messages  │  tool_call_logs         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
MachineLearning/
├── controller.py            # FastAPI 入口：鉴权 + 会话 CRUD + 聊天（含 /api/chat/stream SSE）
├── agent.py                 # Agent 编排核心：意图识别、工具循环、流式输出、持久化
├── auth.py                  # 密码哈希、JWT 签发/校验、当前用户依赖
├── database.py              # SQLAlchemy 引擎、SessionLocal、get_db
├── models.py                # ORM 模型：User / Session / Message / ToolCallLog
├── schemas.py               # Pydantic 请求/响应模型（含输入长度校验）
├── intent.py                # 意图识别器（LLM 分类）
├── tool_registry.py         # 工具注册中心（单例）
├── output_validator.py      # 反幻觉输出校验（数值来源回溯）
├── nl2sql.py                # NL2SQL 工具（生成 + 校验 + 执行 SQLite）
├── diagnose.py              # 故障诊断工具（Chroma RAG 语义检索 + 关键词降级）
├── build_fault_kb_vector.py # 构建故障知识库 Chroma 向量索引
├── init_ops_db.py           # 初始化 NL2SQL 示例 SQLite 库
├── fault_kb.json            # 故障诊断知识库（6 类故障）
├── chroma_db/               # Chroma 向量库持久化目录（不入仓，由 build 脚本生成）
├── sql/
│   └── init.sql             # MySQL 初始化脚本（四张表）
├── docs/
│   └── PRD-Agent-Ops.md     # 需求文档
├── frontend/                # Vue 3 前端工程
│   ├── src/
│   │   ├── api/             # 接口层（auth / chat / session / request）
│   │   ├── components/      # ChatBubble / ChatInput / SessionList / ToolLogPanel / SchemaPanel
│   │   ├── layouts/         # ChatLayout
│   │   ├── router/          # Vue Router + 登录守卫
│   │   ├── stores/          # Pinia：user / session / chat
│   │   ├── types/           # TypeScript 类型定义
│   │   ├── utils/           # markdown.ts（安全 Markdown 解析器，无 v-html）
│   │   └── views/           # LoginView / RegisterView / ChatView
│   ├── vite.config.ts       # Vite 配置（含 /api 代理到 8000）
│   └── package.json
├── .gitignore
├── .env                     # 环境变量（不入仓）
├── 项目说明书.md
├── 操作说明书.md
└── README.md
```

---

## ⚙️ 环境变量配置

在项目根目录创建 `.env` 文件（已被 `.gitignore` 忽略）。

```ini
# ============ LLM（硅基流动，OpenAI 兼容接口）============
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL_NAME=deepseek-ai/DeepSeek-V4-Pro

# ============ 高德天气 API ============
AMAP_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
AMAP_WEATHER_URL=https://restapi.amap.com/v3/weather/weatherInfo

# ============ MySQL 数据库 ============
MYSQL_DSN=mysql+pymysql://root:your_password@127.0.0.1:3306/agent_ops?charset=utf8mb4

# ============ JWT 鉴权 ============
JWT_SECRET=please-change-this-to-a-random-secret-string
JWT_EXP_DAYS=7

# ============ RAG 故障诊断（可选）============
# 嵌入模型（硅基流动，默认 BAAI/bge-large-zh-v1.5）
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
# Chroma 向量库持久化目录（默认 ./chroma_db）
# FAULT_CHROMA_PATH=./chroma_db
# Chroma collection 名称（默认 fault_kb）
# FAULT_CHROMA_COLLECTION=fault_kb
# 检索 top-k（默认 3）
# FAULT_TOP_K=3

# ============ 可选配置 ============
# NL2SQL_DB_PATH=./ops.db
# FAULT_KB_PATH=./fault_kb.json
```

| 变量名 | 必填 | 说明 |
|---|:---:|---|
| `SILICONFLOW_API_KEY` | ✅ | 硅基流动 API Key |
| `SILICONFLOW_BASE_URL` | ✅ | 硅基流动 API 地址 |
| `SILICONFLOW_MODEL_NAME` | ✅ | 模型名称 |
| `AMAP_API_KEY` | ✅ | 高德开放平台 Web 服务 Key |
| `AMAP_WEATHER_URL` | ✅ | 高德天气查询接口地址 |
| `MYSQL_DSN` | ✅ | MySQL 连接串 |
| `JWT_SECRET` | ✅ | JWT 签名密钥（生产环境务必修改） |
| `JWT_EXP_DAYS` | ⬜ | JWT 过期天数，默认 7 |
| `NL2SQL_DB_PATH` | ⬜ | NL2SQL 示例库路径，默认 `./ops.db` |
| `FAULT_KB_PATH` | ⬜ | 故障知识库路径，默认 `./fault_kb.json` |
| `SILICONFLOW_EMBEDDING_MODEL` | ⬜ | RAG 嵌入模型，默认 `BAAI/bge-large-zh-v1.5` |
| `FAULT_CHROMA_PATH` | ⬜ | Chroma 向量库目录，默认 `./chroma_db` |
| `FAULT_CHROMA_COLLECTION` | ⬜ | Chroma collection 名，默认 `fault_kb` |
| `FAULT_TOP_K` | ⬜ | 检索召回条数，默认 `3` |

> ⚠️ 启动时会校验前 5 个变量，缺失则直接报错退出。

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/banaka1/AIOps-Platform.git
cd AIOps-Platform
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key 和数据库配置
```

### 3. 安装后端依赖

```bash
pip install fastapi uvicorn sqlalchemy pymysql python-jose[cryptography] bcrypt python-dotenv langchain langchain-openai requests sqlparse chromadb langchain-chroma
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 5. 初始化数据库

```bash
# MySQL 建表
mysql -u root -p < sql/init.sql

# 生成 NL2SQL 示例 SQLite 库
python init_ops_db.py

# 构建故障知识库 Chroma 向量索引（RAG 故障诊断必需）
python build_fault_kb_vector.py
```

### 6. 启动后端

```bash
uvicorn controller:app --reload --host 127.0.0.1 --port 8000
```

后端运行于 `http://127.0.0.1:8000`，API 文档见 `http://127.0.0.1:8000/docs`。

### 7. 启动前端

```bash
cd frontend
npm run dev
```

前端运行于 `http://127.0.0.1:5173`，`/api` 自动代理到后端 8000 端口。

---

## 💡 使用指南

### 🔐 注册与登录

1. 访问 `http://127.0.0.1:5173`，自动跳转登录页
2. 点击「注册」创建账号 → 自动跳转登录页
3. 登录成功进入聊天主界面，Token 存储于 localStorage

### 💬 对话操作

| 操作 | 说明 |
|---|---|
| **新建对话** | 点击左侧「+ 新对话」按钮 |
| **切换对话** | 点击左侧会话列表项 |
| **删除对话** | 悬停会话项 → 点击右侧垃圾桶图标 → 确认 |
| **发送消息** | 输入框输入 → `Enter` 发送 / `Shift+Enter` 换行 |
| **退出登录** | 点击右上角用户名 → 「退出登录」 |

### 🛠️ 工具能力演示

| 场景 | 示例输入 | 调用工具 |
|---|---|---|
| 🌤️ **天气查询** | `北京今天天气怎么样？` | `get_weather`（高德 API） |
| 📊 **运维数据查询** | `CPU 使用率最高的服务器是哪台？` | `nl2sql_query`（SQLite + sqlparse） |
| 📝 **生成 SQL** | `帮我写一个查询服务器 CPU 和内存的多表关联 SQL` | `generate_sql`（仅生成不执行） |
| 🔧 **故障诊断** | `服务器 CPU 飙高了怎么办？` | `diagnose_fault`（知识库匹配） |

### 📋 查看工具日志

AI 回复气泡底部有「工具调用」折叠面板，展开可查看每次工具调用的名称、参数、结果和耗时。

---

## 🔌 API 接口

所有 `/api/*` 接口（除注册登录外）需携带 `Authorization: Bearer <token>`。

### 鉴权

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| `POST` | `/api/auth/register` | `{username, password}` | `{user_id, username}` |
| `POST` | `/api/auth/login` | `{username, password}` | `{token, user:{user_id, username}}` |
| `GET` | `/api/auth/me` | — | `{user_id, username}` |

### 会话

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| `POST` | `/api/sessions` | — | `{session_id, title}` |
| `GET` | `/api/sessions` | — | `[{id, title, updated_at}]` |
| `GET` | `/api/sessions/{id}/messages` | `?page&size` | `[{role, content, ts}]` |
| `PATCH` | `/api/sessions/{id}` | `{title}` | `{ok}` |
| `DELETE` | `/api/sessions/{id}` | — | `{ok}`（软删除） |

### 对话

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| `POST` | `/api/chat` | `{session_id, message}` | `{reply, intent, tools:[{name, args, result, ms}]}` |
| `POST` | `/api/chat/stream` | `{session_id, message}` | SSE 流（见下方事件） |

**流式接口事件**（`Content-Type: text/event-stream`）：

| event | data | 说明 |
|---|---|---|
| `meta` | `{intent}` | 意图识别结果 |
| `tool_call` | `{name, args}` | 模型决定调用工具 |
| `tool_result` | `{name, result, ms}` | 工具执行结果 |
| `token` | `{text}` | 逐 token 输出 |
| `reset` | `{}` | 反幻觉校验不通过，清空当前回复重试 |
| `done` | `{reply, tools}` | 流式结束，返回完整回复 |
| `error` | `{detail}` | 异常信息 |

---

## 🗄️ 数据库设计

### users 用户表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增主键 |
| username | VARCHAR(64) UNIQUE | 用户名 |
| password | VARCHAR(128) | bcrypt 哈希 |
| created_at | DATETIME | 创建时间 |

### sessions 会话表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | CHAR(36) PK | UUID |
| user_id | BIGINT FK | 归属用户 |
| title | VARCHAR(128) | 标题（首条消息取前 12 字） |
| is_deleted | TINYINT(1) | 软删除标记 |
| created_at / updated_at | DATETIME | 时间戳 |

### messages 消息表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增 |
| session_id | CHAR(36) FK | 所属会话 |
| role | ENUM | human / ai / tool / system |
| content | TEXT | 消息内容 |
| tool_calls | JSON | ai 消息的工具调用决策 |
| created_at | DATETIME | 创建时间 |

### tool_call_logs 工具调用日志

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增 |
| session_id | CHAR(36) FK | 所属会话 |
| tool_name | VARCHAR(64) | 工具名 |
| args | JSON | 调用参数 |
| result | TEXT | 工具返回结果 |
| latency_ms | INT | 耗时（毫秒） |
| created_at | DATETIME | 调用时间 |

---

## 🧩 核心模块

### 🔐 鉴权模块（auth.py）

- `hash_password` / `verify_password`：bcrypt 加盐哈希
- `create_access_token`：HS256 签发 JWT，默认 7 天过期
- `get_current_user`：FastAPI 依赖，解析 `Bearer <token>` 并校验用户

### 🤖 Agent 编排（agent.py）

```
意图识别 → 拉取历史 → 组装 Prompt → 持久化 human 消息
    → 多工具循环（上限 3 次）
        → LLM 决策 → 执行工具 → 写 tool_call_logs → 再调 LLM
    → 反幻觉校验（不通过重试 1 次）
    → 兜底空回复 → 持久化 ai 回答
```

### 🎯 意图识别（intent.py）

LLM 分类输出 `{chat, weather, nl2sql, diagnose, unknown}` + 置信度，置信度 < 0.6 回退 `chat`。

### 🔧 工具注册中心（tool_registry.py）

单例 `ToolRegistry`，`register(tool)` 注册 LangChain `@tool`，`all_tools()` 一次性绑定 LLM。

### 📊 NL2SQL（nl2sql.py）

- `nl2sql_query`：自然语言 → SQL → 安全校验 → 执行 SQLite → 自然语言回显
- `generate_sql`：仅生成 SQL，不执行
- 安全校验：黑名单 + 仅 SELECT + 强制 LIMIT ≤ 100

### 🔧 故障诊断（diagnose.py）

基于 Chroma 向量库的 RAG 语义检索，嵌入模型走硅基流动 `BAAI/bge-large-zh-v1.5`。

- 支持模糊语义描述命中（如"机器跑不动了进程被杀"→ 内存/OOM）
- 向量库未初始化或检索异常时自动降级为 `fault_kb.json` 关键词匹配
- 命中后回查 JSON 原始条目，返回分步骤排查清单 + 追问建议
- 排查命令带安全免责声明，提醒先在测试环境验证
- 索引由 `build_fault_kb_vector.py` 幂等构建，修改知识库后重新运行即可

### 🛡️ 反幻觉校验（output_validator.py）

提取回答中的数值，检查是否在工具结果中有来源；工具失败时回答不应包含未来源数值；不通过由 agent.py 重试 1 次。

---

## 🔒 安全约束

- 🔐 **密码**：bcrypt 加盐哈希，不存明文
- 🎫 **JWT**：HS256，exp 默认 7 天，密钥走 `.env`
- 🚫 **越权防护**：所有会话接口校验 `session.user_id == user.id`
- 💉 **SQL 注入**：ORM 参数化 + NL2SQL 黑名单 + 仅 SELECT + LIMIT ≤ 100
- �️ **XSS 防护**：AI 回复不使用 `v-html`，Markdown（表格/加粗/代码）通过自定义解析器用 Vue 模板渲染，自动转义
- 📏 **输入校验**：Pydantic `Field` 限制用户名 ≤64、密码 ≤128、消息 ≤2000 字符，防超长输入
- �� **密钥**：`.env` 不入仓，启动时校验必需变量
- 📝 **日志脱敏**：tool_call_logs 不记录密钥
- ⚠️ **命令免责**：故障诊断返回的 shell 命令均带安全提示，标注副作用操作

---

## 📦 部署说明

### 后端

```bash
uvicorn controller:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend && npm run build
# 将 dist/ 部署到 Nginx 或静态文件服务器
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## ❓ 常见问题

<details>
<summary><b>启动报错 Missing required env vars</b></summary>

检查 `.env` 文件是否存在，确认 `MYSQL_DSN`、`JWT_SECRET`、`SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL`、`SILICONFLOW_MODEL_NAME` 均已配置。

</details>

<details>
<summary><b>ModuleNotFoundError: No module named 'xxx'</b></summary>

安装缺失依赖：`sqlparse` → `pip install sqlparse`，`jose` → `pip install python-jose[cryptography]`，`bcrypt` → `pip install bcrypt`。

</details>

<details>
<summary><b>前端请求 401 Unauthorized</b></summary>

检查 Network 面板是否携带 `Authorization: Bearer <token>` 头；token 过期则重新登录；确认后端 `JWT_SECRET` 一致。

</details>

<details>
<summary><b>NL2SQL 提示 "SQL 安全校验未通过"</b></summary>

LLM 生成的 SQL 包含黑名单关键词或不是 SELECT 语句，尝试用更明确的自然语言描述查询需求。

</details>

<details>
<summary><b>天气查询返回 "未配置AMAP_API_KEY"</b></summary>

检查 `.env` 中 `AMAP_API_KEY` 是否配置，高德 Key 可在 https://console.amap.com/ 免费申请。

</details>

<details>
<summary><b>NL2SQL 查询失败 "no such table"</b></summary>

`ops.db` 不存在或未初始化，运行 `python init_ops_db.py` 重新生成示例库。

</details>

<details>
<summary><b>故障诊断未命中或返回关键词匹配结果</b></summary>

Chroma 向量库未构建或初始化失败，系统会自动降级为关键词匹配。运行 `python build_fault_kb_vector.py` 重新构建向量索引即可启用语义检索。若嵌入接口报错，检查 `.env` 中 `SILICONFLOW_API_KEY` 是否有效。

</details>

<details>
<summary><b>故障诊断报 "The parameter is invalid"（400）</b></summary>

嵌入模型默认传 tiktoken token id 数组，硅基流动只接受字符串输入。代码已通过 `check_embedding_ctx_length=False` 规避此问题，若仍出现请确认 `diagnose.py` 和 `build_fault_kb_vector.py` 均为最新版本。

</details>

---

<div align="center">

**📄 更多文档**：[项目说明书](项目说明书.md) · [操作说明书](操作说明书.md) · [需求文档](docs/PRD-Agent-Ops.md)

</div>
