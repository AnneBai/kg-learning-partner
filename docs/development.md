# 开发指南

## 目录

- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [模型配置](#模型配置)
- [前端开发](#前端开发)
- [后端开发](#后端开发)
- [调试技巧](#调试技巧)
- [生产部署](#生产部署)
- [常见问题](#常见问题)

---

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| npm | 9+ | 前端包管理 |

---

## 快速启动

### 1. 克隆仓库

```bash
git clone <repo-url>
cd kg-learning-partner
```

### 2. 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 安装基础依赖
pip install -r requirements.txt

# 按所选模型提供商安装额外依赖
pip install "smolagents[openai]"    # OpenAI 兼容（Kimi 等）
# pip install "smolagents[litellm]" # LiteLLM

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key（见下方「模型配置」章节）

# 启动服务
python main.py
# → 服务运行在 http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

### 3. 启动前端

```bash
# 新开一个终端
cd frontend

npm install
npm run dev
# → 前端运行在 http://localhost:5173
```

打开浏览器访问 `http://localhost:5173`，在输入框中填入学习主题即可开始使用。

---

## 模型配置

编辑 `backend/.env` 文件。选择以下任一方案：

### 方案 A：Kimi（推荐国内用户）

```bash
MODEL_PROVIDER=openai
MODEL_ID=moonshot-v1-8k
OPENAI_API_KEY=sk-your-kimi-api-key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
```

获取 API Key：https://platform.moonshot.cn/console/api-keys

### 方案 B：OpenAI

```bash
MODEL_PROVIDER=openai
MODEL_ID=gpt-4o
OPENAI_API_KEY=sk-your-openai-api-key
# OPENAI_BASE_URL 留空，使用默认地址
```

### 方案 C：HuggingFace Inference API

```bash
MODEL_PROVIDER=huggingface
MODEL_ID=Qwen/Qwen3-Next-80B-A3B-Thinking
HF_TOKEN=hf_your-token
```

获取 Token：https://huggingface.co/settings/tokens

**注意**：需要有模型 Inference API 访问权限，部分模型需要申请。

### 方案 D：LiteLLM（100+ 提供商）

```bash
MODEL_PROVIDER=litellm
MODEL_ID=claude-3-5-sonnet-20241022
LITELLM_API_KEY=sk-your-api-key
LITELLM_API_BASE=https://your-litellm-proxy.com
```

---

## 前端开发

### 目录结构

```
frontend/src/
├── main.ts              # 应用入口，挂载 Vue 实例
├── App.vue              # 根组件，管理全局状态
├── api/
│   └── graph.ts         # 所有 HTTP 请求封装
├── types/
│   └── graph.ts         # 类型定义 & 颜色常量
└── components/
    ├── GraphCanvas.vue  # vis-network 图谱渲染
    └── Sidebar.vue      # 侧边栏（输入/详情/聊天）
```

### 常用命令

```bash
cd frontend

npm run dev      # 启动开发服务器（HMR 热更新）
npm run build    # 生产构建，输出到 dist/
npm run preview  # 预览生产构建
```

### 添加新 API 调用

1. 在 `src/api/graph.ts` 中添加函数：

```typescript
export async function myNewApi(graphId: string, data: MyRequest): Promise<MyResponse> {
  return request<MyResponse>(`/api/graph/${graphId}/my-endpoint`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

2. 在 `src/types/graph.ts` 中补充接口：

```typescript
export interface MyRequest {
  field: string;
}

export interface MyResponse {
  result: string;
}
```

3. 在 `App.vue` 中调用并更新状态。

### 修改图谱样式

节点样式在 `src/types/graph.ts` 的 `CATEGORY_STYLES` 常量中定义。  
vis-network 的完整配置在 `GraphCanvas.vue` 的 `options` 对象中。

### API 基础地址

`src/api/graph.ts` 中 `BASE_URL = 'http://localhost:8000'`。

生产环境部署时需修改此地址，或通过环境变量注入：

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
```

在 `.env.production` 中设置：

```
VITE_API_BASE_URL=https://your-production-api.com
```

---

## 后端开发

### 目录结构

```
backend/
├── main.py          # FastAPI 路由层
├── agent_engine.py  # Agent + 提示词 + JSON 解析
├── db.py            # SQLite 数据访问层
├── requirements.txt
├── .env.example
└── kg_store.db      # 运行时生成的 SQLite 数据库
```

### 添加新端点

1. 在 `main.py` 定义 Pydantic 请求模型和路由：

```python
class MyRequest(BaseModel):
    field: str

@app.post("/api/graph/{graph_id}/my-endpoint")
async def my_endpoint(graph_id: str, req: MyRequest):
    data = load_graph(graph_id)
    if data is None:
        raise HTTPException(status_code=404, detail="图谱不存在")
    # ... 业务逻辑
    return {"result": "..."}
```

2. 在 `db.py` 添加数据库操作（如需）：

```python
def my_db_operation(graph_id: str, field: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE ...", (field, graph_id))
```

### 修改提示词

所有提示词在 `agent_engine.py` 中：

| 函数 | 用途 | 关键参数 |
|------|------|---------|
| `build_graph_prompt(topic)` | 初始图谱生成 | 节点数量（8-12）、分类规则 |
| `build_expand_prompt(...)` | 节点展开 | 新节点数量（4-6）、existing_ids 去重 |
| `build_chat_prompt(...)` | 图谱对话 | 历史窗口（最近 6 条）|

**提示词修改注意事项**：
- JSON 格式的 `{{` 和 `}}` 是 Python f-string 的转义，代表字面量 `{` `}`
- `existing_ids` 用于防止 Agent 生成重复节点 ID，修改展开提示词时务必保留此约束
- 图谱生成/展开提示词末尾必须包含「请只输出 JSON，不要任何其他解释」，否则 `extract_json` 可能失败

### 数据库操作

查看当前数据库内容（调试用）：

```bash
cd backend
sqlite3 kg_store.db

# 查看所有图谱
SELECT id, topic, node_count, edge_count, created_at FROM graphs;

# 查看图谱节点
SELECT id, label, category, expanded FROM nodes WHERE graph_id = 'a1b2c3d4';

# 查看对话历史
SELECT role, content FROM conversations WHERE graph_id = 'a1b2c3d4' ORDER BY id;

.quit
```

重置数据库：

```bash
rm backend/kg_store.db
# 重启服务后会自动重建
```

---

## 调试技巧

### 查看 Agent 推理过程

smolagents 的 `CodeAgent` 默认会打印推理步骤到控制台。启动服务后，每次 API 调用都会输出类似：

```
Step 1: Calling tool WebSearchTool with args: {"query": "机器学习 核心知识点"}
Step 2: Processing search results...
...
```

### 快速测试 API

使用 curl 测试：

```bash
# 生成图谱
curl -X POST http://localhost:8000/api/graph/init \
  -H "Content-Type: application/json" \
  -d '{"topic": "深度学习"}'

# 展开节点（替换 graph_id）
curl -X POST http://localhost:8000/api/graph/a1b2c3d4/expand \
  -H "Content-Type: application/json" \
  -d '{"node_id": "deepLearning", "node_label": "深度学习", "category": "核心概念"}'

# 对话
curl -X POST http://localhost:8000/api/graph/a1b2c3d4/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是反向传播？"}'
```

或使用 Swagger UI：`http://localhost:8000/docs`

### 前端调试

Vite 开发服务器已配置 `/api` 代理到 `http://localhost:8000`，但 `src/api/graph.ts` 目前直接使用 `http://localhost:8000`（未走 Vite 代理）。  
若需切换到代理模式，将 `BASE_URL` 改为空字符串 `''` 即可。

---

## 生产部署

### 构建前端

```bash
cd frontend
npm run build
# 产物在 frontend/dist/
```

### 部署选项

**选项 1：Nginx 反向代理（推荐）**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

同时修改 `backend/main.py` 的 CORS 配置，将 `allow_origins=["*"]` 改为具体域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    ...
)
```

**选项 2：直接服务（简单场景）**

```bash
# 后端
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# 前端（使用任意静态文件服务）
cd frontend/dist
python -m http.server 8080
```

### 数据库路径配置

默认 `DB_PATH = "./kg_store.db"` 相对于启动目录。生产环境建议使用绝对路径：

```python
# backend/db.py
DB_PATH = os.environ.get("DB_PATH", "./kg_store.db")
```

---

## 常见问题

### Q: 服务启动时报 `ImportError: smolagents 未安装`

```bash
pip install "smolagents[toolkit]"
# 根据 MODEL_PROVIDER 还需安装：
pip install "smolagents[openai]"    # openai
pip install "smolagents[litellm]"   # litellm
```

### Q: 图谱生成时报 `ValueError: 无法从文本中提取有效 JSON`

Agent 返回了非 JSON 格式的内容。排查步骤：
1. 查看控制台输出，找到 Agent 的原始返回
2. 检查提示词末尾是否包含「请只输出 JSON」的约束
3. 尝试换用更强的模型（如 GPT-4o、Kimi-moonshot-v1-32k）

### Q: 前端显示空白页 / Cannot GET /

检查后端是否正常运行：`curl http://localhost:8000/docs`

检查前端是否正常运行：访问 `http://localhost:5173`

检查浏览器控制台是否有 CORS 报错。

### Q: 节点展开后前端没有更新

检查 `App.vue` 中的 `handleExpand` 函数是否正确合并了新节点：
- 新节点应 push 到 `graphData.value.nodes`
- 新边应 push 到 `graphData.value.edges`
- `GraphCanvas.vue` 通过 `watch(props.graphData)` 监听变化并更新 DataSet

### Q: 拖拽节点后刷新位置重置

确认 `savePosition` API 调用是否成功（HTTP 200）。  
确认 `GET /api/graph/{id}` 返回的节点 `x`、`y` 字段不为 `null`。  
在 `GraphCanvas.vue` 中，`x`/`y` 不为 `null` 时节点会使用 `fixed: { x: true, y: true }` 固定坐标。

### Q: 多次请求 Agent 后内存占用持续增加

`CodeAgent` 全局单例会积累历史推理步骤。如果内存压力较大，可以在每次请求中重新创建 Agent 实例（牺牲初始化时间）：

```python
# main.py 中去掉全局缓存，每次调用 create_agent()
agent = create_agent()
```
