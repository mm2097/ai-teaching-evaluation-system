<!--
  登录页面
  系统入口，支持演示账号快速登录
-->
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, DataAnalysis } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/** 登录表单数据 */
const loginForm = reactive({
  username: '',
  password: '',
})

/** 登录加载状态 */
const loading = ref(false)

/** 演示账号列表 */
const demoAccounts = [
  { username: 'admin', role: '系统管理员' },
  { username: 'manager', role: '教学管理者' },
  { username: 'teacher', role: '任课教师' },
  { username: 'student', role: '学生用户' },
]

/**
 * 提交登录表单
 */
async function handleLogin(): Promise<void> {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }

  loading.value = true
  try {
    const success = await userStore.login(loginForm.username, loginForm.password)
    if (success) {
      ElMessage.success('登录成功，欢迎回来！')
      const redirect = (route.query.redirect as string) || '/dashboard'
      router.push(redirect)
    } else {
      ElMessage.error('账号或密码错误，请重试')
    }
  } finally {
    loading.value = false
  }
}

/**
 * 快速填充演示账号（密码统一为 123456）
 * @param username 演示账号名
 */
function fillDemoAccount(username: string): void {
  loginForm.username = username
  loginForm.password = '123456'
}
</script>

<template>
  <div class="login-page">
    <!-- 左侧品牌展示区 -->
    <div class="login-banner">
      <div class="banner-content">
        <div class="banner-icon">
          <el-icon :size="48"><DataAnalysis /></el-icon>
        </div>
        <h1>数智化教学分析评价系统</h1>
        <p>数据驱动 · 智能分析 · 多维评价 · 科学决策</p>
        <ul class="feature-list">
          <li>多源教学数据统一采集与清洗</li>
          <li>AI 引擎驱动的学情分析与预警</li>
          <li>教师 / 学生 / 课程多维量化评价</li>
          <li>可视化看板与自动化报告生成</li>
        </ul>
      </div>
    </div>

    <!-- 右侧登录表单区 -->
    <div class="login-form-area">
      <div class="login-card">
        <h2>欢迎登录</h2>
        <p class="subtitle">请输入您的账号信息</p>

        <el-form :model="loginForm" size="large" @keyup.enter="handleLogin">
          <el-form-item>
            <el-input
              v-model="loginForm.username"
              placeholder="请输入账号"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" class="login-btn" @click="handleLogin">
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 演示账号快捷入口 -->
        <div class="demo-accounts">
          <p class="demo-title">演示账号（密码均为 123456）</p>
          <div class="demo-tags">
            <el-tag
              v-for="item in demoAccounts"
              :key="item.username"
              class="demo-tag"
              effect="plain"
              @click="fillDemoAccount(item.username)"
            >
              {{ item.role }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login-page {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.login-banner {
  flex: 1;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #2563eb 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
    top: -100px;
    right: -100px;
  }

  .banner-content {
    color: #fff;
    max-width: 480px;
    padding: 40px;
    position: relative;
    z-index: 1;

    .banner-icon {
      width: 80px;
      height: 80px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 24px;
      backdrop-filter: blur(10px);
    }

    h1 {
      font-size: 32px;
      font-weight: 700;
      margin-bottom: 12px;
      line-height: 1.3;
    }

    p {
      font-size: 16px;
      color: rgba(255, 255, 255, 0.7);
      margin-bottom: 32px;
    }

    .feature-list {
      list-style: none;

      li {
        padding: 10px 0;
        font-size: 15px;
        color: rgba(255, 255, 255, 0.85);
        display: flex;
        align-items: center;

        &::before {
          content: '';
          width: 6px;
          height: 6px;
          background: #60a5fa;
          border-radius: 50%;
          margin-right: 12px;
          flex-shrink: 0;
        }
      }
    }
  }
}

.login-form-area {
  width: 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  padding: 40px;
}

.login-card {
  width: 100%;
  max-width: 360px;

  h2 {
    font-size: 24px;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 8px;
  }

  .subtitle {
    color: #94a3b8;
    margin-bottom: 32px;
  }

  .login-btn {
    width: 100%;
    height: 44px;
    font-size: 16px;
    border-radius: 8px;
  }

  .demo-accounts {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;

    .demo-title {
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 10px;
    }

    .demo-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .demo-tag {
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        color: #2563eb;
        border-color: #2563eb;
      }
    }
  }
}

@media (max-width: 900px) {
  .login-banner {
    display: none;
  }

  .login-form-area {
    width: 100%;
  }
}
</style>
