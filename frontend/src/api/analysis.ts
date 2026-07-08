/**
 * AI 分析 API（调用真实后端 /api/v1/analysis/*）
 */
import request from '@/utils/request'
import type { AnalysisQuery, StudentProfileData, TargetType, WarningRecord } from '@/types'

export interface KnowledgeHeatmapResult {
  knowledgePoints: string[]
  students: string[]
  data: number[][]
  classAvgByKp?: number[]
}

/** 从热力图数据计算班级统计 */
export function computeClassKnowledgeStats(heatmap: KnowledgeHeatmapResult) {
  const { knowledgePoints, data } = heatmap
  const kpStats = knowledgePoints.map((name, kpIdx) => {
    const values = data.filter((d) => d[0] === kpIdx).map((d) => d[2]!)
    const rate = values.length
      ? Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10
      : 0
    const weakCount = values.filter((v) => v < 75).length
    const level: '严重' | '中等' | '轻微' = rate < 60 ? '严重' : rate < 75 ? '中等' : '轻微'
    return { name, rate, weakCount, level }
  })
  const allValues = data.map((d) => d[2]!)
  const avgRate = allValues.length
    ? Math.round((allValues.reduce((a, b) => a + b, 0) / allValues.length) * 10) / 10
    : 0
  const sorted = [...kpStats].sort((a, b) => a.rate - b.rate)
  const needAttentionCount = new Set(
    data.filter((d) => d[2]! < 75).map((d) => d[1]),
  ).size
  return {
    avgRate,
    lowest: sorted[0] ?? { name: '-', rate: 0, weakCount: 0, level: '轻微' as const },
    highest: sorted[sorted.length - 1] ?? { name: '-', rate: 0, weakCount: 0, level: '轻微' as const },
    needAttentionCount,
    weakPoints: kpStats.filter((p) => p.rate < 75).sort((a, b) => a.rate - b.rate),
    classAvgByKp: kpStats.map((p) => p.rate),
  }
}

/** 获取学情画像 */
export async function fetchStudentProfile(query: AnalysisQuery): Promise<StudentProfileData | null> {
  if (query.targetType !== 'student' || !query.targetId) return null
  try {
    const res = await request.get('/v1/analysis/profile', {
      params: { student_id: query.targetId, course_id: query.courseId },
    })
    return res.data || null
  } catch {
    return null
  }
}

/** 获取成绩趋势数据 */
export async function fetchGradeTrend(query: AnalysisQuery) {
  try {
    const res = await request.get('/v1/dashboard/grade-trend', {
      params: {
        course_id: query.courseId,
        class_id: query.targetType === 'class' ? query.classId : query.classId,
        student_id: query.targetType === 'student' ? query.targetId : undefined,
      },
    })
    return res.data
  } catch {
    return { months: [], avgScore: [], passRate: [], maxScore: [], minScore: [] }
  }
}

/** 获取知识点热力图数据 */
export async function fetchKnowledgeHeatmap(query: AnalysisQuery): Promise<KnowledgeHeatmapResult> {
  try {
    const res = await request.get('/v1/analysis/knowledge-heatmap', {
      params: {
        course_id: query.courseId,
        class_id: query.targetType === 'class' ? query.targetId : query.classId,
        student_id: query.targetType === 'student' ? query.targetId : undefined,
      },
    })
    return res.data
  } catch {
    return { knowledgePoints: [], students: [], data: [] }
  }
}

/** 获取预警记录 */
export async function fetchWarnings(query: AnalysisQuery & {
  level?: string
  type?: string
  status?: number
  teacherId?: number
}): Promise<WarningRecord[]> {
  try {
    const res = await request.get('/v1/analysis/warnings', {
      params: {
        course_id: query.courseId,
        class_id: query.classId,
        level: query.level,
      },
    })
    return res.data
  } catch {
    return []
  }
}

/** 获取成绩预测列表 */
export async function fetchGradePredictions(query: AnalysisQuery) {
  try {
    const res = await request.get('/v1/analysis/grade-predictions', {
      params: { course_id: query.courseId, class_id: query.classId },
    })
    return res.data
  } catch {
    return []
  }
}

/** 分析对象类型选项 */
export const targetTypeOptions: { label: string; value: TargetType }[] = [
  { label: '学生', value: 'student' },
  { label: '班级', value: 'class' },
]
