/**
 * 路由匹配核心：匹配 method + url → 返回数据
 * 支持 query 过滤、路径参数提取
 */
import {
  departments,
  semesters,
  classes,
  students,
  teachers,
  courses,
  type MockClass,
  type MockStudent,
  type MockTeacher,
  type MockCourse,
} from './static'
import {
  users,
  questionBank,
  answerTasks,
  answerRecords,
  teachingData,
  importLogs,
  nextUserId,
  nextQuestionId,
  nextTaskId,
  nextRecordId,
  type MockUser,
  type MockQuestion,
  type MockAnswerTask,
  type MockAnswerRecord,
} from './db'
import {
  dashboardStats,
  gradeTrend,
  studentProfile,
  knowledgeHeatmap,
  warnings,
  gradePredictions,
} from './analysis'
import {
  studentEvaluations,
  teacherEvaluations,
  courseEvaluations,
  studentEvaluationResults,
} from './evaluation'
import { classReport, studentReport } from './report'
import { systemLogs } from './logs'

/* ============================================================ */
/* 字段映射工具（后端格式 → 前端期望）                             */
/* ============================================================ */

function mapClass(c: MockClass) {
  return {
    class_id: c.class_id,
    class_name: c.class_name,
    college: c.college,
    major: c.major,
    grade: c.grade,
  }
}

function mapStudent(s: MockStudent) {
  return {
    student_id: s.student_id,
    student_no: s.student_no,
    real_name: s.real_name,
    class_id: s.class_id,
  }
}

function mapTeacher(t: MockTeacher) {
  return {
    teacher_id: t.teacher_id,
    teacher_no: t.teacher_no,
    real_name: t.real_name,
  }
}

function mapCourse(c: MockCourse) {
  return {
    course_id: c.course_id,
    course_code: c.course_code,
    course_name: c.course_name,
    teacher_id: c.teacher_id,
    semester: c.semester,
  }
}

function mapUser(u: MockUser) {
  return {
    user_id: u.user_id,
    username: u.username,
    real_name: u.real_name,
    role_id: u.role_id,
    status: u.status,
    create_time: u.create_time,
  }
}

function mapQuestion(q: MockQuestion) {
  return {
    id: q.id,
    courseId: q.courseId,
    courseName: q.courseName,
    knowledgePoint: q.knowledgePoint,
    type: q.type,
    content: q.content,
    difficulty: q.difficulty,
    createdTime: q.createdTime,
  }
}

function mapAnswerTask(t: MockAnswerTask) {
  return {
    id: t.id,
    title: t.title,
    courseId: t.courseId,
    courseName: t.courseName,
    classId: t.classId,
    className: t.className,
    teacherName: t.teacherName,
    knowledgePoints: t.knowledgePoints,
    questionCount: t.questionCount,
    totalScore: t.totalScore,
    status: t.status,
    publishTime: t.publishTime,
    deadline: t.deadline,
    submittedCount: t.submittedCount,
    averageScore: t.averageScore,
    assignedTime: t.publishTime,
    questions: t.questions,
  }
}

function mapAnswerRecord(r: MockAnswerRecord) {
  return {
    id: r.id,
    studentName: r.studentName,
    studentNo: r.studentNo,
    courseName: r.courseName,
    quizTitle: r.quizTitle,
    score: r.score,
    totalScore: r.totalScore,
    submitTime: r.submitTime,
    isLate: r.isLate,
    status: r.status,
    answers: r.answers,
  }
}

/* ============================================================ */
/* 路由匹配                                                      */
/* ============================================================ */

export interface MockConfig {
  method: string
  url: string
  params?: Record<string, unknown>
  data?: unknown
}

