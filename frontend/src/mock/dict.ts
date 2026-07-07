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

export const classes: ClassInfo[] = [
  { id: 1, classCode: 'CS2401', className: '计科2401', majorId: 1, deptId: 1, grade: '2024' },
  { id: 2, classCode: 'CS2402', className: '计科2402', majorId: 1, deptId: 1, grade: '2024' },
  { id: 3, classCode: 'SE2401', className: '软工2401', majorId: 2, deptId: 1, grade: '2024' },
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

export const courses: Course[] = [
  { id: 1, courseNo: 'CS101', courseName: '数据结构', deptId: 1, teacherId: 1, semesterId: 1 },
  { id: 2, courseNo: 'CS102', courseName: '操作系统', deptId: 1, teacherId: 1, semesterId: 1 },
  { id: 3, courseNo: 'CS103', courseName: '计算机网络', deptId: 1, teacherId: 3, semesterId: 1 },
  { id: 4, courseNo: 'CS104', courseName: 'Java程序设计', deptId: 1, teacherId: 1, semesterId: 1 },
  { id: 5, courseNo: 'CS105', courseName: '数据库原理', deptId: 1, teacherId: 3, semesterId: 1 },
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
]

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
export const studentProfiles: StudentProfileData[] = [
  {
    studentId: 1,
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
      { name: '知识掌握', score: 76, desc: '核心知识点平均掌握度 76%' },
      { name: '课堂参与', score: 80, desc: '课堂问答正确率 85%，高于班级均值' },
    ],
    strongPoints: '链表操作 (95%)、二叉树遍历 (92%)、栈与队列 (88%)',
    weakPoints: '面向对象 (65%)、异常处理 (72%)',
  },
  {
    studentId: 2,
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
    strongPoints: '控制结构 (82%)、数组操作 (80%)',
    weakPoints: '面向对象 (58%)、文件IO (62%)、异常处理 (65%)',
  },
  {
    studentId: 3,
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
    strongPoints: '链表操作 (98%)、二叉树遍历 (95%)、栈与队列 (90%)',
    weakPoints: '暂无显著薄弱项',
  },
]

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
