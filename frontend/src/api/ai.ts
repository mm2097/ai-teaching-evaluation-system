/**
 * AI 能力 API（预留，需要 AI 服务对接）
 */
import request from '@/utils/request'

export interface AIQuestionParams {
  knowledgePoint: string
  count: number
  types: string[]
}

export interface GeneratedQuestion {
  content: string
  type: string
  options?: string[]
  answer: string
  knowledgePoint: string
  difficulty: string
}

/** 生成练习题（当前返回空，后续接入 AI 服务） */
export async function generateExercises(_params: AIQuestionParams): Promise<GeneratedQuestion[]> {
  return []
}

/** 生成 AI 分析报告（当前返回空，后续接入 AI 服务） */
export async function generateAiReport(_studentId: string, _courseName: string): Promise<string> {
  return 'AI 分析服务对接中，敬请期待...'
}