export function handleRequest(config: MockConfig): { status: number; data: unknown } {
  const method = config.method.toUpperCase()
  // url 形如 "/login" 或 "/v1/dashboard/stats"（不含 baseURL /api）
  const url = config.url
  const params = config.params || {}
  const body = parseBody(config.data)

  /* ----- 认证 ----- */
  if (method === 'POST' && url === '/login') {
    return handleLogin(body)
  }

  /* ----- 用户管理 ----- */
  if (method === 'GET' && url === '/users') {
    return ok(users.map(mapUser))
  }
  if (method === 'POST' && url === '/users') {
    return handleCreateUser(body)
  }
  if (method === 'PUT' && matchPath(url, '/users/:id')) {
    return handleUpdateUser(extractId(url), body)
  }
  if (method === 'DELETE' && matchPath(url, '/users/:id')) {
    const id = extractId(url)
    const idx = users.findIndex((u) => u.user_id === id)
    if (idx !== -1) users.splice(idx, 1)
    return ok(null)
  }

  /* ----- 字典 ----- */
  if (method === 'GET' && url === '/v1/dictionaries/departments') {
    return ok(departments)
  }
  if (method === 'GET' && url === '/v1/dictionaries/semesters') {
    return ok(semesters)
  }
  if (method === 'GET' && url === '/v1/classes') {
    return ok(classes.map(mapClass))
  }
  if (method === 'GET' && url === '/v1/dictionaries/majors') {
    return handleMajors(params)
  }
  if (method === 'GET' && url === '/v1/dictionaries/grades') {
    return handleGrades(params)
  }
  if (method === 'GET' && url === '/v1/students') {
    return handleStudents(params)
  }
  if (method === 'GET' && url === '/v1/teachers') {
    return ok(teachers.map(mapTeacher))
  }
  if (method === 'GET' && url === '/v1/courses') {
    return handleCourses(params)
  }

  /* ----- 看板 ----- */
  if (method === 'GET' && url === '/v1/dashboard/stats') {
    return ok(dashboardStats(params.course_id as number))
  }
  if (method === 'GET' && url === '/v1/dashboard/grade-trend') {
    return ok(gradeTrend(params))
  }

  /* ----- 分析 ----- */
  if (method === 'GET' && url === '/v1/analysis/profile') {
    return ok(studentProfile(params.student_id as number, params.course_id as number))
  }
  if (method === 'GET' && url === '/v1/analysis/knowledge-heatmap') {
    return ok(knowledgeHeatmap(params.course_id as number, params.class_id as number, params.student_id as number))
  }
  if (method === 'GET' && url === '/v1/analysis/warnings') {
    return ok(warnings(params))
  }
  if (method === 'GET' && url === '/v1/analysis/grade-predictions') {
    return ok(gradePredictions(params.course_id as number, params.class_id as number))
  }

  /* ----- 题库 ----- */
  if (method === 'GET' && url === '/v1/question-bank') {
    return handleQuestionBank(params)
  }
  if (method === 'POST' && url === '/v1/question-bank') {
    return handleAddQuestions(body)
  }
  if (method === 'POST' && url === '/v1/question-bank/check') {
    return handleCheckQuestions(body)
  }
  if (method === 'GET' && url === '/v1/question-bank/templates') {
    return handleTemplates(params)
  }
  if (method === 'POST' && url === '/v1/question-bank/import-rows') {
    return handleImportRows(body)
  }
  if (method === 'POST' && url === '/v1/question-bank/import-builtin') {
    return handleImportBuiltin(body)
  }
  if (method === 'PUT' && matchPath(url, '/v1/question-bank/:id')) {
    return handleUpdateQuestion(extractId(url), body)
  }
  if (method === 'DELETE' && matchPath(url, '/v1/question-bank/:id')) {
    const id = extractId(url)
    const idx = questionBank.findIndex((q) => q.id === id)
    if (idx !== -1) questionBank.splice(idx, 1)
    return ok(null)
  }

  /* ----- AI 出题 ----- */
  if (method === 'POST' && url === '/v1/exercises/generate') {
    return handleGenerateExercises(body)
  }

  /* ----- 答题任务 ----- */
  if (method === 'GET' && url === '/v1/answer-tasks') {
    return handleAnswerTasks(params)
  }
  if (method === 'POST' && url === '/v1/answer-tasks') {
    return handleCreateAnswerTask(body)
  }
  if (method === 'POST' && matchPath(url, '/v1/answer-tasks/:id/publish')) {
    const id = extractIdFromSegment(url, 2)
    const task = answerTasks.find((t) => t.id === id)
    if (task) task.status = 'published'
    return ok(null)
  }
  if (method === 'POST' && matchPath(url, '/v1/answer-tasks/:id/close')) {
    const id = extractIdFromSegment(url, 2)
    const task = answerTasks.find((t) => t.id === id)
    if (task) task.status = 'closed'
    return ok(null)
  }

  /* ----- 答题记录 ----- */
  if (method === 'GET' && url === '/v1/answer-records') {
    return ok(answerRecords.map(mapAnswerRecord))
  }
  if (method === 'POST' && url === '/v1/answer-records') {
    return handleSubmitAnswers(body)
  }

  /* ----- 报告 ----- */
  if (method === 'GET' && url === '/v1/report/class') {
    return ok(classReport(params.course_id as number, params.class_id as number))
  }
  if (method === 'GET' && url === '/v1/report/student') {
    return ok(studentReport(params.student_id as number, params.course_id as number))
  }

  /* ----- 评价 ----- */
  if (method === 'GET' && url === '/v1/evaluations') {
    return ok(studentEvaluations())
  }
  if (method === 'GET' && url === '/v1/evaluations/results') {
    return ok(studentEvaluationResults(params.student_id as number))
  }

  /* ----- 日志 ----- */
  if (method === 'GET' && url === '/v1/logs') {
    return ok({ list: systemLogs })
  }

  /* ----- 教学数据 ----- */
  if (method === 'GET' && url === '/v1/teaching-data') {
    return ok({ list: teachingData })
  }

  /* ----- 教师评价（单独路由） ----- */
  if (method === 'GET' && url === '/v1/evaluations/teacher') {
    return ok(teacherEvaluations())
  }
  if (method === 'GET' && url === '/v1/evaluations/course') {
    return ok(courseEvaluations())
  }

  // 未匹配
  console.warn(`[Mock] 未匹配路由: ${method} ${url}`)
  return { status: 404, data: { detail: `Mock 未匹配路由: ${method} ${url}` } }
}

