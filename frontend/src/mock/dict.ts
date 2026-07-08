/**
 * 数据字典模拟数据（对应 td_* 表）
 */
import type { ClassInfo, Course, Department, Major, Semester, Student, StudentProfileData, Teacher } from '@/types'

export const departments: Department[] = [
  { id: 1, deptCode: 'CS', deptName: '计算机学院' },
]

export const majors: Major[] = [
  { id: 1, majorCode: 'CS01', majorName: '计算机科学与技术', deptId: 1 },
  { id: 2, majorCode: 'SE01', majorName: '软件工程', deptId: 1 },
]

const majorNameById = Object.fromEntries(majors.map((m) => [m.id, m.majorName]))

export const classes: ClassInfo[] = [
  { id: 1, classCode: 'CS2401', className: '计科2401', majorId: 1, majorName: majorNameById[1]!, deptId: 1, grade: '2024' },
  { id: 2, classCode: 'CS2402', className: '计科2402', majorId: 1, majorName: majorNameById[1]!, deptId: 1, grade: '2024' },
  { id: 3, classCode: 'SE2401', className: '软工2401', majorId: 2, majorName: majorNameById[2]!, deptId: 1, grade: '2024' },
  { id: 4, classCode: 'CS2301', className: '计科2301', majorId: 1, majorName: majorNameById[1]!, deptId: 1, grade: '2023' },
  { id: 5, classCode: 'SE2301', className: '软工2301', majorId: 2, majorName: majorNameById[2]!, deptId: 1, grade: '2023' },
]

export const semesters: Semester[] = [
  { id: 1, semesterCode: '2025-2026-1', semesterName: '2025-2026 学年第一学期', isCurrent: true },
  { id: 2, semesterCode: '2024-2025-2', semesterName: '2024-2025 学年第二学期', isCurrent: false },
  { id: 3, semesterCode: '2024-2025-1', semesterName: '2024-2025 学年第一学期', isCurrent: false },
]

export const teachers: Teacher[] = [
  { id: 1, teacherNo: 'T001', teacherName: '王教授', deptId: 1 },
  { id: 3, teacherNo: 'T003', teacherName: '张讲师', deptId: 1 },
]

const semesterById = Object.fromEntries(semesters.map((s) => [s.id, s]))

function buildCourse(
  id: number,
  courseNo: string,
  courseName: string,
  teacherId: number,
  semesterId: number,
): Course {
  const sem = semesterById[semesterId]!
  return {
    id,
    courseNo,
    courseName,
    deptId: 1,
    teacherId,
    semesterId,
    semesterCode: sem.semesterCode,
    semesterName: sem.semesterName,
  }
}

export const courses: Course[] = [
  // 2025-2026 学年第一学期
  buildCourse(1, 'CS101', '数据结构', 1, 1),
  buildCourse(2, 'CS102', '操作系统', 1, 1),
  buildCourse(3, 'CS103', '计算机网络', 3, 1),
  buildCourse(4, 'CS104', 'Java程序设计', 1, 1),
  buildCourse(5, 'CS105', '数据库原理', 3, 1),
  // 2024-2025 学年第二学期
  buildCourse(6, 'CS101', '数据结构', 1, 2),
  buildCourse(7, 'CS102', '操作系统', 1, 2),
  buildCourse(8, 'CS103', '计算机网络', 3, 2),
  // 2024-2025 学年第一学期
  buildCourse(9, 'CS104', 'Java程序设计', 1, 3),
  buildCourse(10, 'CS105', '数据库原理', 3, 3),
]

export const students: Student[] = [
  { id: 1, studentNo: '2024001001', studentName: '陈同学', classId: 1, majorId: 1, deptId: 1, grade: '2024' },
  { id: 2, studentNo: '2024001002', studentName: '刘同学', classId: 1, majorId: 1, deptId: 1, grade: '2024' },
  { id: 3, studentNo: '2024001003', studentName: '赵同学', classId: 1, majorId: 1, deptId: 1, grade: '2024' },
  { id: 4, studentNo: '2024001004', studentName: '孙同学', classId: 2, majorId: 1, deptId: 1, grade: '2024' },
  { id: 5, studentNo: '2024001005', studentName: '周同学', classId: 1, majorId: 1, deptId: 1, grade: '2024' },
  { id: 6, studentNo: '2024001023', studentName: '李四', classId: 1, majorId: 1, deptId: 1, grade: '2024' },
  { id: 7, studentNo: '2024001045', studentName: '王五', classId: 2, majorId: 1, deptId: 1, grade: '2024' },
  { id: 8, studentNo: '2024001067', studentName: '赵六', classId: 3, majorId: 2, deptId: 1, grade: '2024' },
  { id: 9, studentNo: '2024001089', studentName: '钱七', classId: 3, majorId: 2, deptId: 1, grade: '2024' },
  { id: 10, studentNo: '2023001001', studentName: '吴同学', classId: 4, majorId: 1, deptId: 1, grade: '2023' },
  { id: 11, studentNo: '2023001002', studentName: '郑同学', classId: 4, majorId: 1, deptId: 1, grade: '2023' },
  { id: 12, studentNo: '2023001003', studentName: '冯同学', classId: 5, majorId: 2, deptId: 1, grade: '2023' },
]

