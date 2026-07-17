<!--
  登录页面
  系统入口，支持演示账号快速登录
-->
<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
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

/** 演示账号（teacher / student / 201726010101 均为计科2401班，便于联调发布练习） */
const demoAccounts = [
  { username: 'admin', role: '系统管理员' },
  { username: 'teacher', role: '任课教师（计科2401）' },
  { username: 'student', role: '学生（计科2401）' },
  { username: '201726010101', role: '学生（计科2401·测试数据）' },
]

onMounted(() => {
  // 进入登录页时清除可能已过期的本地 token，避免后续请求反复弹「登录已过期」
  userStore.logout()
})

/**
 * 快捷填充演示账号（含初始密码，需手动点击登录）
 */
function fillDemoAccount(username: string): void {
  loginForm.username = username
  loginForm.password = '123456'
}

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
      const role = userStore.userInfo?.role
      const defaultPath = role === 'admin'
        ? '/admin/dashboard'
        : role === 'student'
          ? '/student/dashboard'
          : '/dashboard'
      const redirect = (route.query.redirect as string) || defaultPath
      router.push(redirect)
    }
    // 登录失败时，具体错误信息由 userStore 统一弹出
  } finally {
    loading.value = false
  }
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
        <h1>计算机学院学情分析系统</h1>
        <p>数据驱动 · 智能分析 · 学情评价 · 精准教学</p>
        <ul class="feature-list">
          <li>标准模板下载与格式校验上传</li>
          <li>AI 引擎驱动的学情分析与预警</li>
          <li>知识点热力图与学生学习质量评价</li>
          <li>AI 出题在线答题与自动化报告</li>
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
              autocomplete="username"
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
              autocomplete="current-password"
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
          <p class="demo-title">演示账号快捷填充（密码 123456，点击后手动登录）</p>
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
