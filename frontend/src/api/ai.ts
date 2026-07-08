/**
 * AI 服务 API
 * 对齐 AI算法_需求与开发文档 第 7 章
 */
import request from '@/utils/request'
import { delay } from '@/utils/auth'
import { mockGenerateExercises, mockAiReport } from '@/mock/ai'
import type { AiReportResult, GenerateExerciseParams, GenerateExerciseResult } from '@/types'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

/** AI 生成练习题 */
export async function generateExercises(params: GenerateExerciseParams): Promise<GenerateExerciseResult> {
  if (USE_MOCK) {
    await delay(1500)
    return mockGenerateExercises(params)
  }

  const { data } = await request.post<GenerateExerciseResult>('/v1/ai/exercises/generate', params)
  return data
}

/** AI 生成报告结论与建议 */
export async function generateAiReport(params: {
  courseId: number
  scope?: 'class' | 'student'
}): Promise<AiReportResult> {
  if (USE_MOCK) {
    await delay(2000)
    return { ...mockAiReport }
  }

  const { data } = await request.post<AiReportResult>('/v1/ai/report/generate', params)
  return data
}
