/**
 * 认证 API（调用真实后端 /api/login）
 */
import request from '@/utils/request'
import type { UserInfo, UserRole } from '@/types'

export const authApi = {
  /** 登录，成功返回 token + 用户信息 */
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    const res = await request.post('/login', { username, password })  // → POST /api/login
    const data = res.data
    const roleMap: Record<string, UserRole> = { admin: 'admin', teacher: 'teacher', student: 'student' }
    return {
      token: data.token,
      user: {
        id: data.user.user_id,
        username: data.user.username,
        name: data.user.real_name,
        role: roleMap[data.user.role_code] ?? 'student',
        department: '',
        studentId: data.user.student_id ?? undefined,
        studentNo: data.user.student_no ?? undefined,
        classId: data.user.class_id ?? undefined,
      },
    }
  },
}
