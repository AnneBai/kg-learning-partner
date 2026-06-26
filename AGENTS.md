# AGENTS.md — KG Learning Partner

> 面向 AI Agent / 自动化工具的项目指南。本文件描述仓库结构、Agent 行为约束、开发工作流及调用规范。

## 目录

- [项目概览](#项目概览)
- [仓库结构](#仓库结构)
- [核心 Agent 行为](#核心-agent-行为)
- [开发工作流](#开发工作流)
- [环境配置](#环境配置)
- [API 快速参考](#api-快速参考)
- [代码规范约束](#代码规范约束)
- [关联文档索引](#关联文档索引)

---

## 项目概览

**KG Learning Partner** 是一个基于 AI Agent 的可交互知识图谱学习工具。

- **后端**：FastAPI + [smolagents](https://github.com/huggingface/smolagents) `CodeAgent` + SQLite
- **前端**：Vue 3 + TypeScript + vis-network 力导向图谱
- **核心能力**：输入学习主题 → Agent 搜索网络 → 生成结构化知识图谱 → 支持节点展开与图谱上下文对话

```
用户输入主题
    ↓
POST /api/graph/init
    ↓
CodeAgent (WebSearchTool + LLM)
    ↓
JSON {nodes, edges}
    ↓
SQLite 持久化
    ↓
前端 vis-network 可视化
```

---

## 仓库结构

```
kg-learning-partner/
├── AGENTS.md               # 本文件
├── README.md               # 用户文档
├── docs/
│   ├── architecture.md     # 系统架构详解
│   ├── api-reference.md    # REST API 参考
│   ├── data-model.md       # 数据模型 & 数据库 Schema
│   └── development.md      # 开发环境搭建与工作流
├── backend/
│   ├── main.py             # FastAPI 路由层（5 个端点）
│   ├── agent_engine.py     # Agent 工厂 + 提示词 + JSON 解析
│   ├── db.py               # SQLite 数据访问层
│   ├── requirements.txt    # Python 依赖
│   └── .env.example        # 环境变量模板
└── frontend/
    ├── src/
    │   ├── App.vue          # 根组件（全局状态）
    │   ├── api/graph.ts     # HTTP 客户端封装
    │   ├── types/graph.ts   # TypeScript 类型 & 颜色常量
    │   └── components/
    │       ├── GraphCanvas.vue  # vis-network 图谱渲染
    │       └── Sidebar.vue      # 侧边栏（输入/详情/聊天）
    ├── vite.config.ts
    └── package.json
```

---

## 核心 Agent 行为

### Agent 类型

后端使用 **`smolagents.CodeAgent`**，配置如下：

| 参数 | 值 | 说明 |
|------|-----|------|
| `tools` | `[WebSearchTool()]` | 支持联网搜索 |
| `max_steps` | `12` | 最大推理步骤数 |
| `additional_authorized_imports` | `["json"]` | 允许 import json |

### Agent 触发场景

| 场景 | 触发端点 | 提示词构建函数 |
|------|---------|--------------|
| 初始化图谱 | `POST /api/graph/init` | `build_graph_prompt(topic)` |
| 展开节点 | `POST /api/graph/{id}/expand` | `build_expand_prompt(node_id, label, category, existing_ids)` |
| 图谱对话 | `POST /api/graph/{id}/chat` | `build_chat_prompt(question, graph_ctx, history, selected_node)` |

### Agent 输出规范

**图谱生成 / 节点展开**：Agent 必须返回以下结构的纯 JSON（不含 Markdown 解释）：

```json
{
  "nodes": [
    {
      "id": "camelCaseEnglish",
      "label": "中文名称",
      "category": "核心概念 | 底层原理 | 关联工具 | 实践案例",
      "description": "50字以内中文描述"
    }
  ],
  "edges": [
    {
      "id": "camelCaseEdgeId",
      "source": "sourceNodeId",
      "target": "targetNodeId",
      "relation": "中文动词（如：包含、依赖于）",
      "strength": 8
    }
  ]
}
```

**对话回复**：纯文本，使用 `【节点名】` 格式引用图谱中的节点。

### JSON 提取策略（`extract_json`）

`agent_engine.py` 中的 `extract_json()` 按优先级尝试：

1. 提取 Markdown 代码块 ` ```json ... ``` ` 内的内容
2. 提取最外层 `{ ... }` 括号内的内容
3. 尝试修复尾部逗号等常见格式问题后重试
4. 全部失败时抛出 `ValueError`

---

## 开发工作流

### 快速启动

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 API Key
python main.py         # → http://localhost:8000

# 前端
cd frontend
npm install
npm run dev            # → http://localhost:5173
```

### 修改 Agent 提示词

提示词集中在 `backend/agent_engine.py` 的三个函数：

- `build_graph_prompt()` — 控制初始图谱的节点数量、分类、JSON 格式
- `build_expand_prompt()` — 控制展开节点数量与去重逻辑
- `build_chat_prompt()` — 控制对话上下文窗口（默认最近 6 条消息）

修改提示词后无需重启服务，但建议删除 `kg_store.db` 重新测试，避免历史数据干扰。

### 添加新 API 端点

1. 在 `backend/main.py` 添加路由函数（Pydantic 请求模型 → 业务逻辑 → 返回 dict）
2. 在 `backend/db.py` 添加对应的 DB 操作函数
3. 在 `frontend/src/api/graph.ts` 添加对应的 HTTP 客户端方法
4. 在 `frontend/src/types/graph.ts` 补充相关 TypeScript 接口

### 添加新模型提供商

在 `backend/agent_engine.py` 的 `_create_model()` 函数中添加新的 `elif MODEL_PROVIDER == "xxx"` 分支，并在 `_DEFAULT_MODEL_IDS` 和 `_REQUIRED_EXTRAS` 中补充配置。

---

## 环境配置

`backend/.env` 文件（基于 `.env.example`）：

```bash
# 模型提供商：huggingface | openai | litellm
MODEL_PROVIDER=openai

# 模型 ID（各提供商格式不同）
MODEL_ID=moonshot-v1-8k

# HuggingFace（MODEL_PROVIDER=huggingface 时必填）
HF_TOKEN=hf_xxx

# OpenAI 兼容（MODEL_PROVIDER=openai 时必填）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.moonshot.cn/v1   # Kimi，可选

# LiteLLM（MODEL_PROVIDER=litellm 时必填）
LITELLM_API_KEY=sk-xxx
LITELLM_API_BASE=https://...
```

**注意**：`.env` 已在 `.gitignore` 中，不会被提交到版本库。

---

## API 快速参考

完整 API 文档见 [`docs/api-reference.md`](docs/api-reference.md)。

| 方法 | 路径 | 功能 |
|------|------|------|
| `POST` | `/api/graph/init` | 生成新图谱 |
| `GET` | `/api/graph/{graph_id}` | 获取完整图谱 |
| `POST` | `/api/graph/{graph_id}/expand` | 展开节点 |
| `POST` | `/api/graph/{graph_id}/chat` | 图谱对话 |
| `POST` | `/api/graph/{graph_id}/node/{node_id}/position` | 更新节点坐标 |

FastAPI 自动生成的交互文档：`http://localhost:8000/docs`

---

## 代码规范约束

### 后端（Python）

- 所有数据库操作通过 `db.py` 中的函数完成，禁止在路由层直接操作 SQLite
- Agent 实例为全局单例，通过 `get_agent()` 获取（延迟初始化）
- 使用 `contextmanager` 管理数据库连接，不要手动调用 `conn.close()`
- HTTP 错误统一使用 `HTTPException(status_code=..., detail=...)`

### 前端（TypeScript / Vue 3）

- 组件命名使用大驼峰 + `export default`（如 `export default defineComponent(...)`）
- 目录使用小写加短横线（如 `components/graph-canvas/`）
- API 调用统一通过 `src/api/graph.ts` 中的封装函数，不要在组件中直接 `fetch`
- 类型定义统一维护在 `src/types/graph.ts`
- 颜色常量使用 `CATEGORY_COLORS` / `CATEGORY_STYLES`，不要硬编码颜色值

### 通用

- 不引入 ORM、状态管理库（Pinia/Vuex）、路由库等额外框架——保持轻量单体架构
- 节点 ID 格式必须为英文驼峰命名（`machineLearning`），不使用数字前缀或特殊字符

---

## 关联文档索引

| 文档 | 内容 |
|------|------|
| [`docs/architecture.md`](docs/architecture.md) | 系统架构图、数据流、技术选型 |
| [`docs/api-reference.md`](docs/api-reference.md) | 所有 REST API 的请求/响应格式 |
| [`docs/data-model.md`](docs/data-model.md) | SQLite Schema、字段说明、查询示例 |
| [`docs/development.md`](docs/development.md) | 完整开发环境搭建、调试、部署指南 |
| [`README.md`](README.md) | 面向用户的快速入门文档 |
