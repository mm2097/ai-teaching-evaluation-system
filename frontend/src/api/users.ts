/**
 * 用户管理 API
 * 对应后端 /api/users
 */
import request from '@/utils/request'
import type { SystemUser, UserRole } from '@/types'

/** 后端原始用户字段(snake_case) */
interface UserRaw {
  id: number
  username: string
  name: string
  role: string
  department: string
  status: boolean
  created_at: string
}

/** 后端字段 → 前端字段 */
function mapUser(u: UserRaw): SystemUser {
  return {
    id: u.id,
    username: u.username,
    name: u.name,
    role: u.role as UserRole,
    department: u.department,
    status: u.status,
    createTime: u.created_at?.slice(0, 10) ?? '',
  }
}

export const userApi = {
  /** 列出全部用户 */
  list(): Promise<SystemUser[]> {
    return request.get<UserRaw[]>('/users').then((r) => r.data.map(mapUser))
  },

  /** 创建用户(默认密码 123456) */
  create(data: {
    username: string
    name: string
    role: UserRole
    department: string
    status: boolean
  }): Promise<SystemUser> {
    return request
      .post<UserRaw>('/users', { ...data, password: '123456' })
      .then((r) => mapUser(r.data))
  },

  /** 更新用户(只传要改的字段) */
  update(
    id: number,
    data: Partial<{ name: string; role: UserRole; department: string; status: boolean; password: string }>,
  ): Promise<SystemUser> {
    return request.put<UserRaw>(`/users/${id}`, data).then((r) => mapUser(r.data))
  },

  /** 删除用户 */
  remove(id: number): Promise<void> {
    return request.delete(`/users/${id}`).then(() => undefined)
  },
}