/** 各课程知识点（与课程名称对应） */
export const courseKnowledgePoints: Record<number, string[]> = {
  1: ['链表操作', '二叉树遍历', '栈与队列', '平衡二叉树', '排序算法', '哈希表', '图遍历'],
  2: ['进程调度', '死锁', '内存管理', '文件系统', '虚拟内存'],
  3: ['TCP/IP协议', '路由算法', '网络安全', 'DNS', 'HTTP协议'],
  4: ['变量与表达式', '控制结构', '面向对象', '异常处理', '文件IO', '集合框架'],
  5: ['SQL查询', '关系模型', '索引优化', '事务处理', '规范化理论'],
  6: ['链表操作', '二叉树遍历', '栈与队列', '平衡二叉树', '排序算法', '哈希表', '图遍历'],
  7: ['进程调度', '死锁', '内存管理', '文件系统', '虚拟内存'],
  8: ['TCP/IP协议', '路由算法', '网络安全', 'DNS', 'HTTP协议'],
  9: ['变量与表达式', '控制结构', '面向对象', '异常处理', '文件IO', '集合框架'],
  10: ['SQL查询', '关系模型', '索引优化', '事务处理', '规范化理论'],
}

/** 课程-班级开设关系（某课程在某学期向哪些班级开设） */
export const courseClassRelations: { courseId: number; classId: number; semesterId: number }[] = [
  // 2025-2026-1 · 2024 级班级
  { courseId: 1, classId: 1, semesterId: 1 },
  { courseId: 1, classId: 2, semesterId: 1 },
  { courseId: 1, classId: 3, semesterId: 1 },
  { courseId: 2, classId: 1, semesterId: 1 },
  { courseId: 2, classId: 2, semesterId: 1 },
  { courseId: 3, classId: 2, semesterId: 1 },
  { courseId: 3, classId: 3, semesterId: 1 },
  { courseId: 4, classId: 1, semesterId: 1 },
  { courseId: 4, classId: 2, semesterId: 1 },
  { courseId: 4, classId: 3, semesterId: 1 },
  { courseId: 5, classId: 2, semesterId: 1 },
  { courseId: 5, classId: 3, semesterId: 1 },
  // 2024-2025-2 · 2023 级班级
  { courseId: 6, classId: 4, semesterId: 2 },
  { courseId: 7, classId: 4, semesterId: 2 },
  { courseId: 8, classId: 5, semesterId: 2 },
  // 2024-2025-1 · 2023 级班级
  { courseId: 9, classId: 4, semesterId: 3 },
  { courseId: 10, classId: 5, semesterId: 3 },
]

/** 课程-专业开设关系（由 courseClassRelations 聚合，表示某课程在某学期向哪些专业开设） */
export const courseMajorRelations: { courseId: number; majorId: number; semesterId: number }[] = (() => {
  const seen = new Set<string>()
  const result: { courseId: number; majorId: number; semesterId: number }[] = []
  courseClassRelations.forEach((rel) => {
    const cls = classes.find((c) => c.id === rel.classId)
    if (!cls) return
    const key = `${rel.courseId}-${cls.majorId}-${rel.semesterId}`
    if (seen.has(key)) return
    seen.add(key)
    result.push({ courseId: rel.courseId, majorId: cls.majorId, semesterId: rel.semesterId })
  })
  return result
})()

/** 课程选修表 course_student（对应 DB course_student） */
export const courseStudentEnrollments: { id: number; courseId: number; studentId: number; status: number }[] =
  students.flatMap((student) =>
    courseClassRelations
      .filter((rel) => rel.classId === student.classId)
      .map((rel, idx) => ({
        id: student.id * 100 + rel.courseId + idx,
        courseId: rel.courseId,
        studentId: student.id,
        status: 1,
      })),
  )

