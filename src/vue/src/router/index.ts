/**
 * 路由配置
 * 定义系统全部页面路由，含登录守卫与权限校验
 */
import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/auth'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/DashboardView.vue'),
          meta: { title: '综合看板' },
        },
        // 数据采集模块
        {
          path: 'data/import',
          name: 'DataImport',
          component: () => import('@/views/data/DataImportView.vue'),
          meta: { title: '多源数据接入', roles: ['admin', 'manager', 'teacher'] },
        },
        {
          path: 'data/clean',
          name: 'DataClean',
          component: () => import('@/views/data/DataCleanView.vue'),
          meta: { title: '数据清洗', roles: ['admin', 'manager', 'teacher'] },
        },
        {
          path: 'data/manage',
          name: 'DataManage',
          component: () => import('@/views/data/DataManageView.vue'),
          meta: { title: '数据管理', roles: ['admin', 'manager', 'teacher'] },
        },
        // AI 智能分析模块
        {
          path: 'analysis/profile',
          name: 'StudentProfile',
          component: () => import('@/views/analysis/StudentProfileView.vue'),
          meta: { title: '学情画像' },
        },
        {
          path: 'analysis/trend',
          name: 'GradeTrend',
          component: () => import('@/views/analysis/GradeTrendView.vue'),
          meta: { title: '成绩趋势预测' },
        },
        {
          path: 'analysis/knowledge',
          name: 'Knowledge',
          component: () => import('@/views/analysis/KnowledgeView.vue'),
          meta: { title: '知识点掌握度' },
        },
        {
          path: 'analysis/warning',
          name: 'Warning',
          component: () => import('@/views/analysis/WarningView.vue'),
          meta: { title: '异常学情预警', roles: ['admin', 'manager', 'teacher'] },
        },
        {
          path: 'analysis/correlation',
          name: 'Correlation',
          component: () => import('@/views/analysis/CorrelationView.vue'),
          meta: { title: '教学效果关联', roles: ['admin', 'manager', 'teacher'] },
        },
        // 多维评价模块
        {
          path: 'evaluation/config',
          name: 'EvalConfig',
          component: () => import('@/views/evaluation/EvalConfigView.vue'),
          meta: { title: '评价体系配置', roles: ['admin'] },
        },
        {
          path: 'evaluation/teacher',
          name: 'TeacherEval',
          component: () => import('@/views/evaluation/TeacherEvalView.vue'),
          meta: { title: '教师教学质量', roles: ['admin', 'manager', 'teacher'] },
        },
        {
          path: 'evaluation/student',
          name: 'StudentEval',
          component: () => import('@/views/evaluation/StudentEvalView.vue'),
          meta: { title: '学生学习质量', roles: ['admin', 'manager', 'teacher'] },
        },
        {
          path: 'evaluation/course',
          name: 'CourseEval',
          component: () => import('@/views/evaluation/CourseEvalView.vue'),
          meta: { title: '课程建设质量', roles: ['admin', 'manager', 'teacher'] },
        },
        // 报告中心
        {
          path: 'report/center',
          name: 'ReportCenter',
          component: () => import('@/views/report/ReportCenterView.vue'),
          meta: { title: '报告生成导出' },
        },
        // 系统管理模块
        {
          path: 'system/user',
          name: 'UserManage',
          component: () => import('@/views/system/UserManageView.vue'),
          meta: { title: '用户权限管理', roles: ['admin'] },
        },
        {
          path: 'system/log',
          name: 'LogManage',
          component: () => import('@/views/system/LogManageView.vue'),
          meta: { title: '系统日志', roles: ['admin'] },
        },
        {
          path: 'system/config',
          name: 'ParamConfig',
          component: () => import('@/views/system/ParamConfigView.vue'),
          meta: { title: '基础参数配置', roles: ['admin'] },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard',
    },
  ],
})

/** 路由前置守卫：登录校验与权限控制 */
router.beforeEach((to) => {
  // 动态设置页面标题
  document.title = `${to.meta.title || '首页'} - 数智化教学分析评价系统`

  // 公开页面直接放行
  if (to.meta.public) {
    return true
  }

  const token = getToken()
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 角色权限校验
  const roles = to.meta.roles
  if (roles) {
    const userStore = useUserStore()
    if (!userStore.userInfo) {
      userStore.restoreSession()
    }
    if (userStore.userInfo && !roles.includes(userStore.userInfo.role)) {
      return '/dashboard'
    }
  }

  return true
})

export default router
