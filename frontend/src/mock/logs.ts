/**
 * 系统日志(模块名与后端 sys_operation_log 保持一致)
 */

export interface MockLog {
  id: number
  username: string
  operation: string
  type: string
  ip: string
  time: string
}

export const systemLogs: MockLog[] = [
  { id: 1, username: 'admin', operation: '创建教师账号 teacher3（陈晓芳）', type: '用户管理', ip: '127.0.0.1', time: '2026-08-30 08:30:00' },
  { id: 2, username: 'admin', operation: '导入2025-2026-1学期计算机网络课程成绩数据', type: '数据管理', ip: '127.0.0.1', time: '2026-08-30 08:35:00' },
  { id: 3, username: 'teacher1', operation: '新增课程：计算机网络 CS3001', type: '课程管理', ip: '127.0.0.1', time: '2026-08-29 09:00:00' },
  { id: 4, username: 'teacher1', operation: '批量导入计算机网络试题 5 道', type: '题库管理', ip: '127.0.0.1', time: '2026-08-29 09:05:00' },
  { id: 5, username: 'teacher1', operation: '发布计算机网络单元测验1', type: '考试管理', ip: '127.0.0.1', time: '2026-08-29 09:15:00' },
  { id: 6, username: 'admin', operation: '修改教师李明远职称信息', type: '用户管理', ip: '127.0.0.1', time: '2026-08-28 16:00:00' },
  { id: 7, username: 'teacher2', operation: '新增课程：数据结构 CS3003', type: '课程管理', ip: '127.0.0.1', time: '2026-08-28 10:00:00' },
  { id: 8, username: 'admin', operation: '导入2025-2026-1学期操作系统课程成绩数据', type: '数据管理', ip: '127.0.0.1', time: '2026-08-27 14:00:00' },
]
