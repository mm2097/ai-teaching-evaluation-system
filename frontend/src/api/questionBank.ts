/**
 * 题库管理 API（调用真实后端 /api/v1/question-bank）
 */
import request from '@/utils/request'
import type { ParsedQuestionRow } from '@/utils/questionTemplateValidator'
import { ALL_EXERCISE_TYPES, exerciseTypeLabels, normalizeExerciseType } from '@/utils/exerciseJudge'
import type {
  DifficultyLevel,
  ExerciseSource,
  ExerciseType,
  QuestionBankStats,
  QuizQuestion,
} from '@/types'

export interface QuestionRecord {
  id: number
  courseId: number
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  options?: { key: string; text: string }[] | string[]
  answer?: string
  explanation?: string
  difficulty: string
  source?: string
  createdTime: string
}

export interface QuestionTypeOption {
  value: string
  label: string
}

export const questionTypeOptions: QuestionTypeOption[] = ALL_EXERCISE_TYPES.map((t) => ({
  value: t,
  label: exerciseTypeLabels[t],
}))

function parseQuestionOptions(raw: QuestionRecord['options']): { key: string; text: string }[] | undefined {
  if (!raw?.length) return undefined
  return raw.map((item, index) => {
    if (typeof item === 'string') {
      const match = item.match(/^\s*([A-Za-z])\s*[.、．:]\s*(.*)$/)
      return {
        key: match?.[1]?.toUpperCase() ?? String.fromCharCode(65 + index),
        text: match?.[2] ?? item,
      }
    }
    return { key: item.key, text: item.text }
  })
}

function mapRecordToQuizQuestion(q: QuestionRecord): QuizQuestion {
  const answer = q.answer ?? ''
  const type = normalizeExerciseType(q.type)
  return {
    id: q.id,
    courseId: q.courseId,
    courseName: q.courseName,
    type,
    stem: q.content,
    options: parseQuestionOptions(q.options),
    answer,
    answerList: type === 'fill_blank' && answer
      ? answer.split(/[,、|]/).map((s) => s.trim()).filter(Boolean)
      : undefined,
    explanation: q.explanation,
    knowledgePoint: q.knowledgePoint,
    difficulty: q.difficulty as DifficultyLevel,
    score: type === 'short_answer' ? 10 : 5,
    status: 'published',
    source: (q.source as QuizQuestion['source']) || 'manual',
  }
}

export interface AddQuestionParams {
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  difficulty: string
}

export interface FetchQuestionBankParams {
  course_id?: number
  status?: string
}

export interface QuestionBankItem {
  courseId: number
  type: string
  stem: string
  options?: { key: string; text: string }[]
  answer: string
  answerList?: string[]
  explanation?: string
  knowledgePoint?: string
  difficulty?: string
  score?: number
}

export interface AddToBankOptions {
  source?: string
}

export interface AddToBankResult {
  added: number
  skipped: number
}

export interface QuestionImportResult {
  imported: number
  skipped: number
}

export interface QuestionBuiltinTemplate {
  id: string
  name: string
  courseId: number
  courseName: string
  questionCount: number
  description: string
}

/** 获取题库列表 */
export async function fetchQuestionBankList(params?: FetchQuestionBankParams): Promise<QuestionRecord[]> {
  const res = await request.get('/v1/question-bank', { params })
  return res.data
}

/** 获取题库列表（QuizManageView 使用的名字） */
export async function fetchQuestionBank(params: FetchQuestionBankParams): Promise<QuizQuestion[]> {
  const res = await request.get('/v1/question-bank', { params })
  const items = res.data as QuestionRecord[]
  return items.map(mapRecordToQuizQuestion)
}

/** 新增单道试题 */
export async function addQuestion(params: AddQuestionParams): Promise<void> {
  await request.post('/v1/question-bank', {
    questions: [params],
    source: 'manual',
  })
}

/** 批量新增题目到题库 */
export async function addQuestionsToBank(
  questions: QuestionBankItem[],
  options?: AddToBankOptions,
): Promise<AddToBankResult> {
  const res = await request.post('/v1/question-bank', {
    questions,
    source: options?.source || 'manual',
  })
  return res.data
}

/** 检查题干是否已在题库中 */
export async function checkQuestionsInBank(
  stems: string[],
  courseId: number,
): Promise<Record<string, boolean>> {
  const res = await request.post('/v1/question-bank/check', { stems, courseId })
  return res.data.status
}

