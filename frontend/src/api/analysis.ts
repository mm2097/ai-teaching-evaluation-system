/**
 * AI 分析 API（调用真实后端 /api/v1/analysis/*）
 */
import request from '@/utils/request'
import { streamAgentChat } from '@/api/agent'
import type {
  AgentStreamEvent,
  AnalysisQuery,
  StudentProfileData,
  TargetType,
  WarningRecord,
} from '@/types'

export interface KnowledgeHeatmapResult {
  knowledgePoints: string[]
  students: string[]
  data: number[][]
  classAvgByKp?: number[]
  lossRateByKp?: number[]
  classLossRateByKp?: number[]
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
  if (!query.targetId) return null
  try {
    // 学生视角 → student_id；班级视角 → class_id（后端返回班级平均画像）
    const params: Record<string, number> = { course_id: query.courseId! }
    if (query.targetType === 'class') {
      params.class_id = query.targetId
      params.student_id = query.targetId
    } else {
      params.student_id = query.targetId
    }
    const res = await request.get('/v1/analysis/profile', { params })
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
  studentNo?: string
}): Promise<WarningRecord[]> {
  try {
    const res = await request.get('/v1/analysis/warnings', {
      params: {
        course_id: query.courseId,
        class_id: query.classId,
        level: query.level,
        warning_type: query.type,
        status: query.status,
        student_no: query.studentNo,
      },
    })
    return res.data
  } catch {
    return []
  }
}

/** 更新预警处理状态（标记已处理：status=1 / 恢复待处理：status=0） */
export async function updateWarningStatus(
  warningId: number,
  status: number,
): Promise<WarningRecord> {
  const res = await request.put(`/v1/analysis/warnings/${warningId}/status`, null, {
    params: { status },
  })
  return res.data as WarningRecord
}

/** 手动刷新课程预警列表（全课程重扫耗时较长，超时放宽到 60 秒） */
export async function refreshWarnings(params: { courseId: number; classId?: number }): Promise<{ message: string }> {
  const res = await request.post('/v1/analysis/warnings/refresh', null, {
    params: { course_id: params.courseId, class_id: params.classId },
    timeout: 60000,
  })
  return res.data as { message: string }
}

/** 向预警学生发送站内通知（学生端铃铛可见） */
export async function sendWarningNotice(
  warningId: number,
): Promise<{ notificationId: number; studentName: string; message: string }> {
  const res = await request.post(`/v1/analysis/warnings/${warningId}/notify`)
  return res.data as { notificationId: number; studentName: string; message: string }
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

export interface GradeDistributionBucket {
  range: string
  low: number
  high: number
  count: number
  ratio: number
}

export interface GradeDistributionStats {
  count?: number
  mean?: number
  median?: number
  stdDev?: number
  maxScore?: number
  minScore?: number
  passRate?: number
  excellentRate?: number
  failRate?: number
  skewness?: number
}

export interface GradeDistributionResult {
  distribution: GradeDistributionBucket[]
  statistics: GradeDistributionStats
  characteristic: string
}

/** 成绩分布与班级特征（Analysis.ScoreTrend.Distribute） */
export async function fetchGradeDistribution(query: AnalysisQuery): Promise<GradeDistributionResult> {
  try {
    const res = await request.get('/v1/analysis/grade-distribution', {
      params: { course_id: query.courseId, class_id: query.classId },
    })
    return res.data as GradeDistributionResult
  } catch {
    return { distribution: [], statistics: {}, characteristic: '暂无成绩数据' }
  }
}

/** 分析对象类型选项 */
export const targetTypeOptions: { label: string; value: TargetType }[] = [
  { label: '学生', value: 'student' },
  { label: '班级', value: 'class' },
]

// ============================================================================
// AI 学情诊断（diagnosis Agent）
// ============================================================================

/** 诊断维度标识 → 中文标签 */
export const DIAGNOSIS_DIMENSIONS: { key: string; label: string }[] = [
  { key: 'score', label: '成绩' },
  { key: 'attendance', label: '考勤' },
  { key: 'knowledge', label: '知识点' },
  { key: 'warning', label: '预警' },
  { key: 'exercise', label: '答题' },
]

/** 诊断流式参数 */
export interface StreamDiagnosisParams {
  courseId: number
  studentId?: number
  scope: 'class' | 'student'
  dimensions: string[]
  depth: 'detail' | 'brief'
  sessionId?: string
}

/** 拼装首条诊断消息（分析对象 + 维度 + 深度） */
export function buildDiagnosisMessage(p: StreamDiagnosisParams): string {
  const dimLabels = p.dimensions
    .map((k) => DIAGNOSIS_DIMENSIONS.find((d) => d.key === k)?.label || k)
    .join('、')
  const target =
    p.scope === 'student' ? `学生(student_id=${p.studentId})` : '班级'
  const depth = p.depth === 'brief' ? '概览(只调3个核心工具)' : '详细'
  return `请对${target}做${depth}学情诊断，分析维度：${dimLabels}。按工具编排策略调用学情查询工具全面收集数据，最后输出结构化JSON诊断报告。`
}

/**
 * 流式 AI 学情诊断（SSE）。
 * 封装 streamAgentChat，固定 agentType='diagnosis' + 预设首条消息 + maxSteps=10。
 * detail 模式提示词要求 6-8 个工具，另需给模型留出最终写报告的一步，故取上限 10。
 * 透传 SSE 事件（thinking/tool_call/tool_result/content_done/error）。
 */
export async function* streamDiagnosis(
  params: StreamDiagnosisParams,
): AsyncGenerator<AgentStreamEvent> {
  const message = buildDiagnosisMessage(params)
  const stream = streamAgentChat({
    agentType: 'diagnosis',
    message,
    courseId: params.courseId,
    studentId: params.studentId,
    sessionId: params.sessionId ?? `diagnosis_c${params.courseId}`,
    maxSteps: 10,
  })
  for await (const evt of stream) {
    yield evt
  }
}

/** 保存 AI 学情诊断报告快照，返回 report_id 供下载 */
export async function saveDiagnosisReport(params: {
  courseId: number
  studentId?: number
  scope: 'class' | 'student'
  diagnosisJson: Record<string, unknown>
  exportFormat?: 'pdf' | 'xlsx'
}): Promise<{ id: number; name: string }> {
  const { data } = await request.post('/v1/report/diagnosis', {
    course_id: params.courseId,
    student_id: params.studentId ?? null,
    scope: params.scope,
    diagnosis_json: params.diagnosisJson,
    export_format: params.exportFormat ?? 'pdf',
  })
  return { id: data.id, name: data.name }
}
