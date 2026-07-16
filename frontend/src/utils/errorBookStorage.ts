/**
 * 错题本本地存储（后端无专用接口，前端持久化）
 */
import type { QuizQuestion } from '@/types'
import type { ErrorBookItem } from '@/api/quiz'

const STORAGE_PREFIX = 'student_error_book_'

export function loadLocalErrorBook(studentId: number): ErrorBookItem[] {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${studentId}`)
    return raw ? (JSON.parse(raw) as ErrorBookItem[]) : []
  } catch {
    return []
  }
}

export function appendLocalErrorBook(studentId: number, items: ErrorBookItem[]): void {
  if (!items.length) return
  const existing = loadLocalErrorBook(studentId)
  const merged = [...items, ...existing]
  localStorage.setItem(`${STORAGE_PREFIX}${studentId}`, JSON.stringify(merged))
}

export function buildErrorBookItems(
  details: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    manualRequired?: boolean
    aiScore?: number | null
    aiReason?: string
  }[],
): ErrorBookItem[] {
  const now = new Date().toLocaleString('zh-CN', { hour12: false })
  return details
    .filter((d) => !d.correct && !d.manualRequired)
    .map((d) => ({
      quizQuestion: d.question,
      userAnswer: String(d.userAnswer ?? ''),
      correctAnswer: d.question.answer,
      submitTime: now,
      knowledgePoint: d.question.knowledgePoint,
      aiScore: d.aiScore,
      aiReason: d.aiReason,
    }))
}

/** 过滤自主练习任务（前端标识，不展示在教师布置列表） */
export const SELF_PRACTICE_PREFIX = '【自主练习】'

export function isSelfPracticeTask(title: string): boolean {
  return title.startsWith(SELF_PRACTICE_PREFIX)
}
