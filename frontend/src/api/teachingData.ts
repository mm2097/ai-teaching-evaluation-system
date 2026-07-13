/**
 * 教学数据 API（查询、编辑、导出）
 */
import request from '@/utils/request'
import type { TeachingDataRecord } from '@/types'

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
