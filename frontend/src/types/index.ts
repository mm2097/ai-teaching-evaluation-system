/**
 * 系统全局 TypeScript 类型定义
 */

/** 用户角色枚举 */
export type UserRole = 'admin' | 'manager' | 'teacher' | 'student'

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  name: string
  role: UserRole
  department: string
  avatar?: string
}

/** 角色中文名称映射 */
export const RoleLabels: Record<UserRole, string> = {
  admin: '系统管理员',
  manager: '教学管理者',
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
  type: string
  level: '高' | '中' | '低'
  reason: string
  warningTime: string
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
