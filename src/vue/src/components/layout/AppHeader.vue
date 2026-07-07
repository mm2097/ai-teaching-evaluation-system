<!--
  顶部导航栏组件
  包含折叠按钮、面包屑、用户信息下拉菜单
-->
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Expand, Fold, SwitchButton, User } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import BreadcrumbNav from './BreadcrumbNav.vue'

const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

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
