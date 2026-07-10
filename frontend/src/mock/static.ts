/**
 * 静态字典数据（学院、专业、班级、学生、教师、课程、学期）
 * 湖南大学计算机学院场景
 */

/** 学院名称列表（后端返回 string[]） */
export const departments: string[] = [
  '信息科学与工程学院',
  '软件学院',
  '信息科学实验班',
]

/** 学期编码列表（后端返回 string[]） */
export const semesters: string[] = [
  '2024-2025-2',
  '2025-2026-1',
  '2025-2026-2',
]

/** 班级列表（后端格式） */
export interface MockClass {
  class_id: number
  class_name: string
  college: string
  enroll_year: number
}

export const classes: MockClass[] = [
  { class_id: 1, class_name: '计科2401', college: '信息科学与工程学院', enroll_year: 2024 },
  { class_id: 2, class_name: '计科2402', college: '信息科学与工程学院', enroll_year: 2024 },
  { class_id: 3, class_name: '软工2401', college: '软件学院', enroll_year: 2024 },
  { class_id: 4, class_name: '软工2402', college: '软件学院', enroll_year: 2024 },
  { class_id: 5, class_name: '信科2401', college: '信息科学实验班', enroll_year: 2024 },
  { class_id: 6, class_name: '信科2402', college: '信息科学实验班', enroll_year: 2024 },
]

/** 学生列表（后端格式） */
export interface MockStudent {
  student_id: number
  student_no: string
  real_name: string
  class_id: number
}

const studentRoster: [string, number][] = [
  // 计科2401 (class_id=1)
  ['陈思远', 1], ['林雨晴', 1], ['王浩然', 1], ['张雅琪', 1], ['刘嘉伟', 1],
  // 计科2402 (class_id=2)
  ['赵子墨', 2], ['钱欣怡', 2], ['孙博文', 2], ['周梓涵', 2], ['吴俊杰', 2],
  // 软工2401 (class_id=3)
  ['郑明轩', 3], ['冯佳怡', 3], ['陈天佑', 3], ['褚思颖', 3], ['卫子轩', 3],
  // 软工2402 (class_id=4)
  ['蒋雨涵', 4], ['沈一鸣', 4], ['韩诗韵', 4], ['杨思远', 4], ['朱嘉宁', 4],
  // 信科2401 (class_id=5)
  ['秦煜祺', 5], ['尤雅文', 5], ['许明远', 5], ['何林晓', 5], ['吕天成', 5],
  // 信科2402 (class_id=6)
  ['施嘉慧', 6], ['张毅峰', 6], ['孔梓萱', 6], ['曹锦程', 6], ['严思齐', 6],
]

export const students: MockStudent[] = studentRoster.map(([name, classId], i) => ({
  student_id: i + 1,
  student_no: `2024${String(classId).padStart(2, '0')}${String(i % 5 + 1).padStart(2, '0')}`,
  real_name: name,
  class_id: classId,
}))

/** 教师列表（后端格式） */
export interface MockTeacher {
  teacher_id: number
  teacher_no: string
  real_name: string
}

export const teachers: MockTeacher[] = [
  { teacher_id: 1, teacher_no: 'T001', real_name: '王建国' },
  { teacher_id: 2, teacher_no: 'T002', real_name: '李秀芳' },
  { teacher_id: 3, teacher_no: 'T003', real_name: '张伟' },
  { teacher_id: 4, teacher_no: 'T004', real_name: '刘洋' },
  { teacher_id: 5, teacher_no: 'T005', real_name: '陈静' },
]

/** 课程列表（后端格式） */
export interface MockCourse {
  course_id: number
  course_code: string
  course_name: string
  teacher_id: number
  semester: string
}

export const courses: MockCourse[] = [
  { course_id: 1, course_code: 'CS101', course_name: '数据结构与算法', teacher_id: 1, semester: '2025-2026-1' },
  { course_id: 2, course_code: 'CS102', course_name: '人工智能导论', teacher_id: 2, semester: '2025-2026-1' },
  { course_id: 3, course_code: 'CS103', course_name: '操作系统', teacher_id: 3, semester: '2025-2026-1' },
  { course_id: 4, course_code: 'CS104', course_name: '数据库原理', teacher_id: 4, semester: '2025-2026-1' },
]

/** 按班级查学生 */
export function studentsByClass(classId: number): MockStudent[] {
  return students.filter((s) => s.class_id === classId)
}

/** 按课程查班级（模拟教学班关系：课程 1→班级 1,2；课程 2→班级 3,4；课程 3→班级 5,6；课程 4→班级 1,3,5） */
export function classesByCourse(courseId: number): MockClass[] {
  const map: Record<number, number[]> = {
    1: [1, 2],
    2: [3, 4],
    3: [5, 6],
    4: [1, 3, 5],
  }
  const ids = map[courseId] || []
  return classes.filter((c) => ids.includes(c.class_id))
}
