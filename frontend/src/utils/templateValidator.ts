/**
 * 数据模板格式校验
 *
 * 上传时校验文件结构是否与后端模板一致。
 * 校验字段由调用方从后端模板接口（GET /teaching-data/templates）动态获取，
 * 保证下载模板、填写数据、上传校验三者字段一致。
 */
import * as XLSX from 'xlsx'
import type { ValidationError } from '@/types'

export interface ValidateResult {
  valid: boolean
  errors: ValidationError[]
  rowCount: number
}

// ---------------------------------------------------------------------------
// 关键字段 — 用于判定空行和必填校验
// ---------------------------------------------------------------------------

/** 关键字段名列表，当这些字段全部为空时视为空行跳过 */
const KEY_FIELD_NAMES = ['学号', '姓名']

/**
 * 查找关键字段在预期表头中的列索引。
 */
function findKeyFieldIndices(expectedHeaders: string[]): number[] {
  return KEY_FIELD_NAMES
    .map((name) => expectedHeaders.indexOf(name))
    .filter((idx) => idx >= 0)
}

// ---------------------------------------------------------------------------
// 表头校验
// ---------------------------------------------------------------------------

function validateHeaders(actualHeaders: string[], expected: string[]): ValidationError[] {
  const errors: ValidationError[] = []

  expected.forEach((col, idx) => {
    const actual = actualHeaders[idx]?.trim() ?? ''
    if (actual !== col) {
      errors.push({
        row: 1,
        column: col,
        message: `第 1 行第 ${idx + 1} 列应为「${col}」，实际为「${actual || '空'}」`,
      })
    }
  })

  // 仅当文件缺少列时报错；多余尾部列（如公式列、备注列）允许通过
  if (actualHeaders.length < expected.length) {
    errors.push({
      row: 1,
      column: '—',
      message: `模板需要至少 ${expected.length} 列，文件仅有 ${actualHeaders.length} 列`,
    })
  }

  return errors
}

// ---------------------------------------------------------------------------
// 行数据校验
// ---------------------------------------------------------------------------

function validateRows(
  rows: string[][],
  expectedHeaders: string[],
  startRowNum: number,
): ValidationError[] {
  const errors: ValidationError[] = []
  const keyIndices = findKeyFieldIndices(expectedHeaders)

  rows.forEach((row, idx) => {
    const lineNum = startRowNum + idx

    // 跳过完全空行（所有单元格均为空）
    if (row.every((cell) => !cell?.trim())) return

    // 跳过关键字段全部为空的行（如备注行、说明行）
    if (keyIndices.length > 0 && keyIndices.every((i) => !row[i]?.trim())) return

    // 关键字段不可为空
    keyIndices.forEach((colIdx) => {
      const colName = expectedHeaders[colIdx]!
      if (!row[colIdx]?.trim()) {
        errors.push({
          row: lineNum,
          column: colName,
          message: `第 ${lineNum} 行「${colName}」不能为空`,
        })
      }
    })
  })

  return errors
}

// ---------------------------------------------------------------------------
// 读取文件行
// ---------------------------------------------------------------------------

function parseRowsFromExcel(sheet: XLSX.WorkSheet): string[][] {
  return XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, defval: '' })
}

function parseRowsFromTxt(text: string): string[][] {
  if (text.includes('\t')) {
    return [] // 返回空，调用方处理错误
  }
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim() !== '')
    .map((line) => line.split(',').map((c) => c.trim()))
}

// ---------------------------------------------------------------------------
// 公开校验函数
// ---------------------------------------------------------------------------

/**
 * 校验 Excel (.xlsx) 文件 — 遍历所有 sheet 逐一校验，合并结果。
 * 每个 sheet 的表头与数据行均按 expectedHeaders 校验，错误带上 sheet 名。
 */
