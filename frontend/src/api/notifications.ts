/**
 * 消息通知 API（学生接收教师发送的预警通知）
 */
import request from '@/utils/request'
import type { NotificationItem } from '@/types'

/** 获取当前学生的站内通知（最新 50 条） */
export async function fetchNotifications(): Promise<NotificationItem[]> {
  try {
    const res = await request.get('/v1/notifications')
    return res.data
  } catch {
    return []
  }
}

/** 将单条通知标记为已读 */
export async function markNotificationRead(id: number): Promise<NotificationItem> {
  const res = await request.put(`/v1/notifications/${id}/read`)
  return res.data
}

/** 将全部通知标记为已读，返回更新条数 */
export async function markAllNotificationsRead(): Promise<number> {
  try {
    const res = await request.put('/v1/notifications/read-all')
    return res.data?.updated ?? 0
  } catch {
    return 0
  }
}
