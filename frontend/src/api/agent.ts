/**
 * AI 智能助手 API（预留，需要 AI 服务对接）
 */
import request from '@/utils/request'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

/** 发送消息（当前返回占位回复，后续接入 AI 服务） */
export async function sendMessage(_content: string, _context?: string): Promise<ChatMessage> {
  return {
    role: 'assistant',
    content: 'AI 智能助手对接中，请稍后再试...',
    timestamp: Date.now(),
  }
}
