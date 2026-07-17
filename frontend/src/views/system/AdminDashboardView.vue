<!--
  管理员首页
  视觉风格与教师、学生看板保持一致，聚焦系统治理与运行状态
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, List, Operation, Refresh, UserFilled } from '@element-plus/icons-vue'
import StatCard from '@/components/common/StatCard.vue'
import { fetchAdminOverview } from '@/api/admin'
import type { AdminOverview } from '@/api/admin'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)

const statCards = computed(() => {
  const data = overview.value
  return [
    {
      title: '账号总数',
      value: data?.summary.totalUsers ?? 0,
      icon: 'UserFilled',
      color: '#2563eb',
      link: '/system/user',
    },
    {
      title: '正常账号',
      value: data?.summary.activeUsers ?? 0,
      icon: 'CircleCheck',
      color: '#10b981',
      link: '/system/user',
    },
    {
      title: '教师账号',
      value: data?.roleCounts.teacher ?? 0,
      icon: 'Reading',
      color: '#06b6d4',
      link: '/system/user',
    },
    {
      title: '学生账号',
      value: data?.roleCounts.student ?? 0,
      icon: 'School',
      color: '#8b5cf6',
      link: '/system/user',
    },
    {
      title: '停用账号',
      value: data?.summary.disabledUsers ?? 0,
      icon: 'Warning',
      color: '#f59e0b',
      link: '/system/user',
    },
  ]
})

const serviceItems = computed(() => {
  const services = overview.value?.services
  return [
    { name: '后端 API', desc: '业务接口与权限校验服务', status: services?.backend ?? 'offline' },
    { name: '业务数据库', desc: '用户、角色及日志数据存储', status: services?.database ?? 'offline' },
    { name: 'AI 算法服务', desc: '教师端智能出题与分析能力', status: services?.aiService ?? 'offline' },
  ]
})

const serviceLabel = {
  online: '运行正常',
  degraded: '响应异常',
  offline: '未连接',
}

const managementEntries = [
  {
    title: '用户权限管理',
    desc: '新增账号、分配角色、启停账号与重置密码',
    icon: UserFilled,
    color: '#2563eb',
    path: '/system/user',
  },
  {
    title: '基础数据概览',
    desc: '核对系统院系、学期等公共基础目录',
    icon: Operation,
    color: '#10b981',
    path: '/system/config',
  },
  {
    title: '系统日志',
    desc: '查看管理操作记录并追踪异常行为',
    icon: List,
    color: '#f59e0b',
    path: '/system/log',
  },
]

async function loadOverview(): Promise<void> {
  loading.value = true
  try {
    overview.value = await fetchAdminOverview()
  } finally {
    loading.value = false
  }
}

function handleStatClick(item: { link?: string }): void {
  if (item.link) router.push(item.link)
}

onMounted(loadOverview)
</script>

<template>
  <div v-loading="loading" class="page-container admin-dashboard">
    <!-- 欢迎区 -->
    <div class="content-card welcome-card">
      <div class="welcome-info">
        <h2>欢迎回来，{{ userStore.userInfo?.name || '系统管理员' }}</h2>
        <p>系统管理中心 · 负责账号、权限、基础数据与运行审计</p>
      </div>
      <el-button class="refresh-button" :icon="Refresh" @click="loadOverview">
        刷新数据
      </el-button>
    </div>

    <!-- 核心指标 -->
    <div class="stat-grid admin-stat-grid">
      <StatCard
        v-for="item in statCards"
        :key="item.title"
        v-bind="item"
        class="clickable"
        @click="handleStatClick(item)"
      />
    </div>

    <!-- 管理入口 -->
    <div class="content-card">
      <div class="content-card__title">系统管理</div>
      <div class="management-grid">
        <button
          v-for="entry in managementEntries"
          :key="entry.path"
          type="button"
          class="management-card"
          @click="router.push(entry.path)"
        >
          <div
            class="management-card__icon"
            :style="{ color: entry.color, background: `${entry.color}15` }"
          >
            <el-icon :size="28"><component :is="entry.icon" /></el-icon>
          </div>
          <div class="management-card__body">
            <h3>{{ entry.title }}</h3>
            <p>{{ entry.desc }}</p>
          </div>
          <el-icon class="management-card__arrow"><ArrowRight /></el-icon>
        </button>
      </div>
    </div>

    <!-- 日志与服务状态 -->
    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <div class="content-card section-card">
          <div class="section-header">
            <div class="content-card__title">最近操作记录</div>
            <el-button link type="primary" @click="router.push('/system/log')">
              查看全部
            </el-button>
          </div>

          <div v-if="overview?.recentOperations.length" class="operation-list">
            <div
              v-for="item in overview.recentOperations"
              :key="item.id"
              class="operation-item"
            >
              <div class="operation-avatar">
                {{ item.username.slice(0, 1).toUpperCase() || '系' }}
              </div>
              <div class="operation-content">
                <div class="operation-meta">
                  <strong>{{ item.username || '系统' }}</strong>
                  <el-tag size="small" effect="plain">{{ item.module }}</el-tag>
                  <span>{{ item.operation }}</span>
                </div>
                <p>{{ item.content }}</p>
              </div>
              <time>{{ item.time }}</time>
            </div>
          </div>
          <el-empty v-else description="暂无操作日志" :image-size="80" />
        </div>
      </el-col>

      <el-col :xs="24" :lg="8">
        <div class="content-card section-card">
          <div class="content-card__title">服务运行状态</div>
          <div class="service-list">
            <div v-for="service in serviceItems" :key="service.name" class="service-item">
              <span class="status-dot" :class="service.status" />
              <div class="service-info">
                <strong>{{ service.name }}</strong>
                <small>{{ service.desc }}</small>
              </div>
              <el-tag
                size="small"
                effect="light"
                :type="service.status === 'online' ? 'success' : service.status === 'degraded' ? 'warning' : 'danger'"
              >
                {{ serviceLabel[service.status] }}
              </el-tag>
            </div>
          </div>
          <div class="system-version">
            <span>{{ overview?.system.appName || 'AI 教学评价系统' }}</span>
            <span>v{{ overview?.system.version || '--' }}</span>
          </div>
        </div>
      </el-col>
    </el-row>

  </div>
