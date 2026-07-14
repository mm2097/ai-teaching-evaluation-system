/**
 * 学生学习质量评价 API
 * 对应 backend/app/api/v1/evaluations.py 三个接口
 */
import request from '@/utils/request'

export interface EvalDimensionScore {
  dimensionId: number
  name: string
  score: number
  weight: number
}

/** GET /evaluations 返回项 */
export interface StudentEvaluationItem {
  id: number
  studentDbId: number
  studentId: string
  studentName: string
  targetName: string
  targetType: string
  courseId: number
  courseName: string
  totalScore: number
  grade: string
  dimensions: EvalDimensionScore[]
}

/** GET /evaluations/results 返回项 */
export interface EvaluationResultItem {
  id: number
  studentId: number
  studentName: string
  courseId: number
  totalScore: number
  grade: string
  computed?: boolean
}

export interface ScoreBucket {
  range: string
  low: number
  high: number
  count: number
  ratio: number
}

/** GET /evaluations/distribution 返回体 */
export interface EvaluationDistribution {
  courseId: number
  courseName: string
  classId?: number | null
  totalStudents: number
  levelDistribution: Record<string, number>
  levelRatio?: Record<string, number>
  dominantLevel?: string
  scoreDistribution?: ScoreBucket[]
  statistics: {
    mean?: number
    median?: number
    stdDev?: number
    maxScore?: number
    minScore?: number
  }
  characteristic: string
}

const GRADE_TAG: Record<string, 'success' | 'primary' | 'warning' | 'info' | 'danger'> = {
  优: 'success',
  良: 'primary',
  中: 'warning',
  差: 'danger',
  优秀: 'success',
  良好: 'primary',
  中等: 'warning',
  不及格: 'danger',
  合格: 'info',
  不合格: 'danger',
}

export function evalGradeTagType(grade: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
  return GRADE_TAG[grade] || 'info'
}

/**
 * GET /evaluations
 * 参数：course_id、eval_level（与 DB eval_level 精确匹配）、student_id
 */
export async function fetchEvaluations(params?: {
  courseId?: number
  evalLevel?: string
  studentId?: number
}): Promise<StudentEvaluationItem[]> {
  const q: Record<string, string | number> = {}
  if (params?.courseId) q.course_id = params.courseId
  if (params?.evalLevel) q.eval_level = params.evalLevel
  if (params?.studentId) q.student_id = params.studentId
  const res = await request.get('/v1/evaluations', { params: q })
  return res.data ?? []
}

/**
 * GET /evaluations/results
 * 参数：student_id、course_id、dept_id；按 eval_id 正序，最后一条为最新
 */
export async function fetchEvaluationResults(params?: {
  studentId?: number
  courseId?: number
  deptId?: number
}): Promise<EvaluationResultItem[]> {
  const q: Record<string, number> = {}
  if (params?.studentId) q.student_id = params.studentId
  if (params?.courseId) q.course_id = params.courseId
  if (params?.deptId) q.dept_id = params.deptId
  const res = await request.get('/v1/evaluations/results', { params: q })
  return res.data ?? []
}

/**
 * GET /evaluations/distribution
 * 参数：course_id（必填）、class_id
 */
export async function fetchEvaluationDistribution(params: {
  courseId: number
  classId?: number
}): Promise<EvaluationDistribution> {
  const q: Record<string, number> = { course_id: params.courseId }
  if (params.classId) q.class_id = params.classId
  const res = await request.get('/v1/evaluations/distribution', { params: q })
  return res.data
}
