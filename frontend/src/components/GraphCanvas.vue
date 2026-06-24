<script setup lang="ts">
/**
 * 知识图谱可视化组件
 * 基于 vis-network/standalone 实现交互式图谱渲染
 */
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { Network, DataSet } from 'vis-network/standalone';
import type { GraphData, KNode } from '../types/graph';
import { CATEGORY_COLORS } from '../types/graph';

// ==================== Props & Emits ====================

interface Props {
  /** 图谱数据 */
  graphData: GraphData;
  /** 当前图谱 ID（用于保存位置） */
  graphId?: string | null;
  /** 节点选中回调 */
  onNodeSelect?: (node: KNode) => void;
  /** 节点展开回调 */
  onNodeExpand?: (node: KNode) => void;
}

const props = defineProps<Props>();

// ==================== Refs & State ====================

const containerRef = ref<HTMLDivElement | null>(null);
let network: Network | null = null;

/** 内部 vis-network 数据集 */
const visNodes = new DataSet<any>([]);
const visEdges = new DataSet<any>([]);

/** 用于查找节点原始数据的映射表 */
const nodeMap = new Map<string, KNode>();

// ==================== 样式配置 ====================

/**
 * 根据节点分类获取颜色
 */
function getNodeColor(category: string): string {
  return CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] || '#6B7280';
}

/**
 * 将内部 KNode 转换为 vis-network 节点格式
 */
function toVisNode(node: KNode): any {
  const color = getNodeColor(node.category);
  const isExpanded = node.expanded === true;

  return {
    id: node.id,
    label: node.label,
    shape: 'dot',
    size: isExpanded ? 22 : 18,
    color: {
      background: color,
      border: '#ffffff',
      highlight: { background: color, border: '#ffffff' },
      hover: { background: color, border: '#ffffff' },
    },
    borderWidth: isExpanded ? 3 : 2,
    borderWidthSelected: 4,
    dashes: isExpanded ? [5, 5] : false,
    font: {
      size: 14,
      face: 'system-ui, -apple-system, sans-serif',
      color: '#1F2937',
      strokeWidth: 3,
      strokeColor: '#ffffff',
    },
    // 保存原始数据用于回调
    _raw: node,
    // 如果有坐标则使用
    x: node.x ?? undefined,
    y: node.y ?? undefined,
  };
}

/**
 * 将内部 KEdge 转换为 vis-network 边格式
 */
function toVisEdge(edge: any): any {
  return {
    id: edge.id,
    from: edge.source,
    to: edge.target,
    label: edge.relation,
    width: Math.max(1, (edge.strength || 5) / 3),
    arrows: {
      to: {
        enabled: true,
        scaleFactor: 0.6,
      },
    },
    color: {
      color: '#9CA3AF',
      highlight: '#4F46E5',
      hover: '#4F46E5',
    },
    font: {
      size: 11,
      face: 'system-ui, -apple-system, sans-serif',
      color: '#6B7280',
      strokeWidth: 2,
      strokeColor: '#ffffff',
      align: 'middle',
    },
    smooth: {
      enabled: true,
      type: 'continuous',
      roundness: 0.2,
    },
  };
}

// ==================== 数据同步 ====================

/**
 * 同步 graphData 到 vis-network DataSet
 * 使用 merge 策略避免重复，保留已有位置
 */
function syncData() {
  if (!props.graphData) return;

  const { nodes: newNodes, edges: newEdges } = props.graphData;

  // 收集新节点
  const visNodeUpdates: any[] = [];
  const newNodeIds = new Set<string>();

  for (const node of newNodes) {
    newNodeIds.add(node.id);
    nodeMap.set(node.id, node);

    const existing = visNodes.get(node.id);
    const visNode = toVisNode(node);

    if (existing) {
      // 保留已有坐标
      if (existing.x !== undefined) visNode.x = existing.x;
      if (existing.y !== undefined) visNode.y = existing.y;
      visNodes.update(visNode);
    } else {
      visNodeUpdates.push(visNode);
    }
  }

  if (visNodeUpdates.length > 0) {
    visNodes.add(visNodeUpdates);
  }

  // 收集新边
  const visEdgeUpdates: any[] = [];
  const existingEdgeIds = new Set(visEdges.getIds() as string[]);

  for (const edge of newEdges) {
    if (!existingEdgeIds.has(edge.id)) {
      visEdgeUpdates.push(toVisEdge(edge));
    }
  }

  if (visEdgeUpdates.length > 0) {
    visEdges.add(visEdgeUpdates);
  }
}

