/**
 * AI Agent API（学情问答 + 组卷 Agent）
 * 对接后端 /api/v1/agent/chat 和 /api/v1/agent/chat/stream
 */
import request, { USE_MOCK } from '@/utils/request'
import type { AgentType, AgentStreamEvent } from '@/types'
import { mockStreamAgentChat } from '@/mock/agentMock'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface StreamAgentChatParams {
  agentType: AgentType
  courseId: number
  courseName?: string
  message: string
}

/**
 * 流式 Agent 对话（SSE）。
 *
 * 后端事件类型 → 前端 AgentStreamEvent 映射：
 *   step_start  → thinking
 *   tool_call   → tool_call
 *   tool_result → tool_result
 *   content     → content_done
 *   done        → 跳过（已由 content 处理）
 *   error       → error
 */
export async function* streamAgentChat(
  params: StreamAgentChatParams,
): AsyncGenerator<AgentStreamEvent> {
  // Mock 模式：走本地流式生成器
  if (USE_MOCK) {
    yield* mockStreamAgentChat(params.message)
    return
  }

  const res = await fetch('/api/v1/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: params.message,
      course_id: params.courseId,
      agent_type: params.agentType,
      max_steps: 5,
    }),
  })

  if (!res.ok || !res.body) {
    throw new Error(`Agent 请求失败（${res.status}）`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  // 工具调用 id 映射：step+name → 生成唯一 id
  let toolCallCounter = 0

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const jsonStr = trimmed.slice(5).trim()
        if (!jsonStr) continue

        let evt: Record<string, unknown>
        try {
          evt = JSON.parse(jsonStr)
        } catch {
          continue
        }

        const type = evt.type as string

        if (type === 'step_start') {
          yield { type: 'thinking' }

        } else if (type === 'tool_call') {
          const id = `tc-${++toolCallCounter}`
          yield {
            type: 'tool_call',
            call: {
              id,
              tool: evt.name as string,
              params: (evt.arguments as Record<string, unknown>) || {},
              status: 'running' as const,
            },
          }

        } else if (type === 'tool_result') {
          // 匹配最后一个同名工具调用
          const name = evt.name as string
          yield {
            type: 'tool_result',
            callId: `tc-${toolCallCounter}`,
            result: evt.result,
            summary: _summarizeResult(name, evt.result),
          }

        } else if (type === 'content') {
          yield {
            type: 'content_done',
            content: (evt.content as string) || '',
            sources: [],
          }

        } else if (type === 'error') {
          yield {
            type: 'error',
            message: (evt.message as string) || 'Agent 处理失败',
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** 根据工具名+结果生成人类可读摘要 */
function _summarizeResult(toolName: string, result: unknown): string {
  if (!result || typeof result !== 'object') return ''
  const r = result as Record<string, unknown>
  // 常见字段
  if ('count' in r || 'student_count' in r) {
    return `${r.student_count ?? r.count ?? 0} 条数据`
  }
  if ('scores' in r && Array.isArray(r.scores)) {
    return `${r.scores.length} 条成绩`
  }
  if ('trend' in r && Array.isArray(r.trend)) {
    return `${r.trend.length} 个数据点`
  }
  if ('points' in r && Array.isArray(r.points)) {
    return `${r.points.length} 个知识点`
  }
  return ''
}
