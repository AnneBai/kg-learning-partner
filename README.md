# 知识图谱学习伙伴 (KG-Learning-Partner)

一个基于 AI Agent 的可交互知识图谱学习工具。用户输入任意学习主题，系统自动搜索并生成结构化的认知图谱，支持点击节点展开子图、基于图谱上下文的智能对话，所有数据持久化到本地 SQLite。

## 功能特性

- **AI 自动生成图谱**：输入主题后，Agent 自动搜索并生成 8-12 个核心知识节点
- **交互式可视化**：基于 vis-network 的力导向图谱，支持拖拽、缩放、点击查看详情
- **节点展开探索**：双击节点可展开 4-6 个关联知识点，不断丰富图谱
- **图谱上下文对话**：基于当前图谱内容进行智能问答，Agent 会引用相关节点
- **数据持久化**：所有图谱和对话记录保存在本地 SQLite，随时可回溯
- **实时位置保存**：拖拽节点后位置自动保存，下次加载保持不变
- **多模型支持**：支持 HuggingFace、Kimi、OpenAI、OpenRouter、LiteLLM 等任意模型

## 技术架构

```
+-------------------------------------------------+
|                  前端 (Vue 3)                    |
|  +--------------+      +------------------+    |
|  |   Sidebar    |      |   GraphCanvas    |    |
|  |  - 主题输入   |      |  - vis-network   |    |
|  |  - 节点详情   |      |  - 力导向布局     |    |
|  |  - 聊天对话   |      |  - 交互事件       |    |
|  +--------------+      +------------------+    |
+--------------------+---------------------------+
                     | REST API + CORS
                     v
+-------------------------------------------------+
|              后端 (FastAPI)                      |
|  +----------+  +----------+  +--------------+  |
|  |   API    |  |  Agent   |  |    SQLite    |  |
|  |  路由    |--|  引擎    |--|   kg_store.db|  |
|  +----------+  +----------+  +--------------+  |
|       |               |                         |
|       v               v                         |
|  smolagents      多模型支持                     |
|  CodeAgent    HF / OpenAI / LiteLLM            |
+-------------------------------------------------+
```

## 安装步骤

### 1. 克隆项目

```bash
cd kg-learning-partner
```

### 2. 安装后端依赖

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装基础依赖
pip install -r requirements.txt

# 如果使用 OpenAI 兼容 API（Kimi、OpenRouter 等），额外安装：
pip install "smolagents[openai]"

# 如果使用 LiteLLM，额外安装：
pip install "smolagents[litellm]"
```

### 3. 安装前端依赖

```bash
cd ../frontend
npm install
```

## 模型配置

项目支持三种模型提供商，通过环境变量切换。选择适合你的方案：

### 方案 A：HuggingFace（默认）

```bash
MODEL_PROVIDER=huggingface
MODEL_ID=Qwen/Qwen3-Next-80B-A3B-Thinking
HF_TOKEN=your_huggingface_token
```

获取 HF Token：[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

### 方案 B：OpenAI 兼容 API（推荐 Kimi）

```bash
MODEL_PROVIDER=openai
MODEL_ID=moonshot-v1-8k
OPENAI_API_KEY=your_kimi_api_key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
```

支持任意 OpenAI 兼容的服务：

| 服务商 | MODEL_ID | OPENAI_BASE_URL |
|--------|----------|-----------------|
| **Kimi** | `moonshot-v1-8k` / `moonshot-v1-32k` / `moonshot-v1-128k` | `https://api.moonshot.cn/v1` |
| **OpenAI** | `gpt-4o` / `gpt-4o-mini` | `https://api.openai.com/v1` 或留空 |
| **OpenRouter** | `openai/gpt-4o` | `https://openrouter.ai/api/v1` |
| **Together** | `deepseek-ai/DeepSeek-R1` | `https://api.together.xyz/v1/` |
| **vLLM 本地** | 你的模型名 | `http://localhost:8000/v1` |

