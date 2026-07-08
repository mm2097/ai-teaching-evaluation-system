/**
 * 数据字典 API（模拟后端 /api/dict/* 接口）
 */
import { delay } from '@/utils/auth'
import {
  classes,
  courseClassRelations,
  courses,
  departments,
  getClassesByTeacher,
  isStudentEnrolled,
  majors,
  semesters,
  students,
  teachers,
} from '@/mock/dict'
import type { ClassInfo, Course, Department, Major, Semester, Student, Teacher } from '@/types'

export async function fetchDepartments(): Promise<Department[]> {
  await delay(200)
  return departments
}

export async function fetchMajors(deptId?: number): Promise<Major[]> {
  await delay(200)
  if (!deptId) return majors
  return majors.filter((m) => m.deptId === deptId)
}

export async function fetchClasses(params?: {
  majorId?: number
  deptId?: number
  grade?: string
  courseId?: number
  teacherId?: number
}): Promise<ClassInfo[]> {
  await delay(200)
  let result = classes.filter((c) => {
    if (params?.deptId && c.deptId !== params.deptId) return false
    if (params?.majorId && c.majorId !== params.majorId) return false
    if (params?.grade && c.grade !== params.grade) return false
    return true
  })

  if (params?.courseId) {
    const classIds = courseClassRelations
      .filter((r) => r.courseId === params.courseId)
      .map((r) => r.classId)
    result = result.filter((c) => classIds.includes(c.id))
  }

  if (params?.teacherId) {
    const teacherClassIds = new Set(getClassesByTeacher(params.teacherId).map((c) => c.id))
    result = result.filter((c) => teacherClassIds.has(c.id))
  }

  return result
}

export async function fetchSemesters(): Promise<Semester[]> {
  await delay(200)
  return semesters
}

export async function fetchStudents(params?: { classId?: number; deptId?: number; majorId?: number }): Promise<Student[]> {
  await delay(200)
  return students.filter((s) => {
    if (params?.classId && s.classId !== params.classId) return false
    if (params?.deptId && s.deptId !== params.deptId) return false
    if (params?.majorId && s.majorId !== params.majorId) return false
    return true
  })
}

export async function fetchTeachers(deptId?: number): Promise<Teacher[]> {
  await delay(200)
  if (!deptId) return teachers
  return teachers.filter((t) => t.deptId === deptId)
}

export async function fetchCourses(params?: {
  teacherId?: number
  deptId?: number
  semesterId?: number
  classId?: number
}): Promise<Course[]> {
  await delay(200)
  let result = courses.filter((c) => {
    if (params?.teacherId && c.teacherId !== params.teacherId) return false
    if (params?.deptId && c.deptId !== params.deptId) return false
    if (params?.semesterId && c.semesterId !== params.semesterId) return false
    return true
  })

  if (params?.classId) {
    const courseIds = courseClassRelations
      .filter((r) => r.classId === params.classId)
      .map((r) => r.courseId)
    result = result.filter((c) => courseIds.includes(c.id))
  }

  return result
}

/** 学生模糊搜索（姓名、学号分开匹配，支持课程/教师范围限定） */
export async function searchStudents(params?: {
  name?: string
  studentNo?: string
  classId?: number
  courseId?: number
  teacherId?: number
  deptId?: number
}): Promise<Student[]> {
  await delay(200)
  let result = students.filter((s) => {
    if (params?.deptId && s.deptId !== params.deptId) return false
    if (params?.classId && s.classId !== params.classId) return false
    return true
  })

  if (params?.courseId) {
    result = result.filter((s) => isStudentEnrolled(s.id, params.courseId!))
  }

  if (params?.teacherId) {
    const teacherCourseIds = courses
      .filter((c) => c.teacherId === params.teacherId)
      .map((c) => c.id)
    result = result.filter((s) =>
      teacherCourseIds.some((cid) => isStudentEnrolled(s.id, cid)),
    )
    if (params.courseId && !teacherCourseIds.includes(params.courseId)) {
      result = []
    }
  }

  if (params?.name?.trim()) {
    const nameKw = params.name.trim().toLowerCase()
    result = result.filter((s) => s.studentName.toLowerCase().includes(nameKw))
  }

  if (params?.studentNo?.trim()) {
    const noKw = params.studentNo.trim().toLowerCase()
    result = result.filter((s) => s.studentNo.toLowerCase().includes(noKw))
  }

  return result
}
