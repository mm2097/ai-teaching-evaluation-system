/**
 * 模拟用户账号数据
 * 演示环境使用，正式环境由后端接口提供
 */
import type { UserInfo } from '@/types'

/** 演示账号列表 */
export const mockUsers: (UserInfo & { password: string })[] = [
  {
    id: 1,
    username: 'admin',
    password: '123456',
    name: '张管理',
    role: 'admin',
    department: '信息中心',
  },
  {
    id: 2,
    username: 'manager',
    password: '123456',
    name: '李教务',
    role: 'manager',
    department: '教务处',
  },
  {
    id: 3,
    username: 'teacher',
    password: '123456',
    name: '王教授',
    role: 'teacher',
    department: '计算机学院',
  },
  {
    id: 4,
    username: 'student',
    password: '123456',
    name: '陈同学',
    role: 'student',
    department: '计算机学院',
  },
]

/** 看板统计数据 */
export const dashboardStats = {
  studentCount: 2846,
  courseCount: 186,
  teacherCount: 128,
  passRate: 87.6,
  excellentRate: 23.4,
  attendanceRate: 92.3,
  warningCount: 47,
  excellentTeacherCount: 35,
  excellentCourseCount: 28,
}

/** 学期选项 */
export const semesterOptions = [
  { label: '2025-2026 学年第一学期', value: '2025-1' },
  { label: '2024-2025 学年第二学期', value: '2024-2' },
  { label: '2024-2025 学年第一学期', value: '2024-1' },
]

/** 院系选项 */
export const departmentOptions = [
  { label: '全部院系', value: '' },
  { label: '计算机学院', value: 'cs' },
  { label: '数学学院', value: 'math' },
  { label: '外国语学院', value: 'lang' },
  { label: '经济管理学院', value: 'econ' },
]

/** 年级选项 */
export const gradeOptions = [
  { label: '全部年级', value: '' },
  { label: '2022级', value: '2022' },
  { label: '2023级', value: '2023' },
  { label: '2024级', value: '2024' },
  { label: '2025级', value: '2025' },
]

/** 成绩趋势模拟数据 */
export const gradeTrendData = {
  months: ['9月', '10月', '11月', '12月', '1月', '2月'],
  avgScore: [72, 74, 76, 75, 78, 80],
  passRate: [82, 84, 85, 83, 87, 89],
  maxScore: [98, 97, 99, 96, 98, 100],
  minScore: [45, 48, 50, 47, 52, 55],
}

/** 学情画像雷达图数据 */
export const studentProfileRadar = {
  indicators: [
    { name: '学业水平', max: 100 },
    { name: '学习态度', max: 100 },
    { name: '学习进步', max: 100 },
    { name: '知识掌握', max: 100 },
    { name: '课堂参与', max: 100 },
  ],
  values: [85, 72, 88, 76, 80],
}

/** 学情标签 */
export const studentTags = ['成绩优秀', '进步明显', '考勤良好', '作业积极']

/** 知识点掌握度热力图数据 */
export const knowledgeHeatmap = {
  knowledgePoints: ['变量与表达式', '控制结构', '函数定义', '数组操作', '面向对象', '文件IO', '异常处理', '数据结构'],
  students: ['陈同学', '刘同学', '赵同学', '孙同学', '周同学'],
  data: [
    [0, 0, 92], [0, 1, 85], [0, 2, 78], [0, 3, 90], [0, 4, 65], [0, 5, 88], [0, 6, 72], [0, 7, 80],
    [1, 0, 78], [1, 1, 82], [1, 2, 70], [1, 3, 75], [1, 4, 60], [1, 5, 68], [1, 6, 55], [1, 7, 72],
    [2, 0, 88], [2, 1, 90], [2, 2, 85], [2, 3, 92], [2, 4, 78], [2, 5, 82], [2, 6, 70], [2, 7, 85],
    [3, 0, 65], [3, 1, 70], [3, 2, 58], [3, 3, 62], [3, 4, 45], [3, 5, 55], [3, 6, 48], [3, 7, 60],
    [4, 0, 95], [4, 1, 92], [4, 2, 88], [4, 3, 96], [4, 4, 82], [4, 5, 90], [4, 6, 85], [4, 7, 88],
  ],
}

