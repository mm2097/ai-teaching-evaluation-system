import request from '@/utils/request'

export interface StudentScoreDetail {
  batchName: string
  batchType: number
  score: number
  weight: number
  isPass: boolean
}

export interface StudentCourseScore {
  courseId: number
  courseName: string
  totalScore: number
  details: StudentScoreDetail[]
}

interface ScoreDetailResponse {
  batch_name?: string
  batch_type?: number
  batch_weight?: number
  score?: number
  is_pass?: number
}

interface CourseScoreResponse {
  course_id: number
  course_name?: string
  total_score?: number
  details?: ScoreDetailResponse[]
}

export async function fetchStudentScores(studentId: number): Promise<StudentCourseScore[]> {
  const res = await request.get(`/v1/score-records/student/${studentId}`)
  const courses = (res.data?.courses ?? []) as CourseScoreResponse[]
  return courses.map((course) => ({
    courseId: course.course_id,
    courseName: course.course_name || `课程 ${course.course_id}`,
    totalScore: Number(course.total_score ?? 0),
    details: (course.details ?? []).map((detail) => ({
      batchName: detail.batch_name || '未命名考核',
      batchType: Number(detail.batch_type ?? 0),
      score: Number(detail.score ?? 0),
      weight: Number(detail.batch_weight ?? 0),
      isPass: detail.is_pass === 1,
    })),
  }))
}