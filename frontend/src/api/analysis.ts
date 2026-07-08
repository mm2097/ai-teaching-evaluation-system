/**
 * AI 分析 API（模拟后端 /api/analysis/* 接口）
 */
import { delay } from '@/utils/auth'
import { findStudentProfile, gradeTrendData, gradeTrendFactors, warningRecords, buildClassProfile } from '@/mock'
import {
  buildCourseClassHeatmap,
  buildPersonalKnowledgeHeatmap,
  courses,
  getKnowledgePointsByCourse,
  getStudentMastery,
  getStudentsInCourseClass,
} from '@/mock/dict'
import type {
  AnalysisQuery,
  ClassProfileData,
  GradePredictionItem,
  GradeTrendData,
  StudentGradePrediction,
  StudentGradeTrendData,
  StudentProfileData,
  TargetType,
  WarningRecord,
} from '@/types'

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

/** 获取班级学情画像 */
export async function fetchClassProfile(query: AnalysisQuery): Promise<ClassProfileData | null> {
  await delay(350)
  const classId = query.classId ?? query.targetId
  if (!classId || !query.courseId) return null

  const profile = buildClassProfile(classId, query.courseId)
  if (!profile) return null

  const warningCount = warningRecords.filter(
    (w) => w.classId === classId && w.courseId === query.courseId && w.status !== 2,
  ).length

  return { ...profile, warningCount }
}

/** 获取成绩趋势数据（班级维度，按班级/课程微调） */
export async function fetchGradeTrend(query: AnalysisQuery): Promise<GradeTrendData> {
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

function getStudentCurrentScore(studentId: number, courseId: number): number {
  const mastery = getStudentMastery(studentId, courseId)
  if (mastery?.length) {
    return Math.round(mastery.reduce((a, b) => a + b, 0) / mastery.length)
  }
  const profile = findStudentProfile(studentId, courseId)
  return profile?.dimensionScores[0]?.score ?? 70
}

function buildPrediction(current: number): Pick<GradePredictionItem, 'predicted' | 'trend' | 'confidence'> {
  const delta = current >= 85 ? 3 : current >= 70 ? 0 : -4
  const low = Math.max(0, current + delta - 3)
  const high = Math.min(100, current + delta + 3)
  const trend = delta > 1 ? '上升' as const : delta < -1 ? '下滑' as const : '稳定' as const
  return {
    predicted: `${low}-${high}`,
    trend,
    confidence: Math.min(95, 70 + Math.floor(current / 5)),
  }
}

/** 获取学生个人成绩趋势（含班级均值对比） */
export async function fetchStudentGradeTrend(query: AnalysisQuery): Promise<StudentGradeTrendData> {
  await delay(300)
  if (!query.targetId || !query.courseId) {
    return { months: [], scores: [], classAvgScores: [] }
  }

  const classTrend = await fetchGradeTrend(query)
  const current = getStudentCurrentScore(query.targetId, query.courseId)
  const profile = findStudentProfile(query.targetId, query.courseId)
  const progressScore = profile?.dimensionScores.find((d) => d.name === '学习进步')?.score ?? 75
  const startOffset = progressScore >= 80 ? -12 : progressScore >= 65 ? -6 : progressScore >= 50 ? -3 : 2

  const months = classTrend.months
  const lastIdx = Math.max(months.length - 1, 1)
  const scores = months.map((_, i) => {
    const progress = i / lastIdx
    const base = current + startOffset
    const noise = (i % 2 === 0 ? 1 : -1) * Math.round((1 - progress) * 2)
    const val = Math.round(base + (current - base) * progress + noise)
    return Math.min(100, Math.max(0, val))
  })
  if (scores.length) scores[scores.length - 1] = current

  return {
    months,
    scores,
    classAvgScores: classTrend.avgScore,
  }
}

/** 获取学生个人成绩预测 */
export async function fetchStudentGradePrediction(query: AnalysisQuery): Promise<StudentGradePrediction | null> {
  await delay(250)
  if (!query.targetId || !query.courseId || !query.classId) return null

  const profile = findStudentProfile(query.targetId, query.courseId)
  const studentsInClass = getStudentsInCourseClass(query.courseId, query.classId)
  if (!studentsInClass.some((s) => s.id === query.targetId)) return null

  const student = studentsInClass.find((s) => s.id === query.targetId)!
  const classScores = studentsInClass.map((s) => ({
    id: s.id,
    score: getStudentCurrentScore(s.id, query.courseId!),
  }))
  const sorted = [...classScores].sort((a, b) => b.score - a.score)
  const current = getStudentCurrentScore(query.targetId, query.courseId)
  const classAvg = Math.round(classScores.reduce((a, b) => a + b.score, 0) / classScores.length)
  const vsClassAvg = current - classAvg
  const rank = sorted.findIndex((s) => s.id === query.targetId) + 1
  const pred = buildPrediction(current)

  const kps = getKnowledgePointsByCourse(query.courseId)
  const mastery = getStudentMastery(query.targetId, query.courseId) ?? []
  const weakKps = kps
    .map((name, i) => ({ name, score: mastery[i] ?? 0 }))
    .filter((p) => p.score < 75)
    .sort((a, b) => a.score - b.score)
    .slice(0, 2)

  const analysisItems = [
    {
      title: '当前水平',
      content: `本课程当前综合得分 ${current} 分，班级排名第 ${rank}/${classScores.length}，${vsClassAvg >= 0 ? `高于班级均值 ${vsClassAvg} 分` : `低于班级均值 ${Math.abs(vsClassAvg)} 分`}`,
    },
    {
      title: '变化趋势',
      content: pred.trend === '上升'
        ? '近期成绩呈上升趋势，学习状态良好，建议保持当前节奏'
        : pred.trend === '下滑'
          ? '近期成绩有所下滑，建议加强薄弱模块练习并及时复习'
          : '近期成绩较为稳定，可在巩固基础上寻求突破',
    },
    {
      title: '薄弱模块',
      content: weakKps.length
        ? `需重点关注 ${weakKps.map((p) => `${p.name}(${p.score}%)`).join('、')}`
        : '各模块掌握较均衡，可尝试进阶挑战',
    },
  ]

  const suggestion = pred.trend === '下滑'
    ? '建议制定阶段性复习计划，优先攻克薄弱知识点，必要时寻求教师辅导'
    : pred.trend === '上升'
      ? '保持现有学习节奏，可参与更多拓展练习以巩固优势'
      : '维持稳定学习状态，针对薄弱模块进行专项突破'

  return {
    studentId: query.targetId,
    studentName: profile?.studentName ?? student.studentName,
    studentNo: profile?.studentNo ?? student.studentNo,
    className: profile?.className ?? '',
    courseName: profile?.courseName ?? '',
    current,
    ...pred,
    classRank: rank,
    classSize: classScores.length,
    vsClassAvg,
    analysisItems,
    suggestion,
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

/** 获取某课程某班级学生成绩预测列表（班级维度） */
export async function fetchGradePredictions(query: AnalysisQuery): Promise<GradePredictionItem[]> {
  await delay(200)
  if (!query.courseId || !query.classId) return []

  const studentsInClass = getStudentsInCourseClass(query.courseId, query.classId)
  return studentsInClass.map((s) => {
    const current = getStudentCurrentScore(s.id, query.courseId!)
    return {
      name: s.studentName,
      current,
      ...buildPrediction(current),
    }
  })
}

/** 分析对象类型选项（单课程/单班级维度） */
export const targetTypeOptions: { label: string; value: TargetType }[] = [
  { label: '学生', value: 'student' },
  { label: '班级', value: 'class' },
]
