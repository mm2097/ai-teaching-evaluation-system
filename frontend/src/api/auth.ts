/**
 * 认证 API
 * 对应后端 /api/login
 */
import request from '@/utils/request'
import type { UserInfo, UserRole } from '@/types'

interface LoginResponse {
  token: string
  user: {
    id: number
    username: string
    name: string
    role: string
    department: string
  }
}

export const authApi = {
  /** 登录,成功返回 token + 用户信息 */
  login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    return request
      .post<LoginResponse>('/login', { username, password })
      .then((r) => ({
        token: r.data.token,
        user: {
          id: r.data.user.id,
          username: r.data.user.username,
          name: r.data.user.name,
          role: r.data.user.role as UserRole,
          department: r.data.user.department,
        },
      }))
  },
}
