<!--
  侧边栏菜单组件
  根据用户角色动态渲染可见菜单，支持折叠模式
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import * as Icons from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import PersonalSettingsDialog from './PersonalSettingsDialog.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

/** 当前激活菜单路径 */
const activeMenu = computed(() => route.path)

function handleSelect(index: string) {
  router.push(index)
}

/**
 * 根据图标名称获取组件
 * @param iconName 图标名称字符串
 */
function getIcon(iconName: string) {
  return (Icons as Record<string, unknown>)[iconName] || Icons.Menu
}

/* ============================================================
 * 底部"设置"入口：修改个人信息 / 退出登录
 * 与右上角头像下拉的退出登录并存，两处入口均保留
 * ============================================================ */
/** 设置弹层显隐 */
const settingsPopVisible = ref(false)
/** 个人设置弹窗显隐 */
const settingsVisible = ref(false)

/** 打开个人设置弹窗（修改个人信息/密码） */
function openSettings(): void {
  settingsPopVisible.value = false
  settingsVisible.value = true
}

/**
 * 退出登录确认（与顶部头像下拉交互一致）
 */
async function handleLogout(): Promise<void> {
  settingsPopVisible.value = false
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
  <aside class="app-sidebar" :class="{ collapsed: appStore.sidebarCollapsed }">
    <!-- Logo 区域 -->
    <div class="sidebar-logo">
      <div class="logo-icon">
        <el-icon :size="24"><component :is="Icons.DataAnalysis" /></el-icon>
      </div>
      <transition name="fade">
        <span v-show="!appStore.sidebarCollapsed" class="logo-text">数智教学评价</span>
      </transition>
    </div>

    <!-- 导航菜单 -->
    <el-scrollbar class="sidebar-menu-wrap">
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        background-color="#0f172a"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
        router
        unique-opened
        @select="handleSelect"
      >
        <template v-for="menu in userStore.visibleMenus" :key="menu.path">
          <!-- 有子菜单的分组 -->
          <el-sub-menu v-if="menu.children?.length" :index="menu.path">
            <template #title>
              <el-icon><component :is="getIcon(menu.icon)" /></el-icon>
              <span>{{ menu.title }}</span>
            </template>
            <el-menu-item
              v-for="child in menu.children"
              :key="child.path"
              :index="child.path"
            >
              <el-icon><component :is="getIcon(child.icon)" /></el-icon>
              <span>{{ child.title }}</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 无子菜单的独立项 -->
          <el-menu-item v-else :index="menu.path">
            <el-icon><component :is="getIcon(menu.icon)" /></el-icon>
            <span>{{ menu.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>

    <!-- 底部设置区：修改个人信息 / 退出登录 -->
    <div class="sidebar-settings">
      <el-popover
        v-model:visible="settingsPopVisible"
        placement="right-end"
        :width="180"
        trigger="click"
        :show-arrow="false"
      >
        <template #reference>
          <div class="settings-btn">
            <el-icon :size="18"><component :is="Icons.Setting" /></el-icon>
            <span v-show="!appStore.sidebarCollapsed">设置</span>
          </div>
        </template>
        <div class="settings-menu">
          <div class="settings-menu__item" @click="openSettings">
            <el-icon :size="16"><component :is="Icons.User" /></el-icon>
            <span>修改个人信息</span>
          </div>
          <div class="settings-menu__item settings-menu__item--danger" @click="handleLogout">
            <el-icon :size="16"><component :is="Icons.SwitchButton" /></el-icon>
            <span>退出登录</span>
          </div>
        </div>
      </el-popover>
    </div>

    <!-- 个人设置弹窗（基本信息 + 修改密码） -->
    <PersonalSettingsDialog v-model="settingsVisible" />
  </aside>
</template>

<style scoped lang="scss">
.app-sidebar {
  width: 240px;
  height: 100%;
  background: #0f172a;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  flex-shrink: 0;

  &.collapsed {
    width: 64px;

    .sidebar-logo {
      padding: 0;
      justify-content: center;
    }
  }

  .sidebar-logo {
    height: 60px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);

    .logo-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #2563eb, #6366f1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;
    }

    .logo-text {
      font-size: 16px;
      font-weight: 600;
      color: #f1f5f9;
      white-space: nowrap;
    }
  }

  .sidebar-menu-wrap {
    flex: 1;
    overflow: hidden;
  }

  .sidebar-settings {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;

    .settings-btn {
      height: 48px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0 16px;
      font-size: 14px;
      color: #cbd5e1;
      cursor: pointer;
      transition: background 0.2s, color 0.2s;

      &:hover {
        background: rgba(255, 255, 255, 0.05);
        color: #fff;
      }
    }
  }

  &.collapsed .sidebar-settings .settings-btn {
    padding: 0;
    justify-content: center;
  }

  :deep(.el-menu) {
    border-right: none;

    .el-menu-item.is-active {
      background: linear-gradient(90deg, rgba(37, 99, 235, 0.3), transparent) !important;
      border-right: 3px solid #2563eb;
    }

    .el-sub-menu__title:hover,
    .el-menu-item:hover {
      background-color: rgba(255, 255, 255, 0.05) !important;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 设置弹层菜单（el-popover 内容，teleport 后 scoped 属性仍生效） */
.settings-menu {
  margin: -12px;

  &__item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    font-size: 13px;
    color: #334155;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: #f1f5f9;
    }

    &--danger {
      color: #dc2626;

      &:hover {
        background: #fef2f2;
      }
    }
  }
}
</style>
