/**
 * 用户管理 API（模拟后端 /api/users 接口）
 */
import { delay } from '@/utils/auth'
import { systemUserList } from '@/mock'
import type { SystemUser, UserRole } from '@/types'

/** 内存中的用户列表，支持演示 CRUD */
const users: SystemUser[] = systemUserList.map((u) => ({ ...u }))

export const userApi = {
  /** 列出全部用户 */
  async list(): Promise<SystemUser[]> {
    await delay(300)
    return [...users]
  },

  /** 创建用户（默认密码 123456） */
  async create(data: {
    username: string
    name: string
    role: UserRole
    department: string
    status: boolean
  }): Promise<SystemUser> {
    await delay(500)
    if (users.some((u) => u.username === data.username)) {
      throw new Error('账号已存在')
    }
    const newUser: SystemUser = {
      id: Date.now(),
      username: data.username,
      name: data.name,
      role: data.role,
      department: data.department,
      status: data.status,
      createTime: new Date().toISOString().slice(0, 10),
    }
    users.unshift(newUser)
    return { ...newUser }
  },

  /** 更新用户（只传要改的字段） */
  async update(
    id: number,
    data: Partial<{ name: string; role: UserRole; department: string; status: boolean; password: string }>,
  ): Promise<SystemUser> {
    await delay(300)
    const idx = users.findIndex((u) => u.id === id)
    if (idx < 0) throw new Error('用户不存在')
    users[idx] = { ...users[idx]!, ...data }
    return { ...users[idx]! }
  },

  /** 删除用户 */
  async remove(id: number): Promise<void> {
    await delay(300)
    const idx = users.findIndex((u) => u.id === id)
    if (idx < 0) throw new Error('用户不存在')
    users.splice(idx, 1)
  },
}
