<script setup lang="ts">
/**
 * 知识图谱学习伙伴 - 主入口组件
 * 整体布局：左侧 Sidebar（固定 380px）+ 右侧 GraphCanvas（flex: 1）
 */
import { ref, reactive } from 'vue';
import type { KNode, GraphData, ChatMessage } from './types/graph';
import GraphCanvas from './components/GraphCanvas.vue';
import Sidebar from './components/Sidebar.vue';
import * as api from './api/graph';

// ==================== 状态管理 ====================

/** 当前图谱 ID */
const graphId = ref<string | null>(null);

/** 当前图谱数据（节点 + 边） */
const graphData = reactive<GraphData>({
  nodes: [],
  edges: [],
});

/** 当前选中的节点 */
const selectedNode = ref<KNode | null>(null);

/** 聊天消息列表 */
const messages = ref<ChatMessage[]>([]);

/** 全局加载状态 */
const loading = ref(false);

/** 当前主题 */
const currentTopic = ref('');

// ==================== 错误提示 ====================

/**
 * 显示错误信息
 */
function showError(message: string) {
  // 将错误添加到聊天区域
  messages.value.push({
    role: 'agent',
    content: `❌ ${message}`,
  });
  loading.value = false;
}

// ==================== 事件处理 ====================

/**
 * 处理初始化新图谱
 * @param topic 用户输入的主题
 */
async function handleInit(topic: string) {
  loading.value = true;
  currentTopic.value = topic;

  try {
    const result = await api.initGraph(topic);

    graphId.value = result.graph_id;
    currentTopic.value = topic;

    // 设置图谱数据
    graphData.nodes = result.nodes || [];
    graphData.edges = result.edges || [];

    // 清空之前的对话和选中状态
    messages.value = [];
    selectedNode.value = null;

    // 添加欢迎消息
    messages.value.push({
      role: 'agent',
      content: `已为您生成"${topic}"的知识图谱！共 ${graphData.nodes.length} 个知识点，${graphData.edges.length} 条关联。\n\n💡 单击节点查看详情，双击节点展开探索。`,
    });
  } catch (error: any) {
    showError(error.message || '图谱生成失败，请重试');
  } finally {
    loading.value = false;
  }
}

/**
 * 处理展开节点探索
 * @param node 要展开的节点
 */
async function handleExpand(node: KNode) {
  if (!graphId.value || loading.value) return;
  loading.value = true;

  try {
    const result = await api.expandNode(
      graphId.value,
      node.id,
      node.label,
      node.category
    );

    // 合并新节点（去重）
    const existingNodeIds = new Set(graphData.nodes.map((n) => n.id));
    const newNodes = (result.nodes || []).filter(
      (n) => !existingNodeIds.has(n.id)
    );

    // 合并新边（去重）
    const existingEdgeIds = new Set(graphData.edges.map((e) => e.id));
    const newEdges = (result.edges || []).filter(
      (e) => !existingEdgeIds.has(e.id)
    );

    // 追加到图谱
    if (newNodes.length > 0) {
      graphData.nodes.push(...newNodes);
      graphData.edges.push(...newEdges);

      messages.value.push({
        role: 'agent',
        content: `已展开【${node.label}】，新增 ${newNodes.length} 个知识点！`,
      });
    } else {
      messages.value.push({
        role: 'agent',
        content: `【${node.label}】的探索已完成，没有发现新的关联知识点。`,
      });
    }
  } catch (error: any) {
    showError(error.message || '节点展开失败');
  } finally {
    loading.value = false;
  }
}

/**
 * 处理发送聊天消息
 * @param question 用户问题
 * @param nodeId 关联节点 ID（可选）
 */
async function handleChat(question: string, nodeId?: string) {
  if (!graphId.value || loading.value) return;
  loading.value = true;

  // 添加用户消息到列表
  messages.value.push({
    role: 'user',
    content: question,
    node_id: nodeId,
  });

  try {
    const result = await api.chat(
      graphId.value,
      question,
      nodeId || undefined
    );

    // 添加 Agent 回复
    messages.value.push({
      role: 'agent',
      content: result.answer,
    });
  } catch (error: any) {
    showError(error.message || '对话处理失败');
  } finally {
    loading.value = false;
  }
}

/**
 * 处理节点选中
 * @param node 选中的节点
 */
function handleNodeSelect(node: KNode) {
  selectedNode.value = node;

  // 增加访问计数（前端本地更新）
  node.visit_count = (node.visit_count || 0) + 1;
}

/**
 * 处理节点展开（来自图谱的双击事件）
 * @param node 双击的节点
 */
function handleNodeExpand(node: KNode) {
  handleExpand(node);
}
</script>

<template>
  <div class="app-container">
    <!-- 左侧侧边栏 -->
    <Sidebar
      :selected-node="selectedNode"
      :messages="messages"
      :loading="loading"
      :topic="currentTopic"
      @init="handleInit"
      @expand="handleExpand"
      @chat="handleChat"
    />

    <!-- 右侧图谱画布 -->
    <div class="canvas-wrapper">
      <GraphCanvas
        :graph-data="graphData"
        :graph-id="graphId"
        :on-node-select="handleNodeSelect"
        :on-node-expand="handleNodeExpand"
      />

      <!-- 空状态提示 -->
      <div v-if="graphData.nodes.length === 0 && !loading" class="empty-state">
        <div class="empty-content">
          <div class="empty-illustration">🗺️</div>
          <h2>欢迎使用知识图谱学习伙伴</h2>
          <p>在左侧面板输入学习主题，AI 将为您生成可交互的认知图谱</p>
          <div class="demo-topics">
            <span class="demo-label">试试这些主题：</span>
            <button
              v-for="t in ['机器学习', 'React 框架', '量子计算', '区块链技术']"
              :key="t"
              class="demo-chip"
              @click="handleInit(t)"
            >
              {{ t }}
            </button>
          </div>
        </div>
      </div>

      <!-- 加载遮罩 -->
      <div v-if="loading && graphData.nodes.length === 0" class="loading-overlay">
        <div class="loading-content">
          <div class="loading-spinner"></div>
          <p>AI 正在构建知识图谱...</p>
          <p class="loading-hint">这可能需要几秒钟，正在搜索并整理知识点</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 全局样式 */
* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100vh;
  width: 100vw;
}
</style>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #FAFBFC;
}

.canvas-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

/* 空状态 */
.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FAFBFC;
  z-index: 10;
}

.empty-content {
  text-align: center;
  padding: 40px;
  max-width: 480px;
}

.empty-illustration {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.7;
}

.empty-content h2 {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 10px 0;
}

.empty-content p {
  font-size: 14px;
  color: #6B7280;
  line-height: 1.6;
  margin: 0 0 24px 0;
}

.demo-topics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.demo-label {
  font-size: 12px;
  color: #9CA3AF;
  margin-right: 4px;
}

.demo-chip {
  padding: 6px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 20px;
  background: #ffffff;
  font-size: 13px;
  color: #4F46E5;
  cursor: pointer;
  transition: all 0.2s ease;
}

.demo-chip:hover {
  background: #4F46E5;
  color: white;
  border-color: #4F46E5;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
}

/* 加载遮罩 */
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(250, 251, 252, 0.95);
  z-index: 20;
}

.loading-content {
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E5E7EB;
  border-top-color: #4F46E5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-content p {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 6px 0;
}

.loading-hint {
  font-size: 13px;
  color: #9CA3AF;
  margin: 0;
}
</style>
