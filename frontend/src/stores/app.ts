/**
 * 应用全局状态 Store
 * 管理侧边栏折叠、页面加载等 UI 状态
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  /** 侧边栏是否折叠 */
  const sidebarCollapsed = ref(false)

  /** 全局页面加载状态 */
  const pageLoading = ref(false)

  /**
   * 切换侧边栏折叠状态
   */
  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  /**
   * 设置页面加载状态
   * @param loading 是否加载中
   */
  function setPageLoading(loading: boolean): void {
    pageLoading.value = loading
  }

  return {
    sidebarCollapsed,
    pageLoading,
    toggleSidebar,
    setPageLoading,
  }
})