export async function validateExcelFile(
  file: File,
  expectedHeaders: string[],
): Promise<ValidateResult> {
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  if (!workbook.SheetNames.length) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: '文件为空或无法解析' }],
      rowCount: 0,
    }
  }

  const allErrors: ValidationError[] = []
  let totalRowCount = 0

  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName]
    if (!sheet) continue
    const rows = parseRowsFromExcel(sheet)
    if (!rows.length) continue

    const actualHeaders = (rows[0] as string[]).map((h) => String(h).trim())

    // 跳过完全空的 sheet
    if (actualHeaders.every((h) => h === '')) continue

    // 表头校验
    const headerErrors = validateHeaders(actualHeaders, expectedHeaders)
    headerErrors.forEach((e) => (e.sheet = sheetName))
    allErrors.push(...headerErrors)

    // 数据行校验
    const dataRows = rows.slice(1).map((r) => (r as string[]).map((c) => String(c ?? '').trim()))
    const rowErrors = validateRows(dataRows, expectedHeaders, 2)
    rowErrors.forEach((e) => (e.sheet = sheetName))
    allErrors.push(...rowErrors)

    totalRowCount += dataRows.filter((r) => r.some((c) => c)).length
  }

  return { valid: allErrors.length === 0, errors: allErrors, rowCount: totalRowCount }
}

/** 校验 Txt (UTF-8 英文逗号分隔) 文件 */
export async function validateTxtFile(
  file: File,
  expectedHeaders: string[],
): Promise<ValidateResult> {
  const text = await file.text()

  if (text.includes('\t')) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: 'Txt 文件须为英文逗号分隔，不支持 Tab 分隔' }],
      rowCount: 0,
    }
  }

  const rows = parseRowsFromTxt(text)
  if (rows.length === 0) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: '文件无数据' }],
      rowCount: 0,
    }
  }

  // 跳过 # 开头的注释行，找到真正的表头行
  let headerRowIdx = 0
  while (headerRowIdx < rows.length && rows[headerRowIdx]![0]?.startsWith('#')) {
    headerRowIdx++
  }
  if (headerRowIdx >= rows.length) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: '文件无有效表头行' }],
      rowCount: 0,
    }
  }

  const actualHeaders = rows[headerRowIdx]!
  const headerErrors = validateHeaders(actualHeaders, expectedHeaders)

  const dataRows = rows.slice(headerRowIdx + 1)
  const rowErrors = validateRows(dataRows, expectedHeaders, headerRowIdx + 2)
  const errors = [...headerErrors, ...rowErrors]

  return { valid: errors.length === 0, errors, rowCount: dataRows.filter((r) => r.some((c) => c)).length }
}

/**
 * 根据文件扩展名自动选择校验方式。
 *
 * @param file            上传的文件
 * @param expectedHeaders 预期表头列表（从后端模板接口获取）
 */
export async function validateUploadFile(
  file: File,
  expectedHeaders: string[],
): Promise<ValidateResult> {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext === 'xlsx') return validateExcelFile(file, expectedHeaders)
  if (ext === 'txt') return validateTxtFile(file, expectedHeaders)
  return {
    valid: false,
    errors: [
      { row: 0, column: '—', message: '仅支持 .xlsx（Excel）或 .txt（UTF-8 英文逗号分隔）格式' },
    ],
    rowCount: 0,
  }
}

// ---------------------------------------------------------------------------
// 从文件读取表头（用于自动识别文件对应哪个模板）
// ---------------------------------------------------------------------------

/**
 * 读取上传文件的表头行，返回去空白后的字符串数组。
 * 读取失败时返回 null。
 */
export async function readHeadersFromFile(file: File): Promise<string[] | null> {
  const ext = file.name.split('.').pop()?.toLowerCase()

  try {
    if (ext === 'xlsx') {
      const buffer = await file.arrayBuffer()
      const workbook = XLSX.read(buffer, { type: 'array' })
      // 遍历所有 sheet，返回首个非空 sheet 的表头（用于模板自动识别）
      // 所有 sheet 表头结构应一致，取首个非空即可
      for (const sheetName of workbook.SheetNames) {
        const sheet = workbook.Sheets[sheetName]
        if (!sheet) continue
        const rows: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' })
        if (!rows.length) continue
        const headers = (rows[0] as unknown[]).map((h) => String(h ?? '').trim())
        if (headers.some((h) => h !== '')) return headers
      }
      return null
    }

    if (ext === 'txt') {
      const text = await file.text()
      if (text.includes('\t')) return null
      const lines = text
        .split(/\r?\n/)
        .filter((l) => l.trim() !== '' && !l.trim().startsWith('#'))
      if (!lines.length) return null
      return lines[0]!.split(',').map((h) => h.trim())
    }
  } catch {
    return null
  }

  return null
}
