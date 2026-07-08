/**
 * 答题记录 API（调用真实后端 /api/v1/answer-records）
 */
import request from '@/utils/request'

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

/** 获取答题任务列表 */
export async function fetchQuizAssignments(): Promise<QuizAssignmentRecord[]> {
  try {
    const res = await request.get('/v1/answer-tasks')
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
