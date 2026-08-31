/**
 * 用户管理 API（调用真实后端 /api/users）
 */
import type { SystemUser, UserRole } from '@/types'
import request from '@/utils/request'

interface RoleResponse {
  role_id: number
  role_code: UserRole
}

interface UserResponse {
  user_id: number
  username: string
  real_name: string
  role_id: number
  role_code?: UserRole
  department?: string
  class_id?: number | null
  class_name?: string
  status: number
  create_time?: string
}

interface UserUpdatePayload {
  real_name?: string
  role_id?: number
  status?: number
  password?: string
  college?: string
  class_id?: number | null
}

let roleIdMap: Partial<Record<UserRole, number>> = {}

async function getRoleId(role: UserRole): Promise<number> {
  if (!roleIdMap[role]) {
    const response = await request.get('/roles')
    roleIdMap = Object.fromEntries(
      (response.data as RoleResponse[]).map((item) => [item.role_code, item.role_id]),
    ) as Partial<Record<UserRole, number>>
  }
  const roleId = roleIdMap[role]
  if (!roleId) {
    throw new Error(`系统未配置角色：${role}`)
  }
  return roleId
}

export const userApi = {
  /** 列出用户，可按角色、学生班级、账号状态筛选 */
  async list(params?: { classId?: number; role?: UserRole | ''; status?: number }): Promise<SystemUser[]> {
    const q: Record<string, string | number> = {}
    if (params?.classId) q.class_id = params.classId
    if (params?.role) q.role_code = params.role
    if (params?.status !== undefined && params.status !== null) q.status = params.status
    const res = await request.get('/users', { params: q })
    return (res.data as UserResponse[]).map(mapUser)
  },

  /** 创建用户（默认密码 123456，学生须传班级） */
  async create(data: {
    username: string
    name: string
    role: UserRole
    status: boolean
    college?: string
    classId?: number | null
  }): Promise<SystemUser> {
    const roleId = await getRoleId(data.role)
    const res = await request.post('/users', {
      username: data.username,
      password: '123456',
      real_name: data.name,
      role_id: roleId,
      status: data.status ? 1 : 0,
      college: data.college,
      class_id: data.role === 'student' ? data.classId : undefined,
    })
    return mapUser(res.data)
  },

  /** 更新用户（只传要改的字段） */
  async update(
    id: number,
    data: Partial<{ name: string; role: UserRole; status: boolean; password: string; college: string; classId: number | null }>,
  ): Promise<SystemUser> {
    const payload: UserUpdatePayload = {}
    if (data.name !== undefined) payload.real_name = data.name
    if (data.role !== undefined) {
      payload.role_id = await getRoleId(data.role)
    }
    if (data.status !== undefined) payload.status = data.status ? 1 : 0
    if (data.password !== undefined) payload.password = data.password
    if (data.college !== undefined) payload.college = data.college
    if (data.classId !== undefined) payload.class_id = data.classId
    const res = await request.put(`/users/${id}`, payload)
    return mapUser(res.data)
  },

  /** 删除用户 */
  async remove(id: number): Promise<void> {
    await request.delete(`/users/${id}`)
  },
}

function mapUser(raw: UserResponse): SystemUser {
  const roleMap: Record<number, UserRole> = { 1: 'admin', 2: 'teacher', 3: 'student' }
  return {
    id: raw.user_id,
    username: raw.username,
    name: raw.real_name,
    role: raw.role_code || roleMap[raw.role_id] || 'student',
    department: raw.department || '',
    classId: raw.class_id ?? null,
    className: raw.class_name || '',
    status: raw.status === 1,
    createTime: raw.create_time?.slice(0, 10) ?? '',
  }
}