/** 获取内置模板列表 */
export async function fetchBuiltinTemplates(courseId?: number): Promise<QuestionBuiltinTemplate[]> {
  const res = await request.get('/v1/question-bank/templates', {
    params: courseId ? { course_id: courseId } : {},
  })
  return res.data
}

/** 从文件解析后的行导入 */
export async function importQuestionsFromFile(
  courseId: number,
  rows: ParsedQuestionRow[],
): Promise<QuestionImportResult> {
  const res = await request.post('/v1/question-bank/import-rows', {
    courseId,
    rows: rows.map((r) => ({
      type: r.type,
      stem: r.stem,
      options: r.options,
      answer: r.answer,
      answerList: r.answerList,
      explanation: r.explanation,
      knowledgePoint: r.knowledgePoint,
      difficulty: r.difficulty,
      score: r.score,
    })),
  })
  return res.data
}

/** 从内置模板导入 */
export async function importQuestionsFromBuiltin(
  courseId: number,
  templateId: string,
): Promise<QuestionImportResult> {
  const res = await request.post('/v1/question-bank/import-builtin', {
    courseId,
    templateId,
  })
  return res.data
}

// ===== QuestionBankView 使用的接口 =====

/** 获取课程知识点选项（课程知识树 + 题库已有题目合并去重） */
export async function fetchCourseKnowledgePoints(courseId?: number): Promise<string[]> {
  if (!courseId) return []

  const names = new Set<string>()

  try {
    const heatmapRes = await request.get<{ knowledgePoints?: string[] }>(
      '/v1/analysis/knowledge-heatmap',
      { params: { course_id: courseId } },
    )
    for (const kp of heatmapRes.data?.knowledgePoints ?? []) {
      if (kp?.trim()) names.add(kp.trim())
    }
  } catch {
    // 热力图接口不可用时，继续从题库提取
  }

  try {
    const bankRes = await request.get<QuestionRecord[]>('/v1/question-bank', {
      params: { course_id: courseId },
    })
    for (const q of bankRes.data ?? []) {
      if (q.knowledgePoint?.trim()) names.add(q.knowledgePoint.trim())
    }
  } catch {
    // ignore
  }

  return Array.from(names).sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

/** 题库统计（按课程维度） */
export async function fetchQuestionBankStats(courseId?: number): Promise<QuestionBankStats> {
  const params: FetchQuestionBankParams = courseId ? { course_id: courseId } : {}
  const res = await request.get<QuestionRecord[]>('/v1/question-bank', { params })
  const items = res.data
  const stats: QuestionBankStats = {
    total: items.length,
    byType: { single_choice: 0, multi_choice: 0, judge: 0, fill_blank: 0, short_answer: 0 },
    bySource: { ai: 0, manual: 0, import: 0 } as Record<ExerciseSource, number>,
    byDifficulty: { easy: 0, medium: 0, hard: 0 },
  }
  for (const q of items) {
    const type = normalizeExerciseType(q.type)
    if (type in stats.byType) (stats.byType[type] as number)++
    if (q.difficulty in stats.byDifficulty) (stats.byDifficulty[q.difficulty as DifficultyLevel] as number)++
  }
  return stats
}

/** 新增单道题目（QuestionBankView 使用） */
export async function createQuestion(question: Omit<QuizQuestion, 'id'>): Promise<void> {
  await request.post('/v1/question-bank', {
    questions: [
      {
        courseId: question.courseId,
        type: question.type,
        stem: question.stem,
        options: question.options,
        answer: question.answer,
        answerList: question.answerList,
        explanation: question.explanation,
        knowledgePoint: question.knowledgePoint,
        difficulty: question.difficulty,
        score: question.score,
      },
    ],
    source: question.source || 'manual',
  })
}

/** 更新题目 */
export async function updateQuestion(id: number, question: Partial<QuizQuestion>): Promise<void> {
  await request.put(`/v1/question-bank/${id}`, {
    type: question.type,
    stem: question.stem,
    options: question.options,
    answer: question.answer,
    answerList: question.answerList,
    explanation: question.explanation,
    knowledgePoint: question.knowledgePoint,
    difficulty: question.difficulty,
    score: question.score,
  })
}

/** 删除题目 */
export async function deleteQuestion(id: number): Promise<void> {
  await request.delete(`/v1/question-bank/${id}`)
}