</template>

<style scoped lang="scss">
.admin-dashboard {
  .welcome-card {
    padding: 28px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #fff;
    background: linear-gradient(135deg, #2563eb, #6366f1);

    h2 {
      margin-bottom: 6px;
      font-size: 22px;
    }

    p {
      font-size: 14px;
      opacity: 0.85;
    }
  }

  .refresh-button {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.48);
    background: rgba(255, 255, 255, 0.12);

    &:hover {
      color: #2563eb;
      border-color: #fff;
      background: #fff;
    }
  }

  .admin-stat-grid {
    grid-template-columns: repeat(5, minmax(180px, 1fr));
  }

  .clickable {
    cursor: pointer;
  }
}

.management-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.management-card {
  min-height: 120px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  color: #1e293b;
  text-align: left;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;

  &:hover {
    border-color: #bfdbfe;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.1);
    transform: translateY(-2px);
  }

  &__icon {
    width: 58px;
    height: 58px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 12px;
  }

  &__body {
    flex: 1;
    min-width: 0;

    h3 {
      margin-bottom: 8px;
      font-size: 16px;
    }

    p {
      color: #64748b;
      font-size: 13px;
      line-height: 1.6;
    }
  }

  &__arrow {
    flex-shrink: 0;
    color: #94a3b8;
  }
}

.section-card {
  height: 100%;
  min-height: 330px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;

  .content-card__title {
    margin-bottom: 16px;
  }
}

.operation-list {
  display: flex;
  flex-direction: column;
}

.operation-item {
  padding: 14px 0;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;

  &:last-child {
    border-bottom: 0;
  }

  time {
    color: #94a3b8;
    font-size: 12px;
  }
}

.operation-avatar {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2563eb;
  font-weight: 700;
  border-radius: 10px;
  background: #eff6ff;
}

.operation-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;

  strong {
    color: #1e293b;
  }

  span {
    color: #64748b;
    font-size: 12px;
  }
}

.operation-content p {
  margin-top: 5px;
  color: #64748b;
  font-size: 13px;
}

.service-list {
  display: flex;
  flex-direction: column;
}

.service-item {
  padding: 17px 0;
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;

  &.online {
    background: #10b981;
    box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
  }

  &.degraded {
    background: #f59e0b;
    box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
  }

  &.offline {
    background: #ef4444;
    box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1);
  }
}

.service-info {
  min-width: 0;

  strong,
  small {
    display: block;
  }

  strong {
    margin-bottom: 4px;
    color: #1e293b;
  }

  small {
    color: #94a3b8;
    line-height: 1.4;
  }
}

.system-version {
  margin-top: 20px;
  padding-top: 16px;
  display: flex;
  justify-content: space-between;
  color: #64748b;
  border-top: 1px solid #e2e8f0;
}

@media (max-width: 1280px) {
  .admin-dashboard .admin-stat-grid {
    grid-template-columns: repeat(3, minmax(180px, 1fr));
  }
}

@media (max-width: 900px) {
  .admin-dashboard {
    .welcome-card {
      align-items: flex-start;
      gap: 18px;
    }

    .admin-stat-grid {
      grid-template-columns: repeat(2, minmax(160px, 1fr));
    }
  }

  .management-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .admin-dashboard {
    .welcome-card {
      padding: 24px;
      flex-direction: column;
    }

    .admin-stat-grid {
      grid-template-columns: 1fr;
    }
  }

  .operation-item {
    grid-template-columns: 40px minmax(0, 1fr);

    time {
      grid-column: 2;
    }
  }

  .service-item {
    grid-template-columns: 10px minmax(0, 1fr);

    .el-tag {
      grid-column: 2;
      justify-self: start;
    }
  }
}
</style>
