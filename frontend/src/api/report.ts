import request from '@/utils/request'
import type { ReportCharts, ReportResponse } from '@/api/ai'

export interface DashboardStatsSnapshot {
  studentCount?: number
  courseCount?: number
  passRate?: number
  excellentRate?: number
  attendanceRate?: number
  warningCount?: number
  charts?: ReportCharts
}

export interface ReportHistoryItem {
  id: number
  name: string
  type: string
  report_type: 1 | 2 | 3 | 4
  scope: string
  format: 'PDF' | 'XLSX'
  time: string
  created_at: string
  course_id: number
  course_name: string
  class_id?: number
  class_name?: string
  student_id?: number
  student_name?: string
}

export interface ReportHistoryDetail extends ReportHistoryItem {
  parameters: {
    course_id: number
    report_type: 1 | 2 | 3 | 4
    class_id?: number
    student_id?: number
    semester?: string
    use_llm: boolean
    export_format: 'pdf' | 'xlsx'
  }
  data: ReportResponse
  stats: DashboardStatsSnapshot
}

export async function generateAndSaveReport(params: {
  courseId: number
  reportType: 1 | 2 | 3 | 4
  classId?: number
  studentId?: number
  semester?: string
  exportFormat: 'pdf' | 'xlsx'
  dashboardStats?: DashboardStatsSnapshot
}): Promise<ReportHistoryDetail> {
  // LLM 增强报告生成耗时较长（后端 httpx 30 秒），超时放宽到 60 秒
  const { data } = await request.post('/v1/report/history', {
    course_id: params.courseId,
    report_type: params.reportType,
    class_id: params.classId,
    student_id: params.studentId,
    semester: params.semester,
    export_format: params.exportFormat,
    dashboard_stats: params.dashboardStats ?? {},
  }, { timeout: 60000 })
  return data
}

export async function fetchReportHistory(): Promise<ReportHistoryItem[]> {
  const { data } = await request.get('/v1/report/history')
  return data
}

export async function fetchReportHistoryDetail(id: number): Promise<ReportHistoryDetail> {
  const { data } = await request.get(`/v1/report/history/${id}`)
  return data
}

export async function downloadReportFile(id: number, format: 'pdf' | 'xlsx'): Promise<Blob> {
  const { data } = await request.get(`/v1/report/history/${id}/download`, {
    params: { format },
    responseType: 'blob',
  })
  return data
}