/* ============================================================ */
/* 工具函数                                                      */
/* ============================================================ */

function ok(data: unknown): { status: number; data: unknown } {
  return { status: 200, data }
}

function parseBody(data: unknown): Record<string, any> {
  if (!data) return {}
  if (typeof data === 'string') {
    try {
      return JSON.parse(data)
    } catch {
      return {}
    }
  }
  return data as Record<string, any>
}

/** 简单路径匹配："/users/:id" 匹配 "/users/123" */
function matchPath(url: string, pattern: string): boolean {
  const urlSegs = url.split('/').filter(Boolean)
  const patSegs = pattern.split('/').filter(Boolean)
  if (urlSegs.length !== patSegs.length) return false
  return urlSegs.every((seg, i) => patSegs[i] === ':id' || patSegs[i] === seg)
}

/** 从 url 提取 :id（最后一段为数字） */
function extractId(url: string): number {
  const segs = url.split('/').filter(Boolean)
  return Number(segs[segs.length - 1]) || 0
}

/** 从指定段提取 id */
function extractIdFromSegment(url: string, segFromEnd: number): number {
  const segs = url.split('/').filter(Boolean)
  return Number(segs[segs.length - 1 - segFromEnd]) || 0
}

/* ============================================================ */
/* 业务处理函数                                                  */
/* ============================================================ */

function handleLogin(body: Record<string, any>) {
  const username = body.username || ''
  let roleCode = 'student'
  let realName = username
  let userId = 999

  if (username.startsWith('admin')) {
    roleCode = 'admin'
    realName = '系统管理员'
    userId = 1
  } else if (username.startsWith('teacher')) {
    roleCode = 'teacher'
    const teacherMatch = users.find((u) => u.username === username)
    if (teacherMatch) {
      realName = teacherMatch.real_name
      userId = teacherMatch.user_id
    } else {
      realName = '王建国'
      userId = 2
    }
  } else {
    roleCode = 'student'
    const stuMatch = users.find((u) => u.username === username)
    if (stuMatch) {
      realName = stuMatch.real_name
      userId = stuMatch.user_id
    } else {
      realName = '陈思远'
      userId = 100
    }
  }

  return ok({
    token: `mock-token-${username}`,
    user: {
      user_id: userId,
      username,
      real_name: realName,
      role_code: roleCode,
    },
  })
}