获取 Kimi API Key：[https://platform.moonshot.cn/console/api-keys](https://platform.moonshot.cn/console/api-keys)

### 方案 C：LiteLLM（100+ 提供商）

```bash
MODEL_PROVIDER=litellm
MODEL_ID=gpt-4o
LITELLM_API_KEY=your_api_key
LITELLM_API_BASE=https://api.openai.com/v1
```

### 配置文件

在 `backend/` 目录创建 `.env` 文件（参考 `.env.example`）：

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入你的配置
```

### 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `MODEL_PROVIDER` | 否 | 模型提供商：`huggingface` / `openai` / `litellm`，默认 `huggingface` |
| `MODEL_ID` | 否 | 模型 ID，各提供商不同 |
| `HF_TOKEN` | 条件 | HuggingFace Token（PROVIDER=huggingface 时必填） |
| `OPENAI_API_KEY` | 条件 | OpenAI 兼容 API Key（PROVIDER=openai 时必填） |
| `OPENAI_BASE_URL` | 否 | 自定义 API 基础地址（Kimi 等第三方需要） |
| `LITELLM_API_KEY` | 条件 | LiteLLM API Key（PROVIDER=litellm 时必填） |
| `LITELLM_API_BASE` | 否 | LiteLLM 自定义基础地址 |

## 启动服务

### 方式一：分别启动（推荐开发）

**终端 1 - 启动后端：**

```bash
cd backend

# Linux/Mac:
export MODEL_PROVIDER=openai
export MODEL_ID=moonshot-v1-8k
export OPENAI_API_KEY=your_kimi_key
export OPENAI_BASE_URL=https://api.moonshot.cn/v1

# 或使用 .env 文件
# export $(cat .env | xargs)

python main.py
```

后端服务将启动在 `http://localhost:8000`

**终端 2 - 启动前端：**

```bash
cd frontend
npm run dev
```

前端开发服务器将启动在 `http://localhost:5173`

### 方式二：生产构建

```bash
# 构建前端
cd frontend
npm run build

# 前端静态文件生成在 frontend/dist/ 目录
# 可使用 nginx 或任何静态文件服务器部署
```

## 使用流程

1. **打开应用**：浏览器访问 `http://localhost:5173`
2. **输入主题**：在左侧面板的输入框中输入学习主题（如"机器学习"）
3. **生成图谱**：点击"生成图谱"按钮，等待 AI 构建知识图谱
4. **探索节点**：
   - **单击节点**：在左侧面板查看节点详情（分类、描述）
   - **双击节点**：围绕该节点展开更多关联知识点
5. **智能对话**：
   - 选中节点后点击"问我关于这个"，AI 会基于图谱上下文回答
   - 也可在底部输入框自由提问
6. **持续学习**：不断展开新节点，与 AI 对话深化理解

## 项目结构

```
kg-learning-partner/
├── backend/
│   ├── main.py           # FastAPI 主服务
│   ├── agent_engine.py   # Agent 引擎（多模型支持）
│   ├── db.py             # SQLite 数据库层
│   ├── requirements.txt  # Python 依赖
│   ├── .env.example      # 环境变量模板
│   └── kg_store.db       # SQLite 数据库文件（运行时创建）
├── frontend/
│   ├── src/
│   │   ├── main.ts              # Vue 3 入口
│   │   ├── App.vue              # 主布局组件
│   │   ├── types/graph.ts       # TypeScript 类型定义
│   │   ├── api/graph.ts         # API 请求封装
│   │   └── components/
│   │       ├── GraphCanvas.vue  # 图谱可视化组件
│   │       └── Sidebar.vue      # 侧边栏组件
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
└── README.md
```

## 节点分类说明

| 分类 | 颜色 | 说明 |
|------|------|------|
| 核心概念 | 靛蓝 | 主题的核心知识点 |
| 底层原理 | 翠绿 | 技术原理和理论基础 |
| 关联工具 | 琥珀 | 相关的工具、框架、库 |
| 实践案例 | 红色 | 实际应用场景和案例 |

## 常见问题

### Q: smolagents 安装失败？

根据不同模型提供商安装对应 extras：

```bash
# HuggingFace
pip install "smolagents[toolkit]"

# OpenAI 兼容
pip install "smolagents[openai]"

# LiteLLM
pip install "smolagents[litellm]"
```

### Q: 使用 Kimi 时报错？

1. 确认已安装 openai extras：`pip install "smolagents[openai]"`
2. 确认环境变量设置正确：
   ```bash
   MODEL_PROVIDER=openai
   OPENAI_API_KEY=sk-xxx
   OPENAI_BASE_URL=https://api.moonshot.cn/v1
   ```
3. 确认 Kimi API Key 有效且有余额

### Q: 可以切换模型吗？

可以，修改环境变量后重启后端即可，无需改动代码：

```bash
# 从 Kimi 切换到 OpenAI
export MODEL_PROVIDER=openai
export MODEL_ID=gpt-4o
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.openai.com/v1

# 重启后端
python main.py
```

### Q: 数据存储在哪里？

所有数据保存在 `backend/kg_store.db`（SQLite 单文件），可随时备份或删除重置。

## License

MIT
