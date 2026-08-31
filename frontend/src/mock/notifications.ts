/**
 * 消息通知 mock（与后端 /v1/notifications 对齐）
 * 学生角色（USE_MOCK=true 时）铃铛读取该列表
 */
export interface MockNotification {
  id: number
  courseId?: number
  courseName?: string
  warningId?: number
  title: string
  content: string
  isRead: boolean
  createTime: string
}

let nextNotificationId = 100

const notifications: MockNotification[] = [
  {
    id: 1, courseId: 1, courseName: '计算机网络', warningId: 1,
    title: '学情预警：成绩下滑',
    content: '您在《计算机网络》课程中触发学情预警（中风险）：期末成绩较平时大幅下滑。请及时关注学习状态，并与任课老师沟通。',
    isRead: false, createTime: '2026-03-18 09:00',
  },
  {
    id: 2, courseId: 1, courseName: '计算机网络', warningId: undefined,
    title: '考试成绩发布提醒',
    content: '《计算机网络》期中考试成绩已发布，请登录系统查看个人成绩档案。',
    isRead: true, createTime: '2026-03-15 10:30',
  },
]

export function listNotifications(): MockNotification[] {
  return notifications
}

export function markRead(id: number): MockNotification | undefined {
  const item = notifications.find((n) => n.id === id)
  if (item) item.isRead = true
  return item
}

export function markAllRead(): number {
  const updated = notifications.filter((n) => !n.isRead).length
  notifications.forEach((n) => { n.isRead = true })
  return updated
}

export function addNotification(
  input: Omit<MockNotification, 'id' | 'isRead' | 'createTime'>,
): MockNotification {
  const item: MockNotification = {
    ...input,
    id: nextNotificationId++,
    isRead: false,
    createTime: new Date().toISOString().slice(0, 16).replace('T', ' '),
  }
  notifications.unshift(item)
  return item
}
