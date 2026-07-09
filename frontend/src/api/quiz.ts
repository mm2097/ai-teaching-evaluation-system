/**
 * 答题记录 API（调用真实后端 /api/v1/answer-records）
 */
import request from '@/utils/request'
import type { DifficultyLevel, ExerciseType, QuizQuestion } from '@/types'

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
  await delay(300)
  const submission = quizSubmissions.find((s) => s.id === submissionId)
  if (!submission) throw new Error('提交记录不存在')

  const assignment = quizAssignments.find((a) => a.id === submission.assignmentId)
  if (!assignment) throw new Error('练习信息不存在')

  const questionResults = assignment.questions.map((q) => {
    const ans = submission.answers[q.id]
    let isCorrect = false
    if (Array.isArray(q.answer)) {
      const userAns = Array.isArray(ans) ? [...ans].sort().join(',') : ''
      const correct = [...q.answer].sort().join(',')
      isCorrect = userAns === correct
    } else {
      isCorrect = String(ans).trim() === String(q.answer).trim()
    }
    return { question: q, userAnswer: ans ?? '', isCorrect }
  })

  return { score: submission.score, totalScore: submission.totalScore, questionResults }
}

/** 错题本（按学生聚合所有已提交练习的错题） */
export async function fetchErrorBook(studentId: number): Promise<{
  quizQuestion: QuizQuestion
  userAnswer: string | string[]
  correctAnswer: string | string[]
  submitTime: string
  knowledgePoint: string
}[]> {
  await delay(300)
  const mySubmissions = quizSubmissions.filter((s) => s.studentId === studentId)
  const errors: {
    quizQuestion: QuizQuestion
    userAnswer: string | string[]
    correctAnswer: string | string[]
    submitTime: string
    knowledgePoint: string
  }[] = []

  mySubmissions.forEach((sub) => {
    const assignment = quizAssignments.find((a) => a.id === sub.assignmentId)
    if (!assignment) return
    assignment.questions.forEach((q) => {
      const ans = sub.answers[q.id]
      let isCorrect = false
      if (Array.isArray(q.answer)) {
        const userAns = Array.isArray(ans) ? [...ans].sort().join(',') : ''
        const correct = [...q.answer].sort().join(',')
        isCorrect = userAns === correct
      } else {
        isCorrect = String(ans).trim() === String(q.answer).trim()
      }
      if (!isCorrect) {
        errors.push({
          quizQuestion: q,
          userAnswer: ans ?? '',
          correctAnswer: q.answer,
          submitTime: sub.submitTime,
          knowledgePoint: q.knowledgePoint,
        })
      }
    })
  })

  return errors.sort((a, b) => b.submitTime.localeCompare(a.submitTime))
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
