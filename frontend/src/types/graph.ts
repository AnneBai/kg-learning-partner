/**
 * 知识图谱类型定义
 * 所有组件共享的核心数据结构
 */

/** 节点分类 - 四选一 */
export type NodeCategory = '核心概念' | '底层原理' | '关联工具' | '实践案例';

/** 知识图谱节点 */
export interface KNode {
  /** 英文驼峰 ID（如 machineLearning） */
  id: string;
  /** 中文显示名称 */
  label: string;
  /** 节点分类 */
  category: NodeCategory;
  /** 50字以内的中文描述 */
  description: string;
  /** 物理引擎坐标 X */
  x?: number;
  /** 物理引擎坐标 Y */
  y?: number;
  /** 是否已展开探索 */
  expanded?: boolean;
  /** 访问次数 */
  visit_count?: number;
  /** 扩展元数据 */
  metadata?: Record<string, unknown>;
}

/** 知识图谱边（关系） */
export interface KEdge {
  /** 边 ID */
  id: string;
  /** 源节点 ID */
  source: string;
  /** 目标节点 ID */
  target: string;
  /** 中文关系动词（如"包含"、"应用于"） */
  relation: string;
  /** 关联强度 1-10 */
  strength: number;
}

/** 完整图谱数据 */
export interface GraphData {
  /** 节点列表 */
  nodes: KNode[];
  /** 边列表 */
  edges: KEdge[];
}

/** 聊天消息 */
export interface ChatMessage {
  /** 消息角色 */
  role: 'user' | 'agent';
  /** 消息内容 */
  content: string;
  /** 关联节点 ID（可选） */
  node_id?: string;
  /** 创建时间 */
  created_at?: string;
}

/** 初始化图谱返回结果（含 graph_id） */
export interface InitGraphResult extends GraphData {
  graph_id: string;
}

/** 节点展开返回结果 */
export interface ExpandResult extends GraphData {
  /** 无额外字段，结构与 GraphData 相同 */
}

/** 对话返回结果 */
export interface ChatResult {
  answer: string;
}

/** 节点分类对应的颜色映射 */
export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  '核心概念': '#4F46E5',
  '底层原理': '#059669',
  '关联工具': '#D97706',
  '实践案例': '#DC2626',
};

/** 节点分类对应的中文标签颜色样式 */
export const CATEGORY_STYLES: Record<NodeCategory, { bg: string; text: string; border: string }> = {
  '核心概念': { bg: '#EEF2FF', text: '#4F46E5', border: '#C7D2FE' },
  '底层原理': { bg: '#ECFDF5', text: '#059669', border: '#A7F3D0' },
  '关联工具': { bg: '#FFFBEB', text: '#D97706', border: '#FDE68A' },
  '实践案例': { bg: '#FEF2F2', text: '#DC2626', border: '#FECACA' },
};
