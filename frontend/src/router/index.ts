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
        {
          path: 'data/import',
          name: 'DataImport',
          component: () => import('@/views/data/DataImportView.vue'),
          meta: { title: '模板上传', roles: ['admin', 'teacher'] },
        },
        {
          path: 'data/manage',
          name: 'DataManage',
          component: () => import('@/views/data/DataManageView.vue'),
          meta: { title: '数据管理', roles: ['admin', 'teacher'] },
        },
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
          meta: { title: '异常学情预警', roles: ['admin', 'teacher'] },
        },
        {
          path: 'quiz/manage',
          name: 'QuizManage',
          component: () => import('@/views/quiz/QuizManageView.vue'),
          meta: { title: 'AI 出题', roles: ['admin', 'teacher'] },
        },
        {
          path: 'quiz/answer',
          name: 'QuizAnswer',
          component: () => import('@/views/quiz/QuizAnswerView.vue'),
          meta: { title: '在线答题', roles: ['student'] },
        },
        {
          path: 'evaluation/config',
          name: 'EvalConfig',
          component: () => import('@/views/evaluation/EvalConfigView.vue'),
          meta: { title: '评价体系配置', roles: ['admin'] },
        },
        {
          path: 'evaluation/student',
          name: 'StudentEval',
          component: () => import('@/views/evaluation/StudentEvalView.vue'),
          meta: { title: '学生学习质量', roles: ['admin', 'teacher'] },
        },
        {
          path: 'report/center',
          name: 'ReportCenter',
          component: () => import('@/views/report/ReportCenterView.vue'),
          meta: { title: '报告生成导出' },
        },
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
  document.title = `${to.meta.title || '首页'} - 计算机学院学情分析系统`

  if (to.meta.public) {
    return true
  }

  const token = getToken()
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const roles = to.meta.roles as string[] | undefined
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