/** 预警记录模拟数据 */
export const warningRecords = [
  { id: 1, studentId: '2024001001', studentName: '张三', className: '计科2401', type: '成绩下滑', level: '高' as const, reason: '连续三次考试成绩下降超过15分', warningTime: '2026-03-15' },
  { id: 2, studentId: '2024001023', studentName: '李四', className: '计科2401', type: '缺勤异常', level: '中' as const, reason: '本月缺勤率达到25%', warningTime: '2026-03-14' },
  { id: 3, studentId: '2024001045', studentName: '王五', className: '计科2402', type: '作业未交', level: '高' as const, reason: '连续4次作业未提交', warningTime: '2026-03-13' },
  { id: 4, studentId: '2024001067', studentName: '赵六', className: '软工2401', type: '成绩下滑', level: '低' as const, reason: '最近一次考试成绩下降8分', warningTime: '2026-03-12' },
  { id: 5, studentId: '2024001089', studentName: '钱七', className: '软工2401', type: '综合异常', level: '中' as const, reason: '考勤与成绩同时出现异常', warningTime: '2026-03-11' },
]

/** 教师评价模拟数据 */
export const teacherEvalList = [
  { id: 1, targetName: '王教授', targetType: '教师', totalScore: 92.5, grade: '优秀' as const, dimensions: [{ name: '教学效果', score: 95, weight: 35 }, { name: '教学投入', score: 90, weight: 25 }, { name: '学生反馈', score: 93, weight: 25 }, { name: '教学规范', score: 91, weight: 15 }], rank: 1 },
  { id: 2, targetName: '李副教授', targetType: '教师', totalScore: 86.2, grade: '良好' as const, dimensions: [{ name: '教学效果', score: 85, weight: 35 }, { name: '教学投入', score: 88, weight: 25 }, { name: '学生反馈', score: 86, weight: 25 }, { name: '教学规范', score: 87, weight: 15 }], rank: 2 },
  { id: 3, targetName: '张讲师', targetType: '教师', totalScore: 78.6, grade: '中等' as const, dimensions: [{ name: '教学效果', score: 76, weight: 35 }, { name: '教学投入', weight: 25, score: 80 }, { name: '学生反馈', score: 78, weight: 25 }, { name: '教学规范', score: 82, weight: 15 }], rank: 3 },
]

/** 学生评价模拟数据 */
export const studentEvalList = [
  { id: 1, targetName: '陈同学', targetType: '学生', totalScore: 88.5, grade: '优秀' as const, dimensions: [{ name: '学业成绩', score: 90, weight: 40 }, { name: '学习态度', score: 85, weight: 25 }, { name: '学习进步', score: 92, weight: 20 }, { name: '知识掌握', score: 86, weight: 15 }] },
  { id: 2, targetName: '刘同学', targetType: '学生', totalScore: 72.3, grade: '中等' as const, dimensions: [{ name: '学业成绩', score: 70, weight: 40 }, { name: '学习态度', score: 75, weight: 25 }, { name: '学习进步', score: 68, weight: 20 }, { name: '知识掌握', score: 78, weight: 15 }] },
]

