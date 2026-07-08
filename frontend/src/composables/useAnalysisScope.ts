/**
 * AI 分析筛选 composable
 * 限定单课程、单班级维度，面向计算机学院
 */
import { computed, onMounted, ref, watch } from 'vue'
import { fetchClasses, fetchCourses, fetchSemesters, searchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { AnalysisQuery, LinkedStudentOption, TargetType, UserRole } from '@/types'
import { semesters as semesterDict } from '@/mock/dict'

/** 各角色允许的分析对象类型 */
const roleTargetTypes: Record<UserRole, TargetType[]> = {
  admin: ['student', 'class'],
  teacher: ['student', 'class'],
  student: ['student'],
}

function pickFirstOption<T extends { value: number }>(
  options: T[],
  current?: number,
): number | undefined {
  if (current && options.some((o) => o.value === current)) return current
  return options[0]?.value
}

function pickFirstStudent(
  students: LinkedStudentOption[],
  current?: number,
): number | undefined {
  if (current && students.some((s) => s.id === current)) return current
  const first = students[0]?.id
  return typeof first === 'number' ? first : undefined
}

export function useAnalysisScope(defaultTargetType?: TargetType) {
  const userStore = useUserStore()
  const role = computed(() => userStore.userInfo?.role || 'student')

  const allowedTargetTypes = computed(() => roleTargetTypes[role.value])

  const targetType = ref<TargetType>(
    defaultTargetType && allowedTargetTypes.value.includes(defaultTargetType)
      ? defaultTargetType
      : allowedTargetTypes.value[0]!,
  )
  const semesterId = ref(semesterDict.find((s) => s.isCurrent)?.id || 1)
  const classId = ref<number | undefined>()
  const courseId = ref<number | undefined>()
  const targetId = ref<number | undefined>()
  const studentList = ref<LinkedStudentOption[]>([])
  const studentLoading = ref(false)

  const semesterOptions = ref<{ label: string; value: number }[]>([])
  const classOptions = ref<{ label: string; value: number }[]>([])
  const courseOptions = ref<{ label: string; value: number }[]>([])

  const showDeptFilter = computed(() => false)
  const showClassFilter = computed(() => ['admin', 'teacher'].includes(role.value))
  const showCourseFilter = computed(() => true)
  const showTargetTypeFilter = computed(() => role.value !== 'student')
  const showStudentPicker = computed(() => targetType.value === 'student' && role.value !== 'student')

  async function loadStudentOptions(): Promise<void> {
    studentLoading.value = true
    try {
      const students = await searchStudents({
        classId: classId.value,
        courseId: courseId.value,
        deptId: 1,
        teacherId: role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined,
      })
      studentList.value = students.map((s) => ({
        id: s.id,
        studentName: s.studentName,
        studentNo: s.studentNo,
      }))
      targetId.value = pickFirstStudent(studentList.value, targetId.value)
    } finally {
      studentLoading.value = false
    }
  }

  async function loadOptions(preserveTarget = false): Promise<void> {
    const sems = await fetchSemesters()
    semesterOptions.value = sems.map((s) => ({ label: s.semesterName, value: s.id }))

    if (role.value === 'teacher') {
      const teacherId = userStore.userInfo?.teacherId
      const courses = await fetchCourses({ teacherId, semesterId: semesterId.value, deptId: 1 })
      courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
      courseId.value = pickFirstOption(courseOptions.value, courseId.value)

      const classes = await fetchClasses({
        deptId: 1,
        courseId: courseId.value,
        teacherId,
      })
      classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
      classId.value = pickFirstOption(classOptions.value, classId.value)
    } else if (role.value === 'admin') {
      const courses = await fetchCourses({ deptId: 1, semesterId: semesterId.value })
      courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
      courseId.value = pickFirstOption(courseOptions.value, courseId.value)

      const classes = await fetchClasses({
        deptId: 1,
        courseId: courseId.value,
      })
      classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
      classId.value = pickFirstOption(classOptions.value, classId.value)
    } else if (role.value === 'student') {
      const studentClassId = userStore.userInfo?.classId
      const courses = studentClassId
        ? await fetchCourses({ deptId: 1, semesterId: semesterId.value, classId: studentClassId })
        : []
      courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
      courseId.value = pickFirstOption(courseOptions.value, courseId.value)
      classId.value = studentClassId
      targetId.value = userStore.userInfo?.studentId
    }

    if (!preserveTarget) {
      if (targetType.value === 'student') {
        if (role.value === 'student') {
          targetId.value = userStore.userInfo?.studentId
        } else {
          await loadStudentOptions()
        }
      } else if (targetType.value === 'class') {
        targetId.value = classId.value
      }
    }
  }

  watch(targetType, async () => {
    targetId.value = undefined
    await loadOptions()
  })

  watch([semesterId, courseId], async () => {
    await loadOptions()
  })

  watch(classId, async () => {
    if (targetType.value === 'student' && role.value !== 'student') {
      targetId.value = undefined
      await loadStudentOptions()
    } else if (targetType.value === 'class') {
      targetId.value = classId.value
    }
  })

  onMounted(async () => {
    if (role.value === 'student') {
      targetType.value = 'student'
      targetId.value = userStore.userInfo?.studentId
    }
    await loadOptions(true)
  })

  const queryParams = computed<AnalysisQuery>(() => ({
    targetType: targetType.value,
    targetId: targetType.value === 'class' ? (targetId.value ?? classId.value) : targetId.value,
    semesterId: semesterId.value,
    deptId: 1,
    classId: classId.value,
    courseId: courseId.value,
  }))

  return {
    role,
    allowedTargetTypes,
    targetType,
    semesterId,
    classId,
    courseId,
    targetId,
    studentList,
    studentLoading,
    semesterOptions,
    classOptions,
    courseOptions,
    showDeptFilter,
    showClassFilter,
    showCourseFilter,
    showTargetTypeFilter,
    showStudentPicker,
    queryParams,
    loadOptions,
    loadStudentOptions,
  }
}
