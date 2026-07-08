/**
 * 认证 API
 * 对接后端 /api/login 接口，同时保留 mock 降级
 */
import type { UserInfo, UserRole } from '@/types'
import { mockUsers } from '@/mock'
import { delay } from '@/utils/auth'
import axios from 'axios'

export const authApi = {
  /** 登录，成功返回 token + 用户信息 */
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    // 尝试调用真实后端登录接口
    try {
      const res = await axios.post('/api/login', { username, password })
      if (res.data?.token) {
        return {
          token: res.data.token,
          user: {
            id: res.data.user?.id || 0,
            username: res.data.user?.username || username,
            name: res.data.user?.name || username,
            role: (res.data.user?.role as UserRole) || 'student',
            department: res.data.user?.department || '',
            deptId: res.data.user?.deptId,
            studentId: res.data.user?.studentId,
            studentNo: res.data.user?.studentNo,
            teacherId: res.data.user?.teacherId,
            classId: res.data.user?.classId,
          },
        }
      }
    } catch {
      // 后端不可用时降级为 mock 登录
    }

    // Mock 降级
    await delay(300)
    const found = mockUsers.find((u) => u.username === username && u.password === password)
    if (!found) {
      throw new Error('用户名或密码错误')
    }
    const { password: _pwd, ...user } = found
    return {
      token: `mock-token-${found.id}`,
      user: {
        id: user.id,
        username: user.username,
        name: user.name,
        role: user.role as UserRole,
        department: user.department,
        deptId: user.deptId,
        studentId: user.studentId,
        studentNo: user.studentNo,
        teacherId: user.teacherId,
        classId: user.classId,
      },
    }
  },
}