/** 学生知识点掌握度，key 为 `${studentId}-${courseId}`，values 与 courseKnowledgePoints 对齐 */
export const studentKnowledgeMastery: Record<string, number[]> = {
  // 数据结构 CS101 · 计科2401
  '1-1': [92, 88, 90, 72, 85, 80, 78],
  '2-1': [78, 75, 70, 58, 72, 65, 68],
  '3-1': [95, 92, 88, 85, 90, 82, 86],
  '5-1': [96, 94, 92, 88, 95, 90, 88],
  '6-1': [70, 68, 65, 55, 62, 58, 60],
  // 数据结构 CS101 · 计科2402
  '4-1': [65, 62, 58, 50, 55, 52, 48],
  '7-1': [72, 70, 68, 60, 65, 62, 58],
  // 操作系统 CS102 · 计科2401
  '1-2': [88, 82, 85, 78, 80],
  '2-2': [75, 70, 72, 68, 65],
  '3-2': [90, 85, 88, 82, 86],
  '5-2': [92, 88, 90, 85, 88],
  '6-2': [62, 58, 60, 55, 52],
  // 计算机网络 CS103 · 计科2402 / 软工2401
  '4-3': [58, 55, 52, 60, 48],
  '7-3': [68, 65, 62, 70, 58],
  '8-3': [55, 52, 48, 50, 45],
  '9-3': [60, 58, 55, 62, 50],
  // 数据结构 CS101 · 软工2401
  '8-1': [68, 65, 62, 58, 60, 55, 52],
  '9-1': [72, 70, 68, 62, 65, 60, 58],
  // 操作系统 CS102 · 计科2402
  '4-2': [70, 68, 65, 62, 60],
  '7-2': [75, 72, 70, 68, 65],
  // Java程序设计 CS104 · 计科2402
  '4-4': [68, 65, 62, 58, 60, 55],
  '7-4': [74, 70, 68, 65, 62, 60],
  '1-4': [90, 88, 85, 78, 82, 80],
  '2-4': [72, 70, 68, 62, 65, 60],
  '3-4': [88, 85, 90, 82, 80, 85],
  '5-4': [94, 92, 88, 85, 88, 90],
  '6-4': [65, 62, 58, 55, 60, 58],
  '8-4': [60, 58, 55, 50, 52, 48],
  '9-4': [68, 65, 62, 58, 60, 55],
  // 数据库原理 CS105 · 计科2402 / 软工2401
  '4-5': [62, 58, 55, 60, 52],
  '7-5': [70, 68, 65, 72, 60],
  '8-5': [58, 55, 52, 58, 50],
  '9-5': [65, 62, 60, 58, 55],
  // 2024-2025-2 学期 · 计科2301 / 软工2301
  '10-6': [82, 78, 80, 75, 76, 74, 72],
  '11-6': [76, 72, 74, 68, 70, 66, 65],
  '10-7': [80, 76, 78, 72, 74],
  '11-7': [72, 68, 70, 65, 62],
  '12-8': [70, 66, 68, 62, 60],
}

/** 获取课程知识点列表 */
export function getKnowledgePointsByCourse(courseId: number): string[] {
  if (courseKnowledgePoints[courseId]) {
    return courseKnowledgePoints[courseId]
  }
  const course = courses.find((c) => c.id === courseId)
  if (!course) return []
  const sameNoCourse = courses.find(
    (c) => c.courseNo === course.courseNo && courseKnowledgePoints[c.id],
  )
  return sameNoCourse ? (courseKnowledgePoints[sameNoCourse.id] ?? []) : []
}

/** 获取某课程开设的班级 */
export function getClassesByCourse(courseId: number): ClassInfo[] {
  const course = courses.find((c) => c.id === courseId)
  const classIds = courseClassRelations
    .filter((r) => r.courseId === courseId && (!course || r.semesterId === course.semesterId))
    .map((r) => r.classId)
  return classes.filter((c) => classIds.includes(c.id))
}

/** 获取某教师授课涉及的班级 */
export function getClassesByTeacher(teacherId: number): ClassInfo[] {
  const courseIds = courses.filter((c) => c.teacherId === teacherId).map((c) => c.id)
  const classIds = new Set(
    courseClassRelations
      .filter((r) => courseIds.includes(r.courseId))
      .map((r) => r.classId),
  )
  return classes.filter((c) => classIds.has(c.id))
}

/** 获取某班级开设的课程 */
export function getCoursesByClass(classId: number): Course[] {
  const courseIds = courseClassRelations
    .filter((r) => r.classId === classId)
    .map((r) => r.courseId)
  return courses.filter((c) => courseIds.includes(c.id))
}

