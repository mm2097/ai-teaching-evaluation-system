/**
 * AI 分析筛选 composable
 * 限定单课程、单班级维度，面向计算机学院
 */
import { computed, onMounted, ref, watch } from 'vue'
import { fetchClasses, fetchCourses, fetchSemesters, searchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { AnalysisQuery, TargetType, UserRole } from '@/types'
import { semesters as semesterDict } from '@/mock/dict'

/** 各角色允许的分析对象类型 */
const roleTargetTypes: Record<UserRole, TargetType[]> = {
  admin: ['student', 'class'],
  teacher: ['student', 'class'],
  student: ['student'],
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
  const studentKeyword = ref('')

  const semesterOptions = ref<{ label: string; value: number }[]>([])
  const classOptions = ref<{ label: string; value: number }[]>([])
  const courseOptions = ref<{ label: string; value: number }[]>([])
  const targetOptions = ref<{ label: string; value: number }[]>([])

  const showDeptFilter = computed(() => false)
  const showClassFilter = computed(() => ['admin', 'teacher'].includes(role.value))
  const showCourseFilter = computed(() => role.value !== 'student')
  const showTargetTypeFilter = computed(() => role.value !== 'student')
  const showStudentPicker = computed(() => targetType.value === 'student' && role.value !== 'student')

  /** 并发锁，防止 loadOptions 重入 */
  let loadingPromise: Promise<void> | null = null

  async function loadStudentOptions(keyword?: string): Promise<void> {
    const students = await searchStudents({
      keyword: keyword ?? studentKeyword.value,
      classId: classId.value,
      courseId: courseId.value,
      teacherId: role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined,
    })
    targetOptions.value = students.map((s) => ({
      label: `${s.studentName} (${s.studentNo})`,
      value: s.id,
    }))
    if (!targetId.value && targetOptions.value.length) {
      targetId.value = targetOptions.value[0]!.value
    }
  }

  async function loadOptions(): Promise<void> {
    // 防止并发重入
    if (loadingPromise) return loadingPromise

    loadingPromise = (async () => {
      const sems = await fetchSemesters()
      semesterOptions.value = sems.map((s) => ({ label: s.semesterName, value: s.id }))

      if (role.value === 'teacher') {
        const teacherId = userStore.userInfo?.teacherId
        const courses = await fetchCourses({ teacherId, semesterId: semesterId.value })
        courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
        if (!courseId.value && courseOptions.value.length) {
          courseId.value = courseOptions.value[0]!.value
        }
        const classes = await fetchClasses({ deptId: 1 })
        classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
        if (!classId.value && classOptions.value.length) {
          classId.value = classOptions.value[0]!.value
        }
      } else if (role.value === 'admin') {
        const classes = await fetchClasses({ deptId: 1 })
        classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
        if (!classId.value && classOptions.value.length) {
          classId.value = classOptions.value[0]!.value
        }
        const courses = await fetchCourses({ deptId: 1, semesterId: semesterId.value })
        courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
        if (!courseId.value && courseOptions.value.length) {
          courseId.value = courseOptions.value[0]!.value
        }
      }

      if (targetType.value === 'student') {
        if (role.value === 'student') {
          targetId.value = userStore.userInfo?.studentId
        } else {
          await loadStudentOptions()
        }
      } else if (targetType.value === 'class') {
        targetOptions.value = classOptions.value
        if (!targetId.value && targetOptions.value.length) {
          targetId.value = targetOptions.value[0]!.value
        }
      }
    })()

    await loadingPromise
    loadingPromise = null
  }

  // 仅监听外部变化（学期切换、分析对象类型切换），不再监听 classId/courseId 避免递归
  watch([targetType, semesterId], () => {
    targetId.value = undefined
    loadOptions()
  })

  onMounted(async () => {
    if (role.value === 'student') {
      targetType.value = 'student'
      targetId.value = userStore.userInfo?.studentId
    }
    await loadOptions()
  })

  const queryParams = computed<AnalysisQuery>(() => ({
    targetType: targetType.value,
    targetId: targetId.value,
    semesterId: semesterId.value,
    deptId: 1,
    classId: classId.value,
    courseId: courseId.value,
    keyword: studentKeyword.value || undefined,
  }))

  return {
    role,
    allowedTargetTypes,
    targetType,
    semesterId,
    classId,
    courseId,
    targetId,
    studentKeyword,
    semesterOptions,
    classOptions,
    courseOptions,
    targetOptions,
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
