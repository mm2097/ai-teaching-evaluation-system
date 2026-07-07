/**
 * 标准数据模板下载
 */
import * as XLSX from 'xlsx'
import { templateSchemas } from './templateValidator'
import type { DataTemplateType } from '@/types'

const templateLabels: Record<DataTemplateType, string> = {
  score: '成绩数据模板',
  attendance: '考勤数据模板',
  assignment: '作业数据模板',
  qa: '课堂问答数据模板',
}

const sampleRows: Record<DataTemplateType, string[][]> = {
  score: [
    ['2024001001', '陈同学', 'CS101', '数据结构', '92', '2026-03-15'],
    ['2024001002', '刘同学', 'CS101', '数据结构', '78', '2026-03-15'],
  ],
  attendance: [
    ['2024001001', '陈同学', 'CS101', '2026-03-10', '正常', ''],
    ['2024001002', '刘同学', 'CS101', '2026-03-10', '迟到', '迟到 5 分钟'],
  ],
  assignment: [
    ['2024001001', '陈同学', 'CS101', '链表实现作业', '已提交', '95'],
    ['2024001003', '赵同学', 'CS102', '进程调度实验', '未提交', '0'],
  ],
  qa: [
    ['2024001001', '陈同学', 'CS101', '2026-03-12', '课堂提问', '正确回答', '10'],
    ['2024001002', '刘同学', 'CS101', '2026-03-12', '随堂测验', '部分正确', '6'],
  ],
}

/** 下载 Excel 模板 (.xlsx) */
export function downloadExcelTemplate(templateType: DataTemplateType): void {
  const headers = templateSchemas[templateType]
  const samples = sampleRows[templateType]
  const ws = XLSX.utils.aoa_to_sheet([headers, ...samples])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '数据')
  XLSX.writeFile(wb, `${templateLabels[templateType]}.xlsx`)
}

/** 下载 Txt 模板 (UTF-8 英文逗号分隔) */
export function downloadTxtTemplate(templateType: DataTemplateType): void {
  const headers = templateSchemas[templateType]
  const samples = sampleRows[templateType]
  const lines = [headers.join(','), ...samples.map((r) => r.join(','))]
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${templateLabels[templateType]}.txt`
  a.click()
  URL.revokeObjectURL(url)
}
