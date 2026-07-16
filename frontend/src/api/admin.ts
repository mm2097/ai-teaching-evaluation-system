import request from '@/utils/request'

export interface AdminOverview {
  summary: {
    totalUsers: number
    activeUsers: number
    disabledUsers: number
    roleCount: number
  }
  roleCounts: {
    admin: number
    teacher: number
    student: number
  }
  recentOperations: {
    id: number
    username: string
    module: string
    operation: string
    content: string
    time: string
  }[]
  services: {
    backend: 'online' | 'degraded' | 'offline'
    database: 'online' | 'degraded' | 'offline'
    aiService: 'online' | 'degraded' | 'offline'
  }
  system: {
    appName: string
    version: string
    environment: string
    currentAdmin: string
    updatedAt: string
  }
}

export async function fetchAdminOverview(): Promise<AdminOverview> {
  const response = await request.get('/v1/admin/overview')
  return response.data as AdminOverview
}
