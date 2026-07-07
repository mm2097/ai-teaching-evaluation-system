/**
 * AI 分析 API（模拟后端 /api/analysis/* 接口）
 */
import { delay } from '@/utils/auth'
import { gradeTrendData, knowledgeHeatmap, studentProfiles, warningRecords } from '@/mock'
import type { AnalysisQuery, StudentProfileData, TargetType, WarningRecord } from '@/types'

/** 获取学情画像 */
export async function fetchStudentProfile(query: AnalysisQuery): Promise<StudentProfileData | null> {
  await delay(300)
  if (query.targetType === 'student' && query.targetId) {
    return studentProfiles.find((p) => p.studentId === query.targetId) || studentProfiles[0]!
  }
  return studentProfiles[0]!
}

/** 获取成绩趋势数据 */
export async function fetchGradeTrend(_query: AnalysisQuery) {
  await delay(300)
  return gradeTrendData
}

/** 获取知识点热力图数据 */
export async function fetchKnowledgeHeatmap(query: AnalysisQuery) {
  await delay(300)
  if (query.targetType === 'student' && query.targetId) {
    const profile = studentProfiles.find((p) => p.studentId === query.targetId)
    if (profile) {
      const idx = ['陈同学', '刘同学', '赵同学', '孙同学', '周同学'].indexOf(profile.studentName)
      if (idx >= 0) {
        const personalData = knowledgeHeatmap.data.filter((d) => d[1] === idx)
        return { ...knowledgeHeatmap, students: [profile.studentName], data: personalData.map((d) => [d[0]!, 0, d[2]!]) as number[][] }
      }
    }
  }
  return knowledgeHeatmap
}

/** 获取预警记录（带筛选） */
export async function fetchWarnings(query: AnalysisQuery & {
  level?: string
  type?: string
  status?: number
}): Promise<WarningRecord[]> {
  await delay(300)
  return warningRecords.filter((w) => {
    if (query.deptId && w.deptId !== query.deptId) return false
    if (query.classId && w.classId !== query.classId) return false
    if (query.semesterId && w.semesterId !== query.semesterId) return false
    if (query.courseId && w.courseId !== query.courseId) return false
    if (query.level && w.level !== query.level) return false
    if (query.type && w.type !== query.type) return false
    if (query.status !== undefined && query.status !== null && w.status !== query.status) return false
    return true
  })
}

/** 分析对象类型选项（单课程/单班级维度） */
export const targetTypeOptions: { label: string; value: TargetType }[] = [
  { label: '学生', value: 'student' },
  { label: '班级', value: 'class' },
]
