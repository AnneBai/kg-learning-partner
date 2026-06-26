# REST API 参考

**Base URL**：`http://localhost:8000`

交互式文档（Swagger UI）：`http://localhost:8000/docs`

---

## 目录

- [POST /api/graph/init — 生成图谱](#post-apigraphinit)
- [GET /api/graph/{graph\_id} — 获取图谱](#get-apigraphgraph_id)
- [POST /api/graph/{graph\_id}/expand — 展开节点](#post-apigraphgraph_idexpand)
- [POST /api/graph/{graph\_id}/chat — 图谱对话](#post-apigraphgraph_idchat)
- [POST /api/graph/{graph\_id}/node/{node\_id}/position — 更新坐标](#post-apigraphgraph_idnodenodeidposition)
- [通用错误格式](#通用错误格式)
- [类型定义](#类型定义)

---

## POST /api/graph/init

初始化新图谱。调用 CodeAgent 搜索主题、生成结构化知识图谱并持久化到 SQLite。

**耗时**：依赖 LLM 推理，通常 15–60 秒。

### 请求

```http
POST /api/graph/init
Content-Type: application/json
```

```json
{
  "topic": "机器学习"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `topic` | `string` | 是 | 学习主题，不能为空字符串 |

### 响应 200

```json
{
  "graph_id": "a1b2c3d4",
  "nodes": [
    {
      "id": "machineLearning",
      "label": "机器学习",
      "category": "核心概念",
      "description": "让计算机从数据中学习规律的算法集合"
    },
    {
      "id": "deepLearning",
      "label": "深度学习",
      "category": "核心概念",
      "description": "基于多层神经网络的机器学习子领域"
    }
  ],
  "edges": [
    {
      "id": "mlToDL",
      "source": "machineLearning",
      "target": "deepLearning",
      "relation": "包含",
      "strength": 9
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `graph_id` | `string` | 8 位十六进制图谱 ID |
| `nodes` | `Node[]` | 节点列表（8–12 个） |
| `edges` | `Edge[]` | 边列表 |

### 错误

| 状态码 | 说明 |
|--------|------|
| `400` | `topic` 为空 |
| `500` | Agent 推理失败 / JSON 解析失败 / 模型配置错误 |

---

## GET /api/graph/{graph\_id}

获取完整图谱数据，包含节点、边和历史对话。

### 请求

```http
GET /api/graph/{graph_id}
```

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `graph_id` | path | `string` | 图谱 ID |

### 响应 200

```json
{
  "graph_id": "a1b2c3d4",
  "topic": "机器学习",
  "nodes": [
    {
      "id": "machineLearning",
      "label": "机器学习",
      "category": "核心概念",
      "description": "让计算机从数据中学习规律的算法集合",
      "metadata": {},
      "x": 120.5,
      "y": -45.3,
      "expanded": false,
      "visit_count": 3
    }
  ],
  "edges": [
    {
      "id": "mlToDL",
      "source": "machineLearning",
      "target": "deepLearning",
      "relation": "包含",
      "strength": 9
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "深度学习和机器学习有什么区别？",
      "node_id": "deepLearning",
      "created_at": "2024-01-15T10:30:00.123456"
    },
    {
      "role": "agent",
      "content": "【深度学习】是【机器学习】的子集...",
      "node_id": null,
      "created_at": "2024-01-15T10:30:05.456789"
    }
  ]
}
```

**节点字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `x`, `y` | `number \| null` | 拖拽保存的坐标，`null` 表示使用力导向自动布局 |
| `expanded` | `boolean` | 是否已被展开过 |
| `visit_count` | `number` | 访问次数（暂未使用） |
| `metadata` | `object` | 扩展字段，目前为空对象 |

### 错误

| 状态码 | 说明 |
|--------|------|
| `404` | 图谱不存在 |

---

## POST /api/graph/{graph\_id}/expand

围绕指定节点展开探索，生成 4–6 个关联知识点。

**耗时**：依赖 LLM 推理，通常 15–45 秒。

### 请求

```http
POST /api/graph/{graph_id}/expand
Content-Type: application/json
```

```json
{
  "node_id": "deepLearning",
  "node_label": "深度学习",
  "category": "核心概念"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `node_id` | `string` | 是 | 要展开的节点 ID（英文驼峰） |
| `node_label` | `string` | 是 | 节点中文名称（用于提示词） |
| `category` | `string` | 是 | 节点分类（四选一） |

### 响应 200

仅返回**新增**的节点和边（不含已有内容）：

```json
{
  "nodes": [
    {
      "id": "cnn",
      "label": "卷积神经网络",
      "category": "底层原理",
      "description": "专为图像处理设计的神经网络架构"
    }
  ],
  "edges": [
    {
      "id": "dlToCnn",
      "source": "deepLearning",
      "target": "cnn",
      "relation": "包含",
      "strength": 8
    }
  ]
}
```

**注意**：如果 Agent 生成了与已有节点重复的 ID，服务端会自动过滤，`nodes` 可能为空数组。

### 错误

| 状态码 | 说明 |
|--------|------|
| `404` | 图谱不存在 |
| `500` | Agent 推理失败 |

---

## POST /api/graph/{graph\_id}/chat

基于当前图谱上下文回答用户问题，并持久化对话记录。

**耗时**：依赖 LLM 推理，通常 5–20 秒。

### 请求

```http
POST /api/graph/{graph_id}/chat
Content-Type: application/json
```

```json
{
  "question": "卷积神经网络在图像识别中的应用是什么？",
  "selected_node": "卷积神经网络"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | `string` | 是 | 用户问题 |
| `selected_node` | `string \| null` | 否 | 当前选中的节点名称（非 ID），用于增强上下文 |

### 响应 200

```json
{
  "answer": "【卷积神经网络】（CNN）在图像识别领域有广泛应用。它通过卷积层提取局部特征，pooling 层降维，最终全连接层分类。建议展开【深度学习】节点了解更多底层原理。"
}
```

**回答规范**：
- 使用 `【节点名】` 格式引用图谱节点
- 使用「建议展开【xxx】节点」引导用户探索

### 错误

| 状态码 | 说明 |
|--------|------|
| `404` | 图谱不存在 |
| `500` | Agent 推理失败 |

---

## POST /api/graph/{graph\_id}/node/{node\_id}/position

保存节点的拖拽坐标，下次加载图谱时恢复位置。

### 请求

```http
POST /api/graph/{graph_id}/node/{node_id}/position
Content-Type: application/json
```

```json
{
  "x": 250.75,
  "y": -120.33
}
```

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `graph_id` | path | `string` | 图谱 ID |
| `node_id` | path | `string` | 节点 ID |
| `x` | body | `number` | 横坐标（vis-network 坐标系） |
| `y` | body | `number` | 纵坐标（vis-network 坐标系） |

### 响应 200

```json
{
  "status": "ok"
}
```

### 错误

| 状态码 | 说明 |
|--------|------|
| `500` | 数据库写入失败 |

---

## 通用错误格式

所有错误响应遵循 FastAPI 标准格式：

```json
{
  "detail": "错误描述信息"
}
```

常见错误详情：

| 详情前缀 | 说明 |
|---------|------|
| `主题不能为空` | `topic` 字段为空字符串 |
| `图谱不存在` | `graph_id` 在数据库中不存在 |
| `图谱生成失败: ...` | Agent 推理或 JSON 解析错误 |
| `节点展开失败: ...` | Agent 推理错误 |
| `对话处理失败: ...` | Agent 推理错误 |
| `位置更新失败: ...` | SQLite 写入错误 |

---

## 类型定义

### Node（节点）

```typescript
interface KNode {
  id: string;            // 英文驼峰，全图唯一
  label: string;         // 中文名称
  category: NodeCategory;
  description: string;   // 50 字以内
  metadata?: object;     // 扩展字段
  x?: number | null;     // 保存的横坐标
  y?: number | null;     // 保存的纵坐标
  expanded?: boolean;    // 是否已展开
  visit_count?: number;  // 访问次数
}

type NodeCategory = "核心概念" | "底层原理" | "关联工具" | "实践案例";
```

### Edge（边）

```typescript
interface KEdge {
  id: string;       // 英文驼峰，全图唯一
  source: string;   // 源节点 id
  target: string;   // 目标节点 id
  relation: string; // 中文动词（如：包含、依赖于、应用于）
  strength: number; // 1–10，关联强度
}
```

### GraphData（完整图谱响应）

```typescript
interface GraphData {
  graph_id: string;
  topic: string;
  nodes: KNode[];
  edges: KEdge[];
  messages?: ChatMessage[];
}
```

### ChatMessage（对话消息）

```typescript
interface ChatMessage {
  role: "user" | "agent";
  content: string;
  node_id?: string | null;
  created_at: string;   // ISO 8601 格式
}
```

### 节点分类颜色映射

| 分类 | 颜色 | Hex |
|------|------|-----|
| 核心概念 | 靛蓝 | `#4F46E5` |
| 底层原理 | 翠绿 | `#059669` |
| 关联工具 | 琥珀 | `#D97706` |
| 实践案例 | 红色 | `#DC2626` |
