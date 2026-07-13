/**
 * 答题记录 API（调用真实后端 /api/v1/answer-records）
 */
import request, { USE_MOCK } from '@/utils/request'
import type { DifficultyLevel, ExerciseType, QuizQuestion, RagReference } from '@/types'

export interface QuizAssignmentRecord {
  id: number
  courseName: string
  title: string
  knowledgePoints: string[]
  questionCount: number
  totalScore: number
  assignedTime: string
  deadline: string
  submittedCount: number
  averageScore: number
}

export interface QuizSubmissionRecord {
  id: number
  studentName: string
  studentNo: string
  courseName: string
  quizTitle: string
  score: number
  totalScore: number
  submitTime: string
  isLate: boolean
  status: string
  answers: { questionIndex: number; questionContent: string; studentAnswer: string; correctAnswer: string; score: number; isCorrect: boolean }[]
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
export async function fetchQuizSubmissions(): Promise<QuizSubmissionRecord[]> {
  try {
    const res = await request.get('/v1/answer-records')
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
  questionResults: {
    question: QuizQuestion
    userAnswer: string | string[]
    isCorrect: boolean
  }[]
}> {
  if (USE_MOCK) {
    return mockQuizResult(submissionId)
  }
  // 真实后端路径（预留）
  const res = await request.get('/v1/answer-records/' + submissionId)
  return res.data
}

/** 错题本（按学生聚合所有已提交练习的错题） */
export async function fetchErrorBook(studentId: number): Promise<{
  quizQuestion: QuizQuestion
  userAnswer: string | string[]
  correctAnswer: string | string[]
  submitTime: string
  knowledgePoint: string
}[]> {
  if (USE_MOCK) {
    return mockErrorBook(studentId)
  }
  // 真实后端路径（预留）
  try {
    const res = await request.get('/v1/answer-records', { params: { student_id: studentId } })
    return res.data
  } catch {
    return []
  }
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
}

/** AI 生成练习题（经后端代理调用算法服务 8001） */
export async function generateQuizQuestions(params: GenerateQuizParams): Promise<GenerateQuizResult> {
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
  const res = await request.post('/v1/exercises/generate', payload)
  const data = res.data
  // 向后兼容：旧后端可能不返回 ragReferences
  if (!data.ragReferences) {
    data.ragReferences = []
  }
  return data
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
  const payload: Record<string, any> = {
    courseId: params.courseId,
    knowledgePoints: params.knowledgePoints.length ? params.knowledgePoints : ['综合'],
    questionTypes: params.questionTypes,
    questionCount: params.questionCount,
    extraRequirements: params.extraRequirements || '',
  }
  if (params.difficultyDistribution) {
    payload.difficultyDistribution = params.difficultyDistribution
  } else {
    payload.difficulty = params.difficulty || 'medium'
  }

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

/** 获取学生的答题任务列表 */
export async function fetchStudentQuizzes(_studentId: number): Promise<QuizAssignmentRecord[]> {
  return fetchQuizAssignments()
}

/** 提交答题答案 */
export async function submitQuizAnswers(
  taskId: number,
  _studentId: number,
  _studentName: string,
  answers: Record<number, string | string[]>,
): Promise<{ submissionId: number; score: number; totalScore: number; correctCount: number }> {
  const { data } = await request.post('/v1/answer-records', {
    task_id: taskId,
    answers,
  })
  return data
}

/* ============================================================
 * Mock 数据（USE_MOCK=true 时由 fetchQuizResult / fetchErrorBook 使用）
 * ============================================================ */

/** mock 答题结果（5 题，3 对 2 错） */
function mockQuizResult(_submissionId: number): {
  score: number
  totalScore: number
  questionResults: { question: any; userAnswer: string | string[]; isCorrect: boolean }[]
} {
  const questions = [
    {
      id: 1, type: 'single', content: '在长度为 n 的顺序表中删除一个元素，平均需要移动多少个元素？',
      options: ['(n-1)/2', 'n/2', '(n+1)/2', 'n'], answer: '(n-1)/2',
      knowledgePoint: '线性表', score: 20,
    },
    {
      id: 2, type: 'multiple', content: '以下属于线性数据结构的有？',
      options: ['数组', '二叉树', '链表', '队列'], answer: ['数组', '链表', '队列'],
      knowledgePoint: '线性表', score: 20,
    },
    {
      id: 3, type: 'fill', content: '队列的特点是____。',
      options: undefined, answer: '先进先出', knowledgePoint: '栈与队列', score: 20,
    },
    {
      id: 4, type: 'single', content: '深度为 k 的完全二叉树至少有多少个结点？',
      options: ['2^k - 1', '2^(k-1)', '2^(k-1) - 1', '2^k'], answer: '2^(k-1)',
      knowledgePoint: '树与二叉树', score: 20,
    },
    {
      id: 5, type: 'fill', content: '堆排序的最坏时间复杂度为____。',
      options: undefined, answer: 'O(n log n)', knowledgePoint: '排序算法', score: 20,
    },
  ]

  const userAnswers: Record<number, string | string[]> = {
    1: '(n-1)/2',        // 对
    2: ['数组', '队列'],  // 错（漏选链表）
    3: '先进先出',        // 对
    4: '2^k - 1',        // 错
    5: 'O(n log n)',     // 对
  }

  const questionResults = questions.map((q) => {
    const ua = userAnswers[q.id]!
    let isCorrect = false
    if (Array.isArray(q.answer)) {
      isCorrect = Array.isArray(ua) && [...ua].sort().join(',') === [...q.answer].sort().join(',')
    } else {
      isCorrect = String(ua).trim() === String(q.answer).trim()
    }
    return { question: q, userAnswer: ua, isCorrect }
  })

  const correctCount = questionResults.filter((r) => r.isCorrect).length
  return {
    score: correctCount * 20,
    totalScore: 100,
    questionResults,
  }
}

/** mock 错题本（3 道错题） */
function mockErrorBook(_studentId: number): {
  quizQuestion: any
  userAnswer: string | string[]
  correctAnswer: string | string[]
  submitTime: string
  knowledgePoint: string
}[] {
  return [
    {
      quizQuestion: {
        id: 2, type: 'multiple', content: '以下属于线性数据结构的有？',
        options: ['数组', '二叉树', '链表', '队列'],
        answer: ['数组', '链表', '队列'], knowledgePoint: '线性表', score: 20,
      },
      userAnswer: ['数组', '队列'],
      correctAnswer: ['数组', '链表', '队列'],
      submitTime: '2026-03-15 10:30:00',
      knowledgePoint: '线性表',
    },
    {
      quizQuestion: {
        id: 4, type: 'single', content: '深度为 k 的完全二叉树至少有多少个结点？',
        options: ['2^k - 1', '2^(k-1)', '2^(k-1) - 1', '2^k'],
        answer: '2^(k-1)', knowledgePoint: '树与二叉树', score: 20,
      },
      userAnswer: '2^k - 1',
      correctAnswer: '2^(k-1)',
      submitTime: '2026-03-15 10:30:00',
      knowledgePoint: '树与二叉树',
    },
    {
      quizQuestion: {
        id: 7, type: 'single', content: '若进栈序列为 1,2,3,4，则以下哪个不可能是出栈序列？',
        options: ['3,2,1,4', '4,3,2,1', '1,2,3,4', '4,1,2,3'],
        answer: '4,1,2,3', knowledgePoint: '栈与队列', score: 20,
      },
      userAnswer: '4,3,2,1',
      correctAnswer: '4,1,2,3',
      submitTime: '2026-03-14 16:00:00',
      knowledgePoint: '栈与队列',
    },
  ]
}

