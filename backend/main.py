"""
知识图谱学习伙伴 - FastAPI 主服务
提供 REST API 接口，处理图谱生成、展开、对话等请求
"""

import os
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# 内部模块导入
from db import (
    init_db,
    save_graph,
    load_graph,
    list_graphs,
    append_nodes,
    update_node_position,
    mark_expanded,
    save_message,
    get_conversation_history,
)
from agent_engine import (
    create_agent,
    build_graph_prompt,
    build_expand_prompt,
    build_chat_prompt,
    run_agent_json,
    run_agent_text,
)

# 全局 Agent 实例（延迟初始化）
_agent = None


def get_agent():
    """获取或初始化全局 Agent 实例"""
    global _agent
    if _agent is None:
        try:
            _agent = create_agent()
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _agent


# FastAPI 应用实例
app = FastAPI(title="KG Learning Partner", version="0.1.0")

# CORS 中间件 - 允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Pydantic 请求模型 ==========

class InitGraphRequest(BaseModel):
    topic: str


class ExpandRequest(BaseModel):
    node_id: str
    node_label: str
    category: str


class ChatRequest(BaseModel):
    question: str
    selected_node: Optional[str] = None


class PositionRequest(BaseModel):
    x: float
    y: float


# ========== 生命周期事件 ==========

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()


# ========== API 路由 ==========

@app.post("/api/graph/init")
async def api_init_graph(req: InitGraphRequest):
    """
    初始化新图谱：调用 Agent 搜索主题并生成知识图谱
    
    Request Body:
        topic: 学习主题字符串
    
    Returns:
        graph_id: 新图谱 ID
        nodes: 节点列表
        edges: 边列表
    """
    if not req.topic or not req.topic.strip():
        raise HTTPException(status_code=400, detail="主题不能为空")

    try:
        agent = get_agent()
        prompt = build_graph_prompt(req.topic.strip())
        data = run_agent_json(agent, prompt)

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if not nodes:
            raise ValueError("Agent 未返回任何节点")

        # 持久化到数据库
        graph_id = save_graph(req.topic, nodes, edges)

        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": edges,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"图谱生成失败: {str(e)}"
        )


@app.get("/api/graphs")
async def api_list_graphs():
    """
    获取历史图谱列表（按最近更新时间倒序）

    Returns:
        graphs: 图谱摘要列表
    """
    return {"graphs": list_graphs()}


@app.get("/api/graph/{graph_id}")
async def api_get_graph(graph_id: str):
    """
    获取完整图谱数据
    
    Path Parameters:
        graph_id: 图谱 ID
    
    Returns:
        包含 topic, nodes, edges, messages 的完整数据
    """
    data = load_graph(graph_id)
    if data is None:
        raise HTTPException(status_code=404, detail="图谱不存在")
    return data


@app.post("/api/graph/{graph_id}/expand")
async def api_expand_node(graph_id: str, req: ExpandRequest):
    """
    展开节点：围绕指定节点生成新的关联知识点
    
    Path Parameters:
        graph_id: 图谱 ID
    
    Request Body:
        node_id: 要展开的节点 ID
        node_label: 节点中文名称
        category: 节点分类
    
    Returns:
        nodes: 新增节点列表
        edges: 新增边列表
    """
    # 加载现有图谱获取已有节点 ID 列表
    existing = load_graph(graph_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="图谱不存在")

    existing_ids = [n["id"] for n in existing.get("nodes", [])]

    try:
        agent = get_agent()
        prompt = build_expand_prompt(
            req.node_id,
            req.node_label,
            req.category,
            existing_ids
        )
        data = run_agent_json(agent, prompt)

        new_nodes = data.get("nodes", [])
        new_edges = data.get("edges", [])

        # 过滤掉已存在的节点（双重保险）
        new_nodes = [n for n in new_nodes if n.get("id") not in existing_ids]
        new_edges = [e for e in new_edges if e.get("source") in existing_ids or e.get("target") not in existing_ids]

        if new_nodes:
            # 追加到数据库
            append_nodes(graph_id, new_nodes, new_edges)
            # 标记节点为已展开
            mark_expanded(graph_id, req.node_id)

        return {
            "nodes": new_nodes,
            "edges": new_edges,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"节点展开失败: {str(e)}"
        )


@app.post("/api/graph/{graph_id}/chat")
async def api_chat(graph_id: str, req: ChatRequest):
    """
    基于图谱上下文的对话
    
    Path Parameters:
        graph_id: 图谱 ID
    
    Request Body:
        question: 用户问题
        selected_node: 当前选中的节点名称（可选）
    
    Returns:
        answer: Agent 的回答
    """
    # 加载图谱和对话历史
    graph_data = load_graph(graph_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="图谱不存在")

    # 获取最近对话历史
    history = get_conversation_history(graph_id, limit=10)

    # 构建图谱上下文（只取必要的字段减少 token 消耗）
    graph_context = json.dumps(
        {
            "topic": graph_data.get("topic", ""),
            "nodes": [
                {
                    "id": n["id"],
                    "label": n["label"],
                    "category": n["category"],
                    "description": n.get("description", ""),
                }
                for n in graph_data.get("nodes", [])
            ],
            "edges": [
                {
                    "source": e["source"],
                    "target": e["target"],
                    "relation": e["relation"],
                }
                for e in graph_data.get("edges", [])
            ],
        },
        ensure_ascii=False,
    )

    try:
        agent = get_agent()
        prompt = build_chat_prompt(
            req.question,
            graph_context,
            history,
            req.selected_node
        )
        answer = run_agent_text(agent, prompt)

        # 持久化对话记录
        save_message(graph_id, "user", req.question, req.selected_node)
        save_message(graph_id, "agent", answer)

        return {"answer": answer}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话处理失败: {str(e)}"
        )


@app.post("/api/graph/{graph_id}/node/{node_id}/position")
async def api_update_position(
    graph_id: str,
    node_id: str,
    req: PositionRequest
):
    """
    更新节点坐标（拖拽后保存位置）
    
    Path Parameters:
        graph_id: 图谱 ID
        node_id: 节点 ID
    
    Request Body:
        x: 横坐标
        y: 纵坐标
    """
    try:
        update_node_position(graph_id, node_id, req.x, req.y)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"位置更新失败: {str(e)}"
        )


# ========== 主入口 ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