/** 获取某课程某班级的学生列表（course_student + student.class_id） */
export function getStudentsInCourseClass(courseId: number, classId: number): Student[] {
  const enrolledIds = new Set(
    courseStudentEnrollments
      .filter((e) => e.courseId === courseId && e.status === 1)
      .map((e) => e.studentId),
  )
  return students.filter((s) => s.classId === classId && enrolledIds.has(s.id))
}

/** 判断学生是否选修某课程 */
export function isStudentEnrolled(studentId: number, courseId: number): boolean {
  return courseStudentEnrollments.some(
    (e) => e.studentId === studentId && e.courseId === courseId && e.status === 1,
  )
}

/** 获取学生某课程的知识点掌握度 */
export function getStudentMastery(studentId: number, courseId: number): number[] | undefined {
  return studentKnowledgeMastery[`${studentId}-${courseId}`]
}

/** 学期下拉选项（兼容旧 value 格式） */
export const semesterOptions = semesters.map((s) => ({
  label: s.semesterName,
  value: s.semesterCode,
  id: s.id,
}))

/** 院系下拉选项（仅计算机学院） */
export const departmentOptions = [
  { label: '计算机学院', value: 'CS', id: 1 },
]

/** 专业下拉选项 */
export const majorOptions = majors.map((m) => ({
  label: m.majorName,
  value: m.id,
}))

/** 年级下拉选项 */
export const gradeOptions = [
  { label: '全部年级', value: '' },
  { label: '2022级', value: '2022' },
  { label: '2023级', value: '2023' },
  { label: '2024级', value: '2024' },
  { label: '2025级', value: '2025' },
]

/** 导入类型选项 */
export const importTypeOptions = [
  { label: '学生信息', value: 'student' as const },
  { label: '课程信息', value: 'course' as const },
  { label: '成绩数据', value: 'score' as const },
  { label: '考勤数据', value: 'attendance' as const },
  { label: '作业数据', value: 'assignment' as const },
]

/** 数据类型显示映射 */
export const dataTypeLabels: Record<string, string> = {
  score: '成绩',
  attendance: '考勤',
  assignment: '作业',
}

