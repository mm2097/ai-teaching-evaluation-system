/**
 * AI 出题与在线答题 API
 * 对齐 AI算法_需求与开发文档 第 7 章
 */
import request from '@/utils/request'
import { delay } from '@/utils/auth'
import { quizAssignments, quizSubmissions } from '@/mock/quiz'
import { generateExercises } from '@/api/ai'
import { calcQuizScore, judgeAnswer } from '@/utils/exerciseJudge'
import type {
  ExerciseStatus,
  ExerciseType,
  GenerateExerciseParams,
  GenerateExerciseResult,
  QuizAssignment,
  QuizQuestion,
  QuizSubmission,
} from '@/types'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export interface GenerateQuizParams {
  courseId: number
  classId: number
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  questionCount: number
  difficulty: GenerateExerciseParams['difficulty']
  extraRequirements?: string
}

/** 获取练习列表 */
export async function fetchQuizAssignments(params?: {
  teacherId?: number
  courseId?: number
  status?: ExerciseStatus | string
}): Promise<QuizAssignment[]> {
  if (USE_MOCK) {
    await delay(300)
    return quizAssignments.filter((a) => {
      if (params?.courseId && a.courseId !== params.courseId) return false
      if (params?.status && a.status !== params.status) return false
      return true
    })
  }

  const { data } = await request.get<QuizAssignment[]>('/v1/exercises', { params })
  return data
}

/** AI 生成练习题 */
export async function generateQuizQuestions(params: GenerateQuizParams): Promise<GenerateExerciseResult> {
  return generateExercises({
    courseId: params.courseId,
    knowledgePoints: params.knowledgePoints,
    questionTypes: params.questionTypes,
    count: params.questionCount,
    difficulty: params.difficulty,
    extraRequirements: params.extraRequirements,
  })
}

/** 创建/更新练习 */
export async function saveQuizAssignment(
  assignment: Partial<QuizAssignment> & { questions: QuizQuestion[] },
): Promise<QuizAssignment> {
  if (USE_MOCK) {
    await delay(500)
    if (assignment.id) {
      const idx = quizAssignments.findIndex((a) => a.id === assignment.id)
      if (idx >= 0) {
        const updated: QuizAssignment = {
          ...quizAssignments[idx]!,
          ...assignment,
          questionCount: assignment.questions.length,
          totalScore: assignment.questions.reduce((s, q) => s + q.score, 0),
        } as QuizAssignment
        quizAssignments[idx] = updated
        return updated
      }
    }
    const newAssignment: QuizAssignment = {
      id: Date.now(),
      title: assignment.title || '未命名练习',
      courseId: assignment.courseId || 1,
      courseName: assignment.courseName || '数据结构与算法',
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

  const { data } = await request.post<QuizAssignment>('/v1/exercises', assignment)
  return data
}

/** 更新单题 */
export async function updateExercise(id: number, question: Partial<QuizQuestion>): Promise<void> {
  if (USE_MOCK) {
    await delay(200)
    for (const assignment of quizAssignments) {
      const idx = assignment.questions.findIndex((q) => q.id === id)
      if (idx >= 0) {
        assignment.questions[idx] = { ...assignment.questions[idx]!, ...question }
        return
      }
    }
    return
  }
  await request.put(`/v1/exercises/${id}`, question)
}

/** 删除单题 */
export async function deleteExercise(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(200)
    for (const assignment of quizAssignments) {
      assignment.questions = assignment.questions.filter((q) => q.id !== id)
      assignment.questionCount = assignment.questions.length
      assignment.totalScore = assignment.questions.reduce((s, q) => s + q.score, 0)
    }
    return
  }
  await request.delete(`/v1/exercises/${id}`)
}

/** 删除练习（仅草稿可删） */
export async function deleteQuizAssignment(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(300)
    const idx = quizAssignments.findIndex((a) => a.id === id)
    if (idx >= 0) quizAssignments.splice(idx, 1)
    return
  }
  await request.delete(`/v1/exercises/${id}`)
}

/** 批量发布练习 */
export async function publishQuizAssignment(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(300)
    const assignment = quizAssignments.find((a) => a.id === id)
    if (assignment) {
      assignment.status = 'published'
      assignment.publishTime = new Date().toLocaleString('zh-CN', { hour12: false })
    }
    return
  }
  await request.post('/v1/exercises/publish', { exercise_ids: [id] })
}

/** 关闭练习（停止学生作答） */
export async function closeQuizAssignment(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(300)
    const assignment = quizAssignments.find((a) => a.id === id)
    if (assignment) assignment.status = 'closed'
    return
  }
  await request.post(`/v1/exercises/assignments/${id}/close`)
}

/** 获取学生可答练习 */
export async function fetchStudentQuizzes(studentId: number): Promise<QuizAssignment[]> {
  if (USE_MOCK) {
    await delay(300)
    const { students, isStudentEnrolled } = await import('@/mock/dict')
    const student = students.find((s) => s.id === studentId)
    return quizAssignments.filter(
      (a) => a.status === 'published' && student && isStudentEnrolled(student.id, a.courseId),
    )
  }

  const { data } = await request.get<QuizAssignment[]>('/v1/exercises', {
    params: { status: 'published' },
  })
  return data
}

/** 提交单题答案并判分 */
export async function submitExerciseAnswer(
  exerciseId: number,
  answer: string | boolean,
): Promise<{ correct: boolean; score: number; knowledgeMasteryUpdated: boolean }> {
  if (USE_MOCK) {
    await delay(300)
    for (const assignment of quizAssignments) {
      const question = assignment.questions.find((q) => q.id === exerciseId)
      if (question) {
        const correct = judgeAnswer(question, answer)
        return { correct, score: correct ? question.score : 0, knowledgeMasteryUpdated: true }
      }
    }
    throw new Error('题目不存在')
  }

  const { data } = await request.post<{ correct: boolean; score: number; knowledge_mastery_updated: boolean }>(
    `/v1/exercises/${exerciseId}/answer`,
    { answer },
  )
  return {
    correct: data.correct,
    score: data.score,
    knowledgeMasteryUpdated: data.knowledge_mastery_updated,
  }
}

/** 提交整卷答题 */
export async function submitQuizAnswers(
  assignmentId: number,
  studentId: number,
  studentName: string,
  answers: Record<number, string | boolean>,
): Promise<QuizSubmission> {
  if (USE_MOCK) {
    await delay(800)
    const assignment = quizAssignments.find((a) => a.id === assignmentId)
    if (!assignment) throw new Error('练习不存在')

    const score = calcQuizScore(assignment.questions, answers)
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

  const { data } = await request.post<QuizSubmission>(`/v1/exercises/assignments/${assignmentId}/submit`, {
    answers,
  })
  return data
}

/** 获取提交记录 */
export async function fetchQuizSubmissions(assignmentId?: number): Promise<QuizSubmission[]> {
  if (USE_MOCK) {
    await delay(200)
    if (!assignmentId) return [...quizSubmissions]
    return quizSubmissions.filter((s) => s.assignmentId === assignmentId)
  }

  const { data } = await request.get<QuizSubmission[]>('/v1/exercises/submissions', {
    params: { assignment_id: assignmentId },
  })
  return data
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
