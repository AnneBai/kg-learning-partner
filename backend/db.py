"""
知识图谱学习伙伴 - SQLite 数据库层
使用标准库 sqlite3，单文件存储所有数据
"""

import sqlite3
import json
import uuid
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

DB_PATH = "./kg_store.db"


@contextmanager
def get_conn():
    """获取数据库连接，使用 contextmanager 确保自动关闭"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """初始化数据库，创建所有必要的表（如果不存在）"""
    with get_conn() as conn:
        # 图谱主表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graphs (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                node_count INTEGER DEFAULT 0,
                edge_count INTEGER DEFAULT 0
            )
        """)

        # 节点表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT NOT NULL,
                graph_id TEXT NOT NULL,
                label TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                metadata TEXT,
                x REAL,
                y REAL,
                expanded INTEGER DEFAULT 0,
                visit_count INTEGER DEFAULT 0,
                PRIMARY KEY (id, graph_id),
                FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
            )
        """)

        # 边表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT NOT NULL,
                graph_id TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                strength INTEGER NOT NULL,
                PRIMARY KEY (id, graph_id),
                FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
            )
        """)

        # 对话记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                graph_id TEXT NOT NULL,
                node_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
            )
        """)

        # 创建索引优化查询
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_graph ON nodes(graph_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_graph ON edges(graph_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_graph ON conversations(graph_id)")


def save_graph(topic: str, nodes: list, edges: list) -> str:
    """
    保存完整图谱，返回 graph_id（uuid 前 8 位）
    
    Args:
        topic: 学习主题
        nodes: 节点列表，每个节点需包含 id, label, category, description 等字段
        edges: 边列表，每条边需包含 id, source, target, relation, strength 等字段
    
    Returns:
        生成的图谱 ID（uuid 前 8 位）
    """
    graph_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()

    with get_conn() as conn:
        # 插入图谱记录
        conn.execute(
            """INSERT INTO graphs (id, topic, created_at, updated_at, node_count, edge_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (graph_id, topic, now, now, len(nodes), len(edges))
        )

        # 批量插入节点
        for node in nodes:
            meta = json.dumps(node.get("metadata", {}), ensure_ascii=False)
            conn.execute(
                """INSERT INTO nodes (id, graph_id, label, category, description, metadata, x, y, expanded, visit_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    node["id"], graph_id, node["label"], node["category"],
                    node.get("description", ""), meta,
                    node.get("x"), node.get("y"),
                    1 if node.get("expanded") else 0, 0
                )
            )

        # 批量插入边
        for edge in edges:
            conn.execute(
                """INSERT INTO edges (id, graph_id, source, target, relation, strength)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    edge["id"], graph_id, edge["source"],
                    edge["target"], edge["relation"], edge["strength"]
                )
            )

    return graph_id


def load_graph(graph_id: str) -> Optional[dict]:
    """
    加载完整图谱数据（包含节点、边和对话历史）
    
    Args:
        graph_id: 图谱 ID
    
    Returns:
        包含 topic, nodes, edges, messages 的字典；如果图谱不存在返回 None
    """
    with get_conn() as conn:
        # 查询图谱基本信息
        row = conn.execute(
            "SELECT * FROM graphs WHERE id = ?", (graph_id,)
        ).fetchone()

        if row is None:
            return None

        topic = row["topic"]

        # 查询所有节点
        node_rows = conn.execute(
            "SELECT * FROM nodes WHERE graph_id = ?", (graph_id,)
        ).fetchall()

        nodes = []
        for r in node_rows:
            meta = {}
            try:
                meta = json.loads(r["metadata"] or "{}")
            except (json.JSONDecodeError, TypeError):
                pass

            node = {
                "id": r["id"],
                "label": r["label"],
                "category": r["category"],
                "description": r["description"],
                "metadata": meta,
                "x": r["x"],
                "y": r["y"],
                "expanded": bool(r["expanded"]),
                "visit_count": r["visit_count"],
            }
            nodes.append(node)

        # 查询所有边
        edge_rows = conn.execute(
            "SELECT * FROM edges WHERE graph_id = ?", (graph_id,)
        ).fetchall()

        edges = [
            {
                "id": r["id"],
                "source": r["source"],
                "target": r["target"],
                "relation": r["relation"],
                "strength": r["strength"],
            }
            for r in edge_rows
        ]

        # 查询最近对话
        messages = get_conversation_history(graph_id, limit=50)

    return {
        "graph_id": graph_id,
        "topic": topic,
        "nodes": nodes,
        "edges": edges,
        "messages": messages,
    }


