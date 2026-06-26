/**
 * 知识图谱 API 层
 * 使用原生 fetch 与后端 FastAPI 服务通信
 */

import type {
  GraphSummary,
  LoadGraphResult,
  InitGraphResult,
  ExpandResult,
  ChatResult,
} from '../types/graph';

/** API 基础地址 */
const BASE_URL = 'http://localhost:8000';

/**
 * 发送 HTTP 请求的通用封装
 * @param url 请求路径
 * @param options fetch 选项
 * @returns 解析后的 JSON 数据
 */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const fullUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`;

  try {
    const response = await fetch(fullUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '未知错误');
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    return await response.json() as T;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('无法连接到后端服务，请确认后端是否已启动（python backend/main.py）');
    }
    throw error;
  }
}

/**
 * 初始化新图谱
 * @param topic 学习主题
 * @returns 包含 graph_id、nodes、edges 的初始化结果
 */
export async function initGraph(topic: string): Promise<InitGraphResult> {
  return request<InitGraphResult>('/api/graph/init', {
    method: 'POST',
    body: JSON.stringify({ topic }),
  });
}

/**
 * 获取历史图谱列表
 */
export async function listGraphs(): Promise<GraphSummary[]> {
  const result = await request<{ graphs: GraphSummary[] }>('/api/graphs');
  return result.graphs;
}

/**
 * 获取完整图谱数据
 * @param id 图谱 ID
 * @returns 图谱数据（含 topic、messages）
 */
export async function getGraph(id: string): Promise<LoadGraphResult> {
  return request<LoadGraphResult>(`/api/graph/${encodeURIComponent(id)}`);
}

/**
 * 展开指定节点，生成关联知识点
 * @param id 图谱 ID
 * @param node_id 要展开的节点 ID
 * @param node_label 节点中文名称
 * @param category 节点分类
 * @returns 新增的 nodes 和 edges
 */
export async function expandNode(
  id: string,
  node_id: string,
  node_label: string,
  category: string
): Promise<ExpandResult> {
  return request<ExpandResult>(`/api/graph/${encodeURIComponent(id)}/expand`, {
    method: 'POST',
    body: JSON.stringify({ node_id, node_label, category }),
  });
}

/**
 * 基于图谱上下文进行对话
 * @param id 图谱 ID
 * @param question 用户问题
 * @param selected_node 当前选中的节点名称（可选）
 * @returns Agent 的回答
 */
export async function chat(
  id: string,
  question: string,
  selected_node?: string
): Promise<ChatResult> {
  return request<ChatResult>(`/api/graph/${encodeURIComponent(id)}/chat`, {
    method: 'POST',
    body: JSON.stringify({
      question,
      selected_node: selected_node || null,
    }),
  });
}

/**
 * 保存节点拖拽后的位置坐标
 * @param id 图谱 ID
 * @param node_id 节点 ID
 * @param x 横坐标
 * @param y 纵坐标
 */
export async function savePosition(
  id: string,
  node_id: string,
  x: number,
  y: number
): Promise<void> {
  await request<void>(
    `/api/graph/${encodeURIComponent(id)}/node/${encodeURIComponent(node_id)}/position`,
    {
      method: 'POST',
      body: JSON.stringify({ x, y }),
    }
  );
}
