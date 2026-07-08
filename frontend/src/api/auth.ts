/**
 * 认证 API（模拟后端 /api/login 接口）
 */
import { delay } from '@/utils/auth'
import { mockUsers } from '@/mock'
import type { UserInfo, UserRole } from '@/types'

export const authApi = {
  /** 登录，成功返回 token + 用户信息 */
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
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
