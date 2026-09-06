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
export interface ReportChartKnowledge {
  name: string
  accuracy: number
  level?: string
}

export interface ReportChartBucket {
  label: string
  count: number
}

export interface ReportCharts {
  focus?: 'class' | 'student' | 'knowledge' | 'quality'
  scoreBuckets?: ReportChartBucket[]
  knowledge?: ReportChartKnowledge[]
  radar?: Record<string, number>
  evalIndexes?: { name: string; score: number; weight?: number }[]
  academicParts?: { name: string; weight?: number; score?: number | null; part?: string }[]
  rates?: {
    avgScore?: number
    passRate?: number
    excellentRate?: number
    attendanceRate?: number
  }
  scoreHistory?: { name: string; score: number }[]
}

export interface ReportEvalIndex {
  id?: number
  name: string
  weight?: number
  score?: number | null
}

export interface ReportEvalDimension {
  id?: number
  name: string
  description?: string
  score?: number | null
  indexes?: ReportEvalIndex[]
}

export interface ReportResponse {
  summary: string
  conclusion: string
  suggestion: string
  source: string
  scope?: string
  report_type?: number
  report_type_name?: string
  error?: string
  charts?: ReportCharts
  findings?: string[]
  warnings?: ReportWarningItem[]
  metrics?: Record<string, string | number>
  evalScheme?: ReportEvalDimension[]
  academicParts?: { name: string; weight?: number; score?: number | null }[]
}

export interface ReportWarningItem {
  student_id?: number
  name: string
  level: string
  reasons?: string[]
}

export interface ReportHistoryItem {
  id: number
  name: string
  type: string
  time: string
  format: string
  reportType: 1 | 2 | 3 | 4
  courseId: number
  classId?: number | null
  studentId?: number | null
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
  recordHistory?: boolean
}): Promise<ReportResponse> {
  const { data } = await request.get('/v1/report', {
    params: {
      course_id: params.courseId,
      report_type: params.reportType,
      class_id: params.classId,
      student_id: params.studentId,
      record_history: params.recordHistory,
    },
  })
  return data
}

function parseDownloadFilename(disposition: string, fallback: string): string {
  const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/)
  if (rfc5987) return decodeURIComponent(rfc5987[1]!)
  const ascii = disposition.match(/filename="?([^";\s]+)"?/)
  return ascii ? ascii[1]! : fallback
}

export async function exportReportFile(params: {
  courseId: number
  reportType: 1 | 2 | 3 | 4
  classId?: number
  studentId?: number
}): Promise<{ blob: Blob; filename: string }> {
  const res = await request.get('/v1/report/export', {
    params: {
      course_id: params.courseId,
      report_type: params.reportType,
      class_id: params.classId,
      student_id: params.studentId,
      format: 'xlsx',
    },
    responseType: 'blob',
  })
  const disposition = (res.headers as Record<string, string>)['content-disposition'] ?? ''
  return {
    blob: res.data as Blob,
    filename: parseDownloadFilename(disposition, `report_type${params.reportType}.xlsx`),
  }
}
export async function fetchReportHistory(): Promise<ReportHistoryItem[]> {
  const { data } = await request.get('/v1/report/history')
  return data as ReportHistoryItem[]
}

