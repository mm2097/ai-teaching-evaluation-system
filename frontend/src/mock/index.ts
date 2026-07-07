/**
 * 模拟用户账号与业务数据
 * 演示环境使用，正式环境由后端接口提供
 */
import type { ImportLog, TeachingDataRecord, UserInfo, WarningRecord } from '@/types'
export * from './dict'

/** 演示账号列表 */
export const mockUsers: (UserInfo & { password: string })[] = [
  {
    id: 1,
    username: 'admin',
    password: '123456',
    name: '张管理',
    role: 'admin',
    department: '信息中心',
    deptId: 1,
  },
  {
    id: 3,
    username: 'teacher',
    password: '123456',
    name: '王教授',
    role: 'teacher',
    department: '计算机学院',
    deptId: 1,
    teacherId: 1,
  },
  {
    id: 4,
    username: 'student',
    password: '123456',
    name: '陈同学',
    role: 'student',
    department: '计算机学院',
    deptId: 1,
    studentId: 1,
    studentNo: '2024001001',
    classId: 1,
  },
]

/** 看板基础统计数据（计算机学院） */
export const dashboardStats = {
  studentCount: 126,
  courseCount: 5,
  teacherCount: 2,
  passRate: 87.6,
  excellentRate: 23.4,
  attendanceRate: 92.3,
  warningCount: 12,
}

/** 成绩趋势模拟数据 */
export const gradeTrendData = {
  months: ['9月', '10月', '11月', '12月', '1月', '2月'],
  avgScore: [72, 74, 76, 75, 78, 80],
  passRate: [82, 84, 85, 83, 87, 89],
  maxScore: [98, 97, 99, 96, 98, 100],
  minScore: [45, 48, 50, 47, 52, 55],
}

/** 学情画像雷达图指标 */
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
export const warningRecords: WarningRecord[] = [
  { id: 1, studentId: '2024001001', studentName: '张三', className: '计科2401', classId: 1, deptId: 1, courseId: 1, courseName: '数据结构', semesterId: 1, type: '成绩下滑', level: '高', reason: '连续三次考试成绩下降超过15分', warningTime: '2026-03-15', status: 0 },
  { id: 2, studentId: '2024001023', studentName: '李四', className: '计科2401', classId: 1, deptId: 1, courseId: 2, courseName: '操作系统', semesterId: 1, type: '缺勤异常', level: '中', reason: '本月缺勤率达到25%', warningTime: '2026-03-14', status: 0 },
  { id: 3, studentId: '2024001045', studentName: '王五', className: '计科2402', classId: 2, deptId: 1, courseId: 1, courseName: '数据结构', semesterId: 1, type: '作业未交', level: '高', reason: '连续4次作业未提交', warningTime: '2026-03-13', status: 1 },
  { id: 4, studentId: '2024001067', studentName: '赵六', className: '软工2401', classId: 3, deptId: 1, semesterId: 1, type: '成绩下滑', level: '低', reason: '最近一次考试成绩下降8分', warningTime: '2026-03-12', status: 0 },
  { id: 5, studentId: '2024001089', studentName: '钱七', className: '软工2401', classId: 3, deptId: 1, courseId: 3, courseName: '计算机网络', semesterId: 1, type: '综合异常', level: '中', reason: '考勤与成绩同时出现异常', warningTime: '2026-03-11', status: 2 },
]

/** 教师评价模拟数据 */
export const teacherEvalList = [
  { id: 1, targetName: '王教授', targetType: 'teacher', totalScore: 92.5, grade: '优秀' as const, dimensions: [{ name: '教学效果', score: 95, weight: 35 }, { name: '教学投入', score: 90, weight: 25 }, { name: '学生反馈', score: 93, weight: 25 }, { name: '教学规范', score: 91, weight: 15 }], rank: 1 },
  { id: 2, targetName: '李副教授', targetType: 'teacher', totalScore: 86.2, grade: '良好' as const, dimensions: [{ name: '教学效果', score: 85, weight: 35 }, { name: '教学投入', score: 88, weight: 25 }, { name: '学生反馈', score: 86, weight: 25 }, { name: '教学规范', score: 87, weight: 15 }], rank: 2 },
  { id: 3, targetName: '张讲师', targetType: 'teacher', totalScore: 78.6, grade: '中等' as const, dimensions: [{ name: '教学效果', score: 76, weight: 35 }, { name: '教学投入', weight: 25, score: 80 }, { name: '学生反馈', score: 78, weight: 25 }, { name: '教学规范', score: 82, weight: 15 }], rank: 3 },
]

