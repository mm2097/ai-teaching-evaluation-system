/**
 * 标准数据模板下载
 *
 * 下载逻辑已从客户端本地生成迁移至后端接口：
 *   GET /api/v1/teaching-data/templates/{template_id}?format=xlsx|txt
 *
 * 后端负责提供符合系统标准的模板文件（含表头、示例行、填写说明），
 * 保证下载模板与上传校验、导入逻辑保持一致。
 */
import { downloadTemplateFromServer } from '@/api/teachingData'

/**
 * 触发浏览器下载给定的 blob 文件。
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 下载 Excel 模板 (.xlsx) — 从后端获取标准模板 */
export async function downloadExcelTemplate(templateId: string): Promise<void> {
  const { blob, filename } = await downloadTemplateFromServer(templateId, 'xlsx')
  triggerDownload(blob, filename)
}

/** 下载 Txt 模板 (UTF-8 英文逗号分隔) — 从后端获取标准模板 */
export async function downloadTxtTemplate(templateId: string): Promise<void> {
  const { blob, filename } = await downloadTemplateFromServer(templateId, 'txt')
  triggerDownload(blob, filename)
}
