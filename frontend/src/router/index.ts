/**
 * 路由配置
 * 定义系统全部页面路由，含登录守卫与权限校验
 */
import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/auth'
import { useUserStore } from '@/stores/user'

function defaultPathForRole(role?: string): string {
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'student') return '/student/dashboard'
  return '/dashboard'
}

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
        // ---- 管理员工作台 ----
        {
          path: 'admin/dashboard',
          name: 'AdminDashboard',
          component: () => import('@/views/system/AdminDashboardView.vue'),
          meta: { title: '管理工作台', roles: ['admin'] },
        },
        // ---- 看板 ----
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/DashboardView.vue'),
          meta: { title: '综合看板', roles: ['teacher'] },
        },
        // ---- 数据管理 ----
        {
          path: 'data/import',
          name: 'DataImport',
          component: () => import('@/views/data/DataImportView.vue'),
          meta: { title: '数据上传', roles: ['teacher'] },
        },
        {
          path: 'data/manage',
          name: 'DataManage',
          component: () => import('@/views/data/DataManageView.vue'),
          meta: { title: '数据管理', roles: ['teacher'] },
        },
        // ---- AI 分析 ----
        {
          path: 'analysis/profile',
          name: 'StudentProfile',
          component: () => import('@/views/analysis/StudentProfileView.vue'),
          meta: { title: '学情画像', roles: ['teacher'] },
        },
        {
          path: 'analysis/trend',
          name: 'GradeTrend',
          component: () => import('@/views/analysis/GradeTrendView.vue'),
          meta: { title: '成绩趋势预测', roles: ['teacher'] },
        },
        {
          path: 'analysis/knowledge',
          name: 'Knowledge',
          component: () => import('@/views/analysis/KnowledgeView.vue'),
          meta: { title: '知识点掌握度', roles: ['teacher'] },
        },
        {
          path: 'analysis/warning',
          name: 'Warning',
          component: () => import('@/views/analysis/WarningView.vue'),
          meta: { title: '异常学情预警', roles: ['teacher'] },
        },
        // ---- AI 智能辅助教学 ----
        {
          path: 'agent/chat',
          name: 'AgentChat',
          component: () => import('@/views/agent/AgentChatView.vue'),
          meta: { title: 'AI 智能助手', roles: ['teacher'] },
        },
        {
          path: 'quiz/bank',
          name: 'QuestionBank',
          component: () => import('@/views/quiz/QuestionBankView.vue'),
          meta: { title: '题库管理', roles: ['teacher'] },
        },
        {
          path: 'quiz/manage',
          name: 'QuizManage',
          component: () => import('@/views/quiz/QuizManageView.vue'),
          meta: { title: 'AI 出题', roles: ['teacher'] },
        },
        {
          path: 'quiz/records',
          name: 'QuizRecords',
          component: () => import('@/views/quiz/QuizRecordsView.vue'),
          meta: { title: '答题记录', roles: ['teacher'] },
        },
        {
          path: 'quiz/answer',
          name: 'QuizAnswer',
          component: () => import('@/views/quiz/QuizAnswerView.vue'),
          meta: { title: '在线答题', roles: ['student'] },
        },
        // ---- 评价 ----
        {
          path: 'evaluation/config',
          name: 'EvalConfig',
          component: () => import('@/views/evaluation/EvalConfigView.vue'),
          meta: { title: '评价体系配置', roles: ['teacher'] },
        },
        {
          path: 'evaluation/student',
          name: 'StudentEval',
          component: () => import('@/views/evaluation/StudentEvalView.vue'),
          meta: { title: '学生学习质量', roles: ['teacher'] },
        },
        // ---- 报告 ----
        {
          path: 'report/center',
          name: 'ReportCenter',
          component: () => import('@/views/report/ReportCenterView.vue'),
          meta: { title: '报告生成导出', roles: ['teacher', 'student'] },
        },
        // ---- 系统管理 ----
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
          meta: { title: '基础数据概览', roles: ['admin'] },
        },
        // ---- 学生端独立页面 ----
        {
          path: 'student/dashboard',
          name: 'StudentDashboard',
          component: () => import('@/views/student/StudentDashboard.vue'),
          meta: { title: '我的学习', roles: ['student'] },
        },
        {
          path: 'student/profile',
          name: 'StudentProfileView',
          component: () => import('@/views/student/StudentProfileView.vue'),
          meta: { title: '个人学情画像', roles: ['student'] },
        },
        {
          path: 'student/knowledge',
          name: 'StudentKnowledge',
          component: () => import('@/views/student/StudentKnowledgeView.vue'),
          meta: { title: '知识点掌握度', roles: ['student'] },
        },
        {
          path: 'student/evaluation',
          name: 'StudentEvaluation',
          component: () => import('@/views/student/StudentEvalView.vue'),
          meta: { title: '学习评价', roles: ['student'] },
        },
        {
          path: 'student/quiz-list',
          name: 'QuizTaskList',
          component: () => import('@/views/student/QuizTaskList.vue'),
          meta: { title: '答题任务', roles: ['student'] },
        },
        {
          path: 'student/quiz-result',
          name: 'QuizResult',
          component: () => import('@/views/student/QuizResultView.vue'),
          meta: { title: '答题结果', roles: ['student'] },
        },
        {
          path: 'student/grade-archive',
          name: 'GradeArchive',
          component: () => import('@/views/student/GradeArchiveView.vue'),
          meta: { title: '成绩档案', roles: ['student'] },
        },
        {
          path: 'student/error-book',
          name: 'ErrorBook',
          component: () => import('@/views/student/ErrorBookView.vue'),
          meta: { title: '错题本', roles: ['student'] },
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
    if (!userStore.userInfo) {
      return '/login'
    }
    if (!roles.includes(userStore.userInfo.role)) {
      return defaultPathForRole(userStore.userInfo.role)
    }
  }

  return true
})

export default router
