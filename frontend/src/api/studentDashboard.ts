import request from '@/utils/request'

export interface StudentDashboardCourse {
  id: number
  name: string
  teacher: string
  score: number | null
  avgScore: number | null
  rank: number | null
  rankText: string
  progress: number | null
}

export interface StudentDashboardOverview {
  student: {
    id: number
    studentNo: string
    name: string
    classId: number
    className: string
    college: string
  }
  summary: {
    courseCount: number
    averageScore: number | null
    attendanceRate: number | null
    pendingQuizCount: number
    weakKnowledgeCount: number
    classRank: number | null
    classRankText: string
    classStudentCount: number
  }
  courses: StudentDashboardCourse[]
}

export async function fetchStudentDashboardOverview(): Promise<StudentDashboardOverview> {
  const response = await request.get<StudentDashboardOverview>('/v1/dashboard/student-overview')
  return response.data
}