/** 各学生学情画像数据（单课程维度） */
export const studentProfiles: (StudentProfileData & { courseId: number })[] = [
  {
    studentId: 1,
    courseId: 1,
    studentNo: '2024001001',
    studentName: '陈同学',
    className: '计科2401',
    courseName: '数据结构',
    tags: ['成绩优秀', '进步明显', '考勤良好', '作业积极'],
    radarValues: [85, 72, 88, 76, 80],
    dimensionScores: [
      { name: '学业水平', score: 85, desc: '本课程成绩 92 分，处于班级前 20%' },
      { name: '学习态度', score: 72, desc: '出勤率 88%，作业提交率 92%' },
      { name: '学习进步', score: 88, desc: '近三次测验平均分提升 12 分' },
      { name: '知识掌握', score: 76, desc: '核心知识点平均掌握度 83%' },
      { name: '课堂参与', score: 80, desc: '课堂问答正确率 85%，高于班级均值' },
    ],
    strongPoints: '链表操作 (92%)、二叉树遍历 (88%)、栈与队列 (90%)',
    weakPoints: '平衡二叉树 (72%)、图遍历 (78%)',
  },
  {
    studentId: 2,
    courseId: 1,
    studentNo: '2024001002',
    studentName: '刘同学',
    className: '计科2401',
    courseName: '数据结构',
    tags: ['态度良好', '需加强练习'],
    radarValues: [70, 78, 65, 68, 72],
    dimensionScores: [
      { name: '学业水平', score: 70, desc: '本课程成绩 78 分，处于班级中游' },
      { name: '学习态度', score: 78, desc: '出勤率 92%，作业提交率 85%' },
      { name: '学习进步', score: 65, desc: '近三次测验平均分波动较小' },
      { name: '知识掌握', score: 68, desc: '核心知识点平均掌握度 68%' },
      { name: '课堂参与', score: 72, desc: '课堂问答正确率 70%，接近班级均值' },
    ],
    strongPoints: '栈与队列 (70%)、排序算法 (72%)',
    weakPoints: '平衡二叉树 (58%)、哈希表 (65%)、图遍历 (68%)',
  },
  {
    studentId: 3,
    courseId: 1,
    studentNo: '2024001003',
    studentName: '赵同学',
    className: '计科2401',
    courseName: '数据结构',
    tags: ['成绩优秀', '知识扎实'],
    radarValues: [90, 85, 82, 88, 86],
    dimensionScores: [
      { name: '学业水平', score: 90, desc: '本课程成绩 95 分，处于班级前 5%' },
      { name: '学习态度', score: 85, desc: '出勤率 95%，作业提交率 98%' },
      { name: '学习进步', score: 82, desc: '近三次测验平均分稳步提升' },
      { name: '知识掌握', score: 88, desc: '核心知识点平均掌握度 88%' },
      { name: '课堂参与', score: 86, desc: '课堂问答正确率 92%，显著高于班级均值' },
    ],
    strongPoints: '链表操作 (95%)、二叉树遍历 (92%)、平衡二叉树 (85%)',
    weakPoints: '暂无显著薄弱项',
  },
  {
    studentId: 4,
    courseId: 3,
    studentNo: '2024001004',
    studentName: '孙同学',
    className: '计科2402',
    courseName: '计算机网络',
    tags: ['需重点关注', '进步缓慢'],
    radarValues: [58, 65, 52, 55, 60],
    dimensionScores: [
      { name: '学业水平', score: 58, desc: '本课程成绩 68 分，处于班级后 20%' },
      { name: '学习态度', score: 65, desc: '出勤率 78%，作业提交率 70%' },
      { name: '学习进步', score: 52, desc: '近三次测验平均分无明显提升' },
      { name: '知识掌握', score: 55, desc: '核心知识点平均掌握度 55%' },
      { name: '课堂参与', score: 60, desc: '课堂问答正确率 58%，低于班级均值' },
    ],
    strongPoints: 'DNS (60%)',
    weakPoints: '网络安全 (52%)、HTTP协议 (48%)、路由算法 (55%)',
  },
  {
    studentId: 5,
    courseId: 1,
    studentNo: '2024001005',
    studentName: '周同学',
    className: '计科2401',
    courseName: '数据结构',
    tags: ['成绩优秀', '全面发展'],
    radarValues: [92, 88, 90, 94, 89],
    dimensionScores: [
      { name: '学业水平', score: 92, desc: '本课程成绩 95 分，处于班级前 3%' },
      { name: '学习态度', score: 88, desc: '出勤率 96%，作业提交率 100%' },
      { name: '学习进步', score: 90, desc: '近三次测验平均分提升 8 分' },
      { name: '知识掌握', score: 94, desc: '核心知识点平均掌握度 92%' },
      { name: '课堂参与', score: 89, desc: '课堂问答正确率 94%，显著高于班级均值' },
    ],
    strongPoints: '链表操作 (96%)、二叉树遍历 (94%)、排序算法 (95%)',
    weakPoints: '平衡二叉树 (88%)',
  },
  {
    studentId: 6,
    courseId: 2,
    studentNo: '2024001023',
    studentName: '李四',
    className: '计科2401',
    courseName: '操作系统',
    tags: ['缺勤偏多', '需督促'],
    radarValues: [62, 55, 58, 60, 52],
    dimensionScores: [
      { name: '学业水平', score: 62, desc: '本课程成绩 65 分，处于班级后 30%' },
      { name: '学习态度', score: 55, desc: '出勤率 75%，本月缺勤率达 25%' },
      { name: '学习进步', score: 58, desc: '近三次测验平均分略有下降' },
      { name: '知识掌握', score: 60, desc: '核心知识点平均掌握度 57%' },
      { name: '课堂参与', score: 52, desc: '课堂问答正确率 50%，低于班级均值' },
    ],
    strongPoints: '文件系统 (60%)',
    weakPoints: '进程调度 (62%)、虚拟内存 (52%)、死锁 (58%)',
  },
  {
    studentId: 7,
    courseId: 1,
    studentNo: '2024001045',
    studentName: '王五',
    className: '计科2402',
    courseName: '数据结构',
    tags: ['作业滞后', '需关注'],
    radarValues: [68, 60, 55, 62, 58],
    dimensionScores: [
      { name: '学业水平', score: 68, desc: '本课程成绩 72 分，处于班级中游偏下' },
      { name: '学习态度', score: 60, desc: '出勤率 82%，连续 4 次作业未提交' },
      { name: '学习进步', score: 55, desc: '近三次测验平均分无明显提升' },
      { name: '知识掌握', score: 62, desc: '核心知识点平均掌握度 62%' },
      { name: '课堂参与', score: 58, desc: '课堂问答正确率 55%，低于班级均值' },
    ],
    strongPoints: '栈与队列 (68%)',
    weakPoints: '平衡二叉树 (60%)、图遍历 (58%)、哈希表 (62%)',
  },
  {
    studentId: 8,
    courseId: 3,
    studentNo: '2024001067',
    studentName: '赵六',
    className: '软工2401',
    courseName: '计算机网络',
    tags: ['成绩下滑', '需辅导'],
    radarValues: [55, 62, 48, 52, 50],
    dimensionScores: [
      { name: '学业水平', score: 55, desc: '本课程成绩 58 分，最近一次下降 8 分' },
      { name: '学习态度', score: 62, desc: '出勤率 85%，作业提交率 75%' },
      { name: '学习进步', score: 48, desc: '近三次测验平均分持续下滑' },
      { name: '知识掌握', score: 52, desc: '核心知识点平均掌握度 50%' },
      { name: '课堂参与', score: 50, desc: '课堂问答正确率 48%，低于班级均值' },
    ],
    strongPoints: 'DNS (50%)',
    weakPoints: 'TCP/IP协议 (55%)、网络安全 (48%)、HTTP协议 (45%)',
  },
  {
    studentId: 9,
    courseId: 3,
    studentNo: '2024001089',
    studentName: '钱七',
    className: '软工2401',
    courseName: '计算机网络',
    tags: ['综合异常', '多维度预警'],
    radarValues: [58, 52, 55, 57, 50],
    dimensionScores: [
      { name: '学业水平', score: 58, desc: '本课程成绩 62 分，处于班级中下游' },
      { name: '学习态度', score: 52, desc: '出勤率 80%，作业提交率 68%' },
      { name: '学习进步', score: 55, desc: '成绩与考勤同时出现异常波动' },
      { name: '知识掌握', score: 57, desc: '核心知识点平均掌握度 57%' },
      { name: '课堂参与', score: 50, desc: '课堂问答正确率 52%，低于班级均值' },
    ],
    strongPoints: 'HTTP协议 (50%)',
    weakPoints: '路由算法 (58%)、网络安全 (55%)、TCP/IP协议 (60%)',
  },
]