/** 课程评价模拟数据 */
export const courseEvalList = [
  { id: 1, targetName: '数据结构', targetType: '课程', totalScore: 91.2, grade: '优秀' as const, dimensions: [{ name: '考核质量', score: 92, weight: 30 }, { name: '学生参与', score: 88, weight: 25 }, { name: '成绩合理', score: 93, weight: 25 }, { name: '教学效果', score: 90, weight: 20 }], rank: 1 },
  { id: 2, targetName: '操作系统', targetType: '课程', totalScore: 84.6, grade: '良好' as const, dimensions: [{ name: '考核质量', score: 85, weight: 30 }, { name: '学生参与', score: 82, weight: 25 }, { name: '成绩合理', score: 86, weight: 25 }, { name: '教学效果', score: 84, weight: 20 }], rank: 2 },
]

/** 教学数据管理模拟列表 */
export const teachingDataList = [
  { id: 1, studentId: '2024001001', studentName: '陈同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-1', score: 92, attendance: '正常', homework: '已提交', dataType: '成绩' },
  { id: 2, studentId: '2024001002', studentName: '刘同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-1', score: 78, attendance: '迟到', homework: '已提交', dataType: '成绩' },
  { id: 3, studentId: '2024001003', studentName: '赵同学', courseId: 'CS102', courseName: '操作系统', semester: '2025-1', score: 85, attendance: '正常', homework: '未提交', dataType: '成绩' },
  { id: 4, studentId: '2024001004', studentName: '孙同学', courseId: 'CS103', courseName: '计算机网络', semester: '2025-1', score: 68, attendance: '缺勤', homework: '已提交', dataType: '成绩' },
  { id: 5, studentId: '2024001005', studentName: '周同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-1', score: 95, attendance: '正常', homework: '已提交', dataType: '成绩' },
]

/** 系统用户列表 */
export const systemUserList = [
  { id: 1, username: 'admin', name: '张管理', role: 'admin', department: '信息中心', status: true, createTime: '2025-09-01' },
  { id: 2, username: 'manager', name: '李教务', role: 'manager', department: '教务处', status: true, createTime: '2025-09-01' },
  { id: 3, username: 'teacher', name: '王教授', role: 'teacher', department: '计算机学院', status: true, createTime: '2025-09-05' },
  { id: 4, username: 'student', name: '陈同学', role: 'student', department: '计算机学院', status: true, createTime: '2025-09-10' },
  { id: 5, username: 'teacher2', name: '李副教授', role: 'teacher', department: '数学学院', status: false, createTime: '2025-10-01' },
]

/** 操作日志列表 */
export const systemLogList = [
  { id: 1, username: 'admin', operation: '登录系统', type: '登录', ip: '192.168.1.100', time: '2026-03-15 08:30:00' },
  { id: 2, username: 'admin', operation: '导入成绩数据', type: '数据操作', ip: '192.168.1.100', time: '2026-03-15 09:15:00' },
  { id: 3, username: 'manager', operation: '查看教学评价报告', type: '查询', ip: '192.168.1.101', time: '2026-03-15 10:00:00' },
  { id: 4, username: 'teacher', operation: '导出班级学情报告', type: '导出', ip: '192.168.1.102', time: '2026-03-14 16:30:00' },
  { id: 5, username: 'admin', operation: '修改预警阈值配置', type: '配置修改', ip: '192.168.1.100', time: '2026-03-14 14:20:00' },
]

/** 评价指标配置 */
export const evalIndicatorConfig = [
  { id: 1, name: '教学效果', dimension: '教师评价', weight: 35, rule: '基于成绩提升度与及格率加权计算' },
  { id: 2, name: '教学投入', dimension: '教师评价', weight: 25, rule: '基于作业批改与答疑频次统计' },
  { id: 3, name: '学生反馈', dimension: '教师评价', weight: 25, rule: '基于评教问卷得分' },
  { id: 4, name: '教学规范', dimension: '教师评价', weight: 15, rule: '基于教学文档与考勤规范检查' },
  { id: 5, name: '学业成绩', dimension: '学生评价', weight: 40, rule: '基于各科目加权平均分' },
  { id: 6, name: '学习态度', dimension: '学生评价', weight: 25, rule: '基于考勤率与作业提交率' },
]
