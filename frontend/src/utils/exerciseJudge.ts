/**
 * 客观题判分工具（规则匹配，非 AI）
 * 对齐 AI算法_需求与开发文档 第 5 章
 */
import type { ExerciseType, QuizQuestion } from '@/types'

function normalizeText(value: string): string {
  return value.trim().toLowerCase()
}

/** 判断单题是否正确 */
export function judgeAnswer(question: QuizQuestion, studentAnswer: string | boolean | undefined): boolean {
  if (studentAnswer === undefined || studentAnswer === '') return false

  switch (question.type) {
    case 'single_choice':
      return String(studentAnswer).trim().toUpperCase() === question.answer.trim().toUpperCase()

    case 'multi_choice': {
      const expected = new Set(question.answer.toUpperCase().split(''))
      const actual = new Set(String(studentAnswer).toUpperCase().split(''))
      if (expected.size !== actual.size) return false
      for (const key of expected) {
        if (!actual.has(key)) return false
      }
      return true
    }

    case 'judge': {
      const expected = question.answer === 'true' || question.answer === '1'
      const actual = studentAnswer === true || studentAnswer === 'true'
      return expected === actual
    }

    case 'fill_blank': {
      const acceptable = question.answerList?.length
        ? question.answerList
        : [question.answer]
      const normalized = normalizeText(String(studentAnswer))
      return acceptable.some((item) => normalizeText(item) === normalized)
    }

    case 'short_answer':
      // 简答题由后端 AI 判分，前端不参与规则判分
      return false

    default:
      return false
  }
}

/** 计算答卷得分 */
export function calcQuizScore(
  questions: QuizQuestion[],
  answers: Record<number, string | boolean>,
): number {
  return questions.reduce((total, question) => {
    return judgeAnswer(question, answers[question.id]) ? total + question.score : total
  }, 0)
}

/** 题型中文标签 */
export const exerciseTypeLabels: Record<ExerciseType, string> = {
  single_choice: '单选题',
  multi_choice: '多选题',
  judge: '判断题',
  fill_blank: '填空题',
  short_answer: '简答题',
}

/** 难度中文标签 */
export const difficultyLabels: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}
