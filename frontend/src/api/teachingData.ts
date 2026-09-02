/**
 * 教学数据 API（查询、编辑、导出、模板下载）
 */
import request from '@/utils/request'
import type { TeachingDataRecord } from '@/types'

export type TeachingRecordType = TeachingDataRecord['recordType']

// ---------------------------------------------------------------------------
// 模板下载
// ---------------------------------------------------------------------------

/** 模板元信息（与后端 GET /teaching-data/templates 返回一致） */
export interface TemplateMeta {
  templateId: string
  name: string
  dataType: string
  description: string
  headers: string[]
}

/** 获取可用模板列表 */
export async function fetchTemplateList(): Promise<TemplateMeta[]> {
  const res = await request.get('/v1/teaching-data/templates')
  return (res.data ?? []) as TemplateMeta[]
}

/**
 * 从 Content-Disposition 响应头解析下载文件名。
 * 后端返回格式：
 *   attachment; filename="ascii-name.xlsx";
 *                filename*=UTF-8''%E6%A8%A1%E6%9D%BF-...xlsx
 * 优先取 RFC 5987 编码文件名（含中文），ASCII 名兜底。
 */
function parseFilenameFromDisposition(disposition: string, fallback: string): string {
  const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/)
  if (rfc5987) {
    return decodeURIComponent(rfc5987[1]!)
  }
  const ascii = disposition.match(/filename="?([^";\s]+)"?/)
  return ascii ? ascii[1]! : fallback
}

/**
 * 从后端下载模板文件（blob）。
 *
 * @param templateId 后端模板 ID（如 exam_deduction / score_summary / attendance）
 * @param format     下载格式: xlsx / txt（默认 xlsx）
 * @returns blob + 后端 Content-Disposition 中建议的文件名
 */
export async function downloadTemplateFromServer(
  templateId: string,
  format: 'xlsx' | 'txt' = 'xlsx',
): Promise<{ blob: Blob; filename: string }> {
  const res = await request.get(`/v1/teaching-data/templates/${templateId}`, {
    params: { format },
    responseType: 'blob',
  })

  const blob = res.data as Blob
  const disposition = (res.headers as Record<string, string>)['content-disposition'] ?? ''
  const filename = parseFilenameFromDisposition(disposition, `${templateId}.${format}`)

  return { blob, filename }
}

export interface TeachingDataQuery {
  courseId: number
  keyword?: string
  dataType?: 'score' | 'attendance' | 'participation'
  batchId?: number
  page?: number
  pageSize?: number
}

interface TeachingDataApiRow {
  id: string
  recordId: number
  dataType: 'score' | 'attendance' | 'participation'
  recordType?: TeachingRecordType
  subType?: string
  studentId: string
  studentName: string
  courseId: number
  courseName?: string
  classId?: number
  college?: string
  major?: string
  semester?: string
  score?: number
  status?: string
  batchName?: string
  batchId?: number
  remark?: string
  sourceData?: string
  attendanceDate?: string | null
  participationRate?: number
  totalCount?: number
}

function mapTeachingDataRow(row: TeachingDataApiRow, courseName: string): TeachingDataRecord {
  return {
    id: row.recordId,
    recordType: row.recordType || row.dataType,
    studentId: row.studentId,
    studentName: row.studentName,
    courseId: String(row.courseId),
    courseName: row.courseName || courseName,
    semester: row.semester || '',
    semesterId: 0,
    deptId: 0,
    majorId: 0,
    classId: row.classId || 0,
    college: row.college,
    major: row.major,
    dataType: row.dataType,
    subType: row.subType,
    score: row.dataType === 'score' ? row.score : undefined,
    attendance: row.dataType === 'attendance' ? row.status : undefined,
    batchName: row.batchName,
    remark: row.remark,
    batchId: row.batchId,
    participationRate: row.dataType === 'participation' ? row.participationRate : undefined,
    totalCount: row.dataType === 'participation' ? row.totalCount : undefined,
    sourceData: row.sourceData,
  }
}

