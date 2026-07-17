/**
 * AI 能力 & 报告 API
 */
import request from '@/utils/request'
import { generateQuizQuestions } from '@/api/quiz'

export interface AIQuestionParams {
  courseId?: number
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

/** 生成练习题（兼容旧调用，实际走后端 AI 出题代理） */
export async function generateExercises(params: AIQuestionParams): Promise<GeneratedQuestion[]> {
  const result = await generateQuizQuestions({
    courseId: params.courseId ?? 1,
    classId: 0,
    knowledgePoints: params.knowledgePoint ? [params.knowledgePoint] : [],
    questionTypes: params.types as any,
    questionCount: params.count,
    difficulty: 'medium',
  })
  return result.questions.map((question) => ({
    content: question.stem,
    type: question.type,
    options: question.options?.map((option) => option.text),
    answer: question.answer,
    knowledgePoint: question.knowledgePoint,
    difficulty: question.difficulty,
  }))
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