/** 学生评价模拟数据 */
export const studentEvalList = [
  { id: 1, targetName: '陈同学', targetType: 'student', totalScore: 88.5, grade: '优秀' as const, dimensions: [{ name: '学业成绩', score: 90, weight: 40 }, { name: '学习态度', score: 85, weight: 25 }, { name: '学习进步', score: 92, weight: 20 }, { name: '知识掌握', score: 86, weight: 15 }] },
  { id: 2, targetName: '刘同学', targetType: 'student', totalScore: 72.3, grade: '中等' as const, dimensions: [{ name: '学业成绩', score: 70, weight: 40 }, { name: '学习态度', score: 75, weight: 25 }, { name: '学习进步', score: 68, weight: 20 }, { name: '知识掌握', score: 78, weight: 15 }] },
]

/** 课程评价模拟数据 */
export const courseEvalList = [
  { id: 1, targetName: '数据结构', targetType: 'course', totalScore: 91.2, grade: '优秀' as const, dimensions: [{ name: '考核质量', score: 92, weight: 30 }, { name: '学生参与', score: 88, weight: 25 }, { name: '成绩合理', score: 93, weight: 25 }, { name: '教学效果', score: 90, weight: 20 }], rank: 1 },
  { id: 2, targetName: '操作系统', targetType: 'course', totalScore: 84.6, grade: '良好' as const, dimensions: [{ name: '考核质量', score: 85, weight: 30 }, { name: '学生参与', score: 82, weight: 25 }, { name: '成绩合理', score: 86, weight: 25 }, { name: '教学效果', score: 84, weight: 20 }], rank: 2 },
]

/** 数据导入日志 */
export const importLogs: ImportLog[] = [
  { id: 1, importType: 'score', dataSource: 'excel', fileName: '数据结构成绩.xlsx', totalCount: 42, successCount: 42, failCount: 0, operatorName: '王教授', importTime: '2026-03-15 09:15:00', status: 1 },
  { id: 2, importType: 'attendance', dataSource: 'excel', fileName: '计科2401考勤记录.xlsx', totalCount: 520, successCount: 518, failCount: 2, operatorName: '王教授', importTime: '2026-03-14 14:30:00', status: 1 },
  { id: 3, importType: 'assignment', dataSource: 'txt', fileName: '作业提交数据.txt', totalCount: 380, successCount: 375, failCount: 5, operatorName: '王教授', importTime: '2026-03-13 10:00:00', status: 1 },
]

