/**
 * 内存可变状态 —— 支持真实增删改
 * 用户、题库、答题任务、答题记录、教学数据
 */
import { courses, students, classes } from './static'

/* ============================================================ */
/* 用户管理                                                      */
/* ============================================================ */

export interface MockUser {
  user_id: number
  username: string
  password: string
  real_name: string
  role_id: number // 1=admin, 2=teacher, 3=student
  status: number // 1=启用, 0=禁用
  create_time: string
}

export const users: MockUser[] = [
  { user_id: 1, username: 'admin', password: '123456', real_name: '系统管理员', role_id: 1, status: 1, create_time: '2025-09-01 08:00:00' },
  { user_id: 2, username: 'teacher1', password: '123456', real_name: '王建国', role_id: 2, status: 1, create_time: '2025-09-01 08:00:00' },
  { user_id: 3, username: 'teacher2', password: '123456', real_name: '李秀芳', role_id: 2, status: 1, create_time: '2025-09-01 08:00:00' },
  { user_id: 4, username: 'teacher3', password: '123456', real_name: '张伟', role_id: 2, status: 1, create_time: '2025-09-01 08:00:00' },
  { user_id: 5, username: 'teacher4', password: '123456', real_name: '刘洋', role_id: 2, status: 1, create_time: '2025-09-01 08:00:00' },
  ...students.slice(0, 10).map((s, i) => ({
    user_id: 100 + i,
    username: `stu${String(i + 1).padStart(2, '0')}`,
    password: '123456',
    real_name: s.real_name,
    role_id: 3,
    status: 1,
    create_time: '2025-09-01 08:00:00',
  })),
]

let userIdCounter = 200
export function nextUserId(): number {
  return userIdCounter++
}

/* ============================================================ */
/* 题库                                                          */
/* ============================================================ */

export interface MockQuestion {
  id: number
  courseId: number
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  options?: string[]
  answer: string
  difficulty: string
  source: string
  score: number
  createdTime: string
}

/** 知识点池 */
export const knowledgePoints: Record<number, string[]> = {
  1: ['线性表', '栈与队列', '树与二叉树', '图', '排序算法', '查找算法', '哈希表', '递归'],
  2: ['搜索算法', '知识表示', '机器学习', '神经网络', '自然语言处理'],
  3: ['进程管理', '内存管理', '文件系统', 'I/O 管理'],
  4: ['SQL 查询', '数据库设计', '事务管理', '索引优化'],
}

