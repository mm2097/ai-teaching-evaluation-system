/**
 * 教学数据 API（查询、编辑、导出、模板下载）
 */
import request from '@/utils/request'
import type { TeachingDataRecord } from '@/types'

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

  // 从 Content-Disposition 解析文件名
  // 后端返回格式：
  //   attachment; filename="template-score_summary.xlsx";
  //                filename*=UTF-8''%E6%A8%A1%E6%9D%BF-...xlsx
  const disposition = (res.headers as Record<string, string>)['content-disposition'] ?? ''

  // 优先取 RFC 5987 编码文件名（含中文），再用 ASCII 兜底
  let filename: string
  const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/)
  if (rfc5987) {
    filename = decodeURIComponent(rfc5987[1]!)
  } else {
    const ascii = disposition.match(/filename="?([^";\s]+)"?/)
    filename = ascii ? ascii[1]! : `${templateId}.${format}`
  }

  return { blob, filename }
}

export interface TeachingDataQuery {
  courseId: number
  keyword?: string
  dataType?: 'score' | 'attendance'
  batchId?: number
  page?: number
  pageSize?: number
}

interface TeachingDataApiRow {
  id: string
  recordId: number
  dataType: 'score' | 'attendance'
  studentId: string
  studentName: string
  courseId: number
  courseName?: string
  semester?: string
  score?: number
  status?: string
  batchName?: string
  batchId?: number
  remark?: string
  sourceData?: string
  attendanceDate?: string | null
}

function mapTeachingDataRow(row: TeachingDataApiRow, courseName: string): TeachingDataRecord {
  return {
    id: row.recordId,
    studentId: row.studentId,
    studentName: row.studentName,
    courseId: String(row.courseId),
    courseName: row.courseName || courseName,
    semester: row.semester || '',
    semesterId: 0,
    deptId: 0,
    majorId: 0,
    classId: 0,
    dataType: row.dataType,
    score: row.dataType === 'score' ? row.score : undefined,
    attendance: row.dataType === 'attendance' ? row.status : undefined,
    batchName: row.batchName,
    remark: row.remark,
    batchId: row.batchId,
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