export async function fetchTeachingData(
  params: TeachingDataQuery,
  courseName = '',
): Promise<{ list: TeachingDataRecord[]; total: number }> {
  const res = await request.get('/v1/teaching-data', {
    params: {
      course_id: params.courseId,
      keyword: params.keyword || undefined,
      data_type: params.dataType || undefined,
      batch_id: params.batchId || undefined,
      page: params.page || 1,
      page_size: params.pageSize || 200,
    },
  })
  const payload = res.data as { data?: TeachingDataApiRow[]; total?: number }
  const rows = payload.data ?? []
  return {
    list: rows.map((row) => mapTeachingDataRow(row, courseName)),
    total: payload.total ?? rows.length,
  }
}

/** 更新一条记录的完整行数据（含各题子记录等） */
export async function updateRowData(
  recordId: number,
  sourceData: Record<string, unknown>,
): Promise<void> {
  await request.put(`/v1/teaching-data/${recordId}/row`, { source_data: sourceData })
}

/**
 * 删除单条教学数据（Data.Query.Delete，后端写入操作日志 BR4）。
 *
 * @param recordType 记录类型：score / individual_score / course_test_detail / attendance / attendance_sheet
 * @param recordId   后端返回的记录主键
 */
export async function deleteTeachingData(
  recordType: string,
  recordId: number,
): Promise<void> {
  await request.delete(`/v1/teaching-data/${recordType}/${recordId}`)
}

/** @deprecated 旧名，等价于 deleteTeachingData，保留以兼容调用方。 */
export async function deleteTeachingDataRecord(
  recordType: TeachingRecordType,
  recordId: number,
): Promise<void> {
  await request.delete(`/v1/teaching-data/${recordType}/${recordId}`)
}

export async function batchDeleteTeachingDataRecords(
  records: { recordType: TeachingRecordType; recordId: number }[],
): Promise<{ deleted: number }> {
  const res = await request.post('/v1/teaching-data/batch-delete', { records })
  return res.data as { deleted: number }
}

/**
 * 导出教学数据为 Excel 文件（Data.Query.Export，后端生成）。
 *
 * @param params 与查询一致的筛选条件；后端支持 courseId / keyword（姓名学号模糊）/
 *               dataType（score | attendance）/ batchId
 * @returns blob + 后端 Content-Disposition 中建议的文件名
 */
export async function exportTeachingData(
  params: Pick<TeachingDataQuery, 'courseId' | 'keyword' | 'dataType' | 'batchId'>,
): Promise<{ blob: Blob; filename: string }> {
  const res = await request.get('/v1/teaching-data/export', {
    params: {
      course_id: params.courseId,
      keyword: params.keyword || undefined,
      data_type: params.dataType || undefined,
      batch_id: params.batchId || undefined,
    },
    responseType: 'blob',
  })

  const blob = res.data as Blob
  const disposition = (res.headers as Record<string, string>)['content-disposition'] ?? ''
  const filename = parseFilenameFromDisposition(disposition, '教学数据导出.xlsx')

  return { blob, filename }
}

// ============================================================================
// 课堂互动记录（InteractionRecord）—— 教师单次课堂对学生打分
// ============================================================================

export interface InteractionRecordItem {
  interactionId: number
  courseId: number
  studentId: number
  studentName: string
  studentNo: string
  type: number          // 1=课堂提问, 2=小组讨论, 4=课堂测验
  typeLabel: string
  score: number         // 0-100
  remark?: string | null
  date: string
}

export interface InteractionRecordPayload {
  courseId: number
  studentId: number
  interactionType: number  // 1/2/4
  score: number            // 0-100
  interactionDate?: string // YYYY-MM-DD
  remark?: string
}

export async function fetchInteractionRecords(params: {
  courseId: number
  studentId?: number
  interactionType?: number
}): Promise<InteractionRecordItem[]> {
  const res = await request.get('/v1/teaching-data/interactions', { params })
  return res.data || []
}

export async function createInteractionRecord(payload: InteractionRecordPayload): Promise<InteractionRecordItem> {
  const res = await request.post('/v1/teaching-data/interactions', payload)
  return res.data
}

export async function deleteInteractionRecord(interactionId: number): Promise<void> {
  await request.delete(`/v1/teaching-data/interactions/${interactionId}`)
}
