/**
 * 答题记录 API（调用真实后端 /api/v1/answer-records）
 */
import request, { USE_MOCK } from '@/utils/request'
import {
  appendLocalErrorBook,
  buildErrorBookItems,
  isSelfPracticeTask,
  loadLocalErrorBook,
} from '@/utils/errorBookStorage'
import { judgeAnswer } from '@/utils/exerciseJudge'
import type {
  DifficultyLevel,
  ExerciseType,
  QuizAssignment,
  QuizQuestion,
  QuizSubmission,
  RagReference,
} from '@/types'

export type QuizAssignmentRecord = QuizAssignment
export type QuizSubmissionRecord = QuizSubmission

interface QuizQuestionResult {
  question: QuizQuestion
  userAnswer: string | string[]
  isCorrect: boolean
  manualRequired?: boolean
  aiScore?: number | null
  aiReason?: string
}

/** 答题任务查询参数 */
export interface QuizAssignmentQuery {
  courseId?: number
  teacherId?: number
}

/** 获取答题任务列表 */
export async function fetchQuizAssignments(params?: QuizAssignmentQuery): Promise<QuizAssignmentRecord[]> {
  try {
    const res = await request.get('/v1/answer-tasks', { params })
    return res.data
  } catch {
    return []
  }
}

/** 获取答题记录列表 */
export async function fetchQuizSubmissions(taskId?: number): Promise<QuizSubmissionRecord[]> {
  try {
    const res = await request.get('/v1/answer-records', {
      params: taskId ? { task_id: taskId } : undefined,
    })
    return res.data
  } catch {
    return []
  }
}

/** 答题结果详情（含逐题对错） */
export async function fetchQuizResult(
  submissionId: number,
  _studentId: number,
): Promise<{
  score: number
  totalScore: number
  questionResults: QuizQuestionResult[]
}> {
  if (USE_MOCK) {
    return mockQuizResult(submissionId)
  }
  const res = await request.get('/v1/answer-records/' + submissionId)
  return res.data
}

/** 错题本条目 */
export interface ErrorBookItem {
  quizQuestion: QuizQuestion
  userAnswer: string | string[]
  correctAnswer: string | string[]
  submitTime: string
  knowledgePoint: string
  aiScore?: number | null
  aiReason?: string
}

/** 错题本（本地存储，聚合教师布置 + 自主练习错题） */
export async function fetchErrorBook(studentId: number): Promise<ErrorBookItem[]> {
  if (USE_MOCK) {
    return mockErrorBook(studentId)
  }
  return loadLocalErrorBook(studentId)
}

/** 提交后将错题写入本地错题本 */
export function syncWrongAnswersToErrorBook(
  studentId: number,
  details: QuizSubmitResult['details'],
): void {
  appendLocalErrorBook(studentId, buildErrorBookItems(details))
}

// ===== QuizManageView 使用的接口 =====

/** AI 生成练习题请求参数 */
export interface GenerateQuizParams {
  courseId: number
  classId: number
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  questionCount: number
  difficulty?: DifficultyLevel  // 兼容旧前端单一难度
  difficultyDistribution?: { easy: number; medium: number; hard: number }
  extraRequirements?: string
}

/** AI 生成练习题响应 */
export interface GenerateQuizResult {
  questions: QuizQuestion[]
  ragReferences: RagReference[]
  meta: {
    model: string
    elapsedMs: number
  }
}

export interface StartSelfPracticeResult {
  assignment: QuizAssignment
  meta: GenerateQuizResult['meta']
}

/** 保存练习任务参数 */
export interface SaveQuizAssignmentParams {
  title: string
  courseId: number
  courseName: string
  classId: number
  className: string
  teacherName: string
  knowledgePoints: string[]
  status: 'draft' | 'published'
  questions: QuizQuestion[]
  deadline?: string  // 截止时间，如 "2026-07-20 23:59"
  allowReview?: boolean  // 是否允许学生交卷后查看题目详情
}

function buildGeneratePayload(params: GenerateQuizParams) {
  const payload: Record<string, any> = {
    courseId: params.courseId,
    knowledgePoints: params.knowledgePoints.length ? params.knowledgePoints : ['综合'],
    questionTypes: params.questionTypes,
    questionCount: params.questionCount,
    extraRequirements: params.extraRequirements || '',
  }
  // 优先使用难度分布，回退到单一难度（兼容旧前端）
  if (params.difficultyDistribution) {
    payload.difficultyDistribution = params.difficultyDistribution
  } else {
    payload.difficulty = params.difficulty || 'medium'
  }
  return payload
}

