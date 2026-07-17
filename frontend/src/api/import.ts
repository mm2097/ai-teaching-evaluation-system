/**
 * 数据导入 API — 调用真实后端 /api/v1/teaching-data/upload
 */
import request from '@/utils/request'
import type { ImportLog } from '@/types'

// ---------------------------------------------------------------------------
// 导入结果（对应后端 upload_teaching_data 返回值）
// ---------------------------------------------------------------------------

export interface ImportResult {
  fileName: string
  courseId: number
  courseName: string
  detectedTemplate: string | null
  sheetsProcessed: string[]
  successCount: number
  errorCount: number
  errors: { sheet: string; row: number; field: string; message: string }[]
  analysisRefresh: Record<string, unknown>
}

/** 获取导入日志列表（当前后端暂无导入日志表，返回空列表） */
export async function fetchImportLogs(): Promise<ImportLog[]> {
  return []
}

/**
 * 上传文件到后端并执行数据导入。
 * POST /api/v1/teaching-data/upload (multipart/form-data)
 */
export async function executeImport(
  file: File,
  courseId: number,
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await request.post('/v1/teaching-data/upload', formData, {
    params: { course_id: courseId },
    // 不要手动设置 Content-Type，让 axios 自动带上正确的 boundary
    timeout: 120000,  // 大文件多 sheet 上传需要较长时间
  })

  return res.data as ImportResult
}