/** 获取教师授课列表 */
export function getCoursesByTeacher(teacherId: number, semesterId?: number): Course[] {
  return courses.filter((c) => {
    if (c.teacherId !== teacherId) return false
    if (semesterId && c.semesterId !== semesterId) return false
    return true
  })
}

/**
 * 看板筛选维度关联：
 * 学期(semesterCode) → 专业/年级/课程/班级
 * 专业(majorId)      → courseMajorRelations + ClassInfo.majorId
 * 年级(grade)        → ClassInfo.grade
 * 课程(courseId)     → courseClassRelations + courseMajorRelations
 * 班级(classId)      → courseClassRelations
 */
export interface DashboardFilterQuery {
  semesterCode: string
  majorId?: number
  grade?: string
  courseId?: number
  classId?: number
  deptId?: number
  teacherId?: number
}

/** 学期编码转 ID */
export function resolveSemesterId(semesterCode: string): number {
  return semesters.find((s) => s.semesterCode === semesterCode)?.id ?? 1
}

/** 获取某学期某课程的关联班级 ID */
function getRelationClassIds(semesterId: number, filters: {
  courseId?: number
  majorId?: number
  grade?: string
  deptId?: number
  teacherId?: number
}): number[] {
  let relations = courseClassRelations.filter((r) => r.semesterId === semesterId)

  if (filters.courseId) {
    relations = relations.filter((r) => r.courseId === filters.courseId)
  }

  if (filters.teacherId) {
    const teacherCourseIds = courses
      .filter((c) => c.teacherId === filters.teacherId && c.semesterId === semesterId)
      .map((c) => c.id)
    relations = relations.filter((r) => teacherCourseIds.includes(r.courseId))
  }

  return relations
    .map((r) => r.classId)
    .filter((classId) => {
      const cls = classes.find((c) => c.id === classId)
      if (!cls) return false
      if (filters.deptId && cls.deptId !== filters.deptId) return false
      if (filters.majorId && cls.majorId !== filters.majorId) return false
      if (filters.grade && cls.grade !== filters.grade) return false
      return true
    })
}

/** 根据专业/年级获取可用班级 ID 集合 */
function getClassIdsByMajorGrade(majorId?: number, grade?: string, deptId?: number): number[] {
  return classes
    .filter((c) => {
      if (deptId && c.deptId !== deptId) return false
      if (majorId && c.majorId !== majorId) return false
      if (grade && c.grade !== grade) return false
      return true
    })
    .map((c) => c.id)
}

