/**
 * 答题记录 API（调用真实后端 /api/v1/answer-records）
 */
import request, { USE_MOCK } from '@/utils/request'
import {
  appendLocalErrorBook,
  buildErrorBookItems,
  isSelfPracticeTask,
  loadLocalErrorBook,
  SELF_PRACTICE_PREFIX,
} from '@/utils/errorBookStorage'
import { judgeAnswer } from '@/utils/exerciseJudge'
import type { DifficultyLevel, ExerciseType, QuizAssignment, QuizQuestion, QuizSubmission } from '@/types'

export type QuizAssignmentRecord = QuizAssignment
export type QuizSubmissionRecord = QuizSubmission

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
  questionResults: {
    question: QuizQuestion
    userAnswer: string | string[]
    isCorrect: boolean
  }[]
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
  difficulty: DifficultyLevel
  extraRequirements?: string
}

/** AI 生成练习题响应 */
export interface GenerateQuizResult {
  questions: QuizQuestion[]
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
  const res = await request.post('/v1/exercises/generate', {
    courseId: params.courseId,
    knowledgePoints: params.knowledgePoints.length ? params.knowledgePoints : ['综合'],
    questionTypes: params.questionTypes,
    questionCount: params.questionCount,
    difficulty: params.difficulty,
    extraRequirements: params.extraRequirements || '',
  })
  return res.data
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

/** 获取学生的答题任务列表（前端过滤：仅已发布、非自主练习） */
export async function fetchStudentQuizzes(_studentId: number): Promise<QuizAssignment[]> {
  const tasks = await fetchQuizAssignments()
  return tasks.filter(
    (t) => t.status === 'published' && !isSelfPracticeTask(t.title),
  ) as QuizAssignment[]
}

/** 学生自主练习提交参数 */
export interface SubmitSelfQuizParams {
  studentId: number
  courseId: number
  courseName: string
  knowledgePoints: string[]
  questions: QuizQuestion[]
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
  details: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
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

/** 按题目顺序将临时 ID 答案映射到入库后的真实 question_id */
function mapAnswersByIndex(
  originalQuestions: QuizQuestion[],
  savedQuestions: QuizQuestion[],
  answers: Record<number, string | boolean>,
): Record<string, string> {
  const mapped: Record<string, string> = {}
  savedQuestions.forEach((sq, idx) => {
    const orig = originalQuestions[idx]
    if (!orig) return
    const ans = answers[orig.id]
    if (ans === undefined) return
    mapped[String(sq.id)] = typeof ans === 'boolean' ? (ans ? 'true' : 'false') : String(ans)
  })
  return mapped
}

/** 前端组装逐题判分详情（客观题规则判分，简答题标记待 AI 结果） */
export function buildSubmitDetails(
  questions: QuizQuestion[],
  answers: Record<number, string | boolean>,
  backendCorrectCount?: number,
): QuizSubmitResult['details'] {
  const details = questions.map((q) => {
    const userAnswer = answers[q.id] ?? ''
    if (q.type === 'short_answer') {
      return { question: q, correct: false, userAnswer, aiReason: '简答题已由 AI 判分' }
    }
    return { question: q, correct: judgeAnswer(q, userAnswer), userAnswer }
  })

  // 若后端返回了 correctCount，尝试将简答题对错补齐（按得分差额推断）
  if (backendCorrectCount !== undefined) {
    const objectiveCorrect = details.filter((d) => d.question.type !== 'short_answer' && d.correct).length
    const shortItems = details.filter((d) => d.question.type === 'short_answer')
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
  const details = buildSubmitDetails(questions, answers as Record<number, string | boolean>, data.correctCount)
  syncWrongAnswersToErrorBook(studentId, details)
  return { ...data, details }
}

/** 学生自主练习：复用现有 answer-tasks + answer-records 接口 */
export async function submitSelfQuiz(params: SubmitSelfQuizParams): Promise<QuizSubmitResult> {
  const title = `${SELF_PRACTICE_PREFIX}${new Date().toLocaleString('zh-CN', { hour12: false })}`
  const task = await saveQuizAssignment({
    title,
    courseId: params.courseId,
    courseName: params.courseName,
    classId: 0,
    className: '',
    teacherName: '学生自学',
    knowledgePoints: params.knowledgePoints,
    status: 'published',
    questions: params.questions,
  })

  const allTasks = await fetchQuizAssignments()
  const saved = allTasks.find((t) => t.id === task.id)
  const savedQuestions = (saved?.questions || []) as QuizQuestion[]
  if (!savedQuestions.length) {
    throw new Error('自主练习任务创建失败')
  }

  const mappedAnswers = mapAnswersByIndex(params.questions, savedQuestions, params.answers)
  const { data } = await request.post('/v1/answer-records', {
    task_id: task.id,
    student_id: params.studentId,
    answers: mappedAnswers,
  })

  const details = buildSubmitDetails(savedQuestions, params.answers, data.correctCount)
  syncWrongAnswersToErrorBook(params.studentId, details)
  return {
    ...data,
    details,
    taskId: task.id,
    taskTitle: title,
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
