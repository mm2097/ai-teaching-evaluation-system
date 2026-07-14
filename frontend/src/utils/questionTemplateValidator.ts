/**
 * 题库批量导入模板校验
 * 支持 .xlsx / .txt（UTF-8 英文逗号分隔）
 */
import * as XLSX from 'xlsx'
import type { DifficultyLevel, ExerciseType, ValidationError } from '@/types'

export const questionTemplateHeaders = [
  '题型',
  '题干',
  '选项A',
  '选项B',
  '选项C',
  '选项D',
  '参考答案',
  '解析',
  '知识点',
  '难度',
  '分值',
] as const

const typeAlias: Record<string, ExerciseType> = {
  single_choice: 'single_choice',
  单选题: 'single_choice',
  单选: 'single_choice',
  multi_choice: 'multi_choice',
  多选题: 'multi_choice',
  多选: 'multi_choice',
  judge: 'judge',
  判断题: 'judge',
  判断: 'judge',
  fill_blank: 'fill_blank',
  填空题: 'fill_blank',
  填空: 'fill_blank',
  short_answer: 'short_answer',
  简答题: 'short_answer',
  简答: 'short_answer',
}

const difficultyAlias: Record<string, DifficultyLevel> = {
  easy: 'easy',
  简单: 'easy',
  medium: 'medium',
  中等: 'medium',
  hard: 'hard',
  困难: 'hard',
}

export interface ParsedQuestionRow {
  type: ExerciseType
  stem: string
  options?: { key: string; text: string }[]
  answer: string
  answerList?: string[]
  explanation?: string
  knowledgePoint: string
  difficulty: DifficultyLevel
  score: number
}

export interface QuestionValidateResult {
  valid: boolean
  errors: ValidationError[]
  rowCount: number
  rows: ParsedQuestionRow[]
}

function normalizeType(raw: string): ExerciseType | null {
  return typeAlias[raw.trim()] ?? null
}

function normalizeDifficulty(raw: string): DifficultyLevel {
  return difficultyAlias[raw.trim()] ?? 'medium'
}

function parseRow(cells: string[], lineNum: number): { row?: ParsedQuestionRow; errors: ValidationError[] } {
  const errors: ValidationError[] = []
  const [
    typeRaw = '',
    stem = '',
    optA = '',
    optB = '',
    optC = '',
    optD = '',
    answer = '',
    explanation = '',
    knowledgePoint = '',
    difficultyRaw = 'medium',
    scoreRaw = '5',
  ] = cells.map((c) => String(c ?? '').trim())

  const type = normalizeType(typeRaw)
  if (!type) {
    errors.push({ row: lineNum, column: '题型', message: `第 ${lineNum} 行题型无效，支持：单选题/多选题/判断题/填空题/简答题` })
    return { errors }
  }
  if (!stem) {
    errors.push({ row: lineNum, column: '题干', message: `第 ${lineNum} 行题干不能为空` })
  }
  if (!knowledgePoint) {
    errors.push({ row: lineNum, column: '知识点', message: `第 ${lineNum} 行知识点不能为空` })
  }

  const score = Number(scoreRaw)
  if (Number.isNaN(score) || score <= 0) {
    errors.push({ row: lineNum, column: '分值', message: `第 ${lineNum} 行分值须为正数` })
  }

  let options: { key: string; text: string }[] | undefined
  let normalizedAnswer = answer
  let answerList: string[] | undefined

  if (type === 'single_choice' || type === 'multi_choice') {
    options = [
      { key: 'A', text: optA },
      { key: 'B', text: optB },
      { key: 'C', text: optC },
      { key: 'D', text: optD },
    ]
    if (options.some((o) => !o.text)) {
      errors.push({ row: lineNum, column: '选项', message: `第 ${lineNum} 行选择题四个选项均不能为空` })
    }
    if (!answer) {
      errors.push({ row: lineNum, column: '参考答案', message: `第 ${lineNum} 行参考答案不能为空` })
    }
  } else if (type === 'judge') {
    const lower = answer.toLowerCase()
    if (!['true', 'false', '正确', '错误', '1', '0'].includes(lower)) {
      errors.push({ row: lineNum, column: '参考答案', message: `第 ${lineNum} 行判断题答案须为 正确/错误 或 true/false` })
    } else {
      normalizedAnswer = ['true', '正确', '1'].includes(lower) ? 'true' : 'false'
    }
  } else if (type === 'fill_blank') {
    if (!answer) {
      errors.push({ row: lineNum, column: '参考答案', message: `第 ${lineNum} 行填空题参考答案不能为空` })
    }
    answerList = answer.split(/[、|]/).map((s) => s.trim()).filter(Boolean)
  } else if (type === 'short_answer') {
    if (!answer) {
      errors.push({ row: lineNum, column: '参考答案', message: `第 ${lineNum} 行简答题参考答案不能为空` })
    }
  }

  if (errors.length) return { errors }

  return {
    row: {
      type,
      stem,
      options,
      answer: normalizedAnswer,
      answerList,
      explanation,
      knowledgePoint,
      difficulty: normalizeDifficulty(difficultyRaw),
      score: score || 5,
    },
    errors,
  }
}