/** LLM 偶发返回非 JSON 时自动重试（与教师端共用同一算法服务） */
async function postWithGenerateRetry<T>(url: string, params: GenerateQuizParams): Promise<T> {
  const payload = buildGeneratePayload(params)
  const maxAttempts = 3
  let lastError: unknown

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await request.post(url, payload, {
        timeout: 70000,
        silentError: attempt < maxAttempts,
      } as Parameters<typeof request.post>[2])
      return res.data as T
    } catch (error) {
      lastError = error
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const retriable = typeof detail === 'string' && (
        detail.includes('JSON 解析失败')
        || detail.includes('AI 服务暂不可用')
        || detail.includes('AI 服务错误')
      )
      if (!retriable || attempt === maxAttempts) {
        throw error
      }
      await new Promise((resolve) => setTimeout(resolve, 800 * attempt))
    }
  }

  throw lastError
}

/** AI 生成练习题（经后端代理调用算法服务 8001） */
export async function generateQuizQuestions(params: GenerateQuizParams): Promise<GenerateQuizResult> {
  const data = await postWithGenerateRetry<GenerateQuizResult>('/v1/exercises/generate', params)
  // 向后兼容：旧后端可能不返回 ragReferences
  if (!data.ragReferences) {
    data.ragReferences = []
  }
  return data
}

/** 创建学生私人练习，标准答案保留在后端，返回的试卷不含答案与解析 */
export async function startSelfPractice(params: GenerateQuizParams): Promise<StartSelfPracticeResult> {
  return postWithGenerateRetry<StartSelfPracticeResult>('/v1/self-practice/start', params)
}

/** SSE 流式生成回调 */
export interface StreamCallbacks {
  onStage?: (stage: string, difficulty?: string) => void
  onQuestion?: (question: QuizQuestion) => void
  onDone?: (ragReferences: RagReference[], totalCount: number) => void
  onError?: (message: string) => void
}

/** SSE 流式生成练习题（逐题推送，前端实时展示） */
export async function generateQuizStream(params: GenerateQuizParams, callbacks: StreamCallbacks): Promise<void> {
  const payload = buildGeneratePayload(params)

  try {
    const response = await fetch('/api/v1/exercises/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errText = await response.text().catch(() => 'AI 服务不可用')
      callbacks.onError?.(errText)
      return
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'stage') callbacks.onStage?.(event.stage, event.difficulty)
          else if (event.type === 'question') callbacks.onQuestion?.(event.question)
          else if (event.type === 'done') callbacks.onDone?.(event.ragReferences || [], event.totalCount || 0)
          else if (event.type === 'error') callbacks.onError?.(event.message || '生成失败')
        } catch { /* skip malformed */ }
      }
    }
  } catch (e) {
    // fetch 抛出（服务不可达/网络中断/读流失败）时兜底，避免调用方永久卡在加载态
    callbacks.onError?.(
      e instanceof Error ? `无法连接 AI 服务：${e.message}` : 'AI 服务暂不可用',
    )
  }
}

/** 保存练习任务（草稿或已发布） */
export async function saveQuizAssignment(params: SaveQuizAssignmentParams): Promise<QuizAssignmentRecord> {
  const res = await request.post('/v1/answer-tasks', params)
  return res.data
}

/** 发布练习任务 */
export async function publishQuizAssignment(id: number): Promise<void> {
  await request.post(`/v1/answer-tasks/${id}/publish`)
}

/** 关闭练习任务 */
export async function closeQuizAssignment(id: number): Promise<void> {
  await request.post(`/v1/answer-tasks/${id}/close`)
}

/** 修改查看权限（发布前后均可） */
export async function updateReviewPolicy(
  id: number,
  allowReview: boolean,
): Promise<{ id: number; allowReview: boolean; message: string }> {
  const { data } = await request.put(`/v1/answer-tasks/${id}/review-policy`, {
    allowReview,
  })
  return data
}

/** 重新开启/延长期限 */
export async function reopenQuizAssignment(
  id: number,
  deadline?: string,
): Promise<{ id: number; status: string; deadline: string; message: string }> {
  const { data } = await request.post(`/v1/answer-tasks/${id}/reopen`, {
    deadline: deadline || '',
  })
  return data
}

/** 获取学生的答题任务列表（前端过滤：仅已发布、非自主练习） */
export async function fetchStudentQuizzes(_studentId: number): Promise<QuizAssignment[]> {
  const tasks = await fetchQuizAssignments()
  return tasks.filter(
    (t) => (t.status === 'published' || t.status === 'closed') && !isSelfPracticeTask(t.title),
  ) as QuizAssignment[]
}

