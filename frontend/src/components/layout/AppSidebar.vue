<!--
  侧边栏菜单组件
  根据用户角色动态渲染可见菜单，支持折叠模式
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import * as Icons from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

/** 当前激活菜单路径 */
const activeMenu = computed(() => route.path)

/**
 * 根据图标名称获取组件
 * @param iconName 图标名称字符串
 */
function getIcon(iconName: string) {
  return (Icons as Record<string, unknown>)[iconName] || Icons.Menu
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
</style>
