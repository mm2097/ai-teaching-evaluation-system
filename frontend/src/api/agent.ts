/**
 * Agent 对话 API
 * 对齐 AI_Agent_设计方案 SSE 流式接口
 */
import { getToken } from '@/utils/auth'
import { mockAgentStream } from '@/mock/agent'
import type { AgentStreamEvent, AgentType } from '@/types'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export interface AgentChatParams {
  agentType: AgentType
  courseId: number
  courseName: string
  message: string
  sessionId?: string
}

/** 流式对话（优先 SSE，演示环境使用 mock generator） */
export async function* streamAgentChat(params: AgentChatParams): AsyncGenerator<AgentStreamEvent> {
  if (USE_MOCK) {
    yield* mockAgentStream({
      courseId: params.courseId,
      courseName: params.courseName,
      agentType: params.agentType,
      message: params.message,
    })
    return
  }

  const token = getToken()
  const response = await fetch('/api/v1/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      agent_type: params.agentType,
      course_id: params.courseId,
      message: params.message,
      session_id: params.sessionId,
    }),
  })

  if (!response.ok) {
    const detail = await response.text()
    yield { type: 'error', message: detail || 'Agent 服务暂不可用' }
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    yield { type: 'error', message: '无法读取流式响应' }
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (!payload || payload === '[DONE]') continue
      try {
        yield JSON.parse(payload) as AgentStreamEvent
      } catch {
        // 忽略非 JSON 行
      }
    }
  }
}
