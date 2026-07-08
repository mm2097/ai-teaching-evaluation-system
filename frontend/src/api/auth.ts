/**
 * 认证 API（调用真实后端 /api/login，失败时降级为 mock）
 */
import request from '@/utils/request'
import type { UserInfo, UserRole } from '@/types'
import { mockUsers } from '@/mock'
import { delay } from '@/utils/auth'

export const authApi = {
  /** 登录，成功返回 token + 用户信息 */
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    // 1. 尝试调用真实后端登录接口
    try {
      const res = await request.post('/login', { username, password })
      const data = res.data
      if (data?.token) {
        const roleMap: Record<string, UserRole> = { admin: 'admin', teacher: 'teacher', student: 'student' }
        return {
          token: data.token,
          user: {
            id: data.user.user_id,
            username: data.user.username,
            name: data.user.real_name,
            role: roleMap[data.user.role_code] ?? 'student',
            department: data.user.department ?? '',
          },
        }
      }
    } catch {
      // 后端不可用时降级为 mock 登录
    }

    // 2. Mock 降级
    await delay(300)
    const found = mockUsers.find((u) => u.username === username && u.password === password)
    if (!found) {
      throw new Error('用户名或密码错误')
    }
    const { password: _pwd, ...user } = found
    return {
      token: 'mock-token-' + Date.now(),
      user,
    }
  },
}
