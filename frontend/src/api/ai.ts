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
  error?: string
}

/** 生成练习题（当前返回空，后续接入 AI 服务） */
export async function generateExercises(_params: AIQuestionParams): Promise<GeneratedQuestion[]> {
  return []
}

/** 生成班级学情报告 */
export async function generateClassReport(courseId: number, classId?: number): Promise<ReportResponse> {
  const { data } = await request.get('/v1/report/class', {
    params: { course_id: courseId, class_id: classId },
  })
  return data
}

/** 生成学生个人报告 */
export async function generateStudentReport(studentId: number, courseId: number): Promise<ReportResponse> {
  const { data } = await request.get('/v1/report/student', {
    params: { student_id: studentId, course_id: courseId },
  })
  return data
}

/** @deprecated 使用 generateClassReport / generateStudentReport 替代 */
export async function generateAiReport(_studentId: string, _courseName: string): Promise<string> {
  return 'AI 分析服务对接中，敬请期待...'
}
