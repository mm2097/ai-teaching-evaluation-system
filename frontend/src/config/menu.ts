/**
 * 侧边栏菜单配置
 * 根据需求规格说明书划分功能模块，并通过 roles 控制角色可见性
 */
import type { MenuItem, UserRole } from '@/types'

/** 完整菜单树 */
export const menuList: MenuItem[] = [
  {
    path: '/dashboard',
    title: '综合看板',
    icon: 'Odometer',
  },
  {
    path: '/data',
    title: '数据采集',
    icon: 'Upload',
    roles: ['admin', 'manager', 'teacher'],
    children: [
      { path: '/data/import', title: '多源数据接入', icon: 'Connection' },
      { path: '/data/clean', title: '数据清洗', icon: 'Brush' },
      { path: '/data/manage', title: '数据管理', icon: 'Document' },
    ],
  },
  {
    path: '/analysis',
    title: 'AI 智能分析',
    icon: 'DataAnalysis',
    children: [
      { path: '/analysis/profile', title: '学情画像', icon: 'User' },
      { path: '/analysis/trend', title: '成绩趋势预测', icon: 'TrendCharts' },
      { path: '/analysis/knowledge', title: '知识点掌握度', icon: 'Grid' },
      { path: '/analysis/warning', title: '异常学情预警', icon: 'Bell', roles: ['admin', 'manager', 'teacher'] },
      { path: '/analysis/correlation', title: '教学效果关联', icon: 'Link', roles: ['admin', 'manager', 'teacher'] },
    ],
  },
  {
    path: '/evaluation',
    title: '多维评价',
    icon: 'Medal',
    roles: ['admin', 'manager', 'teacher'],
    children: [
      { path: '/evaluation/config', title: '评价体系配置', icon: 'Setting', roles: ['admin'] },
      { path: '/evaluation/teacher', title: '教师教学质量', icon: 'Avatar' },
      { path: '/evaluation/student', title: '学生学习质量', icon: 'Reading' },
      { path: '/evaluation/course', title: '课程建设质量', icon: 'Notebook' },
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
 * @param menus 原始菜单列表
 * @param role 当前用户角色
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

/**
 * 路由 meta 标题映射，用于面包屑
 */
export const routeTitleMap: Record<string, string> = {
  '/dashboard': '综合看板',
  '/data/import': '多源数据接入',
  '/data/clean': '数据清洗',
  '/data/manage': '数据管理',
  '/analysis/profile': '学情画像',
  '/analysis/trend': '成绩趋势预测',
  '/analysis/knowledge': '知识点掌握度',
  '/analysis/warning': '异常学情预警',
  '/analysis/correlation': '教学效果关联',
  '/evaluation/config': '评价体系配置',
  '/evaluation/teacher': '教师教学质量',
  '/evaluation/student': '学生学习质量',
  '/evaluation/course': '课程建设质量',
  '/report/center': '报告生成导出',
  '/system/user': '用户权限管理',
  '/system/log': '系统日志',
  '/system/config': '基础参数配置',
}

/** 路由父级映射，用于面包屑层级 */
export const routeParentMap: Record<string, { path: string; title: string }> = {
  '/data/import': { path: '/data', title: '数据采集' },
  '/data/clean': { path: '/data', title: '数据采集' },
  '/data/manage': { path: '/data', title: '数据采集' },
  '/analysis/profile': { path: '/analysis', title: 'AI 智能分析' },
  '/analysis/trend': { path: '/analysis', title: 'AI 智能分析' },
  '/analysis/knowledge': { path: '/analysis', title: 'AI 智能分析' },
  '/analysis/warning': { path: '/analysis', title: 'AI 智能分析' },
  '/analysis/correlation': { path: '/analysis', title: 'AI 智能分析' },
  '/evaluation/config': { path: '/evaluation', title: '多维评价' },
  '/evaluation/teacher': { path: '/evaluation', title: '多维评价' },
  '/evaluation/student': { path: '/evaluation', title: '多维评价' },
  '/evaluation/course': { path: '/evaluation', title: '多维评价' },
  '/report/center': { path: '/report', title: '报告中心' },
  '/system/user': { path: '/system', title: '系统管理' },
  '/system/log': { path: '/system', title: '系统管理' },
  '/system/config': { path: '/system', title: '系统管理' },
}