function handleCreateUser(body: Record<string, any>) {
  const roleMap: Record<number, number> = { 1: 1, 2: 2, 3: 3 }
  const newUser: MockUser = {
    user_id: nextUserId(),
    username: body.username,
    password: body.password || '123456',
    real_name: body.real_name,
    role_id: body.role_id || roleMap[body.role_id] || 3,
    status: body.status ?? 1,
    create_time: new Date().toISOString().slice(0, 19).replace('T', ' '),
  }
  users.push(newUser)
  return ok(mapUser(newUser))
}

function handleUpdateUser(id: number, body: Record<string, any>) {
  const user = users.find((u) => u.user_id === id)
  if (!user) return { status: 404, data: { detail: '用户不存在' } }
  if (body.real_name !== undefined) user.real_name = body.real_name
  if (body.role_id !== undefined) user.role_id = body.role_id
  if (body.status !== undefined) user.status = body.status
  if (body.password !== undefined) user.password = body.password
  return ok(mapUser(user))
}

function handleStudents(params: Record<string, unknown>) {
  let result = students
  if (params.class_id) {
    result = result.filter((s) => s.class_id === params.class_id)
  }
  if (params.course_id) {
    // 按课程关联班级筛选
    const courseMap: Record<number, number[]> = { 1: [1, 2], 2: [3, 4], 3: [5, 6], 4: [1, 3, 5] }
    const classIds = courseMap[params.course_id as number] || []
    result = result.filter((s) => classIds.includes(s.class_id))
  }
  if (params.keyword) {
    const kw = String(params.keyword)
    result = result.filter((s) => s.real_name.includes(kw) || s.student_no.includes(kw))
  }
  return ok(result.map(mapStudent))
}

function handleCourses(params: Record<string, unknown>) {
  let result = courses
  if (params.teacher_id) {
    result = result.filter((c) => c.teacher_id === params.teacher_id)
  }
  if (params.semester) {
    result = result.filter((c) => c.semester === params.semester)
  }
  return ok(result.map(mapCourse))
}

function handleMajors(params: Record<string, unknown>) {
  let result = classes
  if (params.grade) {
    result = result.filter((c) => c.grade === params.grade)
  }
  const seen = new Set<string>()
  const majors: { id: number; majorName: string; college: string }[] = []
  for (const c of result) {
    if (c.major && !seen.has(c.major)) {
      seen.add(c.major)
      majors.push({ id: majors.length + 1, majorName: c.major, college: c.college })
    }
  }
  return ok(majors)
}

function handleGrades(params: Record<string, unknown>) {
  let result = classes
  if (params.major) {
    result = result.filter((c) => c.major === params.major)
  }
  const grades = [...new Set(result.map((c) => c.grade).filter(Boolean))]
  return ok(grades.sort())
}

function handleQuestionBank(params: Record<string, unknown>) {
  let result = questionBank
  if (params.course_id) {
    result = result.filter((q) => q.courseId === Number(params.course_id))
  }
  if (params.status) {
    // 按状态过滤（暂不过滤，返回全部）
  }
  return ok(result.map(mapQuestion))
}

function handleAddQuestions(body: Record<string, any>) {
  const questions = body.questions || []
  const source = body.source || 'manual'
  let added = 0
  let skipped = 0
  for (const q of questions) {
    // 简单去重：题干完全相同则跳过
    const exists = questionBank.some((eq) => eq.content === q.stem)
    if (exists) {
      skipped++
      continue
    }
    const course = courses.find((c) => c.course_id === (q.courseId || 1))
    questionBank.push({
      id: nextQuestionId(),
      courseId: q.courseId || 1,
      courseName: course?.course_name || '数据结构与算法',
      knowledgePoint: q.knowledgePoint || '综合',
      type: q.type || 'single_choice',
      content: q.stem,
      options: q.options,
      answer: q.answer || '',
      difficulty: q.difficulty || 'medium',
      source,
      score: q.score || 5,
      createdTime: new Date().toISOString().slice(0, 19).replace('T', ' '),
    })
    added++
  }
  return ok({ added, skipped })
}

