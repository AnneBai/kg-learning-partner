<script setup lang="ts">
/**
 * 侧边栏组件
 * 包含：主题输入、节点详情、聊天对话三个区域
 */
import { ref, computed, nextTick, watch } from 'vue';
import type { KNode, ChatMessage, GraphSummary } from '../types/graph';
import { CATEGORY_STYLES } from '../types/graph';

// ==================== Props & Emits ====================

interface Props {
  /** 当前选中的节点 */
  selectedNode: KNode | null;
  /** 聊天消息列表 */
  messages: ChatMessage[];
  /** 加载状态 */
  loading: boolean;
  /** 当前图谱主题 */
  topic?: string;
  /** 当前图谱 ID */
  graphId?: string | null;
  /** 历史图谱列表 */
  graphList?: GraphSummary[];
  /** 历史列表加载中 */
  historyLoading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  topic: '',
  graphId: null,
  graphList: () => [],
  historyLoading: false,
});

const emit = defineEmits<{
  /** 初始化新图谱 */
  (e: 'init', topic: string): void;
  /** 加载已有图谱 */
  (e: 'load', graphId: string): void;
  /** 展开节点探索 */
  (e: 'expand', node: KNode): void;
  /** 发送聊天消息 */
  (e: 'chat', question: string, nodeId?: string): void;
}>();

// ==================== 状态 ====================

const topicInput = ref('');
const chatInput = ref('');
const chatContainerRef = ref<HTMLDivElement | null>(null);
const historyExpanded = ref(true);

// ==================== 计算属性 ====================

/**
 * 获取节点分类的样式
 */
const categoryStyle = computed(() => {
  if (!props.selectedNode) return null;
  return CATEGORY_STYLES[props.selectedNode.category];
});

// ==================== 方法 ====================

/**
 * 处理加载历史图谱
 */
function handleLoadGraph(id: string) {
  if (props.loading || props.graphId === id) return;
  emit('load', id);
}

/**
 * 格式化相对时间
 */
