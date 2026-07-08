/**
 * 题库管理 API
 * 对齐 AI算法_需求与开发文档 题目管理接口 + Agent get_existing_exercises 工具
 */
import request from '@/utils/request'
import { delay } from '@/utils/auth'
import type { ParsedQuestionRow } from '@/utils/questionTemplateValidator'
import {
  questionBankItems,
  allocateQuestionId,
  builtinQuestionTemplates,
  builtinTemplatePools,
  isStemInBank,
} from '@/mock/questionBank'
import type {
  AddToBankResult,
  DifficultyLevel,
  ExerciseSource,
  ExerciseType,
  QuestionBankQuery,
  QuestionBankStats,
  QuestionBuiltinTemplate,
  QuestionImportResult,
  QuizQuestion,
} from '@/types'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

function filterItems(items: QuizQuestion[], params?: QuestionBankQuery): QuizQuestion[] {
  if (!params) return items
  return items.filter((q) => {
    if (params.courseId && q.courseId !== params.courseId) return false
    if (params.knowledgePoint && q.knowledgePoint !== params.knowledgePoint) return false
    if (params.type && q.type !== params.type) return false
    if (params.difficulty && q.difficulty !== params.difficulty) return false
    if (params.source && q.source !== params.source) return false
    if (params.status && q.status !== params.status) return false
    if (params.keyword) {
      const kw = params.keyword.toLowerCase()
      if (!q.stem.toLowerCase().includes(kw) && !q.knowledgePoint.toLowerCase().includes(kw)) {
        return false
      }
    }
    return true
  })
}

function calcStats(items: QuizQuestion[]): QuestionBankStats {
  const byType = { single_choice: 0, multi_choice: 0, judge: 0, fill_blank: 0 } as Record<ExerciseType, number>
  const bySource = { ai: 0, manual: 0, import: 0 } as Record<ExerciseSource, number>
  const byDifficulty = { easy: 0, medium: 0, hard: 0 } as Record<DifficultyLevel, number>

  items.forEach((q) => {
    byType[q.type]++
    if (q.source) bySource[q.source]++
    byDifficulty[q.difficulty]++
  })

  return { total: items.length, byType, bySource, byDifficulty }
}

function rowToQuestion(row: ParsedQuestionRow, courseId: number, source: ExerciseSource): Omit<QuizQuestion, 'id'> {
  return {
    courseId,
    type: row.type,
    stem: row.stem,
    options: row.options,
    answer: row.answer,
    answerList: row.answerList,
    explanation: row.explanation,
    knowledgePoint: row.knowledgePoint,
    difficulty: row.difficulty,
    score: row.score,
    status: 'published',
    source,
  }
}

function importQuestions(items: Omit<QuizQuestion, 'id'>[], courseId: number): QuestionImportResult {
  let imported = 0
  let skipped = 0
  items.forEach((item) => {
    if (isStemInBank(item.stem, courseId)) {
      skipped++
      return
    }
    questionBankItems.unshift({ ...item, id: allocateQuestionId(), courseId, status: 'published' })
    imported++
  })
  return { imported, skipped }
}

/** 查询题库列表 */
export async function fetchQuestionBank(params?: QuestionBankQuery): Promise<QuizQuestion[]> {
  if (USE_MOCK) {
    await delay(300)
    return filterItems(questionBankItems, params)
  }
  const { data } = await request.get<QuizQuestion[]>('/v1/exercises', { params })
  return data
}

/** 获取内置模板目录 */
export async function fetchBuiltinTemplates(courseId?: number): Promise<QuestionBuiltinTemplate[]> {
  if (USE_MOCK) {
    await delay(200)
    if (!courseId) return builtinQuestionTemplates
    return builtinQuestionTemplates.filter((t) => t.courseId === courseId)
  }
  const { data } = await request.get<QuestionBuiltinTemplate[]>('/v1/exercises/templates', {
    params: { course_id: courseId },
  })
  return data
}

/** 获取题库统计 */
export async function fetchQuestionBankStats(courseId?: number): Promise<QuestionBankStats> {
  if (USE_MOCK) {
    await delay(150)
    const items = filterItems(questionBankItems, { courseId, status: 'published' })
    return calcStats(items)
  }
  const { data } = await request.get<QuestionBankStats>('/v1/exercises/stats', { params: { course_id: courseId } })
  return data
}

