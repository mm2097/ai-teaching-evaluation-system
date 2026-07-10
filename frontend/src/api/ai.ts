/**
 * AI 能力 & 报告 API
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

/** 报告 API 返回类型 */
export interface ReportResponse {
  summary: string
  conclusion: string
  suggestion: string
  source: string
  scope?: string
  report_type?: number
  report_type_name?: string
  error?: string
}

/** 生成练习题（当前返回空，后续接入 AI 服务） */
export async function generateExercises(_params: AIQuestionParams): Promise<GeneratedQuestion[]> {
  return []
}

/** 生成报告（统一接口，后端按 report_type 返回不同内容） */
export async function generateReport(params: {
  courseId: number
  reportType: 1 | 2 | 3 | 4
  classId?: number
  studentId?: number
}): Promise<ReportResponse> {
  const { data } = await request.get('/v1/report', {
    params: {
      course_id: params.courseId,
      report_type: params.reportType,
      class_id: params.classId,
      student_id: params.studentId,
    },
  })
  return data
}