function handleCheckQuestions(body: Record<string, any>) {
  const stems: string[] = body.stems || []
  const status: Record<string, boolean> = {}
  for (const stem of stems) {
    status[stem] = questionBank.some((q) => q.content === stem)
  }
  return ok({ status })
}

function handleTemplates(params: Record<string, unknown>) {
  const cid = params.course_id as number
  return ok([
    { id: 'ds-basic', name: '数据结构基础题库', courseId: cid || 1, courseName: '数据结构与算法', questionCount: 20, description: '覆盖线性表、栈队列、树等基础知识点' },
    { id: 'ds-advanced', name: '数据结构进阶题库', courseId: cid || 1, courseName: '数据结构与算法', questionCount: 15, description: '图论、高级排序、哈希表等进阶题目' },
  ])
}

function handleImportRows(body: Record<string, any>) {
  const rows = body.rows || []
  return ok({ imported: rows.length, skipped: 0 })
}

function handleImportBuiltin(body: Record<string, any>) {
  const templateId = body.templateId || 'ds-basic'
  const count = templateId === 'ds-advanced' ? 15 : 20
  return ok({ imported: count, skipped: 0 })
}

function handleUpdateQuestion(id: number, body: Record<string, any>) {
  const q = questionBank.find((eq) => eq.id === id)
  if (!q) return { status: 404, data: { detail: '题目不存在' } }
  if (body.type) q.type = body.type
  if (body.stem) q.content = body.stem
  if (body.options) q.options = body.options
  if (body.answer !== undefined) q.answer = body.answer
  if (body.knowledgePoint !== undefined) q.knowledgePoint = body.knowledgePoint
  if (body.difficulty) q.difficulty = body.difficulty
  if (body.score !== undefined) q.score = body.score
  return ok(null)
}

function handleGenerateExercises(body: Record<string, any>) {
  const count = body.questionCount || 5
  const kps = body.knowledgePoints?.length ? body.knowledgePoints : ['综合']
  const types = body.questionTypes?.length ? body.questionTypes : ['single_choice']
  const difficulty = body.difficulty || 'medium'

  const generated: unknown[] = []
  let id = -1
  for (let i = 0; i < count; i++) {
    const type = types[i % types.length]
    const kp = kps[i % kps.length]
    const question = generateOneQuestion(type, kp, difficulty, id)
    generated.push(question)
    id--
  }

  return ok({
    questions: generated,
    meta: {
      model: 'qwen-plus (mock)',
      elapsedMs: 800 + Math.floor(Math.random() * 500),
    },
  })
}

