/**
 * AI 分析筛选范围 composable
 * 根据用户角色限制可选 target_type 及数据范围
 */
import { computed, onMounted, ref, watch } from 'vue'
import { fetchClasses, fetchCourses, fetchSemesters, fetchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { AnalysisQuery, TargetType, UserRole } from '@/types'
import { semesters as semesterDict } from '@/mock/dict'

/** 各角色允许的分析对象类型 */
const roleTargetTypes: Record<UserRole, TargetType[]> = {
  admin: ['student', 'class', 'course', 'teacher'],
  manager: ['student', 'class', 'course', 'teacher'],
  teacher: ['student', 'class', 'course'],
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
  const deptId = ref<number | undefined>(userStore.userInfo?.deptId)
  const classId = ref<number | undefined>()
  const courseId = ref<number | undefined>()
  const targetId = ref<number | undefined>()

  const semesterOptions = ref<{ label: string; value: number }[]>([])
  const classOptions = ref<{ label: string; value: number }[]>([])
  const courseOptions = ref<{ label: string; value: number }[]>([])
  const targetOptions = ref<{ label: string; value: number }[]>([])

  const showDeptFilter = computed(() => ['admin', 'manager'].includes(role.value))
  const showClassFilter = computed(() => ['admin', 'manager', 'teacher'].includes(role.value))
  const showCourseFilter = computed(() => targetType.value !== 'teacher' && role.value !== 'student')
  const showTargetTypeFilter = computed(() => role.value !== 'student')
  const showStudentPicker = computed(() => targetType.value === 'student' && role.value !== 'student')

  async function loadOptions(): Promise<void> {
    const sems = await fetchSemesters()
    semesterOptions.value = sems.map((s) => ({ label: s.semesterName, value: s.id }))

    if (role.value === 'teacher') {
      const teacherId = userStore.userInfo?.teacherId
      const courses = await fetchCourses({ teacherId, semesterId: semesterId.value })
      courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
      classId.value = userStore.userInfo?.classId ? undefined : classId.value
      const classes = await fetchClasses({ deptId: userStore.userInfo?.deptId })
      classOptions.value = classes.filter((c) => c.deptId === 1).map((c) => ({ label: c.className, value: c.id }))
    } else if (showDeptFilter.value) {
      const classes = await fetchClasses({ deptId: deptId.value })
      classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
      const courses = await fetchCourses({ deptId: deptId.value, semesterId: semesterId.value })
      courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
    }

    if (targetType.value === 'student') {
      if (role.value === 'student') {
        targetId.value = userStore.userInfo?.studentId
      } else {
        const students = await fetchStudents({ classId: classId.value, deptId: deptId.value })
        targetOptions.value = students.map((s) => ({ label: `${s.studentName} (${s.studentNo})`, value: s.id }))
        if (!targetId.value && targetOptions.value.length) {
          targetId.value = targetOptions.value[0]!.value
        }
      }
    } else if (targetType.value === 'class') {
      targetOptions.value = classOptions.value
      if (!targetId.value && targetOptions.value.length) {
        targetId.value = targetOptions.value[0]!.value
      }
    } else if (targetType.value === 'course') {
      targetOptions.value = courseOptions.value
      if (!targetId.value && targetOptions.value.length) {
        targetId.value = targetOptions.value[0]!.value
      }
    }
  }

  watch([targetType, semesterId, deptId, classId, courseId], () => {
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
    deptId: deptId.value,
    classId: classId.value,
    courseId: courseId.value,
  }))

  return {
    role,
    allowedTargetTypes,
    targetType,
    semesterId,
    deptId,
    classId,
    courseId,
    targetId,
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
  }
}
