/**
 * AI 出题与在线答题 API（模拟）
 */
import { delay } from '@/utils/auth'
import { quizAssignments, quizSubmissions } from '@/mock/quiz'
import type { QuizAssignment, QuizQuestion, QuizSubmission } from '@/types'

export interface GenerateQuizParams {
  courseId: number
  classId: number
  knowledgePoints: string[]
  questionTypes: string[]
  questionCount: number
}

const aiQuestionPool: Omit<QuizQuestion, 'id'>[] = [
  {
    type: 'single',
    content: '哈希表查找的平均时间复杂度是？',
    options: ['O(1)', 'O(n)', 'O(log n)', 'O(n²)'],
    answer: 'O(1)',
    knowledgePoint: '哈希表',
    score: 10,
  },
  {
    type: 'single',
    content: 'TCP 三次握手的第一步是？',
    options: ['SYN', 'ACK', 'FIN', 'RST'],
    answer: 'SYN',
    knowledgePoint: 'TCP协议',
    score: 10,
  },
  {
    type: 'multiple',
    content: '面向对象的三大特性包括？（多选）',
    options: ['封装', '继承', '多态', '递归'],
    answer: ['封装', '继承', '多态'],
    knowledgePoint: '面向对象',
    score: 10,
  },
  {
    type: 'fill',
    content: '栈的特点是 _____ 出栈。',
    answer: '后进先出',
    knowledgePoint: '栈与队列',
    score: 10,
  },
  {
    type: 'short',
    content: '简述二分查找的前提条件。',
    answer: '数据必须有序',
    knowledgePoint: '查找算法',
    score: 10,
  },
]

/** 获取练习列表 */
export async function fetchQuizAssignments(params?: {
  teacherId?: number
  courseId?: number
  status?: string
}): Promise<QuizAssignment[]> {
  await delay(300)
  return quizAssignments.filter((a) => {
    if (params?.courseId && a.courseId !== params.courseId) return false
    if (params?.status && a.status !== params.status) return false
    return true
  })
}

/** AI 生成练习题 */
export async function generateQuizQuestions(params: GenerateQuizParams): Promise<QuizQuestion[]> {
  await delay(1500)
  const filtered = aiQuestionPool.filter(
    (q) => !params.knowledgePoints.length || params.knowledgePoints.includes(q.knowledgePoint),
  )
  const pool = filtered.length ? filtered : aiQuestionPool
  return pool.slice(0, params.questionCount).map((q, idx) => ({
    ...q,
    id: Date.now() + idx,
  }))
}

/** 创建/更新练习 */
export async function saveQuizAssignment(assignment: Partial<QuizAssignment> & { questions: QuizQuestion[] }): Promise<QuizAssignment> {
  await delay(500)
  if (assignment.id) {
    const idx = quizAssignments.findIndex((a) => a.id === assignment.id)
    if (idx >= 0) {
      quizAssignments[idx] = { ...quizAssignments[idx]!, ...assignment } as QuizAssignment
      return quizAssignments[idx]!
    }
  }
  const newAssignment: QuizAssignment = {
    id: Date.now(),
    title: assignment.title || '未命名练习',
    courseId: assignment.courseId || 1,
    courseName: assignment.courseName || '数据结构',
    classId: assignment.classId || 1,
    className: assignment.className || '计科2401',
    teacherName: assignment.teacherName || '王教授',
    knowledgePoints: assignment.knowledgePoints || [],
    questionCount: assignment.questions.length,
    totalScore: assignment.questions.reduce((s, q) => s + q.score, 0),
    status: assignment.status || 'draft',
    questions: assignment.questions,
  }
  quizAssignments.unshift(newAssignment)
  return newAssignment
}

/** 发布练习 */
export async function publishQuizAssignment(id: number): Promise<void> {
  await delay(300)
  const assignment = quizAssignments.find((a) => a.id === id)
  if (assignment) {
    assignment.status = 'published'
    assignment.publishTime = new Date().toLocaleString('zh-CN', { hour12: false })
  }
}

/** 获取学生可答练习 */
export async function fetchStudentQuizzes(studentId: number): Promise<QuizAssignment[]> {
  await delay(300)
  return quizAssignments.filter((a) => a.status === 'published')
}

/** 提交答题 */
export async function submitQuizAnswers(
  assignmentId: number,
  studentId: number,
  studentName: string,
  answers: Record<number, string | string[]>,
): Promise<QuizSubmission> {
  await delay(800)
  const assignment = quizAssignments.find((a) => a.id === assignmentId)
  if (!assignment) throw new Error('练习不存在')

  let score = 0
  assignment.questions.forEach((q) => {
    const ans = answers[q.id]
    if (Array.isArray(q.answer)) {
      const userAns = Array.isArray(ans) ? ans.sort().join(',') : ''
      const correct = [...q.answer].sort().join(',')
      if (userAns === correct) score += q.score
    } else if (String(ans).trim() === String(q.answer).trim()) {
      score += q.score
    }
  })

  const submission: QuizSubmission = {
    id: Date.now(),
    assignmentId,
    studentId,
    studentName,
    score,
    totalScore: assignment.totalScore,
    submitTime: new Date().toLocaleString('zh-CN', { hour12: false }),
    answers,
  }
  quizSubmissions.push(submission)
  return submission
}

/** 获取提交记录 */
export async function fetchQuizSubmissions(assignmentId?: number): Promise<QuizSubmission[]> {
  await delay(200)
  if (!assignmentId) return [...quizSubmissions]
  return quizSubmissions.filter((s) => s.assignmentId === assignmentId)
}
