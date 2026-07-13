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
  majorName: string
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

/** 姓名/学号关联下拉选项 */
export interface LinkedStudentOption {
  id: number | string
  studentName: string
  studentNo: string
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
  semesterCode: string
  semesterName: string
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
  studentNo?: string
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
  radarIndicators?: { name: string; max: number }[]
  dimensionScores: { name: string; score: number; desc: string }[]
  strongPoints: string
  weakPoints: string
}

/** 班级学情画像数据（单课程维度） */
export interface ClassProfileData {
  classId: number
  className: string
  courseId: number
  courseName: string
  majorName: string
  studentCount: number
  totalProfileScore: number
  passRate: number
  excellentRate: number
  warningCount: number
  tags: string[]
  radarValues: number[]
  dimensionScores: { name: string; score: number; desc: string }[]
  strongPoints: string
  weakPoints: string
  levelDistribution: { label: string; count: number; color: string }[]
  topStudents: { studentId: number; studentName: string; score: number }[]
  attentionStudents: { studentId: number; studentName: string; score: number; reason: string }[]
  aiSummary: string
  teachingSuggestions: string[]
}

/** 成绩趋势数据（班级维度） */
export interface GradeTrendData {
  months: string[]
  avgScore: number[]
  passRate: number[]
  maxScore: number[]
  minScore: number[]
}

/** 成绩趋势数据（学生个人维度） */
export interface StudentGradeTrendData {
  months: string[]
  scores: number[]
  classAvgScores: number[]
}

/** 成绩预测条目 */
export interface GradePredictionItem {
  name: string
  current: number
  predicted: string
  trend: '上升' | '下滑' | '稳定'
  confidence: number
}

/** 学生个人成绩预测 */
export interface StudentGradePrediction {
  studentId: number
  studentName: string
  studentNo: string
  className: string
  courseName: string
  current: number
  predicted: string
  trend: '上升' | '下滑' | '稳定'
  confidence: number
  classRank: number
  classSize: number
  vsClassAvg: number
  analysisItems: { title: string; content: string }[]
  suggestion: string
}

/** 数据模板类型 */
export type DataTemplateType = 'score' | 'attendance' | 'assignment' | 'qa'

/** 文件校验错误 */
export interface ValidationError {
  row: number
  column: string
  message: string
}

/** 题目类型（对齐后端 Exercise.type） */
export type ExerciseType = 'single_choice' | 'multi_choice' | 'judge' | 'fill_blank' | 'short_answer'

/** @deprecated 兼容旧引用，请使用 ExerciseType */
export type QuestionType = ExerciseType

/** 难度等级 */
export type DifficultyLevel = 'easy' | 'medium' | 'hard'

/** 题目状态 */
export type ExerciseStatus = 'draft' | 'published' | 'closed'

/** 题目来源 */
export type ExerciseSource = 'ai' | 'manual' | 'import'

/** 题库查询参数 */
export interface QuestionBankQuery {
  courseId?: number
  knowledgePoint?: string
  type?: ExerciseType
  difficulty?: DifficultyLevel
  source?: ExerciseSource
  status?: ExerciseStatus
  keyword?: string
}

/** 题库统计 */
export interface QuestionBankStats {
  total: number
  byType: Record<ExerciseType, number>
  bySource: Record<ExerciseSource, number>
  byDifficulty: Record<DifficultyLevel, number>
}

/** 内置题库模板 */
export interface QuestionBuiltinTemplate {
  id: string
  name: string
  courseId: number
  courseName: string
  questionCount: number
  description: string
}

/** 题库批量导入结果 */
export interface QuestionImportResult {
  imported: number
  skipped: number
  errors?: { row: number; message: string }[]
}

/** 题目加入题库结果 */
export interface AddToBankResult {
  added: number
  skipped: number
}

/** 选择题选项 */
export interface ExerciseOption {
  key: string
  text: string
}

/** AI 智能辅助教学题（对齐后端 Exercise 模型） */
export interface QuizQuestion {
  id: number
  courseId?: number
  type: ExerciseType
  stem: string
  options?: ExerciseOption[]
  answer: string
  answerList?: string[]
  explanation?: string
  difficulty: DifficultyLevel
  knowledgePoint: string
  score: number
  status?: ExerciseStatus
  source?: ExerciseSource
  batchId?: number
}

/** AI 生成题目请求参数 */
export interface GenerateExerciseParams {
  courseId: number
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  count: number
  difficulty: DifficultyLevel
  extraRequirements?: string
}

/** AI 生成题目响应 */
export interface GenerateExerciseResult {
  batchId: number
  questions: QuizQuestion[]
  meta: {
    model: string
    elapsedMs: number
    tokens: number
  }
}

/** AI 报告生成结果 */
export interface AiReportResult {
  metrics: {
    avgScore: number
    passRate: number
    attendanceRate: number
    warningCount: number
    classSize: number
  }
  weakKnowledgePoints: { name: string; correctRate: number }[]
  trend: string
  conclusion: string
  suggestions: string[]
}

/** Agent 类型 */
export type AgentType = 'qa' | 'exam' | 'tutor'

/** Agent 工具调用记录 */
export interface AgentToolCall {
  id: string
  tool: string
  params: Record<string, unknown>
  result?: unknown
  summary?: string
  status: 'running' | 'done' | 'error'
}

/** Agent 对话消息 */
export interface AgentMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: AgentToolCall[]
  sources?: string[]
  timestamp: number
  streaming?: boolean
}

/** Agent SSE 事件 */
export type AgentStreamEvent =
  | { type: 'thinking' }
  | { type: 'tool_call'; call: AgentToolCall }
  | { type: 'tool_result'; callId: string; result: unknown; summary: string }
  | { type: 'content_delta'; delta: string }
  | { type: 'content_done'; content: string; sources?: string[] }
  | { type: 'error'; message: string }

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
  answers: Record<number, string | string[] | boolean>
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