/** 教学数据管理模拟列表 */
export const teachingDataList: TeachingDataRecord[] = [
  { id: 1, studentId: '2024001001', studentName: '陈同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, score: 92, dataType: 'score', importLogId: 1, sourceFileName: '2025春季成绩导入.xlsx' },
  { id: 2, studentId: '2024001002', studentName: '刘同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, score: 78, dataType: 'score', importLogId: 1, sourceFileName: '2025春季成绩导入.xlsx' },
  { id: 3, studentId: '2024001003', studentName: '赵同学', courseId: 'CS102', courseName: '操作系统', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, score: 85, dataType: 'score', importLogId: 1, sourceFileName: '2025春季成绩导入.xlsx' },
  { id: 4, studentId: '2024001004', studentName: '孙同学', courseId: 'CS103', courseName: '计算机网络', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 2, score: 68, dataType: 'score', importLogId: 1, sourceFileName: '2025春季成绩导入.xlsx' },
  { id: 5, studentId: '2024001005', studentName: '周同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, score: 95, dataType: 'score', importLogId: 1, sourceFileName: '2025春季成绩导入.xlsx' },
  { id: 6, studentId: '2024001001', studentName: '陈同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, attendance: '正常', dataType: 'attendance', importLogId: 2, sourceFileName: '计科2401考勤记录.xlsx' },
  { id: 7, studentId: '2024001002', studentName: '刘同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, attendance: '迟到', dataType: 'attendance', importLogId: 2, sourceFileName: '计科2401考勤记录.xlsx' },
  { id: 8, studentId: '2024001004', studentName: '孙同学', courseId: 'CS103', courseName: '计算机网络', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 2, attendance: '缺勤', dataType: 'attendance', importLogId: 2, sourceFileName: '计科2401考勤记录.xlsx' },
  { id: 9, studentId: '2024001001', studentName: '陈同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, homework: '已提交', dataType: 'assignment', importLogId: 3, sourceFileName: '作业提交数据.txt' },
  { id: 10, studentId: '2024001003', studentName: '赵同学', courseId: 'CS102', courseName: '操作系统', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, homework: '未提交', dataType: 'assignment', importLogId: 3, sourceFileName: '作业提交数据.txt' },
  { id: 11, studentId: '2024001001', studentName: '陈同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, attendance: '正常', dataType: 'attendance', sourceFileName: '课堂问答记录.xlsx' },
  { id: 12, studentId: '2024001002', studentName: '刘同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, score: 85, dataType: 'score', sourceFileName: '课堂问答记录.xlsx' },
  { id: 13, studentId: '2024001005', studentName: '周同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, attendance: '正常', dataType: 'attendance', sourceFileName: '课堂问答记录.xlsx' },
  { id: 14, studentId: '2024001003', studentName: '赵同学', courseId: 'CS101', courseName: '数据结构', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 1, homework: '已提交', dataType: 'assignment', sourceFileName: '链表实现作业.xlsx' },
  { id: 15, studentId: '2024001004', studentName: '孙同学', courseId: 'CS103', courseName: '计算机网络', semester: '2025-2026-1', semesterId: 1, deptId: 1, majorId: 1, classId: 2, score: 72, dataType: 'score', sourceFileName: 'TCP协议测验.xlsx' },
]

/** 系统用户列表 */
export const systemUserList = [
  { id: 1, username: 'admin', name: '张管理', role: 'admin', department: '信息中心', status: true, createTime: '2025-09-01' },
  { id: 3, username: 'teacher', name: '王教授', role: 'teacher', department: '计算机学院', status: true, createTime: '2025-09-05' },
  { id: 4, username: 'student', name: '陈同学', role: 'student', department: '计算机学院', status: true, createTime: '2025-09-10' },
  { id: 5, username: 'teacher2', name: '张讲师', role: 'teacher', department: '计算机学院', status: true, createTime: '2025-10-01' },
]

/** 操作日志列表 */
export const systemLogList = [
  { id: 1, username: 'admin', operation: '登录系统', type: '登录', ip: '192.168.1.100', time: '2026-03-15 08:30:00' },
  { id: 2, username: 'teacher', operation: '上传成绩数据', type: '数据操作', ip: '192.168.1.102', time: '2026-03-15 09:15:00' },
  { id: 3, username: 'teacher', operation: '发布 AI 练习', type: '数据操作', ip: '192.168.1.102', time: '2026-03-15 10:00:00' },
  { id: 4, username: 'teacher', operation: '导出班级学情报告', type: '导出', ip: '192.168.1.102', time: '2026-03-14 16:30:00' },
  { id: 5, username: 'admin', operation: '修改预警阈值配置', type: '配置修改', ip: '192.168.1.100', time: '2026-03-14 14:20:00' },
  { id: 6, username: 'teacher', operation: '上传考勤数据', type: '数据操作', ip: '192.168.1.102', time: '2026-03-10 11:00:00' },
]

/** 学生学习质量评价指标配置 */
export const evalIndicatorConfig = [
  { id: 1, name: '学业成绩', dimension: '学生评价', weight: 40, rule: '基于本课程加权平均分' },
  { id: 2, name: '学习态度', dimension: '学生评价', weight: 25, rule: '基于考勤率与作业提交率' },
  { id: 3, name: '学习进步', dimension: '学生评价', weight: 20, rule: '基于近三次测验/考试成绩变化' },
  { id: 4, name: '知识掌握', dimension: '学生评价', weight: 15, rule: '基于知识点掌握度与 AI 练习得分' },
]
