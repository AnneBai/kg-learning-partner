# 系统架构

## 总览

KG Learning Partner 是**前后端分离**的轻量单体应用，无外部服务依赖（除 LLM API 外）。

```
┌─────────────────────────────────────────────────────────────────────┐
│                        浏览器 (localhost:5173)                       │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐   │
│  │  Sidebar.vue │    │    App.vue       │    │ GraphCanvas.vue  │   │
│  │              │◄──►│  (状态中心)      │◄──►│                  │   │
│  │ • 主题输入   │    │  graphId         │    │ vis-network      │   │
│  │ • 节点详情   │    │  graphData       │    │ 力导向布局        │   │
│  │ • 聊天面板   │    │  selectedNode    │    │ 拖拽/点击/双击   │   │
│  └──────────────┘    │  messages        │    └──────────────────┘   │
│                      └────────┬─────────┘                           │
│                               │ api/graph.ts (fetch)                │
└───────────────────────────────┼─────────────────────────────────────┘
                                │ HTTP (localhost:8000)
┌───────────────────────────────┼─────────────────────────────────────┐
│                        后端 FastAPI                                  │
│                               │                                     │
│                      ┌────────▼──────────┐                         │
│                       │     main.py       │                         │
│                       │  REST API 路由层  │                         │
│                       └───────┬───────────┘                        │
│                               │                                     │
│              ┌────────────────┴───────────────────┐                │
│              │                                     │                │
│     ┌────────▼─────────┐              ┌────────────▼──────────┐    │
│     │  agent_engine.py  │              │        db.py           │   │
│     │                   │              │                        │   │
│     │  CodeAgent        │              │  SQLite               │   │
│     │  WebSearchTool    │              │  kg_store.db          │   │
│     │  提示词构建        │              │                        │   │
│     │  JSON 解析         │              └────────────────────────┘  │
│     └────────┬──────────┘                                          │
│              │                                                      │
└──────────────┼──────────────────────────────────────────────────────┘
               │ HTTPS
       ┌───────▼────────┐
       │   LLM API      │
       │ HuggingFace /  │
       │ OpenAI 兼容 /  │
       │ LiteLLM        │
       └────────────────┘
```

---

## 数据流

### 1. 初始化图谱

```
用户输入主题
    │
    ▼
POST /api/graph/init { topic }
    │
    ▼
build_graph_prompt(topic)
    │
    ▼
CodeAgent.run(prompt)
    ├── WebSearchTool("主题 核心知识点")
    ├── WebSearchTool("主题 技术原理")
    └── 生成 JSON {nodes, edges}
    │
    ▼
extract_json(result)         ← 从文本中提取 JSON
    │
    ▼
save_graph(topic, nodes, edges)  ← 入库，返回 graph_id
    │
    ▼
返回 { graph_id, nodes, edges }
    │
    ▼
前端 App.vue 更新状态
    │
    ▼
GraphCanvas.vue vis-network 渲染
```

### 2. 展开节点

```
用户双击节点 / 点击「展开探索」
    │
    ▼
POST /api/graph/{id}/expand { node_id, node_label, category }
    │
    ▼
load_graph(graph_id)         ← 获取已有节点 ID 列表（去重）
    │
    ▼
build_expand_prompt(node_id, node_label, category, existing_ids)
    │
    ▼
CodeAgent.run(prompt)
    ├── WebSearchTool("node_label 深入知识")
    └── 生成 4-6 个新节点 JSON
    │
    ▼
过滤重复节点
    │
    ▼
append_nodes(graph_id, new_nodes, new_edges)
mark_expanded(graph_id, node_id)
    │
    ▼
返回 { nodes, edges }（仅新增部分）
    │
    ▼
前端合并到现有 graphData
```

### 3. 图谱对话

```
用户输入问题
    │
    ▼
POST /api/graph/{id}/chat { question, selected_node? }
    │
    ▼
load_graph(graph_id)         ← 加载完整图谱作为上下文
get_conversation_history(graph_id, limit=10)
    │
    ▼
build_chat_prompt(question, graph_context, history, selected_node)
    │
    ▼
CodeAgent.run(prompt)        ← 基于图谱上下文回答
    │
    ▼
save_message(graph_id, "user", question)
save_message(graph_id, "agent", answer)
    │
    ▼
返回 { answer }
```

### 4. 节点位置保存

```
用户拖拽节点（dragEnd 事件）
    │
    ▼
POST /api/graph/{id}/node/{node_id}/position { x, y }
    │
    ▼
update_node_position(graph_id, node_id, x, y)
    │
    ▼
返回 { status: "ok" }
```

---

## 技术选型

### 后端

| 技术 | 版本 | 选型理由 |
|------|------|---------|
| Python | 3.10+ | smolagents 要求 |
| FastAPI | latest | 自动生成 OpenAPI 文档，类型安全，异步支持 |
| Uvicorn | latest | FastAPI 推荐的 ASGI 服务器 |
| smolagents | latest | HuggingFace 官方 Agent 框架，CodeAgent 支持工具调用 |
| SQLite (标准库) | — | 零依赖，单文件，适合本地学习工具场景 |
| Pydantic v2 | （FastAPI 内置）| 请求/响应模型验证 |

### 前端

| 技术 | 版本 | 选型理由 |
|------|------|---------|
| Vue 3 | ^3.4 | Composition API，响应式状态管理简洁 |
| TypeScript | ^5.3 | 类型安全，IDE 自动补全 |
| Vite | ^5.0 | 极速 HMR，构建性能优秀 |
| vis-network | ^9.1 | 专业图谱/网络可视化库，力导向布局，交互丰富 |

### 无引入的框架（设计决策）

| 类别 | 未引入 | 原因 |
|------|--------|------|
| 状态管理 | Pinia / Vuex | 单页面应用，`App.vue` 中的 `ref/reactive` 已满足需求 |
| 路由 | Vue Router | 单视图，无多页面需求 |
| ORM | SQLAlchemy | 数据模型简单，原生 sqlite3 代码量更少 |
| CSS 框架 | Tailwind / Element Plus | 保持最小依赖，样式写在 `<style scoped>` 中 |

---

## 模块职责边界

### `backend/main.py`

- **只做**：HTTP 路由、请求验证、错误包装
- **不做**：直接操作数据库、直接调用 LLM

### `backend/agent_engine.py`

- **只做**：Agent 初始化、提示词构建、JSON 解析
- **不做**：数据库操作、HTTP 响应处理

### `backend/db.py`

- **只做**：SQLite CRUD 操作
- **不做**：业务逻辑、AI 调用

### `frontend/src/api/graph.ts`

- **只做**：HTTP 请求封装，类型化响应
- **不做**：UI 状态更新、业务逻辑

### `frontend/src/App.vue`

- **只做**：全局状态管理、组件通信协调
- **不做**：直接发 HTTP 请求（通过 `api/graph.ts`）、图谱渲染

---

## 已知局限与扩展方向

| 限制 | 当前实现 | 潜在改进 |
|------|---------|---------|
| 图谱历史 | 后端 `load_graph` 已实现，前端无 UI | 添加图谱列表侧边栏 |
| 并发安全 | 全局单例 Agent，非线程安全 | 使用连接池或每请求初始化 |
| 生产 CORS | `allow_origins=["*"]` | 限制为前端域名 |
| 认证 | 无 | 添加 JWT / API Key |
| 测试 | 无 | 添加 pytest + Vitest |
| 流式回复 | 无 | 使用 SSE / WebSocket |
| 图谱导出 | 无 | 支持导出为 PNG / JSON |
