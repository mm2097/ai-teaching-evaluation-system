/**
 * 侧边栏菜单配置
 * 面向计算机学院单学科、单课程/单班级学情分析
 */
import type { MenuItem, UserRole } from '@/types'

/** 完整菜单树 */
export const menuList: MenuItem[] = [
  {
    path: '/dashboard',
    title: '综合看板',
    icon: 'Odometer',
    roles: ['admin', 'teacher'],
  },
  // ---- 学生端 ----
  {
    path: '/student/dashboard',
    title: '我的学习',
    icon: 'HomeFilled',
    roles: ['student'],
  },
  {
    path: '/data',
    title: '数据采集',
    icon: 'Upload',
    roles: ['admin', 'teacher'],
    children: [
      { path: '/data/import', title: '模板上传', icon: 'Upload' },
      { path: '/data/manage', title: '数据管理', icon: 'Document' },
    ],
  },
  {
    path: '/analysis',
    title: '智能分析',
    icon: 'DataAnalysis',
    roles: ['admin', 'teacher'],
    children: [
      { path: '/analysis/profile', title: '学情画像', icon: 'User' },
      { path: '/analysis/trend', title: '成绩趋势预测', icon: 'TrendCharts' },
      { path: '/analysis/knowledge', title: '知识点掌握度', icon: 'Grid' },
      { path: '/analysis/warning', title: '异常学情预警', icon: 'Bell', roles: ['admin', 'teacher'] },
    ],
  },
  // ---- 学生端分析 ----
  {
    path: '/student',
    title: '个人分析',
    icon: 'DataAnalysis',
    roles: ['student'],
    children: [
      { path: '/student/profile', title: '学情画像', icon: 'User' },
      { path: '/student/knowledge', title: '知识点掌握度', icon: 'Grid' },
      { path: '/student/evaluation', title: '学习评价', icon: 'Medal' },
    ],
  },
  {
    path: '/quiz',
    title: 'AI 智能辅助教学',
    icon: 'EditPen',
    children: [
      { path: '/quiz/bank', title: '题库管理', icon: 'Collection', roles: ['admin', 'teacher'] },
      { path: '/quiz/manage', title: 'AI 出题', icon: 'MagicStick', roles: ['admin', 'teacher'] },
      { path: '/quiz/records', title: '答题记录', icon: 'List', roles: ['admin', 'teacher'] },
      { path: '/quiz/answer', title: '在线答题', icon: 'Edit', roles: ['student'] },
      { path: '/agent/chat', title: 'AI 智能助手', icon: 'ChatDotRound' },
      { path: '/student/quiz-list', title: '答题任务', icon: 'List', roles: ['student'] },
    ],
  },
  {
    path: '/student/archive',
    title: '学习档案',
    icon: 'Collection',
    roles: ['student'],
    children: [
      { path: '/student/grade-archive', title: '成绩档案', icon: 'TrendCharts' },
      { path: '/student/error-book', title: '错题本', icon: 'Notebook' },
    ],
  },
  {
    path: '/evaluation',
    title: '学习质量评价',
    icon: 'Medal',
    roles: ['admin', 'teacher'],
    children: [
      { path: '/evaluation/config', title: '评价体系配置', icon: 'Setting', roles: ['admin'] },
      { path: '/evaluation/student', title: '学生学习质量', icon: 'Reading' },
    ],
  },
  {
    path: '/report',
    title: '报告中心',
    icon: 'Tickets',
    children: [
      { path: '/report/center', title: '报告生成导出', icon: 'Download' },
    ],
  },
  {
    path: '/system',
    title: '系统管理',
    icon: 'Tools',
    roles: ['admin'],
    children: [
      { path: '/system/user', title: '用户权限管理', icon: 'UserFilled' },
      { path: '/system/log', title: '系统日志', icon: 'List' },
      { path: '/system/config', title: '基础参数配置', icon: 'Operation' },
    ],
  },
]

/**
 * 根据用户角色过滤可见菜单
 */
export function filterMenusByRole(menus: MenuItem[], role: UserRole): MenuItem[] {
  return menus
    .filter((item) => !item.roles || item.roles.includes(role))
    .map((item) => {
      if (item.children) {
        const children = item.children.filter(
          (child) => !child.roles || child.roles.includes(role),
        )
        if (children.length === 0) return null
        return { ...item, children }
      }
      return item
    })
    .filter(Boolean) as MenuItem[]
}

/** 路由 meta 标题映射，用于面包屑 */
export const routeTitleMap: Record<string, string> = {
  '/dashboard': '综合看板',
  '/data/import': '模板上传',
  '/data/manage': '数据管理',
  '/analysis/profile': '学情画像',
  '/analysis/trend': '成绩趋势预测',
  '/analysis/knowledge': '知识点掌握度',
  '/analysis/warning': '异常学情预警',
  '/agent/chat': 'AI 智能助手',
  '/quiz/bank': '题库管理',
  '/quiz/manage': 'AI 出题',
  '/quiz/records': '答题记录',
  '/quiz/answer': '在线答题',
  '/evaluation/config': '评价体系配置',
  '/evaluation/student': '学生学习质量',
  '/report/center': '报告生成导出',
  '/system/user': '用户权限管理',
  '/system/log': '系统日志',
  '/system/config': '基础参数配置',
  '/student/dashboard': '我的学习',
  '/student/profile': '个人学情画像',
  '/student/knowledge': '知识点掌握度',
  '/student/evaluation': '学习评价',
  '/student/quiz-list': '答题任务',
  '/student/quiz-result': '答题结果',
  '/student/grade-archive': '成绩档案',
  '/student/error-book': '错题本',
}

/** 路由父级映射，用于面包屑层级 */
export const routeParentMap: Record<string, { path: string; title: string }> = {
  '/data/import': { path: '/data', title: '数据采集' },
  '/data/manage': { path: '/data', title: '数据采集' },
  '/analysis/profile': { path: '/analysis', title: '智能分析' },
  '/analysis/trend': { path: '/analysis', title: '智能分析' },
  '/analysis/knowledge': { path: '/analysis', title: '智能分析' },
  '/analysis/warning': { path: '/analysis', title: '智能分析' },
  '/quiz/bank': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/quiz/manage': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/quiz/records': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/quiz/answer': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/agent/chat': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/evaluation/config': { path: '/evaluation', title: '学习质量评价' },
  '/evaluation/student': { path: '/evaluation', title: '学习质量评价' },
  '/report/center': { path: '/report', title: '报告中心' },
  '/system/user': { path: '/system', title: '系统管理' },
  '/system/log': { path: '/system', title: '系统管理' },
  '/system/config': { path: '/system', title: '系统管理' },
  '/student/profile': { path: '/student', title: '个人分析' },
  '/student/knowledge': { path: '/student', title: '个人分析' },
  '/student/evaluation': { path: '/student', title: '个人分析' },
  '/student/quiz-list': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/student/quiz-result': { path: '/quiz', title: 'AI 智能辅助教学' },
  '/student/grade-archive': { path: '/student/archive', title: '学习档案' },
  '/student/error-book': { path: '/student/archive', title: '学习档案' },
}
