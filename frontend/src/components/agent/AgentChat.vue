<!--
  Agent 对话组件
  展示 SSE 流式工具调用过程与最终回答
-->
<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Tools, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { streamAgentChat, clearAgentSession } from '@/api/agent'
import type { AgentMessage, AgentToolCall, AgentType } from '@/types'

const props = defineProps<{
  agentType: AgentType
  courseId: number
  courseName: string
}>()

const messages = ref<AgentMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const chatBodyRef = ref<HTMLElement>()
const expandedTools = ref<Set<string>>(new Set())

/** 会话 ID：按 (agentType, courseId) 稳定，供后端保持/清空多轮记忆 */
const sessionId = computed(() => `${props.agentType}_c${props.courseId}`)

const isStudent = computed(() => props.agentType === 'tutor')

const agentTitle = computed(() => {
  const map: Record<AgentType, string> = {
    qa: '学情问答助手',
    exam: '自适应组卷助手',
    tutor: '学生助学助手',
  }
  return map[props.agentType]
})

const placeholder = computed(() => {
  const map: Record<AgentType, string> = {
    qa: '例如：这次期中谁退步最明显？班里哪个知识点最差？',
    exam: '例如：给班级出 10 道 medium 难度的薄弱点题',
    tutor: '例如：帮我讲解红黑树的旋转操作',
  }
  return map[props.agentType]
})

const quickPrompts = computed(() => {
  if (props.agentType === 'exam') {
    return ['出 10 道中等难度薄弱点题', '针对红黑树出 5 道题', '组一套期中复习卷']
  }
  if (props.agentType === 'tutor') {
    return ['红黑树是什么？', '帮我分析这道错题', '二叉树遍历怎么记？']
  }
  return ['班里均分和及格率多少？', '期中谁退步最明显？', '张三最近状态怎么样？', '有哪些同学被预警了？']
})

watch(
  () => props.courseId,
  (_next, prev) => {
    // 切课时清空当前会话（本地 + 后端记忆）
    if (prev !== undefined) {
      clearAgentSession(`${props.agentType}_c${prev}`)
    }
    messages.value = []
  },
)

/** 清空对话：重置消息并清除后端会话记忆 */
async function handleClear(): Promise<void> {
  if (sending.value) return
  messages.value = []
  expandedTools.value.clear()
  await clearAgentSession(sessionId.value)
  ElMessage.success('已清空对话')
}

function scrollToBottom(): void {
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}

