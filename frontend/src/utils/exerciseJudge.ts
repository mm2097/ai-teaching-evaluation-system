/**
 * 客观题判分工具（规则匹配，非 AI）
 * 对齐 AI算法_需求与开发文档 第 5 章
 */
import type { ExerciseOption, ExerciseType, QuizQuestion } from '@/types'

/** 判断题固定选项 */
export const JUDGE_OPTIONS: ExerciseOption[] = [
  { key: 'A', text: '对' },
  { key: 'B', text: '错' },
]

/** 判断题答案展示文案 */
export function formatJudgeAnswer(answer: string | boolean | undefined): string {
  if (answer === true || answer === 'true' || answer === '1') return '对'
  if (answer === false || answer === 'false' || answer === '0') return '错'
  const normalized = String(answer ?? '').trim().toLowerCase()
  if (['对', '正确', '是', 'yes'].includes(normalized)) return '对'
  if (['错', '错误', '否', 'no'].includes(normalized)) return '错'
  return String(answer ?? '')
}

/** 判断题选项对应的提交值 */
export function judgeOptionAnswerValue(opt: ExerciseOption): string {
  const text = opt.text.trim()
  if (opt.key === 'true' || text === '对' || text === '正确') return 'true'
  if (opt.key === 'false' || text === '错' || text === '错误') return 'false'
  return opt.key === 'A' ? 'true' : 'false'
}

/** 获取题目展示用选项（判断题自动补全对/错） */
export function getQuestionOptions(question: Pick<QuizQuestion, 'type' | 'options'>): ExerciseOption[] {
  if (question.type === 'judge') {
    return question.options?.length ? question.options : JUDGE_OPTIONS
  }
  return question.options ?? []
}

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
      const normalized = String(studentAnswer).trim().toLowerCase()
      const actual = studentAnswer === true
        || studentAnswer === 'true'
        || ['对', '正确', '是', '1'].includes(normalized)
      const actualFalse = studentAnswer === false
        || studentAnswer === 'false'
        || ['错', '错误', '否', '0'].includes(normalized)
      if (actualFalse && !actual) return !expected
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

/** 全部 5 类题型（与后端 type 1–5 一致） */
export const ALL_EXERCISE_TYPES: ExerciseType[] = [
  'single_choice',
  'multi_choice',
  'judge',
  'fill_blank',
  'short_answer',
]

const TYPE_INT_TO_STR: Record<number, ExerciseType> = {
  1: 'single_choice',
  2: 'multi_choice',
  3: 'judge',
  4: 'fill_blank',
  5: 'short_answer',
}

/** 将后端题型（字符串或数字）规范为 ExerciseType */
export function normalizeExerciseType(raw: string | number): ExerciseType {
  const numeric = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isNaN(numeric) && TYPE_INT_TO_STR[numeric]) {
    return TYPE_INT_TO_STR[numeric]
  }
  const text = String(raw) as ExerciseType
  if (ALL_EXERCISE_TYPES.includes(text)) return text
  return 'single_choice'
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