function buildQuestionBank(): MockQuestion[] {
  const courseName = '数据结构与算法'
  const kps = knowledgePoints[1]!
  const list: MockQuestion[] = []
  let id = 1

  // 单选 5 道
  const singleChoice = [
    { kp: kps[0]!, q: '在长度为 n 的顺序表中删除一个元素，平均需要移动多少个元素？', opts: ['(n-1)/2', 'n/2', '(n+1)/2', 'n'], ans: 'A', diff: 'medium' },
    { kp: kps[2]!, q: '深度为 k 的完全二叉树至少有多少个结点？', opts: ['2^k - 1', '2^(k-1)', '2^(k-1) - 1', '2^k'], ans: 'B', diff: 'medium' },
    { kp: kps[4]!, q: '快速排序的平均时间复杂度为？', opts: ['O(n)', 'O(n log n)', 'O(n²)', 'O(log n)'], ans: 'B', diff: 'easy' },
    { kp: kps[1]!, q: '若进栈序列为 1,2,3,4，则以下哪个不可能是出栈序列？', opts: ['3,2,1,4', '4,3,2,1', '1,2,3,4', '4,1,2,3'], ans: 'D', diff: 'medium' },
    { kp: kps[6]!, q: '哈希表解决冲突的常用方法不包括？', opts: ['开放寻址法', '链地址法', '再哈希法', '顺序查找法'], ans: 'D', diff: 'easy' },
  ]
  singleChoice.forEach((item) => {
    list.push({
      id: id++, courseId: 1, courseName, knowledgePoint: item.kp,
      type: 'single_choice', content: item.q, options: item.opts, answer: item.ans,
      difficulty: item.diff, source: 'manual', score: 5, createdTime: '2025-09-15 10:00:00',
    })
  })

  // 多选 5 道
  const multiChoice = [
    { kp: kps[0]!, q: '以下属于线性数据结构的有？', opts: ['数组', '二叉树', '链表', '队列'], ans: 'A,C,D', diff: 'easy' },
    { kp: kps[4]!, q: '以下排序算法中时间复杂度为 O(n²) 的有？', opts: ['冒泡排序', '快速排序', '插入排序', '选择排序'], ans: 'A,C,D', diff: 'medium' },
    { kp: kps[3]!, q: '关于图的遍历，以下说法正确的有？', opts: ['DFS 使用栈', 'BFS 使用队列', 'DFS 一定比 BFS 慢', 'BFS 可以求最短路径'], ans: 'A,B,D', diff: 'medium' },
    { kp: kps[2]!, q: '以下关于二叉树的性质，正确的有？', opts: ['第 i 层最多 2^(i-1) 个结点', '深度为 k 的二叉树最多 2^k-1 个结点', '叶子结点数 = 度为 2 的结点数 + 1', '中序遍历是广度优先'], ans: 'A,B,C', diff: 'medium' },
    { kp: kps[7]!, q: '递归算法的特点包括？', opts: ['必须有基准条件', '空间复杂度通常较高', '一定比迭代快', '代码通常更简洁'], ans: 'A,B,D', diff: 'easy' },
  ]
  multiChoice.forEach((item) => {
    list.push({
      id: id++, courseId: 1, courseName, knowledgePoint: item.kp,
      type: 'multi_choice', content: item.q, options: item.opts, answer: item.ans,
      difficulty: item.diff, source: 'manual', score: 10, createdTime: '2025-09-15 10:05:00',
    })
  })

  // 判断 5 道
  const judge = [
    { kp: kps[0]!, q: '链表支持随机访问。', ans: '错误', diff: 'easy' },
    { kp: kps[4]!, q: '归并排序是稳定排序。', ans: '正确', diff: 'medium' },
    { kp: kps[2]!, q: '二叉排序树的中序遍历得到一个有序序列。', ans: '正确', diff: 'easy' },
    { kp: kps[3]!, q: '邻接矩阵存储无向图时矩阵一定是对称的。', ans: '正确', diff: 'easy' },
    { kp: kps[6]!, q: '哈希查找的时间复杂度一定为 O(1)。', ans: '错误', diff: 'medium' },
  ]
  judge.forEach((item) => {
    list.push({
      id: id++, courseId: 1, courseName, knowledgePoint: item.kp,
      type: 'judge', content: item.q, options: ['正确', '错误'], answer: item.ans,
      difficulty: item.diff, source: 'manual', score: 5, createdTime: '2025-09-15 10:10:00',
    })
  })

  // 填空 5 道
  const fillBlank = [
    { kp: kps[1]!, q: '队列的特点是____。', ans: '先进先出', diff: 'easy' },
    { kp: kps[0]!, q: '在单链表中，要在指针 p 所指结点后插入新结点 s，关键操作是 s->next = p->next 和 ____。', ans: 'p->next = s', diff: 'medium' },
    { kp: kps[2]!, q: '一棵有 n 个结点的二叉树，其深度至少为____。', ans: 'log2(n+1) 向下取整加 1', diff: 'hard' },
    { kp: kps[4]!, q: '堆排序的最坏时间复杂度为____。', ans: 'O(n log n)', diff: 'hard' },
    { kp: kps[5]!, q: '二分查找要求数据结构必须是____存储且有序。', ans: '顺序（数组）', diff: 'easy' },
  ]
  fillBlank.forEach((item) => {
    list.push({
      id: id++, courseId: 1, courseName, knowledgePoint: item.kp,
      type: 'fill_blank', content: item.q, answer: item.ans,
      difficulty: item.diff, source: 'manual', score: 5, createdTime: '2025-09-15 10:15:00',
    })
  })

  return list
}

export const questionBank: MockQuestion[] = buildQuestionBank()
let questionIdCounter = 1000
export function nextQuestionId(): number {
  return ++questionIdCounter
}

/* ============================================================ */
/* 答题任务                                                      */
/* ============================================================ */

