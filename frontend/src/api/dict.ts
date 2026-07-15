/**
 * 数据字典 API（调用真实后端 /api/v1/* 接口）
 */
import request from '@/utils/request'
import type { ClassInfo, Course, Department, Major, Semester, Student, Teacher } from '@/types'

/* ---------- 工具：字段映射 ---------- */

function mapCourse(raw: any): Course {
  return {
    id: raw.course_id,
    courseNo: raw.course_code,
    courseName: raw.course_name,
    deptId: 0,                    // 后端无 deptId，用 college 名称替代
    teacherId: raw.teacher_id,
    semesterId: 0,                // 后端无 semesterId
    semesterCode: raw.semester,
    semesterName: raw.semester,
  }
}

function mapTeacher(raw: any): Teacher {
  return {
    id: raw.teacher_id,
    teacherNo: raw.teacher_no,
    teacherName: raw.real_name,
    deptId: 0,
  }
}

function mapStudent(raw: any): Student {
  return {
    id: raw.student_id,
    studentNo: raw.student_no,
    studentName: raw.real_name,
    classId: raw.class_id,
    majorId: 0,
    deptId: 0,
    grade: '',
  }
}

function mapClass(raw: any): ClassInfo {
  return {
    id: raw.class_id,
    classCode: '',
    className: raw.class_name,
    majorId: 0,
    majorName: raw.major || '',
    deptId: 0,
    grade: raw.grade || '',
  }
}

/* ---------- 院系 ---------- */

export async function fetchDepartments(): Promise<Department[]> {
  const res = await request.get('/v1/dictionaries/departments')
  const names: string[] = res.data
  return names.map((name, i) => ({
    id: i + 1,
    deptCode: '',
    deptName: name,
  }))
}

/* ---------- 专业（暂无明细表，从班级 college 聚合） ---------- */

export async function fetchMajors(params?: {
  deptId?: number
  semesterCode?: string
  grade?: string
  teacherId?: number
} | number): Promise<Major[]> {
  const q: any = {}
  if (typeof params === 'object' && params) {
    if (params.semesterCode) q.semester = params.semesterCode
    if (params.grade) q.grade = params.grade
  }
  const res = await request.get('/v1/dictionaries/majors', { params: q })
  return (res.data as any[]).map((m: any) => ({
    id: m.id,
    majorCode: '',
    majorName: m.majorName,
    deptId: 0,
  }))
}

export async function fetchDashboardGrades(params?: {
  deptId?: number
  semesterCode?: string
  majorId?: number
  majorName?: string
  teacherId?: number
}): Promise<string[]> {
  const q: any = {}
  if (params?.semesterCode) q.semester = params.semesterCode
  if (params?.majorName) q.major = params.majorName
  const res = await request.get('/v1/dictionaries/grades', { params: q })
  return res.data as string[]
}

/* ---------- 班级 ---------- */

export async function fetchClasses(params?: {
  majorId?: number
  deptId?: number
  grade?: string
  courseId?: number
  teacherId?: number
  semesterCode?: string
}): Promise<ClassInfo[]> {
  const q: any = {}
  // 后端按 college 名称筛选，暂不支持 deptId/majorId 映射
  if (params?.courseId) q.course_id = params.courseId   // 暂不支持，后端无此参数
  const res = await request.get('/v1/classes', { params: q })
  return (res.data as any[]).map(mapClass)
}

/* ---------- 学期 ---------- */

export async function fetchSemesters(): Promise<Semester[]> {
  const res = await request.get('/v1/dictionaries/semesters')
  const codes: string[] = res.data
  return codes.map((code, i) => ({
    id: i + 1,
    semesterCode: code,
    semesterName: code,
    isCurrent: code === '2025-2026-1',
  }))
}

/* ---------- 学生 ---------- */

export async function fetchStudents(params?: {
  classId?: number
  deptId?: number
  majorId?: number
}): Promise<Student[]> {
  const q: any = {}
  if (params?.classId) q.class_id = params.classId
  const res = await request.get('/v1/students', { params: q })
  return (res.data as any[]).map(mapStudent)
}

/* ---------- 教师 ---------- */

export async function fetchTeachers(deptId?: number): Promise<Teacher[]> {
  const q: any = {}
  // 后端暂不支持按 deptId 筛选，按 college 名称
  const res = await request.get('/v1/teachers', { params: q })
  return (res.data as any[]).map(mapTeacher)
}

/* ---------- 课程 ---------- */

export async function fetchCourses(params?: {
  teacherId?: number
  deptId?: number
  semesterId?: number
  semesterCode?: string
  classId?: number
  majorId?: number
  grade?: string
}): Promise<Course[]> {
  const q: any = {}
  if (params?.teacherId) q.teacher_id = params.teacherId
  if (params?.semesterCode) q.semester = params.semesterCode
  // deptId / semesterId / classId / majorId / grade 暂不支持
  const res = await request.get('/v1/courses', { params: q })
  return (res.data as any[]).map(mapCourse)
}

/* ---------- 学生搜索 ---------- */

export async function searchStudents(params?: {
  name?: string
  studentNo?: string
  classId?: number
  courseId?: number
  teacherId?: number
  deptId?: number
}): Promise<Student[]> {
  const q: any = {}
  if (params?.classId) q.class_id = params.classId
  if (params?.courseId) q.course_id = params.courseId
  // 模糊搜索：拼 keyword
  const keyword = [params?.name, params?.studentNo].filter(Boolean).join(' ')
  if (keyword) q.keyword = keyword
  const res = await request.get('/v1/students', { params: q })
  return (res.data as any[]).map(mapStudent)
}
