/**
 * 用户管理 API（调用真实后端 /api/users）
 */
import type { SystemUser, UserRole } from '@/types'
import request from '@/utils/request'

export const userApi = {
  /** 列出全部用户 */
  async list(): Promise<SystemUser[]> {
    const res = await request.get('/users')
    return (res.data as any[]).map(mapUser)
  },

  /** 创建用户（默认密码 123456） */
  async create(data: {
    username: string
    name: string
    role: UserRole
    department: string
    status: boolean
  }): Promise<SystemUser> {
    const roleMap: Record<UserRole, number> = { admin: 1, teacher: 2, student: 3 }
    const res = await request.post('/users', {
      username: data.username,
      password: '123456',
      real_name: data.name,
      role_id: roleMap[data.role],
      status: data.status ? 1 : 0,
    })
    return mapUser(res.data)
  },

  /** 更新用户（只传要改的字段） */
  async update(
    id: number,
    data: Partial<{ name: string; role: UserRole; department: string; status: boolean; password: string }>,
  ): Promise<SystemUser> {
    const payload: Record<string, any> = {}
    if (data.name !== undefined) payload.real_name = data.name
    if (data.role !== undefined) {
      const roleMap: Record<UserRole, number> = { admin: 1, teacher: 2, student: 3 }
      payload.role_id = roleMap[data.role]
    }
    if (data.status !== undefined) payload.status = data.status ? 1 : 0
    if (data.password !== undefined) payload.password = data.password
    const res = await request.put(`/users/${id}`, payload)
    return mapUser(res.data)
  },

  /** 删除用户 */
  async remove(id: number): Promise<void> {
    await request.delete(`/users/${id}`)
  },
}

function mapUser(raw: any): SystemUser {
  const roleMap: Record<number, UserRole> = { 1: 'admin', 2: 'teacher', 3: 'student' }
  return {
    id: raw.user_id,
    username: raw.username,
    name: raw.real_name,
    role: roleMap[raw.role_id] ?? 'student',
    department: '',
    status: raw.status === 1,
    createTime: raw.create_time?.slice(0, 10) ?? '',
  }
}