/** 学生自主练习提交参数 */
export interface SubmitSelfQuizParams {
  studentId: number
  taskId: number
  answers: Record<number, string | boolean>
}

/** 答题提交结果（含逐题详情，详情由前端组装） */
export interface QuizSubmitResult {
  submissionId: number
  score: number
  totalScore: number
  correctCount: number
  taskId?: number
  taskTitle?: string
  allowReview?: boolean
  details: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    manualRequired?: boolean
    aiScore?: number | null
    aiReason?: string
  }[]
}

function normalizeAnswers(answers: Record<number, string | string[] | boolean>): Record<string, string> {
  const normalized: Record<string, string> = {}
  for (const [k, v] of Object.entries(answers)) {
    normalized[String(k)] = typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v)
  }
  return normalized
}

/** 前端组装逐题判分详情（客观题规则判分，简答题标记待 AI 结果） */
export function buildSubmitDetails(
  questions: QuizQuestion[],
  answers: Record<number, string | boolean>,
  backendCorrectCount?: number,
  manualQuestionIds: number[] = [],
  backendQuestionResults: QuizQuestionResult[] = [],
): QuizSubmitResult['details'] {
  if (backendQuestionResults.length) {
    return backendQuestionResults.map((result) => ({
      question: result.question,
      correct: result.isCorrect,
      userAnswer: Array.isArray(result.userAnswer)
        ? result.userAnswer.join('')
        : result.userAnswer,
      manualRequired: result.manualRequired,
      aiScore: result.aiScore,
      aiReason: result.aiReason,
    }))
  }

  const manualQuestionSet = new Set(manualQuestionIds)
  const details = questions.map((q) => {
    const userAnswer = answers[q.id] ?? ''
    if (q.type === 'short_answer') {
      const manualRequired = manualQuestionSet.has(q.id)
      return {
        question: q,
        correct: false,
        userAnswer,
        manualRequired,
        aiReason: manualRequired ? 'AI 判分暂不可用，等待人工批改' : '简答题已由 AI 判分',
      }
    }
    return { question: q, correct: judgeAnswer(q, userAnswer), userAnswer }
  })

  // 若后端返回了 correctCount，尝试将简答题对错补齐（按得分差额推断）
  if (backendCorrectCount !== undefined) {
    const objectiveCorrect = details.filter((d) => d.question.type !== 'short_answer' && d.correct).length
    const shortItems = details.filter(
      (d) => d.question.type === 'short_answer' && !d.manualRequired,
    )
    let remaining = backendCorrectCount - objectiveCorrect
    shortItems.forEach((d) => {
      d.correct = remaining > 0
      if (d.correct) remaining -= 1
    })
  }
  return details
}

/** 提交答题答案（教师布置练习） */
export async function submitQuizAnswers(
  taskId: number,
  studentId: number,
  _studentName: string,
  answers: Record<number, string | string[] | boolean>,
  questions: QuizQuestion[],
): Promise<QuizSubmitResult> {
  const { data } = await request.post('/v1/answer-records', {
    task_id: taskId,
    student_id: studentId,
    answers: normalizeAnswers(answers),
  })
  // 教师禁止查看详情时，不构建逐题详情
  const details = data.allowReview
    ? buildSubmitDetails(
        questions,
        answers as Record<number, string | boolean>,
        data.correctCount,
        data.manualQuestionIds,
        data.questionResults,
      )
    : []
  if (data.allowReview !== false) {
    syncWrongAnswersToErrorBook(studentId, details)
  }
  return { ...data, details, allowReview: data.allowReview }
}

/** 学生自主练习：由后端原子化保存任务、映射临时题号并完成判分 */
export async function submitSelfQuiz(params: SubmitSelfQuizParams): Promise<QuizSubmitResult> {
  const { data } = await request.post('/v1/self-practice/submit', {
    taskId: params.taskId,
    answers: normalizeAnswers(params.answers),
  }, { timeout: 120000 })

  const details = data.allowReview
    ? buildSubmitDetails(
        [],
        params.answers,
        data.correctCount,
        data.manualQuestionIds,
        data.questionResults,
      )
    : []
  if (data.allowReview !== false) {
    syncWrongAnswersToErrorBook(params.studentId, details)
  }
  return {
    ...data,
    details,
    allowReview: data.allowReview,
  }
}