function validateHeaders(headers: string[]): ValidationError[] {
  const errors: ValidationError[] = []
  questionTemplateHeaders.forEach((col, idx) => {
    const actual = headers[idx]?.trim()
    if (actual !== col) {
      errors.push({
        row: 1,
        column: col,
        message: `第 1 行第 ${idx + 1} 列应为「${col}」，实际为「${actual || '空'}」`,
      })
    }
  })
  return errors
}

function parseDataRows(dataRows: string[][]): QuestionValidateResult {
  const errors: ValidationError[] = []
  const rows: ParsedQuestionRow[] = []

  dataRows.forEach((cells, idx) => {
    if (cells.every((c) => !c?.trim())) return
    const { row, errors: rowErrors } = parseRow(cells, idx + 2)
    errors.push(...rowErrors)
    if (row) rows.push(row)
  })

  return { valid: errors.length === 0, errors, rowCount: rows.length, rows }
}

export async function validateQuestionExcelFile(file: File): Promise<QuestionValidateResult> {
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  const sheet = workbook.Sheets[workbook.SheetNames[0]!]
  if (!sheet) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件为空或无法解析' }], rowCount: 0, rows: [] }
  }

  const raw = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, defval: '' })
  if (!raw.length) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件无数据' }], rowCount: 0, rows: [] }
  }

  const headers = (raw[0] as string[]).map((h) => String(h).trim())
  const headerErrors = validateHeaders(headers)
  const dataRows = raw.slice(1).map((r) => (r as string[]).map((c) => String(c ?? '').trim()))
  const result = parseDataRows(dataRows)
  return { ...result, errors: [...headerErrors, ...result.errors] }
}

export async function validateQuestionTxtFile(file: File): Promise<QuestionValidateResult> {
  const text = await file.text()
  if (text.includes('\t')) {
    return {
      valid: false,
      errors: [{ row: 0, column: '—', message: 'Txt 文件须为英文逗号分隔，不支持 Tab 分隔' }],
      rowCount: 0,
      rows: [],
    }
  }

  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (!lines.length) {
    return { valid: false, errors: [{ row: 0, column: '—', message: '文件无数据' }], rowCount: 0, rows: [] }
  }

  const headers = lines[0]!.split(',').map((h) => h.trim())
  const headerErrors = validateHeaders(headers)
  const dataRows = lines.slice(1).map((l) => l.split(',').map((c) => c.trim()))
  const result = parseDataRows(dataRows)
  return { ...result, errors: [...headerErrors, ...result.errors] }
}

export async function validateQuestionUploadFile(file: File): Promise<QuestionValidateResult> {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext === 'xlsx') return validateQuestionExcelFile(file)
  if (ext === 'txt') return validateQuestionTxtFile(file)
  return {
    valid: false,
    errors: [{ row: 0, column: '—', message: '仅支持 .xlsx（Excel）或 .txt（UTF-8 英文逗号分隔）格式' }],
    rowCount: 0,
    rows: [],
  }
}
