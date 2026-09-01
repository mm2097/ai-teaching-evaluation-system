<!--
  顶部导航栏组件
  包含折叠按钮、面包屑、用户信息下拉菜单
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Bell, Expand, Fold, SwitchButton, User } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { fetchNotifications, markNotificationRead, markAllNotificationsRead } from '@/api/notifications'
import type { NotificationItem } from '@/types'
import BreadcrumbNav from './BreadcrumbNav.vue'

const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

const role = computed(() => userStore.userInfo?.role || 'student')

/* ============================================================
 * 消息通知（学生端铃铛）
 * ============================================================ */
const notifications = ref<NotificationItem[]>([])
const notifLoading = ref(false)
const unreadCount = computed(() => notifications.value.filter((n) => !n.isRead).length)
let pollTimer: number | undefined

async function loadNotifications(): Promise<void> {
  if (role.value !== 'student') return
  notifLoading.value = true
  try {
    notifications.value = await fetchNotifications()
  } finally {
    notifLoading.value = false
  }
}

async function handleReadNotification(item: NotificationItem): Promise<void> {
  if (item.isRead) return
  try {
    await markNotificationRead(item.id)
    const idx = notifications.value.findIndex((n) => n.id === item.id)
    if (idx !== -1) notifications.value[idx] = { ...notifications.value[idx]!, isRead: true }
  } catch {
    // 错误提示由 request 拦截器统一处理
  }
}

async function handleReadAll(): Promise<void> {
  if (!unreadCount.value) return
  try {
    await markAllNotificationsRead()
    notifications.value = notifications.value.map((n) => ({ ...n, isRead: true }))
  } catch {
    // 错误提示由 request 拦截器统一处理
  }
}

onMounted(() => {
  loadNotifications()
  if (role.value === 'student') {
    pollTimer = window.setInterval(loadNotifications, 30000)
  }
})
onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

/**
 * 退出登录确认
 */
async function handleLogout(): Promise<void> {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="app-header__left">
      <el-icon class="collapse-btn" :size="20" @click="appStore.toggleSidebar()">
        <Fold v-if="!appStore.sidebarCollapsed" />
        <Expand v-else />
      </el-icon>
      <BreadcrumbNav />
    </div>

    <div class="app-header__right">
      <el-popover
        v-if="role === 'student'"
        placement="bottom-end"
        :width="360"
        trigger="click"
        @show="loadNotifications"
      >
        <template #reference>
          <el-badge
            :value="unreadCount"
            :hidden="unreadCount === 0"
            :max="99"
            class="notif-badge"
          >
            <el-icon :size="20" class="bell-icon"><Bell /></el-icon>
          </el-badge>
        </template>
        <div class="notif-panel">
          <div class="notif-panel__header">
            <span class="notif-panel__title">消息通知</span>
            <el-button
              v-if="unreadCount > 0"
              link
              type="primary"
              size="small"
              @click="handleReadAll"
            >全部已读</el-button>
          </div>
          <el-empty
            v-if="!notifLoading && notifications.length === 0"
            description="暂无通知"
            :image-size="60"
          />
          <div v-else v-loading="notifLoading" class="notif-list">
            <div
              v-for="n in notifications"
              :key="n.id"
              class="notif-item"
              :class="{ unread: !n.isRead }"
              @click="handleReadNotification(n)"
            >
              <div class="notif-item__head">
                <span v-if="!n.isRead" class="notif-item__dot" />
                <span class="notif-item__title">{{ n.title }}</span>
              </div>
              <div class="notif-item__content">{{ n.content }}</div>
              <div class="notif-item__meta">
                {{ n.courseName || '' }} · {{ n.createTime }}
              </div>
            </div>
          </div>
        </div>
      </el-popover>
      <el-tag size="small" type="primary" effect="plain">{{ userStore.roleLabel }}</el-tag>
      <el-dropdown trigger="click">
        <div class="user-info">
          <el-avatar :size="32" class="avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="username">{{ userStore.userInfo?.name }}</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              {{ userStore.userInfo?.department }}
            </el-dropdown-item>
            <el-dropdown-item divided :icon="SwitchButton" @click="handleLogout">
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped lang="scss">
.app-header {
  height: 60px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 100;

  &__left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .collapse-btn {
    cursor: pointer;
    color: #64748b;
    transition: color 0.2s;

    &:hover {
      color: #2563eb;
    }
  }

  .bell-icon {
    cursor: pointer;
    color: #64748b;
    transition: color 0.2s;

    &:hover {
      color: #2563eb;
    }
  }

  .notif-panel {
    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 8px;
      border-bottom: 1px solid #f1f5f9;
    }

    &__title {
      font-size: 14px;
      font-weight: 600;
      color: #1e293b;
    }
  }

  .notif-list {
    max-height: 360px;
    overflow-y: auto;

    .notif-item {
      padding: 10px 4px;
      border-bottom: 1px solid #f8fafc;
      cursor: pointer;
      transition: background 0.2s;

      &:hover {
        background: #f8fafc;
      }

      &.unread {
        background: #eff6ff;

        &:hover {
          background: #e0edff;
        }
      }

      &__head {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      &__dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #2563eb;
        flex-shrink: 0;
      }

      &__title {
        font-size: 13px;
        font-weight: 600;
        color: #1e293b;
      }

      &__content {
        margin-top: 4px;
        font-size: 12px;
        color: #475569;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      &__meta {
        margin-top: 4px;
        font-size: 11px;
        color: #94a3b8;
      }
    }
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;

    .avatar {
      background: linear-gradient(135deg, #2563eb, #3b82f6);
    }

    .username {
      font-size: 14px;
      color: #1e293b;
    }
  }
}
</style>
