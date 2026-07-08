/**
 * AI 分析 API（模拟后端 /api/analysis/* 接口）
 */
import { delay } from '@/utils/auth'
import { findStudentProfile, gradeTrendData, gradeTrendFactors, warningRecords } from '@/mock'
import {
  buildCourseClassHeatmap,
  buildPersonalKnowledgeHeatmap,
  courses,
  getKnowledgePointsByCourse,
  getStudentMastery,
  getStudentsInCourseClass,
} from '@/mock/dict'
import type { AnalysisQuery, StudentProfileData, TargetType, WarningRecord } from '@/types'

export interface KnowledgeHeatmapResult {
  knowledgePoints: string[]
  students: string[]
  data: number[][]
  /** 各知识点班级平均掌握度（个人视角用于对比） */
  classAvgByKp?: number[]
}

function getWeakLevel(rate: number): '严重' | '中等' | '轻微' {
  if (rate < 60) return '严重'
  if (rate < 75) return '中等'
  return '轻微'
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
    return { name, rate, weakCount, level: getWeakLevel(rate) }
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
  await delay(300)
  if (query.targetType === 'student' && query.targetId) {
    const profile = findStudentProfile(query.targetId, query.courseId)
    if (profile) {
      const { courseId: _cid, ...data } = profile
      return data
    }
  }
  return null
}

/** 获取成绩趋势数据（按班级/课程微调） */
export async function fetchGradeTrend(query: AnalysisQuery) {
  await delay(300)
  const classFactor = query.classId ? (gradeTrendFactors[`class-${query.classId}`] ?? 1) : 1
  const courseFactor = query.courseId ? (gradeTrendFactors[`course-${query.courseId}`] ?? 1) : 1
  const factor = classFactor * courseFactor

  return {
    months: gradeTrendData.months,
    avgScore: gradeTrendData.avgScore.map((v) => Math.round(v * factor)),
    passRate: gradeTrendData.passRate.map((v) => Math.min(100, Math.round(v * factor))),
    maxScore: gradeTrendData.maxScore.map((v) => Math.min(100, Math.round(v * factor))),
    minScore: gradeTrendData.minScore.map((v) => Math.round(v * factor)),
  }
}

/** 获取知识点热力图数据 */
export async function fetchKnowledgeHeatmap(query: AnalysisQuery): Promise<KnowledgeHeatmapResult> {
  await delay(300)

  if (!query.courseId) {
    return { knowledgePoints: [], students: [], data: [] }
  }

  if (query.targetType === 'student') {
    if (!query.targetId) {
      return {
        knowledgePoints: getKnowledgePointsByCourse(query.courseId),
        students: [],
        data: [],
      }
    }
    const personal = buildPersonalKnowledgeHeatmap(
      query.targetId,
      query.courseId,
      query.classId,
    )
    return {
      knowledgePoints: personal.knowledgePoints,
      students: personal.students,
      data: personal.data,
      classAvgByKp: personal.classAvgByKp,
    }
  }

  const classId = query.classId ?? query.targetId
  if (!classId) {
    return {
      knowledgePoints: getKnowledgePointsByCourse(query.courseId),
      students: [],
      data: [],
    }
  }

  const heatmap = buildCourseClassHeatmap(query.courseId, classId)
  const classStats = computeClassKnowledgeStats(heatmap)
  return {
    ...heatmap,
    classAvgByKp: classStats.classAvgByKp,
  }
}

/** 获取预警记录（带筛选，教师仅看本人授课范围） */
export async function fetchWarnings(query: AnalysisQuery & {
  level?: string
  type?: string
  status?: number
  teacherId?: number
}): Promise<WarningRecord[]> {
  await delay(300)

  let teacherCourseIds: number[] | undefined
  if (query.teacherId) {
    teacherCourseIds = courses.filter((c) => c.teacherId === query.teacherId).map((c) => c.id)
  }

  return warningRecords.filter((w) => {
    if (query.deptId && w.deptId !== query.deptId) return false
    if (query.classId && w.classId !== query.classId) return false
    if (query.semesterId && w.semesterId !== query.semesterId) return false
    if (query.courseId && w.courseId !== query.courseId) return false
    if (query.level && w.level !== query.level) return false
    if (query.type && w.type !== query.type) return false
    if (query.status !== undefined && query.status !== null && w.status !== query.status) return false
    if (teacherCourseIds && w.courseId && !teacherCourseIds.includes(w.courseId)) return false
    if (query.studentNo && w.studentId !== query.studentNo) return false
    return true
  })
}

/** 获取某课程某班级学生成绩预测列表 */
export async function fetchGradePredictions(query: AnalysisQuery) {
  await delay(200)
  if (!query.courseId || !query.classId) return []

  const studentsInClass = getStudentsInCourseClass(query.courseId, query.classId)
  return studentsInClass.map((s) => {
    const mastery = getStudentMastery(s.id, query.courseId!)
    const current = mastery?.length
      ? Math.round(mastery.reduce((a, b) => a + b, 0) / mastery.length)
      : 70
    const delta = current >= 85 ? 3 : current >= 70 ? 0 : -4
    const low = Math.max(0, current + delta - 3)
    const high = Math.min(100, current + delta + 3)
    const trend = delta > 1 ? '上升' : delta < -1 ? '下滑' : '稳定'
    return {
      name: s.studentName,
      current,
      predicted: `${low}-${high}`,
      trend,
      confidence: Math.min(95, 70 + Math.floor(current / 5)),
    }
  })
}

/** 分析对象类型选项（单课程/单班级维度） */
export const targetTypeOptions: { label: string; value: TargetType }[] = [
  { label: '学生', value: 'student' },
  { label: '班级', value: 'class' },
]
