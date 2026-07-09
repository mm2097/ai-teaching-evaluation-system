/**
 * 题库管理 API（调用真实后端 /api/v1/question-bank）
 */
import request from '@/utils/request'
import type { ParsedQuestionRow } from '@/utils/questionTemplateValidator'

export interface QuestionRecord {
  id: number
  courseId: number
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  difficulty: string
  createdTime: string
}

export interface QuestionTypeOption {
  value: string
  label: string
}

export const questionTypeOptions: QuestionTypeOption[] = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multi_choice', label: '多选题' },
  { value: 'judge', label: '判断题' },
  { value: 'fill_blank', label: '填空题' },
]

export interface AddQuestionParams {
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  difficulty: string
}

export interface FetchQuestionBankParams {
  courseId?: number
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
export async function fetchQuestionBank(params: FetchQuestionBankParams): Promise<import('@/types').QuizQuestion[]> {
  const res = await request.get('/v1/question-bank', { params })
  const items = res.data as QuestionRecord[]
  return items.map((q) => ({
    id: q.id,
    courseId: q.courseId,
    type: q.type as import('@/types').ExerciseType,
    stem: q.content,
    answer: q.content,
    knowledgePoint: q.knowledgePoint,
    difficulty: q.difficulty as import('@/types').DifficultyLevel,
    score: 0,
  }))
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