function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} 天前`;
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

/**
 * 处理"生成图谱"按钮点击
 */
function handleInit() {
  const topic = topicInput.value.trim();
  if (!topic) return;
  emit('init', topic);
}

/**
 * 处理展开节点探索
 */
function handleExpand() {
  if (!props.selectedNode || props.loading) return;
  emit('expand', props.selectedNode);
}

/**
 * 处理发送聊天消息
 */
function handleChat() {
  const question = chatInput.value.trim();
  if (!question || props.loading) return;

  const nodeId = props.selectedNode?.id;
  emit('chat', question, nodeId);
  chatInput.value = '';
}

/**
 * 处理键盘回车发送
 */
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleChat();
  }
}

/**
 * 快捷提问：关于当前节点
 */
function askAboutNode() {
  if (!props.selectedNode) return;
  const question = `请详细介绍一下"${props.selectedNode.label}"`;
  emit('chat', question, props.selectedNode.id);
}

/**
 * 滚动聊天区域到底部
 */
function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
    }
  });
}

/**
 * 高亮 Agent 消息中的【节点名】引用
 */
function highlightNodeRefs(content: string): string {
  return content.replace(
    /【([^】]+)】/g,
    '<span class="node-ref">$1</span>'
  );
}

/**
 * 判断消息是否包含"建议展开"提示
 */
function hasExpandSuggestion(content: string): boolean {
  return content.includes('建议展开');
}

/**
 * 从消息中提取建议展开的节点名
 */
function extractSuggestion(content: string): string | null {
  const match = content.match(/建议展开【([^】]+)】/);
  return match ? match[1] : null;
}

// ==================== 监听 ====================

/**
 * 消息变化时自动滚动到底部
 */
watch(
  () => props.messages.length,
  () => scrollToBottom(),
  { flush: 'post' }
);
</script>

<template>
  <aside class="sidebar">
    <!-- 区域 1：主题输入 -->
    <div class="section topic-section">
      <h2 class="section-title">知识图谱学习伙伴</h2>
      <p class="section-desc">输入主题，AI 生成可交互的认知图谱</p>

      <div class="input-group">
        <input
          v-model="topicInput"
          type="text"
          class="topic-input"
          placeholder="输入学习主题，如：机器学习"
          :disabled="loading"
          @keydown.enter="handleInit"
        />
        <button
          class="btn-primary"
          :disabled="!topicInput.trim() || loading"
          @click="handleInit"
        >
          <span v-if="loading" class="spinner"></span>
          <span v-else>生成图谱</span>
        </button>
      </div>

      <div v-if="topic" class="topic-badge">
        当前主题：{{ topic }}
      </div>
    </div>

    <!-- 区域 1.5：历史图谱 -->
    <div v-if="graphList.length > 0 || historyLoading" class="section history-section">
      <button class="history-header" @click="historyExpanded = !historyExpanded">
        <span class="history-title">📚 历史图谱</span>
        <span class="history-count">{{ graphList.length }}</span>
        <span class="history-toggle">{{ historyExpanded ? '▾' : '▸' }}</span>
      </button>

      <div v-show="historyExpanded" class="history-list">
        <div v-if="historyLoading" class="history-loading">加载中...</div>
        <button
          v-for="item in graphList"
          :key="item.graph_id"
          class="history-item"
          :class="{ active: graphId === item.graph_id }"
          :disabled="loading"
          @click="handleLoadGraph(item.graph_id)"
        >
          <div class="history-item-topic">{{ item.topic }}</div>
          <div class="history-item-meta">
            <span>{{ item.node_count }} 节点 · {{ item.edge_count }} 边</span>
            <span>{{ formatRelativeTime(item.updated_at) }}</span>
          </div>
        </button>
      </div>
    </div>

    <!-- 区域 2：节点详情（仅当选中时显示） -->
    <div v-if="selectedNode" class="section node-detail">
      <div class="detail-header">
        <h3 class="node-label">{{ selectedNode.label }}</h3>
        <span
          v-if="categoryStyle"
          class="category-tag"
          :style="{
            backgroundColor: categoryStyle.bg,
            color: categoryStyle.text,
            borderColor: categoryStyle.border,
          }"
        >
          {{ selectedNode.category }}
        </span>
      </div>

      <p class="node-description">{{ selectedNode.description }}</p>

      <div class="node-meta">
        <span v-if="selectedNode.expanded" class="meta-tag expanded">
          已展开
        </span>
        <span v-else class="meta-tag not-expanded">
          未展开
        </span>
        <span v-if="selectedNode.visit_count" class="meta-tag">
          访问 {{ selectedNode.visit_count }} 次
        </span>
      </div>

      <div class="detail-actions">
        <button
          class="btn-expand"
          :disabled="loading || selectedNode.expanded"
          @click="handleExpand"
        >
          <span class="btn-icon">🔍</span>
          展开探索
        </button>
        <button
          class="btn-chat"
          :disabled="loading"
          @click="askAboutNode"
        >
          <span class="btn-icon">💬</span>
          问我关于这个
        </button>
      </div>
    </div>

    <!-- 区域 3：聊天对话 -->
    <div class="section chat-section">
      <h3 class="chat-title">💬 智能对话</h3>
      <p class="chat-subtitle">基于图谱上下文，随时提问</p>

      <div ref="chatContainerRef" class="chat-messages">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-bubble">
            <div
              class="message-content"
              v-html="highlightNodeRefs(msg.content)"
            ></div>
            <div
              v-if="msg.role === 'agent' && hasExpandSuggestion(msg.content)"
              class="suggestion-hint"
            >
              💡 双击图谱中对应节点即可展开探索
            </div>
          </div>
        </div>

        <div v-if="loading && messages.length > 0 && messages[messages.length - 1].role === 'user'" class="message agent">
          <div class="message-bubble typing">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>

        <div v-if="messages.length === 0" class="chat-empty">
          <div class="empty-icon">🧠</div>
          <p>开始探索知识图谱吧！</p>
          <p class="empty-hint">选中节点后点击"问我关于这个"开始对话</p>
        </div>
      </div>

      <div class="chat-input-area">
        <textarea
          v-model="chatInput"
          class="chat-input"
          placeholder="输入问题..."
          rows="2"
          :disabled="loading"
          @keydown="handleKeydown"
        ></textarea>
        <button
          class="btn-send"
          :disabled="!chatInput.trim() || loading"
          @click="handleChat"
        >
          ➤
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 380px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-right: 1px solid #E5E7EB;
  overflow: hidden;
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
}

/* 通用区域样式 */
.section {
  padding: 16px 20px;
  border-bottom: 1px solid #F3F4F6;
}

.section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 4px 0;
}

.section-desc {
  font-size: 13px;
  color: #6B7280;
  margin: 0 0 12px 0;
}

/* 主题输入区域 */
.topic-section {
  flex-shrink: 0;
  background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
  color: white;
  border-bottom: none;
}

.topic-section .section-title {
  color: white;
}

.topic-section .section-desc {
  color: rgba(255, 255, 255, 0.8);
}

.input-group {
  display: flex;
  gap: 8px;
}

.topic-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
  color: white;
  font-size: 14px;
  outline: none;
  transition: all 0.2s ease;
}

.topic-input::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.topic-input:focus {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.5);
}

.topic-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  padding: 10px 18px;
  border: none;
  border-radius: 8px;
  background: #ffffff;
  color: #4F46E5;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-primary:hover:not(:disabled) {
  background: #F3F4F6;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #4F46E5;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.topic-badge {
  margin-top: 10px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

/* 历史图谱区域 */
.history-section {
  flex-shrink: 0;
  padding: 0;
  background: #FAFBFC;
}

.history-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
}

.history-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.history-count {
  padding: 1px 7px;
  background: #EEF2FF;
  color: #4F46E5;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.history-toggle {
  margin-left: auto;
  font-size: 12px;
  color: #9CA3AF;
}

.history-list {
  max-height: 180px;
  overflow-y: auto;
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-list::-webkit-scrollbar {
  width: 4px;
}

.history-list::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 2px;
}

.history-loading {
  padding: 8px 8px;
  font-size: 12px;
  color: #9CA3AF;
  text-align: center;
}

.history-item {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.history-item:hover:not(:disabled) {
  border-color: #C7D2FE;
  background: #EEF2FF;
}

.history-item.active {
  border-color: #4F46E5;
  background: #EEF2FF;
  box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.15);
}

.history-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history-item-topic {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.history-item-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: #9CA3AF;
}

/* 节点详情区域 */
.node-detail {
  flex-shrink: 0;
  background: #FAFBFC;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.node-label {
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.category-tag {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  white-space: nowrap;
}

.node-description {
  font-size: 13px;
  line-height: 1.6;
  color: #4B5563;
  margin: 0 0 10px 0;
}

.node-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.meta-tag {
  padding: 2px 8px;
  background: #F3F4F6;
  border-radius: 4px;
  font-size: 11px;
  color: #6B7280;
}

.meta-tag.expanded {
  background: #ECFDF5;
  color: #059669;
}

.meta-tag.not-expanded {
  background: #FEF3C7;
  color: #D97706;
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.btn-expand,
.btn-chat {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: #ffffff;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.btn-expand:hover:not(:disabled) {
  background: #ECFDF5;
  border-color: #A7F3D0;
  color: #059669;
}

.btn-chat:hover:not(:disabled) {
  background: #EEF2FF;
  border-color: #C7D2FE;
  color: #4F46E5;
}

.btn-expand:disabled,
.btn-chat:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 14px;
}

/* 聊天区域 */
.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.chat-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin: 0;
  padding: 14px 20px 2px;
}

.chat-subtitle {
  font-size: 12px;
  color: #9CA3AF;
  margin: 0;
  padding: 0 20px 10px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-messages::-webkit-scrollbar {
  width: 4px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 2px;
}

.message {
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message.agent {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.message.user .message-bubble {
  background: #4F46E5;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.agent .message-bubble {
  background: #F3F4F6;
  color: #1F2937;
  border-bottom-left-radius: 4px;
}

/* 节点引用高亮 */
.message-content :deep(.node-ref) {
  background: linear-gradient(135deg, #EEF2FF, #EDE9FE);
  color: #4F46E5;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #C7D2FE;
  transition: all 0.15s ease;
}

.message-content :deep(.node-ref:hover) {
  background: #4F46E5;
  color: white;
}

.suggestion-hint {
  margin-top: 8px;
  padding: 6px 10px;
  background: #FEF3C7;
  border-radius: 6px;
  font-size: 11px;
  color: #92400E;
}

/* 输入中动画 */
.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  background: #9CA3AF;
  border-radius: 50%;
  animation: typingBounce 1.4s ease-in-out infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typingBounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-6px);
  }
}

/* 空状态 */
.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #9CA3AF;
  padding: 40px 20px;
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 8px;
  opacity: 0.6;
}

.chat-empty p {
  margin: 0;
  font-size: 13px;
}

.empty-hint {
  font-size: 12px;
  margin-top: 4px;
  color: #D1D5DB;
}

/* 聊天输入区 */
.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 12px 16px 16px;
  border-top: 1px solid #F3F4F6;
}

.chat-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  background: #F9FAFB;
  font-size: 13px;
  color: #374151;
  resize: none;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  line-height: 1.5;
}

.chat-input:focus {
  background: #ffffff;
  border-color: #4F46E5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.chat-input::placeholder {
  color: #9CA3AF;
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-send {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 10px;
  background: #4F46E5;
  color: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  align-self: flex-end;
}

.btn-send:hover:not(:disabled) {
  background: #4338CA;
  transform: scale(1.05);
}

.btn-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
