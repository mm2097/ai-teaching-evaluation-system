/**
 * 系统日志
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
  { id: 1, username: 'admin', operation: '登录系统', type: '登录', ip: '10.10.1.100', time: '2026-03-20 08:30:00' },
  { id: 2, username: 'admin', operation: '导入学生数据（2024级新生名单.xlsx，180 条）', type: '数据操作', ip: '10.10.1.100', time: '2026-03-20 08:35:00' },
  { id: 3, username: 'teacher1', operation: '登录系统', type: '登录', ip: '10.10.1.201', time: '2026-03-20 09:00:00' },
  { id: 4, username: 'teacher1', operation: '查看班级学情看板（计科2401）', type: '查询', ip: '10.10.1.201', time: '2026-03-20 09:05:00' },
  { id: 5, username: 'teacher1', operation: '生成班级学情报告', type: '数据操作', ip: '10.10.1.201', time: '2026-03-20 09:15:00' },
  { id: 6, username: 'teacher1', operation: '导出成绩统计表', type: '导出', ip: '10.10.1.201', time: '2026-03-20 09:20:00' },
  { id: 7, username: 'admin', operation: '修改预警阈值参数', type: '配置修改', ip: '10.10.1.100', time: '2026-03-19 16:00:00' },
  { id: 8, username: 'stu01', operation: '登录系统', type: '登录', ip: '10.10.2.50', time: '2026-03-20 10:00:00' },
  { id: 9, username: 'stu01', operation: '提交答题（数据结构第三章练习）', type: '数据操作', ip: '10.10.2.50', time: '2026-03-20 10:30:00' },
  { id: 10, username: 'admin', operation: '新增用户 teacher5', type: '数据操作', ip: '10.10.1.100', time: '2026-03-18 14:00:00' },
]