/** 看板：按学期/年级/课程/教师筛选可选专业 */
export function getDashboardMajors(params: DashboardFilterQuery): Major[] {
  const semesterId = resolveSemesterId(params.semesterCode)
  const classIds = new Set(getRelationClassIds(semesterId, params))
  const majorIds = new Set(
    classes
      .filter((c) => classIds.has(c.id))
      .map((c) => c.majorId),
  )
  return majors.filter((m) => {
    if (params.deptId && m.deptId !== params.deptId) return false
    return majorIds.has(m.id)
  })
}

/** 看板：按学期/专业/课程/教师筛选可选年级 */
export function getDashboardGrades(params: DashboardFilterQuery): string[] {
  const semesterId = resolveSemesterId(params.semesterCode)
  const classIds = getRelationClassIds(semesterId, params)
  const grades = new Set(
    classes
      .filter((c) => classIds.includes(c.id))
      .map((c) => c.grade),
  )
  return Array.from(grades).sort((a, b) => Number(b) - Number(a))
}

/** 看板：按学期/专业/教师筛选可选课程 */
export function getDashboardCourses(params: DashboardFilterQuery): Course[] {
  const semesterId = resolveSemesterId(params.semesterCode)
  let result = courses.filter((c) => {
    if (c.semesterId !== semesterId) return false
    if (params.deptId && c.deptId !== params.deptId) return false
    if (params.teacherId && c.teacherId !== params.teacherId) return false
    return true
  })

  if (params.majorId) {
    const majorCourseIds = new Set(
      courseMajorRelations
        .filter((r) => r.semesterId === semesterId && r.majorId === params.majorId)
        .map((r) => r.courseId),
    )
    result = result.filter((c) => majorCourseIds.has(c.id))
  }

  if (params.grade) {
    const classIds = getClassIdsByMajorGrade(params.majorId, params.grade, params.deptId)
    const courseIds = new Set(
      courseClassRelations
        .filter((r) => r.semesterId === semesterId && classIds.includes(r.classId))
        .map((r) => r.courseId),
    )
    result = result.filter((c) => courseIds.has(c.id))
  }

  return result
}

/** 看板：按学期/课程/专业/年级/教师筛选可选班级 */
export function getDashboardClasses(params: DashboardFilterQuery): ClassInfo[] {
  const semesterId = resolveSemesterId(params.semesterCode)
  let classIds = getClassIdsByMajorGrade(params.majorId, params.grade, params.deptId)

  if (params.courseId) {
    const course = courses.find((c) => c.id === params.courseId)
    if (!course || course.semesterId !== semesterId) {
      return []
    }
    const courseClassIds = courseClassRelations
      .filter((r) => r.courseId === params.courseId && r.semesterId === semesterId)
      .map((r) => r.classId)
    classIds = classIds.filter((id) => courseClassIds.includes(id))
  } else {
    const semesterClassIds = new Set(
      courseClassRelations
        .filter((r) => r.semesterId === semesterId)
        .map((r) => r.classId),
    )
    classIds = classIds.filter((id) => semesterClassIds.has(id))
  }

  if (params.teacherId) {
    const teacherCourseIds = courses
      .filter((c) => c.teacherId === params.teacherId && c.semesterId === semesterId)
      .map((c) => c.id)
    const teacherClassIds = new Set(
      courseClassRelations
        .filter((r) => r.semesterId === semesterId && teacherCourseIds.includes(r.courseId))
        .map((r) => r.classId),
    )
    classIds = classIds.filter((id) => teacherClassIds.has(id))
  }

  return classes.filter((c) => classIds.includes(c.id))
}

/** 构建某课程某班级的知识点热力图数据 */
export function buildCourseClassHeatmap(courseId: number, classId: number): {
  knowledgePoints: string[]
  students: string[]
  data: number[][]
} {
  const knowledgePoints = getKnowledgePointsByCourse(courseId)
  const studentsInClass = getStudentsInCourseClass(courseId, classId)
  const data: number[][] = []

  studentsInClass.forEach((student, studentIdx) => {
    const mastery = getStudentMastery(student.id, courseId) ?? knowledgePoints.map(() => 0)
    knowledgePoints.forEach((_, kpIdx) => {
      data.push([kpIdx, studentIdx, mastery[kpIdx] ?? 0])
    })
  })

  return {
    knowledgePoints,
    students: studentsInClass.map((s) => s.studentName),
    data,
  }
}

