/**
 * 本地存储工具函数
 * 封装 localStorage 读写，统一管理 Token 与用户信息
 */

const TOKEN_KEY = 'teaching_eval_token'
const USER_KEY = 'teaching_eval_user'

/**
 * 获取 Token
 * @returns Token 字符串或 null
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 设置 Token
 * @param token 认证令牌
 */
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 移除 Token
 */
export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * 获取缓存的用户信息 JSON
 */
export function getStoredUser(): string | null {
  return localStorage.getItem(USER_KEY)
}

/**
 * 缓存用户信息
 * @param userJson 用户信息 JSON 字符串
 */
export function setStoredUser(userJson: string): void {
  localStorage.setItem(USER_KEY, userJson)
}

/**
 * 清除所有登录态
 */
export function clearAuth(): void {
  removeToken()
  localStorage.removeItem(USER_KEY)
}

/**
 * 模拟延迟，用于演示异步请求效果
 * @param ms 延迟毫秒数
 */
export function delay(ms = 500): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 根据分数获取评价等级
 * @param score 综合得分
 */
export function scoreToGrade(score: number): string {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '中等'
  if (score >= 60) return '合格'
  return '不合格'
}

/**
 * 获取预警等级对应的 Element Tag 类型
 * @param level 预警等级
 */
export function warningLevelType(level: string): 'danger' | 'warning' | 'info' {
  const map: Record<string, 'danger' | 'warning' | 'info'> = {
    高: 'danger',
    中: 'warning',
    低: 'info',
  }
  return map[level] || 'info'
}

/**
 * 获取评价等级对应的 Tag 类型
 * @param grade 评价等级
 */
export function evalGradeType(grade: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'primary' | 'warning' | 'info' | 'danger'> = {
    优秀: 'success',
    良好: 'primary',
    中等: 'warning',
    合格: 'info',
    不合格: 'danger',
  }
  return map[grade] || 'info'
}
