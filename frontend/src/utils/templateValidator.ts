/**
 * 数据模板格式校验
 * 上传时校验文件结构与字段是否匹配标准模板
 */
import * as XLSX from 'xlsx'
import type { DataTemplateType, ValidationError } from '@/types'

/** 各数据类型标准模板字段 */
export const templateSchemas: Record<DataTemplateType, string[]> = {
  score: ['学号', '姓名', '课程编号', '课程名称', '分数', '考试日期'],
  attendance: ['学号', '姓名', '课程编号', '日期', '考勤状态', '备注'],
  assignment: ['学号', '姓名', '课程编号', '作业名称', '提交状态', '得分'],
  qa: ['学号', '姓名', '课程编号', '日期', '问题类型', '回答情况', '得分'],
}

export interface ValidateResult {
  valid: boolean
  errors: ValidationError[]
  rowCount: number
}

function validateHeaders(headers: string[], expected: string[]): ValidationError[] {
  const errors: ValidationError[] = []
  expected.forEach((col, idx) => {
    const actual = headers[idx]?.trim()
    if (actual !== col) {
      errors.push({
        row: 1,
        column: col,
        message: `第 1 行第 ${idx + 1} 列应为「${col}」，实际为「${actual || '空'}」`,
      })
    }
  })
  if (headers.length > expected.length) {
    errors.push({
      row: 1,
      column: '—',
      message: `模板列数应为 ${expected.length} 列，实际为 ${headers.length} 列`,
    })
  }
  return errors
}

function validateRowValues(
  rows: string[][],
  schema: string[],
  startRow: number,
): ValidationError[] {
  const errors: ValidationError[] = []
  rows.forEach((row, idx) => {
    const lineNum = startRow + idx
    if (row.every((cell) => !cell?.trim())) return

    schema.forEach((col, colIdx) => {
      if (!row[colIdx]?.trim()) {
        errors.push({ row: lineNum, column: col, message: `第 ${lineNum} 行「${col}」不能为空` })
      }
    })

    const scoreIdx = schema.indexOf('分数')
    if (scoreIdx >= 0 && row[scoreIdx]) {
      const score = Number(row[scoreIdx])
      if (Number.isNaN(score) || score < 0 || score > 100) {
        errors.push({ row: lineNum, column: '分数', message: `第 ${lineNum} 行分数应为 0-100 之间的数字` })
      }
    }

    const qaScoreIdx = schema.indexOf('得分')
    if (qaScoreIdx >= 0 && row[qaScoreIdx] && schema.includes('问题类型')) {
      const score = Number(row[qaScoreIdx])
      if (Number.isNaN(score) || score < 0 || score > 100) {
        errors.push({ row: lineNum, column: '得分', message: `第 ${lineNum} 行得分应为 0-100 之间的数字` })
      }
    }
  })
  return errors
}

/** 校验 Excel (.xlsx) 文件 */
export async function validateExcelFile(
  file: File,
  templateType: DataTemplateType,
): Promise<ValidateResult> {
  const schema = templateSchemas[templateType]
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  const sheet = workbook.Sheets[workbook.SheetNames[0]!]
  if (!sheet) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件为空或无法解析' }], rowCount: 0 }
  }

  const rows = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, defval: '' })
  if (rows.length === 0) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件无数据' }], rowCount: 0 }
  }

  const headers = (rows[0] as string[]).map((h) => String(h).trim())
  const headerErrors = validateHeaders(headers, schema)
  const dataRows = rows.slice(1).map((r) => (r as string[]).map((c) => String(c ?? '').trim()))
  const rowErrors = validateRowValues(dataRows, schema, 2)
  const errors = [...headerErrors, ...rowErrors]

  return { valid: errors.length === 0, errors, rowCount: dataRows.filter((r) => r.some((c) => c)).length }
}

/** 校验 Txt (UTF-8 英文逗号分隔) 文件 */
export async function validateTxtFile(
  file: File,
  templateType: DataTemplateType,
): Promise<ValidateResult> {
  const schema = templateSchemas[templateType]
  const text = await file.text()

  if (text.includes('\t')) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: 'Txt 文件须为英文逗号分隔，不支持 Tab 分隔' }],
      rowCount: 0,
    }
  }

  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (lines.length === 0) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件无数据' }], rowCount: 0 }
  }

  const headers = lines[0]!.split(',').map((h) => h.trim())
  const headerErrors = validateHeaders(headers, schema)
  const dataRows = lines.slice(1).map((l) => l.split(',').map((c) => c.trim()))
  const rowErrors = validateRowValues(dataRows, schema, 2)
  const errors = [...headerErrors, ...rowErrors]

  return { valid: errors.length === 0, errors, rowCount: dataRows.filter((r) => r.some((c) => c)).length }
}

/** 根据文件扩展名校验 */
export async function validateUploadFile(
  file: File,
  templateType: DataTemplateType,
): Promise<ValidateResult> {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext === 'xlsx') return validateExcelFile(file, templateType)
  if (ext === 'txt') return validateTxtFile(file, templateType)
  return {
    valid: false,
    errors: [{ row: 0, column: '—', message: '仅支持 .xlsx（Excel）或 .txt（UTF-8 英文逗号分隔）格式' }],
    rowCount: 0,
  }
}