/** 构建学生个人知识点热力图（含班级均值对比） */
export function buildPersonalKnowledgeHeatmap(
  studentId: number,
  courseId: number,
  classId?: number,
): {
  knowledgePoints: string[]
  students: string[]
  data: number[][]
  classAvgByKp: number[]
} {
  const student = students.find((s) => s.id === studentId)
  const resolvedClassId = classId ?? student?.classId
  const knowledgePoints = getKnowledgePointsByCourse(courseId)

  if (!student || !resolvedClassId) {
    return { knowledgePoints, students: [], data: [], classAvgByKp: [] }
  }

  const classHeatmap = buildCourseClassHeatmap(courseId, resolvedClassId)
  const studentIdx = classHeatmap.students.indexOf(student.studentName)
  const classAvgByKp = knowledgePoints.map((_, kpIdx) => {
    const values = classHeatmap.data.filter((d) => d[0] === kpIdx).map((d) => d[2]!)
    if (!values.length) return 0
    return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10
  })

  if (studentIdx < 0) {
    const mastery = getStudentMastery(studentId, courseId) ?? knowledgePoints.map(() => 0)
    const data = mastery.map((val, kpIdx) => [kpIdx, 0, val] as number[])
    return { knowledgePoints, students: [student.studentName], data, classAvgByKp }
  }

  const data = classHeatmap.data
    .filter((d) => d[1] === studentIdx)
    .map((d) => [d[0]!, 0, d[2]!] as number[])

  return {
    knowledgePoints,
    students: [student.studentName],
    data,
    classAvgByKp,
  }
}

/** 根据掌握度数据生成学情画像（无预设 profile 时的兜底） */
export function buildStudentProfileFromMastery(
  studentId: number,
  courseId: number,
): (StudentProfileData & { courseId: number }) | null {
  const student = students.find((s) => s.id === studentId)
  const course = courses.find((c) => c.id === courseId)
  const classInfo = classes.find((c) => c.id === student?.classId)
  const mastery = getStudentMastery(studentId, courseId)
  const kps = getKnowledgePointsByCourse(courseId)

  if (!student || !course || !mastery?.length) return null

  const avg = Math.round(mastery.reduce((a, b) => a + b, 0) / mastery.length)
  const paired = kps.map((name, i) => ({ name, score: mastery[i] ?? 0 }))
  const sorted = [...paired].sort((a, b) => b.score - a.score)
  const strong = sorted.filter((p) => p.score >= 80).slice(0, 3)
  const weak = sorted.filter((p) => p.score < 75).slice(-3).reverse()

  return {
    studentId,
    courseId,
    studentNo: student.studentNo,
    studentName: student.studentName,
    className: classInfo?.className ?? '',
    courseName: course.courseName,
    tags: avg >= 85 ? ['成绩优秀'] : avg >= 70 ? ['态度良好'] : ['需加强练习'],
    radarValues: [
      Math.min(100, avg + 5),
      Math.min(100, avg),
      Math.min(100, avg - 3),
      avg,
      Math.min(100, avg - 5),
    ],
    dimensionScores: [
      { name: '学业水平', score: Math.min(100, avg + 5), desc: `本课程核心知识点平均掌握度 ${avg}%` },
      { name: '学习态度', score: Math.min(100, avg), desc: '基于考勤与作业提交情况综合评估' },
      { name: '学习进步', score: Math.min(100, avg - 3), desc: '近三次测验/练习得分变化趋势' },
      { name: '知识掌握', score: avg, desc: `本课程 ${kps.length} 个知识点平均掌握 ${avg}%` },
      { name: '课堂参与', score: Math.min(100, avg - 5), desc: '课堂问答与互动参与度' },
    ],
    strongPoints: strong.length
      ? strong.map((p) => `${p.name} (${p.score}%)`).join('、')
      : '暂无显著优势项',
    weakPoints: weak.length
      ? weak.map((p) => `${p.name} (${p.score}%)`).join('、')
      : '暂无显著薄弱项',
  }
}

/** 查找学情画像（优先精确匹配 studentId + courseId） */
export function findStudentProfile(
  studentId: number,
  courseId?: number,
): (StudentProfileData & { courseId: number }) | null {
  if (courseId) {
    const exact = studentProfiles.find((p) => p.studentId === studentId && p.courseId === courseId)
    if (exact) return exact
    return buildStudentProfileFromMastery(studentId, courseId)
  }
  return studentProfiles.find((p) => p.studentId === studentId) ?? null
}

/** 看板按年级/学期的统计系数 */
export const dashboardFilterFactors = {
  grade: {
    '': 1,
    '2024': 0.55,
    '2023': 0.25,
    '2022': 0.15,
    '2025': 0.05,
  } as Record<string, number>,
  semester: {
    '2025-2026-1': 1,
    '2024-2025-2': 0.92,
    '2024-2025-1': 0.85,
  } as Record<string, number>,
}
