/**
 * 系统全局 TypeScript 类型定义
 */

/** 用户角色枚举 */
export type UserRole = 'admin' | 'teacher' | 'student'

/** 分析/评价对象类型（对应 t_analysis_result.target_type） */
export type TargetType = 'student' | 'class'

/** 数据导入类型（对应 sys_data_import_log.import_type） */
export type ImportType = 'student' | 'course' | 'score' | 'attendance' | 'assignment'

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  name: string
  role: UserRole
  department: string
  deptId?: number
  studentId?: number
  studentNo?: string
  teacherId?: number
  classId?: number
  avatar?: string
}

/** 系统用户(用户管理页面用) */
export interface SystemUser {
  id: number
  username: string
  name: string
  role: UserRole
  department: string
  status: boolean
  createTime: string
}
/** 院系 */
export interface Department {
  id: number
  deptCode: string
  deptName: string
}

/** 专业 */
export interface Major {
  id: number
  majorCode: string
  majorName: string
  deptId: number
}

/** 班级 */
export interface ClassInfo {
  id: number
  classCode: string
  className: string
  majorId: number
  deptId: number
  grade: string
}

/** 学期 */
export interface Semester {
  id: number
  semesterCode: string
  semesterName: string
  isCurrent: boolean
}

/** 学生 */
export interface Student {
  id: number
  studentNo: string
  studentName: string
  classId: number
  majorId: number
  deptId: number
  grade: string
}

/** 教师 */
export interface Teacher {
  id: number
  teacherNo: string
  teacherName: string
  deptId: number
}

/** 课程 */
export interface Course {
  id: number
  courseNo: string
  courseName: string
  deptId: number
  teacherId: number
  semesterId: number
}

/** 数据导入日志（对应 sys_data_import_log） */
export interface ImportLog {
  id: number
  importType: ImportType
  dataSource: 'excel' | 'txt' | 'database'
  fileName: string
  totalCount: number
  successCount: number
  failCount: number
  operatorName: string
  importTime: string
  status: 0 | 1 | 2
}

/** 教学数据记录 */
export interface TeachingDataRecord {
  id: number
  studentId: string
  studentName: string
  courseId: string
  courseName: string
  semester: string
  semesterId: number
  deptId: number
  majorId: number
  classId: number
  score?: number
  attendance?: string
  homework?: string
  dataType: 'score' | 'attendance' | 'assignment'
  importLogId?: number
  sourceFileName?: string
}

/** 分析查询参数 */
export interface AnalysisQuery {
  analysisType?: string
  targetType?: TargetType
  targetId?: number
  courseId?: number
  semesterId?: number
  deptId?: number
  majorId?: number
  classId?: number
  keyword?: string
}

/** 学情画像数据（单课程维度） */
export interface StudentProfileData {
  studentId: number
  studentNo: string
  studentName: string
  className: string
  courseName: string
  tags: string[]
  radarValues: number[]
  dimensionScores: { name: string; score: number; desc: string }[]
  strongPoints: string
  weakPoints: string
}

/** 数据模板类型 */
export type DataTemplateType = 'score' | 'attendance' | 'assignment' | 'qa'

/** 文件校验错误 */
export interface ValidationError {
  row: number
  column: string
  message: string
}

/** 题目类型 */
export type QuestionType = 'single' | 'multiple' | 'fill' | 'short'

/** AI 练习题 */
export interface QuizQuestion {
  id: number
  type: QuestionType
  content: string
  options?: string[]
  answer: string | string[]
  knowledgePoint: string
  score: number
}

/** 练习发布记录 */
export interface QuizAssignment {
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
  status: 'draft' | 'published' | 'closed'
  publishTime?: string
  deadline?: string
  questions: QuizQuestion[]
}

/** 学生答题记录 */
export interface QuizSubmission {
  id: number
  assignmentId: number
  studentId: number
  studentName: string
  score: number
  totalScore: number
  submitTime: string
  answers: Record<number, string | string[]>
}

/** 角色中文名称映射 */
export const RoleLabels: Record<UserRole, string> = {
  admin: '系统管理员',
  teacher: '任课教师',
  student: '学生用户',
}

/** 菜单项定义 */
export interface MenuItem {
  path: string
  title: string
  icon: string
  roles?: UserRole[]
  children?: MenuItem[]
}

/** API 统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页查询参数 */
export interface PageQuery {
  page: number
  pageSize: number
  keyword?: string
}

/** 分页响应 */
export interface PageResult<T> {
  list: T[]
  total: number
}

/** 统计数据卡片 */
export interface StatItem {
  title: string
  value: number | string
  unit?: string
  trend?: number
  icon: string
  color: string
}

/** 预警记录 */
export interface WarningRecord {
  id: number
  studentId: string
  studentName: string
  className: string
  classId: number
  deptId: number
  courseId?: number
  courseName?: string
  semesterId: number
  type: string
  level: '高' | '中' | '低'
  reason: string
  warningTime: string
  status: 0 | 1 | 2 | 3
}

/** 评价等级 */
export type EvalGrade = '优秀' | '良好' | '中等' | '合格' | '不合格'

/** 评价结果 */
export interface EvalResult {
  id: number
  targetName: string
  targetType: string
  totalScore: number
  grade: EvalGrade
  dimensions: { name: string; score: number; weight: number }[]
  rank?: number
}