function toggleToolExpand(id: string): void {
  if (expandedTools.value.has(id)) {
    expandedTools.value.delete(id)
  } else {
    expandedTools.value.add(id)
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatContent(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
}

async function handleSend(text?: string): Promise<void> {
  const content = (text ?? inputText.value).trim()
  if (!content || sending.value) return
  if (!props.courseId) {
    ElMessage.warning('请先选择课程')
    return
  }

  inputText.value = ''
  sending.value = true

  const userMsg: AgentMessage = {
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    timestamp: Date.now(),
  }
  messages.value.push(userMsg)

  const assistantMsg: AgentMessage = {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    toolCalls: [],
    timestamp: Date.now(),
    streaming: true,
  }
  messages.value.push(assistantMsg)
  scrollToBottom()

  try {
    const stream = streamAgentChat({
      agentType: props.agentType,
      courseId: props.courseId,
      courseName: props.courseName,
      message: content,
      sessionId: sessionId.value,
    })

    for await (const event of stream) {
      if (event.type === 'thinking') {
        assistantMsg.content = '思考中…'
        scrollToBottom()
      } else if (event.type === 'tool_call') {
        assistantMsg.content = ''
        assistantMsg.toolCalls = assistantMsg.toolCalls || []
        assistantMsg.toolCalls.push({ ...event.call })
        scrollToBottom()
      } else if (event.type === 'tool_result') {
        const call = assistantMsg.toolCalls?.find((c) => c.id === event.callId)
        if (call) {
          call.status = 'done'
          call.result = event.result
          call.summary = event.summary
        }
        scrollToBottom()
      } else if (event.type === 'content_delta') {
        assistantMsg.content = (assistantMsg.content === '思考中…' ? '' : assistantMsg.content) + event.delta
        scrollToBottom()
      } else if (event.type === 'content_done') {
        assistantMsg.content = event.content
        assistantMsg.sources = event.sources
        assistantMsg.streaming = false
        scrollToBottom()
      } else if (event.type === 'error') {
        assistantMsg.content = event.message
        assistantMsg.streaming = false
        ElMessage.error(event.message)
      }
    }
  } catch (err) {
    assistantMsg.content = '对话失败，请稍后重试'
    assistantMsg.streaming = false
    ElMessage.error(err instanceof Error ? err.message : '对话失败')
  } finally {
    if (assistantMsg.streaming && !assistantMsg.content && !assistantMsg.toolCalls?.length) {
      assistantMsg.content = '未收到有效回复，请重试'
    }
    assistantMsg.streaming = false
    sending.value = false
    scrollToBottom()
  }
}

function renderToolResult(call: AgentToolCall): string {
  return JSON.stringify(call.result, null, 2)
}
</script>

<template>
  <div class="agent-chat">
    <div ref="chatBodyRef" class="agent-chat__body">
      <div v-if="!messages.length" class="agent-chat__welcome">
        <el-icon :size="48" color="#2563eb"><DataAnalysis /></el-icon>
        <h3>{{ agentTitle }}</h3>
        <p>当前课程：{{ courseName || '未选择' }}</p>
        <p class="hint">{{ isStudent ? '我只给思路提示，不直接给答案，帮你自己想明白' : '我会调用数据库查询工具，给出有数据支撑的回答' }}</p>
        <div class="quick-prompts">
          <el-tag
            v-for="prompt in quickPrompts"
            :key="prompt"
            class="quick-tag"
            effect="plain"
            @click="handleSend(prompt)"
          >
            {{ prompt }}
          </el-tag>
        </div>
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        <div class="message__avatar">{{ msg.role === 'user' ? (isStudent ? '我' : '师') : 'AI' }}</div>
        <div class="message__bubble">
          <!-- 工具调用过程 -->
          <div v-if="msg.toolCalls?.length" class="tool-calls">
            <div v-for="call in msg.toolCalls" :key="call.id" class="tool-call-card">
              <div class="tool-call-header" @click="toggleToolExpand(call.id)">
                <el-icon><Tools /></el-icon>
                <span>调用 {{ call.tool }}({{ JSON.stringify(call.params) }})</span>
                <el-tag v-if="call.status === 'running'" size="small" type="warning">执行中</el-tag>
                <el-tag v-else size="small" type="success">完成</el-tag>
              </div>
              <div v-if="call.summary" class="tool-call-summary">返回：{{ call.summary }}</div>
              <el-collapse-transition>
                <pre v-if="expandedTools.has(call.id)" class="tool-call-json">{{ renderToolResult(call) }}</pre>
              </el-collapse-transition>
            </div>
          </div>

          <!-- 回答内容 -->
          <div
            v-if="msg.content"
            class="message__content"
            :class="{ streaming: msg.streaming }"
            v-html="formatContent(msg.content)"
          />

          <!-- 数据来源 -->
          <div v-if="msg.sources?.length" class="message__sources">
            <span>📊 数据来源：{{ msg.sources.length }} 个工具</span>
            <el-tag v-for="src in msg.sources" :key="src" size="small" type="info">{{ src }}</el-tag>
          </div>
        </div>
      </div>
    </div>

    <div class="agent-chat__input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        :placeholder="placeholder"
        :disabled="sending"
        resize="none"
        @keydown.enter.exact.prevent="handleSend()"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :loading="sending"
        :disabled="!inputText.trim()"
        @click="handleSend()"
      >
        发送
      </el-button>
      <el-button
        :icon="Delete"
        :disabled="sending || !messages.length"
        @click="handleClear"
        title="清空对话"
      >
        清空
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.agent-chat {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.agent-chat__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
}

.agent-chat__welcome {
  text-align: center;
  padding: 40px 20px;
  color: #64748b;

  h3 {
    margin: 16px 0 8px;
    color: #1e293b;
  }

  .hint {
    font-size: 13px;
    margin-bottom: 20px;
  }

  .quick-prompts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }

  .quick-tag {
    cursor: pointer;

    &:hover {
      border-color: #2563eb;
      color: #2563eb;
    }
  }
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  min-width: 0;

  &.user {
    flex-direction: row-reverse;

    .message__bubble {
      background: #2563eb;
      color: #fff;
    }

    .message__avatar {
      background: #dbeafe;
      color: #2563eb;
    }
  }

  &.assistant .message__bubble {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
  }
}

.message__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #eff6ff;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.message__bubble {
  max-width: 75%;
  min-width: 0;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  overflow-wrap: break-word;
  word-break: break-word;
}

.message__content.streaming::after {
  content: '▋';
  animation: blink 1s infinite;
  color: #2563eb;
}

@keyframes blink {
  50% { opacity: 0; }
}

.tool-calls {
  margin-bottom: 12px;
}

.tool-call-card {
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  font-size: 13px;
  max-width: 100%;
  overflow: hidden;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #475569;
  min-width: 0;

  span {
    flex: 1;
    min-width: 0;
    font-family: monospace;
    font-size: 12px;
    overflow-wrap: anywhere;
    word-break: break-all;
  }
}

.tool-call-summary {
  margin-top: 6px;
  padding: 6px 8px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #334155;
  font-size: 12px;
}

.tool-call-json {
  margin-top: 8px;
  padding: 8px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 4px;
  font-size: 11px;
  overflow-x: auto;
}

.message__sources {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.agent-chat__input {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #e2e8f0;
  background: #fafafa;
  flex-shrink: 0;

  .el-button {
    align-self: flex-end;
    flex-shrink: 0;
  }
}
</style>