export interface MockAnswerTask {
  id: number
  title: string
  courseId: number
  courseName: string
  classId: number
  className: string
  teacherName: string
  knowledgePoints: string[]
  questionCount: number
  totalScore: number
  status: string // draft | published | closed
  publishTime: string
  deadline: string
  submittedCount: number
  averageScore: number
  questions: unknown[]
}

export const answerTasks: MockAnswerTask[] = [
  {
    id: 1,
    title: '数据结构第三章 - 树与二叉树 练习',
    courseId: 1,
    courseName: '数据结构与算法',
    classId: 1,
    className: '计科2401',
    teacherName: '王建国',
    knowledgePoints: ['树与二叉树', '栈与队列'],
    questionCount: 5,
    totalScore: 100,
    status: 'published',
    publishTime: '2026-03-10 09:00:00',
    deadline: '2026-03-20 23:59:00',
    submittedCount: 4,
    averageScore: 82.5,
    questions: [],
  },
  {
    id: 2,
    title: '排序算法专项训练',
    courseId: 1,
    courseName: '数据结构与算法',
    classId: 1,
    className: '计科2401',
    teacherName: '王建国',
    knowledgePoints: ['排序算法', '查找算法'],
    questionCount: 5,
    totalScore: 100,
    status: 'published',
    publishTime: '2026-03-12 14:00:00',
    deadline: '2026-03-25 23:59:00',
    submittedCount: 3,
    averageScore: 76.0,
    questions: [],
  },
  {
    id: 3,
    title: '线性表复习测验',
    courseId: 1,
    courseName: '数据结构与算法',
    classId: 2,
    className: '计科2402',
    teacherName: '王建国',
    knowledgePoints: ['线性表'],
    questionCount: 5,
    totalScore: 100,
    status: 'closed',
    publishTime: '2026-02-20 09:00:00',
    deadline: '2026-03-01 23:59:00',
    submittedCount: 5,
    averageScore: 85.2,
    questions: [],
  },
]
let taskIdCounter = 100
export function nextTaskId(): number {
  return ++taskIdCounter
}

/* ============================================================ */
/* 答题记录                                                      */
/* ============================================================ */

export interface MockAnswerRecord {
  id: number
  taskId: number
  studentId: number
  studentName: string
  studentNo: string
  courseName: string
  quizTitle: string
  score: number
  totalScore: number
  submitTime: string
  isLate: boolean
  status: string
  answers: Record<number, string | string[]>
}

export const answerRecords: MockAnswerRecord[] = [
  { id: 1, taskId: 1, studentId: 1, studentName: '陈思远', studentNo: '20240101', courseName: '数据结构与算法', quizTitle: '数据结构第三章 - 树与二叉树 练习', score: 90, totalScore: 100, submitTime: '2026-03-15 10:30:00', isLate: false, status: '已批改', answers: {} },
  { id: 2, taskId: 1, studentId: 2, studentName: '林雨晴', studentNo: '20240102', courseName: '数据结构与算法', quizTitle: '数据结构第三章 - 树与二叉树 练习', score: 85, totalScore: 100, submitTime: '2026-03-15 11:00:00', isLate: false, status: '已批改', answers: {} },
  { id: 3, taskId: 1, studentId: 3, studentName: '王浩然', studentNo: '20240103', courseName: '数据结构与算法', quizTitle: '数据结构第三章 - 树与二叉树 练习', score: 72, totalScore: 100, submitTime: '2026-03-16 09:00:00', isLate: false, status: '已批改', answers: {} },
  { id: 4, taskId: 1, studentId: 4, studentName: '张雅琪', studentNo: '20240104', courseName: '数据结构与算法', quizTitle: '数据结构第三章 - 树与二叉树 练习', score: 95, totalScore: 100, submitTime: '2026-03-14 20:00:00', isLate: false, status: '已批改', answers: {} },
  { id: 5, taskId: 2, studentId: 1, studentName: '陈思远', studentNo: '20240101', courseName: '数据结构与算法', quizTitle: '排序算法专项训练', score: 78, totalScore: 100, submitTime: '2026-03-18 15:00:00', isLate: false, status: '已批改', answers: {} },
  { id: 6, taskId: 2, studentId: 2, studentName: '林雨晴', studentNo: '20240102', courseName: '数据结构与算法', quizTitle: '排序算法专项训练', score: 65, totalScore: 100, submitTime: '2026-03-19 09:00:00', isLate: false, status: '已批改', answers: {} },
  { id: 7, taskId: 2, studentId: 5, studentName: '刘嘉伟', studentNo: '20240105', courseName: '数据结构与算法', quizTitle: '排序算法专项训练', score: 88, totalScore: 100, submitTime: '2026-03-20 23:30:00', isLate: true, status: '已批改', answers: {} },
  { id: 8, taskId: 3, studentId: 6, studentName: '赵子墨', studentNo: '20240201', courseName: '数据结构与算法', quizTitle: '线性表复习测验', score: 92, totalScore: 100, submitTime: '2026-02-28 14:00:00', isLate: false, status: '已批改', answers: {} },
]
let recordIdCounter = 100
export function nextRecordId(): number {
  return ++recordIdCounter
}