function generateOneQuestion(type: string, kp: string, difficulty: string, id: number) {
  const templates: Record<string, () => Record<string, any>> = {
    single_choice: () => ({
      id,
      type: 'single_choice',
      stem: `【AI 生成】关于${kp}的单选题（难度：${difficulty}）：下列关于${kp}的描述，正确的是哪一项？`,
      options: [
        { key: 'A', text: '时间复杂度为 O(1)' },
        { key: 'B', text: '空间复杂度为 O(n)' },
        { key: 'C', text: '适用于大规模数据场景' },
        { key: 'D', text: '以上都不对' },
      ],
      answer: 'A',
      knowledgePoint: kp,
      difficulty,
      score: 5,
      source: 'ai',
      explanation: `${kp}的核心操作平均时间复杂度为 O(1)。`,
    }),
    multi_choice: () => ({
      id,
      type: 'multi_choice',
      stem: `【AI 生成】关于${kp}的多选题（难度：${difficulty}）：以下关于${kp}的说法，正确的有哪些？`,
      options: [
        { key: 'A', text: '具有先进先出特性' },
        { key: 'B', text: '支持动态扩容' },
        { key: 'C', text: '可以用于实现广度优先搜索' },
        { key: 'D', text: '插入和删除效率高' },
      ],
      answer: 'A,B,C',
      answerList: ['A', 'B', 'C'],
      knowledgePoint: kp,
      difficulty,
      score: 10,
      source: 'ai',
      explanation: `${kp}的多个特性需要综合理解。`,
    }),
    judge: () => ({
      id,
      type: 'judge',
      stem: `【AI 生成】判断题（难度：${difficulty}）：${kp}在最坏情况下的时间复杂度为 O(n²)。`,
      options: [
        { key: 'A', text: '对' },
        { key: 'B', text: '错' },
      ],
      answer: 'true',
      knowledgePoint: kp,
      difficulty,
      score: 5,
      source: 'ai',
      explanation: `在最坏情况下，${kp}确实可能退化到 O(n²)。`,
    }),
    fill_blank: () => ({
      id,
      type: 'fill_blank',
      stem: `【AI 生成】填空题（难度：${difficulty}）：${kp}的基本操作包括插入、删除和____。`,
      answer: '查找',
      knowledgePoint: kp,
      difficulty,
      score: 5,
      source: 'ai',
      explanation: `${kp}的基本操作包括插入、删除和查找。`,
    }),
  }
  const template = templates[type] ?? templates.single_choice
  return template!()
}

function handleAnswerTasks(params: Record<string, unknown>) {
  let result = answerTasks.filter((t) => !t.title.startsWith('【自主练习】'))
  if (params.for_student) {
    result = result.filter((t) => t.status === 'published')
  }
  if (params.courseId || params.course_id) {
    const cid = Number(params.courseId || params.course_id)
    result = result.filter((t) => t.courseId === cid)
  }
  if (params.teacherId || params.teacher_id) {
    // 按教师名筛选
  }
  return ok(result.map(mapAnswerTask))
}

function handleCreateAnswerTask(body: Record<string, any>) {
  const course = courses.find((c) => c.course_id === body.courseId)
  const cls = classes.find((c) => c.class_id === body.classId)
  const task: MockAnswerTask = {
    id: nextTaskId(),
    title: body.title || '未命名练习',
    courseId: body.courseId || 1,
    courseName: course?.course_name || body.courseName || '数据结构与算法',
    classId: body.classId || 1,
    className: cls?.class_name || body.className || '计科2401',
    teacherName: body.teacherName || '王建国',
    knowledgePoints: body.knowledgePoints || [],
    questionCount: body.questions?.length || 0,
    totalScore: (body.questions || []).reduce((sum: number, q: any) => sum + (q.score || 5), 0),
    status: body.status || 'draft',
    publishTime: new Date().toISOString().slice(0, 19).replace('T', ' '),
    deadline: '',
    submittedCount: 0,
    averageScore: 0,
    questions: body.questions || [],
  }
  answerTasks.push(task)
  return ok(mapAnswerTask(task))
}

function handleSubmitAnswers(body: Record<string, any>) {
  const taskId = body.task_id
  const answers = body.answers || {}
  const task = answerTasks.find((t) => t.id === taskId)
  const record: MockAnswerRecord = {
    id: nextRecordId(),
    taskId,
    studentId: 1,
    studentName: '陈思远',
    studentNo: '20240101',
    courseName: task?.courseName || '数据结构与算法',
    quizTitle: task?.title || '练习',
    score: Math.floor(60 + Math.random() * 40),
    totalScore: task?.totalScore || 100,
    submitTime: new Date().toISOString().slice(0, 19).replace('T', ' '),
    isLate: false,
    status: '已批改',
    answers,
  }
  answerRecords.push(record)
  if (task) task.submittedCount++
  return ok({
    submissionId: record.id,
    score: record.score,
    totalScore: record.totalScore,
    correctCount: Math.floor(record.score / (record.totalScore / Object.keys(answers).length)),
  })
}