/**
 * 监听 graphData 变化，自动同步
 */
watch(
  () => props.graphData,
  () => syncData(),
  { deep: true }
);

// ==================== 网络初始化 ====================

/**
 * 初始化 vis-network 实例
 */
function initNetwork() {
  if (!containerRef.value) return;

  const data = {
    nodes: visNodes,
    edges: visEdges,
  };

  const options = {
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -60,
        centralGravity: 0.005,
        springLength: 120,
        springConstant: 0.08,
        damping: 0.4,
        avoidOverlap: 0.5,
      },
      stabilization: {
        enabled: true,
        iterations: 100,
        updateInterval: 25,
      },
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      hideEdgesOnDrag: false,
      navigationButtons: true,
      keyboard: false,
    },
    layout: {
      randomSeed: 42,
    },
  };

  network = new Network(containerRef.value, data, options);

  // 物理稳定后自动适配视图
  network.once('stabilizationIterationsDone', () => {
    network?.fit({
      animation: {
        duration: 800,
        easingFunction: 'easeInOutQuad',
      },
    });
  });

  // 单击事件 - 选中节点
  network.on('click', (params: any) => {
    if (params.nodes && params.nodes.length > 0) {
      const nodeId = params.nodes[0] as string;
      const rawNode = nodeMap.get(nodeId);
      if (rawNode && props.onNodeSelect) {
        props.onNodeSelect(rawNode);
      }
    }
  });

  // 双击事件 - 展开节点
  network.on('doubleClick', (params: any) => {
    if (params.nodes && params.nodes.length > 0) {
      const nodeId = params.nodes[0] as string;
      const rawNode = nodeMap.get(nodeId);
      if (rawNode && props.onNodeExpand) {
        props.onNodeExpand(rawNode);
      }
    }
  });

  // 拖拽结束 - 保存位置
  network.on('dragEnd', (params: any) => {
    if (params.nodes && params.nodes.length > 0 && props.graphId) {
      const nodeId = params.nodes[0] as string;
      const position = network?.getPositions([nodeId])[nodeId];
      if (position) {
        // 动态导入避免循环依赖
        import('../api/graph').then(({ savePosition }) => {
          savePosition(props.graphId!, nodeId, position.x, position.y)
            .catch((err) => console.warn('保存位置失败:', err));
        });
      }
    }
  });
}

// ==================== 生命周期 ====================

onMounted(() => {
  syncData();
  initNetwork();
});

onUnmounted(() => {
  if (network) {
    network.destroy();
    network = null;
  }
  visNodes.clear();
  visEdges.clear();
  nodeMap.clear();
});
</script>

<template>
  <div ref="containerRef" class="graph-canvas"></div>
</template>

<style scoped>
.graph-canvas {
  width: 100%;
  height: 100%;
  background: #FAFBFC;
  cursor: grab;
}

.graph-canvas:active {
  cursor: grabbing;
}

.graph-canvas :deep(div.vis-network div.vis-navigation) {
  position: absolute;
  right: 16px;
  bottom: 16px;
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-button) {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid #E5E7EB;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #374151;
  transition: all 0.15s ease;
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-button:hover) {
  background: #F3F4F6;
  border-color: #D1D5DB;
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-up::before) {
  content: '▲';
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-down::before) {
  content: '▼';
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-left::before) {
  content: '◀';
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-right::before) {
  content: '▶';
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-zoomIn::before) {
  content: '+';
  font-size: 18px;
  font-weight: 300;
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-zoomOut::before) {
  content: '−';
  font-size: 18px;
  font-weight: 300;
}

.graph-canvas :deep(div.vis-network div.vis-navigation div.vis-zoomExtends::before) {
  content: '⛶';
}
</style>