/* ============================================================
 * Mock 数据（USE_MOCK=true 时由 fetchQuizResult / fetchErrorBook 使用）
 * ============================================================ */

function mockQuizResult(_submissionId: number): {
  score: number
  totalScore: number
  questionResults: { question: QuizQuestion; userAnswer: string | string[]; isCorrect: boolean }[]
} {
  const questions: QuizQuestion[] = [
    {
      id: 1, type: 'single_choice', stem: '在长度为 n 的顺序表中删除一个元素，平均需要移动多少个元素？',
      options: [
        { key: 'A', text: '(n-1)/2' }, { key: 'B', text: 'n/2' },
        { key: 'C', text: '(n+1)/2' }, { key: 'D', text: 'n' },
      ],
      answer: 'A', difficulty: 'medium', knowledgePoint: '线性表', score: 20,
    },
    {
      id: 2, type: 'multi_choice', stem: '以下属于线性数据结构的有？',
      options: [
        { key: 'A', text: '数组' }, { key: 'B', text: '二叉树' },
        { key: 'C', text: '链表' }, { key: 'D', text: '队列' },
      ],
      answer: 'ACD', difficulty: 'medium', knowledgePoint: '线性表', score: 20,
    },
    {
      id: 3, type: 'fill_blank', stem: '队列的特点是____。',
      answer: '先进先出', difficulty: 'medium', knowledgePoint: '栈与队列', score: 20,
    },
    {
      id: 4, type: 'single_choice', stem: '深度为 k 的完全二叉树至少有多少个结点？',
      options: [
        { key: 'A', text: '2^k - 1' }, { key: 'B', text: '2^(k-1)' },
        { key: 'C', text: '2^(k-1) - 1' }, { key: 'D', text: '2^k' },
      ],
      answer: 'B', difficulty: 'medium', knowledgePoint: '树与二叉树', score: 20,
    },
    {
      id: 5, type: 'fill_blank', stem: '堆排序的最坏时间复杂度为____。',
      answer: 'O(n log n)', difficulty: 'medium', knowledgePoint: '排序算法', score: 20,
    },
  ]

  const userAnswers: Record<number, string> = {
    1: 'A', 2: 'AD', 3: '先进先出', 4: 'A', 5: 'O(n log n)',
  }

  const questionResults = questions.map((q) => ({
    question: q,
    userAnswer: userAnswers[q.id]!,
    isCorrect: judgeAnswer(q, userAnswers[q.id]),
  }))

  const correctCount = questionResults.filter((r) => r.isCorrect).length
  return { score: correctCount * 20, totalScore: 100, questionResults }
}

function mockErrorBook(_studentId: number): ErrorBookItem[] {
  return [
    {
      quizQuestion: {
        id: 2, type: 'multi_choice', stem: '以下属于线性数据结构的有？',
        options: [
          { key: 'A', text: '数组' }, { key: 'B', text: '二叉树' },
          { key: 'C', text: '链表' }, { key: 'D', text: '队列' },
        ],
        answer: 'ACD', difficulty: 'medium', knowledgePoint: '线性表', score: 20,
      },
      userAnswer: 'AD', correctAnswer: 'ACD',
      submitTime: '2026-03-15 10:30:00', knowledgePoint: '线性表',
    },
    {
      quizQuestion: {
        id: 4, type: 'single_choice', stem: '深度为 k 的完全二叉树至少有多少个结点？',
        options: [
          { key: 'A', text: '2^k - 1' }, { key: 'B', text: '2^(k-1)' },
          { key: 'C', text: '2^(k-1) - 1' }, { key: 'D', text: '2^k' },
        ],
        answer: 'B', difficulty: 'medium', knowledgePoint: '树与二叉树', score: 20,
      },
      userAnswer: 'A', correctAnswer: 'B',
      submitTime: '2026-03-15 10:30:00', knowledgePoint: '树与二叉树',
    },
    {
      quizQuestion: {
        id: 7, type: 'single_choice', stem: '若进栈序列为 1,2,3,4，则以下哪个不可能是出栈序列？',
        options: [
          { key: 'A', text: '3,2,1,4' }, { key: 'B', text: '4,3,2,1' },
          { key: 'C', text: '1,2,3,4' }, { key: 'D', text: '4,1,2,3' },
        ],
        answer: 'D', difficulty: 'medium', knowledgePoint: '栈与队列', score: 20,
      },
      userAnswer: 'B', correctAnswer: 'D',
      submitTime: '2026-03-14 16:00:00', knowledgePoint: '栈与队列',
    },
  ]
}