/** 新增题目（手动录入） */
export async function createQuestion(question: Omit<QuizQuestion, 'id'>): Promise<QuizQuestion> {
  if (USE_MOCK) {
    await delay(400)
    const newQ: QuizQuestion = { ...question, id: allocateQuestionId(), status: 'published' }
    questionBankItems.unshift(newQ)
    return newQ
  }
  const { data } = await request.post<QuizQuestion>('/v1/exercises', question)
  return data
}

/** 更新题目 */
export async function updateQuestion(id: number, patch: Partial<QuizQuestion>): Promise<QuizQuestion> {
  if (USE_MOCK) {
    await delay(300)
    const idx = questionBankItems.findIndex((q) => q.id === id)
    if (idx >= 0) {
      questionBankItems[idx] = { ...questionBankItems[idx]!, ...patch }
      return questionBankItems[idx]!
    }
    throw new Error('题目不存在')
  }
  const { data } = await request.put<QuizQuestion>(`/v1/exercises/${id}`, patch)
  return data
}

/** 删除题目 */
export async function deleteQuestion(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(200)
    const idx = questionBankItems.findIndex((q) => q.id === id)
    if (idx >= 0) questionBankItems.splice(idx, 1)
    return
  }
  await request.delete(`/v1/exercises/${id}`)
}

/** 从用户上传文件批量导入（xlsx/txt） */
export async function importQuestionsFromFile(
  courseId: number,
  rows: ParsedQuestionRow[],
): Promise<QuestionImportResult> {
  if (USE_MOCK) {
    await delay(800)
    const items = rows.map((row) => rowToQuestion(row, courseId, 'import'))
    return importQuestions(items, courseId)
  }
  const { data } = await request.post<QuestionImportResult>('/v1/exercises/import/file', {
    course_id: courseId,
    questions: rows,
  })
  return data
}

/** 从内置参考模板导入 */
export async function importQuestionsFromBuiltin(
  courseId: number,
  templateId: string,
): Promise<QuestionImportResult> {
  if (USE_MOCK) {
    await delay(1000)
    const pool = builtinTemplatePools[templateId]
    if (!pool) return { imported: 0, skipped: 0 }
    const items = pool.map((q) => ({ ...q, courseId }))
    return importQuestions(items, courseId)
  }
  const { data } = await request.post<QuestionImportResult>('/v1/exercises/import/builtin', {
    course_id: courseId,
    template_id: templateId,
  })
  return data
}

/** AI 生成题 / 预览题批量加入题库 */
export async function addQuestionsToBank(
  questions: QuizQuestion[],
  options?: { source?: ExerciseSource },
): Promise<AddToBankResult> {
  if (USE_MOCK) {
    await delay(500)
    const source = options?.source ?? 'ai'
    let added = 0
    let skipped = 0

    questions.forEach((q) => {
      if (isStemInBank(q.stem, q.courseId)) {
        skipped++
        return
      }
      questionBankItems.unshift({
        ...q,
        id: allocateQuestionId(),
        source,
        status: 'published',
        batchId: q.batchId,
      })
      added++
    })
    return { added, skipped }
  }
  const { data } = await request.post<AddToBankResult>('/v1/exercises/bank/batch', {
    questions,
    source: options?.source ?? 'ai',
  })
  return data
}

/** 检查题目是否已在题库 */
export async function checkQuestionsInBank(
  stems: string[],
  courseId?: number,
): Promise<Record<string, boolean>> {
  if (USE_MOCK) {
    await delay(100)
    const result: Record<string, boolean> = {}
    stems.forEach((stem) => {
      result[stem] = isStemInBank(stem, courseId)
    })
    return result
  }
  const { data } = await request.post<Record<string, boolean>>('/v1/exercises/bank/check', {
    stems,
    course_id: courseId,
  })
  return data
}

/** 按 ID 批量获取题目（组卷选题用） */
export async function fetchQuestionsByIds(ids: number[]): Promise<QuizQuestion[]> {
  if (USE_MOCK) {
    await delay(200)
    const map = new Map(questionBankItems.map((q) => [q.id, q]))
    return ids.map((id) => map.get(id)).filter(Boolean) as QuizQuestion[]
  }
  const { data } = await request.post<QuizQuestion[]>('/v1/exercises/batch', { ids })
  return data
}
