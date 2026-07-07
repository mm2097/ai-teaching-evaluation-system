/**
 * 数据字典 API（模拟后端 /api/dict/* 接口）
 */
import { delay } from '@/utils/auth'
import {
  classes,
  courses,
  departments,
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

export async function fetchClasses(params?: { majorId?: number; deptId?: number; grade?: string }): Promise<ClassInfo[]> {
  await delay(200)
  return classes.filter((c) => {
    if (params?.deptId && c.deptId !== params.deptId) return false
    if (params?.majorId && c.majorId !== params.majorId) return false
    if (params?.grade && c.grade !== params.grade) return false
    return true
  })
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

export async function fetchCourses(params?: { teacherId?: number; deptId?: number; semesterId?: number }): Promise<Course[]> {
  await delay(200)
  return courses.filter((c) => {
    if (params?.teacherId && c.teacherId !== params.teacherId) return false
    if (params?.deptId && c.deptId !== params.deptId) return false
    if (params?.semesterId && c.semesterId !== params.semesterId) return false
    return true
  })
}
