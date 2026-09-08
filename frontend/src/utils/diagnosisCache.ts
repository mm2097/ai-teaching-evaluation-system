import type { DiagnosisReport, DiagnosisStep } from '@/types'

export interface DiagnosisAskMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface DiagnosisCacheEntry {
  key: string
  savedAt: number
  semesterId?: number
  courseId?: number
  classId?: number
  studentId?: number
  courseName?: string
  targetName?: string
  scope?: 'class' | 'student'
  semesterName?: string
  className?: string
  dimensionLabels?: string[]
  report: DiagnosisReport | null
  rawContent: string
  processSteps: DiagnosisStep[]
  askMessages: DiagnosisAskMessage[]
  dimensions: string[]
  depth: 'detail' | 'brief'
}

const STORAGE_KEY = 'teaching_eval_diagnosis_cache_v1'
const CACHE_TTL_MS = 3 * 24 * 60 * 60 * 1000
const MAX_CACHE_ENTRIES = 5
const MAX_ASK_MESSAGES = 10

function readEntries(): DiagnosisCacheEntry[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as unknown
    if (!Array.isArray(parsed)) return []
    const validAfter = Date.now() - CACHE_TTL_MS
    return parsed.filter((item): item is DiagnosisCacheEntry => {
      if (!item || typeof item !== 'object') return false
      const entry = item as Partial<DiagnosisCacheEntry>
      return typeof entry.key === 'string'
        && typeof entry.savedAt === 'number'
        && entry.savedAt >= validAfter
    })
  } catch {
    return []
  }
}

function writeEntries(entries: DiagnosisCacheEntry[]): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_CACHE_ENTRIES)))
    return true
  } catch {
    // 浏览器禁用存储或空间不足时，不影响正常分析流程。
    return false
  }
}

export function loadDiagnosisCache(key: string): DiagnosisCacheEntry | null {
  const entries = readEntries()
  writeEntries(entries)
  return entries.find((entry) => entry.key === key) ?? null
}

export function listDiagnosisCaches(): DiagnosisCacheEntry[] {
  const entries = readEntries().sort((a, b) => b.savedAt - a.savedAt)
  writeEntries(entries)
  return entries
}

export function saveDiagnosisCache(entry: DiagnosisCacheEntry): boolean {
  const normalized: DiagnosisCacheEntry = {
    ...entry,
    processSteps: entry.processSteps.map((step) => ({
      ...step,
      toolCalls: step.toolCalls.map(({ result: _result, ...call }) => call),
    })),
    askMessages: entry.askMessages.slice(-MAX_ASK_MESSAGES),
  }
  const entries = readEntries().filter((item) => item.key !== entry.key)
  return writeEntries([normalized, ...entries])
}

export function removeDiagnosisCache(key: string): void {
  writeEntries(readEntries().filter((entry) => entry.key !== key))
}