/* ============================================================ */
/* 教学数据记录（数据管理页面）                                   */
/* ============================================================ */

export interface MockTeachingData {
  id: number
  studentId: string
  studentName: string
  courseId: string
  courseName: string
  semester: string
  deptId: number
  majorId: number
  classId: number
  score?: number
  attendance?: string
  homework?: string
  dataType: 'score' | 'attendance' | 'assignment'
  sourceFileName?: string
}

export const teachingData: MockTeachingData[] = (() => {
  const records: MockTeachingData[] = []
  let id = 1
  const sampleStudents = students.slice(0, 15)
  for (const s of sampleStudents) {
    const cls = classes.find((c) => c.class_id === s.class_id)!
    // 成绩
    records.push({
      id: id++, studentId: s.student_no, studentName: s.real_name,
      courseId: 'CS101', courseName: '数据结构与算法', semester: '2025-2026-1',
      deptId: 1, majorId: 1, classId: s.class_id,
      score: Math.floor(60 + Math.random() * 40),
      dataType: 'score', sourceFileName: '2025秋-数据结构-成绩.xlsx',
    })
    // 考勤
    records.push({
      id: id++, studentId: s.student_no, studentName: s.real_name,
      courseId: 'CS101', courseName: '数据结构与算法', semester: '2025-2026-1',
      deptId: 1, majorId: 1, classId: s.class_id,
      attendance: Math.random() > 0.15 ? '正常' : '迟到',
      dataType: 'attendance', sourceFileName: '2025秋-数据结构-考勤.xlsx',
    })
    // 作业
    records.push({
      id: id++, studentId: s.student_no, studentName: s.real_name,
      courseId: 'CS101', courseName: '数据结构与算法', semester: '2025-2026-1',
      deptId: 1, majorId: 1, classId: s.class_id,
      homework: Math.random() > 0.2 ? '已提交' : '未提交',
      dataType: 'assignment', sourceFileName: '2025秋-数据结构-作业.xlsx',
    })
  }
  return records
})()

/* ============================================================ */
/* 导入日志                                                      */
/* ============================================================ */

export interface MockImportLog {
  id: number
  importType: string
  dataSource: string
  fileName: string
  totalCount: number
  successCount: number
  failCount: number
  operatorName: string
  importTime: string
  status: number
}

export const importLogs: MockImportLog[] = [
  { id: 1, importType: 'score', dataSource: 'excel', fileName: '2025秋-数据结构-成绩.xlsx', totalCount: 30, successCount: 30, failCount: 0, operatorName: '王建国', importTime: '2025-09-10 10:00:00', status: 1 },
  { id: 2, importType: 'attendance', dataSource: 'excel', fileName: '2025秋-数据结构-考勤.xlsx', totalCount: 30, successCount: 29, failCount: 1, operatorName: '王建国', importTime: '2025-09-10 10:05:00', status: 1 },
  { id: 3, importType: 'assignment', dataSource: 'excel', fileName: '2025秋-数据结构-作业.xlsx', totalCount: 30, successCount: 28, failCount: 2, operatorName: '王建国', importTime: '2025-09-10 10:10:00', status: 1 },
  { id: 4, importType: 'student', dataSource: 'excel', fileName: '2024级新生名单.xlsx', totalCount: 180, successCount: 180, failCount: 0, operatorName: '系统管理员', importTime: '2025-09-01 08:00:00', status: 1 },
]