def append_nodes(graph_id: str, new_nodes: list, new_edges: list) -> None:
    """
    追加新节点和边到已有图谱（使用 INSERT OR IGNORE 避免重复主键）
    
    Args:
        graph_id: 目标图谱 ID
        new_nodes: 新节点列表
        new_edges: 新边列表
    """
    now = datetime.now().isoformat()

    with get_conn() as conn:
        # 插入新节点（忽略重复）
        for node in new_nodes:
            meta = json.dumps(node.get("metadata", {}), ensure_ascii=False)
            conn.execute(
                """INSERT OR IGNORE INTO nodes
                   (id, graph_id, label, category, description, metadata, x, y, expanded, visit_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    node["id"], graph_id, node["label"], node["category"],
                    node.get("description", ""), meta,
                    node.get("x"), node.get("y"),
                    1 if node.get("expanded") else 0, 0
                )
            )

        # 插入新边（忽略重复）
        for edge in new_edges:
            conn.execute(
                """INSERT OR IGNORE INTO edges
                   (id, graph_id, source, target, relation, strength)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    edge["id"], graph_id, edge["source"],
                    edge["target"], edge["relation"], edge["strength"]
                )
            )

        # 更新图谱统计和更新时间
        node_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE graph_id = ?", (graph_id,)
        ).fetchone()[0]
        edge_count = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE graph_id = ?", (graph_id,)
        ).fetchone()[0]

        conn.execute(
            """UPDATE graphs SET node_count = ?, edge_count = ?, updated_at = ?
               WHERE id = ?""",
            (node_count, edge_count, now, graph_id)
        )


def update_node_position(graph_id: str, node_id: str, x: float, y: float) -> None:
    """
    更新节点坐标（用户拖拽后保存位置）
    
    Args:
        graph_id: 图谱 ID
        node_id: 节点 ID
        x: 横坐标
        y: 纵坐标
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE nodes SET x = ?, y = ? WHERE graph_id = ? AND id = ?",
            (x, y, graph_id, node_id)
        )


def mark_expanded(graph_id: str, node_id: str) -> None:
    """
    标记节点为已展开状态
    
    Args:
        graph_id: 图谱 ID
        node_id: 节点 ID
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE nodes SET expanded = 1 WHERE graph_id = ? AND id = ?",
            (graph_id, node_id)
        )


def save_message(graph_id: str, role: str, content: str, node_id: Optional[str] = None) -> None:
    """
    保存对话消息
    
    Args:
        graph_id: 图谱 ID
        role: 消息角色（'user' 或 'agent'）
        content: 消息内容
        node_id: 关联的节点 ID（可选）
    """
    now = datetime.now().isoformat()

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO conversations (graph_id, node_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (graph_id, node_id, role, content, now)
        )


def get_conversation_history(graph_id: str, limit: int = 10) -> list[dict]:
    """
    获取指定图谱的对话历史
    
    Args:
        graph_id: 图谱 ID
        limit: 返回最近 N 条记录
    
    Returns:
        对话记录列表，每条包含 role, content, node_id, created_at
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT role, content, node_id, created_at
               FROM conversations
               WHERE graph_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            (graph_id, limit)
        ).fetchall()

    return [
        {
            "role": r["role"],
            "content": r["content"],
            "node_id": r["node_id"],
            "created_at": r["created_at"],
        }
        for r in reversed(rows)
    ]
