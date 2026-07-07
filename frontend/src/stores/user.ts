/**
 * 用户状态管理 Store
 * 负责登录态、用户信息、权限相关状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UserInfo, UserRole } from '@/types'
import { RoleLabels } from '@/types'
import { authApi } from '@/api/auth'
import { clearAuth, getStoredUser, getToken, setStoredUser, setToken } from '@/utils/auth'
import { filterMenusByRole, menuList } from '@/config/menu'

export const useUserStore = defineStore('user', () => {
  /** 当前登录用户信息 */
  const userInfo = ref<UserInfo | null>(null)

  /** 是否已登录 */
  const isLoggedIn = computed(() => !!userInfo.value)

  /** 当前用户角色 */
  const userRole = computed(() => userInfo.value?.role)

  /** 角色中文名 */
  const roleLabel = computed(() => {
    if (!userInfo.value) return ''
    return RoleLabels[userInfo.value.role]
  })

  /** 当前角色可见菜单 */
  const visibleMenus = computed(() => {
    if (!userInfo.value) return []
    return filterMenusByRole(menuList, userInfo.value.role)
  })

  /**
   * 用户登录
   * @param username 账号
   * @param password 密码
   */
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const { token, user: info } = await authApi.login(username, password)
      userInfo.value = info
      setToken(token)
      setStoredUser(JSON.stringify(info))
      return true
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '登录失败')
      return false
    }
  }

  /**
   * 退出登录，清除本地状态
   */
  function logout(): void {
    userInfo.value = null
    clearAuth()
  }

  /**
   * 从本地存储恢复登录态（页面刷新时）
   */
  function restoreSession(): void {
    const token = getToken()
    const stored = getStoredUser()
    if (token && stored) {
      try {
        userInfo.value = JSON.parse(stored) as UserInfo
      } catch {
        clearAuth()
      }
    }
  }

  /**
   * 判断当前用户是否拥有指定角色之一
   * @param roles 允许的角色列表
   */
  function hasRole(roles: UserRole[]): boolean {
    if (!userInfo.value) return false
    return roles.includes(userInfo.value.role)
  }

  return {
    userInfo,
    isLoggedIn,
    userRole,
    roleLabel,
    visibleMenus,
    login,
    logout,
    restoreSession,
    hasRole,
  }
})
