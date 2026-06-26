# 数据模型

KG Learning Partner 使用单文件 SQLite 数据库（`backend/kg_store.db`）持久化所有数据。

## 目录

- [数据库概览](#数据库概览)
- [表结构](#表结构)
  - [graphs — 图谱主表](#graphs--图谱主表)
  - [nodes — 节点表](#nodes--节点表)
  - [edges — 边表](#edges--边表)
  - [conversations — 对话记录表](#conversations--对话记录表)
- [索引](#索引)
- [关系图](#关系图)
- [常用查询示例](#常用查询示例)
- [数据生命周期](#数据生命周期)

---

## 数据库概览

| 属性 | 值 |
|------|-----|
| 文件路径 | `backend/kg_store.db`（相对于启动目录） |
| 引擎 | SQLite 3（Python 标准库 `sqlite3`） |
| 初始化时机 | FastAPI 应用启动时（`startup` 事件）自动执行 `CREATE TABLE IF NOT EXISTS` |
| 级联删除 | 所有子表均有 `ON DELETE CASCADE`，删除 `graphs` 记录会自动清除关联的节点、边和对话 |

---

## 表结构

### graphs — 图谱主表

存储每个知识图谱的元数据。

```sql
CREATE TABLE IF NOT EXISTS graphs (
    id         TEXT    PRIMARY KEY,
    topic      TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0
);
```

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT | 主键，UUID 前 8 位十六进制（如 `a1b2c3d4`） |
| `topic` | TEXT | 用户输入的学习主题（如「机器学习」） |
| `created_at` | TEXT | 创建时间，ISO 8601 格式（如 `2024-01-15T10:30:00.123456`） |
| `updated_at` | TEXT | 最后更新时间，每次 `append_nodes` 时刷新 |
| `node_count` | INTEGER | 当前节点总数（冗余统计，节点新增后自动更新） |
| `edge_count` | INTEGER | 当前边总数（冗余统计） |

---

### nodes — 节点表

存储知识图谱中的每个知识点。

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT    NOT NULL,
    graph_id    TEXT    NOT NULL,
    label       TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    description TEXT,
    metadata    TEXT,
    x           REAL,
    y           REAL,
    expanded    INTEGER DEFAULT 0,
    visit_count INTEGER DEFAULT 0,
    PRIMARY KEY (id, graph_id),
    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
);
```

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT | 节点 ID，英文驼峰（如 `machineLearning`），与 `graph_id` 联合主键 |
| `graph_id` | TEXT | 所属图谱 ID（外键） |
| `label` | TEXT | 节点中文名称（如「机器学习」） |
| `category` | TEXT | 节点分类，枚举值（见下方） |
| `description` | TEXT | 50 字以内的中文描述，可为 NULL |
| `metadata` | TEXT | JSON 字符串，扩展字段，当前始终为 `{}` |
| `x` | REAL | 用户拖拽后保存的横坐标，NULL 表示使用自动布局 |
| `y` | REAL | 用户拖拽后保存的纵坐标，NULL 表示使用自动布局 |
| `expanded` | INTEGER | 布尔值（0/1），是否已被展开过 |
| `visit_count` | INTEGER | 访问次数，当前未在前端使用 |

**category 枚举值**：

| 值 | 含义 | 颜色 |
|----|------|------|
| `核心概念` | 主题的核心知识点 | 靛蓝 `#4F46E5` |
| `底层原理` | 技术原理与理论基础 | 翠绿 `#059669` |
| `关联工具` | 工具、框架、库 | 琥珀 `#D97706` |
| `实践案例` | 应用场景与案例 | 红色 `#DC2626` |

---

### edges — 边表

存储知识图谱中节点之间的关系。

```sql
CREATE TABLE IF NOT EXISTS edges (
    id       TEXT    NOT NULL,
    graph_id TEXT    NOT NULL,
    source   TEXT    NOT NULL,
    target   TEXT    NOT NULL,
    relation TEXT    NOT NULL,
    strength INTEGER NOT NULL,
    PRIMARY KEY (id, graph_id),
    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
);
```

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT | 边 ID，英文驼峰（如 `mlToDL`），与 `graph_id` 联合主键 |
| `graph_id` | TEXT | 所属图谱 ID（外键） |
| `source` | TEXT | 源节点 ID |
| `target` | TEXT | 目标节点 ID |
| `relation` | TEXT | 关系中文描述（如「包含」「依赖于」「应用于」） |
| `strength` | INTEGER | 关联强度，1–10 的整数，影响 vis-network 的边宽度 |

---

### conversations — 对话记录表

存储每个图谱的问答对话历史。

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id   TEXT    NOT NULL,
    node_id    TEXT,
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
);
```

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 自增主键 |
| `graph_id` | TEXT | 所属图谱 ID（外键） |
| `node_id` | TEXT | 对话时选中的节点 ID，可为 NULL |
| `role` | TEXT | 消息角色，枚举：`user` / `agent` |
| `content` | TEXT | 消息内容 |
| `created_at` | TEXT | 消息时间，ISO 8601 格式 |

**查询时排序**：`get_conversation_history` 使用 `ORDER BY id DESC LIMIT ?` 后再 `reversed()`，确保返回时间升序。

---

## 索引

```sql
CREATE INDEX IF NOT EXISTS idx_nodes_graph ON nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_edges_graph ON edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_conv_graph  ON conversations(graph_id);
```

所有子表均在 `graph_id` 列上建立索引，优化「按图谱查询」的性能。

---

## 关系图

```
graphs (1)
    │
    ├──── nodes (N)        [graph_id → graphs.id, ON DELETE CASCADE]
    │         │
    │         └── conversations.node_id (optional reference, no FK)
    │
    ├──── edges (N)        [graph_id → graphs.id, ON DELETE CASCADE]
    │
    └──── conversations (N)[graph_id → graphs.id, ON DELETE CASCADE]
```

注意：`conversations.node_id` 引用 `nodes.id`，但没有定义外键约束（避免节点被删除时影响对话记录）。

---

## 常用查询示例

### 列出所有图谱

```sql
SELECT id, topic, node_count, edge_count, created_at
FROM graphs
ORDER BY created_at DESC;
```

### 查看图谱的节点统计（按分类）

```sql
SELECT category, COUNT(*) as count
FROM nodes
WHERE graph_id = 'a1b2c3d4'
GROUP BY category;
```

### 查找已展开的节点

```sql
SELECT id, label, category
FROM nodes
WHERE graph_id = 'a1b2c3d4' AND expanded = 1;
```

### 查看对话历史

```sql
SELECT role, content, node_id, created_at
FROM conversations
WHERE graph_id = 'a1b2c3d4'
ORDER BY id ASC;
```

### 查找关联强度最高的边

```sql
SELECT e.source, n1.label as source_label,
       e.target, n2.label as target_label,
       e.relation, e.strength
FROM edges e
JOIN nodes n1 ON e.source = n1.id AND n1.graph_id = e.graph_id
JOIN nodes n2 ON e.target = n2.id AND n2.graph_id = e.graph_id
WHERE e.graph_id = 'a1b2c3d4'
ORDER BY e.strength DESC;
```

### 统计各图谱的对话数量

```sql
SELECT g.id, g.topic, COUNT(c.id) as message_count
FROM graphs g
LEFT JOIN conversations c ON g.id = c.graph_id
GROUP BY g.id
ORDER BY message_count DESC;
```

---

## 数据生命周期

### 创建

1. `POST /api/graph/init` → `save_graph(topic, nodes, edges)`
   - 在 `graphs` 表插入一条记录
   - 批量插入节点到 `nodes` 表
   - 批量插入边到 `edges` 表

### 更新

- **展开节点**：`append_nodes()` 用 `INSERT OR IGNORE` 追加，`mark_expanded()` 更新 `expanded = 1`
- **拖拽坐标**：`update_node_position()` 更新 `x`, `y`
- **对话消息**：`save_message()` 插入新记录到 `conversations`

### 删除

目前没有提供删除 API。如需清除数据：

```bash
# 删除单个图谱（级联删除所有关联数据）
sqlite3 backend/kg_store.db "DELETE FROM graphs WHERE id = 'a1b2c3d4';"

# 清空所有数据
rm backend/kg_store.db
# 重启服务后自动重建空数据库
```

### 备份

SQLite 单文件，直接复制即可备份：

```bash
cp backend/kg_store.db backend/kg_store.db.bak
```
