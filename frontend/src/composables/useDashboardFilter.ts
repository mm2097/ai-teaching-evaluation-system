/**
 * 综合看板五维级联筛选
 * 学期 → 专业 → 年级 → 课程 → 专业班级
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchClasses, fetchCourses, fetchDashboardGrades, fetchMajors, fetchSemesters } from '@/api/dict'
import { useUserStore } from '@/stores/user'

export interface DashboardFilters {
  semester: string
  majorId: number | undefined
  grade: string
  courseId: number | undefined
  classId: number | undefined
}

function normalizeId(value: number | null | undefined): number | undefined {
  return value == null ? undefined : value
}

function keepValidId(
  options: { value: number }[],
  current: number | undefined,
): number | undefined {
  if (current !== undefined && options.some((o) => o.value === current)) return current
  return undefined
}

function keepValidGrade(
  options: { value: string }[],
  current: string,
): string {
  if (current && options.some((o) => o.value === current)) return current
  return ''
}

export function useDashboardFilter() {
  const userStore = useUserStore()
  const deptId = 1

  /** 筛选状态持久化（sessionStorage，按用户隔离，离开看板后返回可恢复） */
  const storageKey = computed(() => `dashboard-filter-${userStore.userInfo?.id ?? 'anonymous'}`)

  /** 保存当前筛选状态，便于从其他页面返回时恢复 */
  function saveState(): void {
    try {
      sessionStorage.setItem(storageKey.value, JSON.stringify({
        filters: filters.value,
        applied: applied.value,
        hasQueried: hasQueried.value,
      }))
    } catch { /* 存储不可用时静默降级，不影响筛选功能 */ }
  }

  /** 恢复上次的筛选状态（在选项加载前调用，选项加载后由 keepValid 系列函数校验） */
  function restoreState(): void {
    try {
      const raw = sessionStorage.getItem(storageKey.value)
      if (!raw) return
      const saved = JSON.parse(raw) as Partial<{ filters: Partial<DashboardFilters>; applied: Partial<DashboardFilters>; hasQueried: boolean }>
      if (!saved || typeof saved !== 'object') return
      if (saved.filters) filters.value = { ...filters.value, ...saved.filters }
      if (saved.applied) applied.value = { ...applied.value, ...saved.applied }
      hasQueried.value = Boolean(saved.hasQueried)
    } catch { /* 数据损坏时忽略，按全新状态初始化 */ }
  }

  const semesterOptions = ref<{ label: string; value: string; id: number }[]>([])

  const filters = ref<DashboardFilters>({
    semester: '',
    majorId: undefined,
    grade: '',
    courseId: undefined,
    classId: undefined,
  })

  const applied = ref<DashboardFilters>({
    semester: '',
    majorId: undefined,
    grade: '',
    courseId: undefined,
    classId: undefined,
  })

  const hasQueried = ref(false)
  const optionsLoading = ref(false)

  const majorOptions = ref<{ label: string; value: number }[]>([])
  const gradeOptions = ref<{ label: string; value: string }[]>([
    { label: '全部年级', value: '' },
  ])
  const courseOptions = ref<{ label: string; value: number }[]>([])
  const classOptions = ref<{ label: string; value: number }[]>([])

  const teacherId = computed(() =>
    userStore.userInfo?.role === 'teacher' ? userStore.userInfo?.teacherId : undefined,
  )

  const isFilterReady = computed(
    () => Boolean(
      filters.value.semester
      && filters.value.courseId != null
      && filters.value.classId != null,
    ),
  )

  const showDashboard = computed(
    () => hasQueried.value
      && applied.value.courseId != null
      && applied.value.classId != null,
  )

  function queryBase() {
    return {
      deptId,
      semesterCode: filters.value.semester,
      majorId: filters.value.majorId,
      grade: filters.value.grade || undefined,
      teacherId: teacherId.value,
    }
  }

  async function loadMajors(): Promise<void> {
    if (!filters.value.semester) {
      majorOptions.value = []
      filters.value.majorId = undefined
      return
    }
    const list = await fetchMajors({
      deptId,
      semesterCode: filters.value.semester,
      grade: filters.value.grade || undefined,
      teacherId: teacherId.value,
    })
    majorOptions.value = list.map((m) => ({ label: m.majorName, value: m.id }))
    filters.value.majorId = keepValidId(majorOptions.value, filters.value.majorId)
  }

  async function loadGrades(): Promise<void> {
    if (!filters.value.semester) {
      gradeOptions.value = [{ label: '全部年级', value: '' }]
      filters.value.grade = ''
      return
    }
    const majorName = majorOptions.value.find((m) => m.value === filters.value.majorId)?.label
    const grades = await fetchDashboardGrades({
      deptId,
      semesterCode: filters.value.semester,
      majorId: filters.value.majorId,
      majorName,
      teacherId: teacherId.value,
    })
    gradeOptions.value = [
      { label: '全部年级', value: '' },
      ...grades.map((g) => ({ label: g, value: g })),
    ]
    filters.value.grade = keepValidGrade(gradeOptions.value, filters.value.grade)
  }

  async function loadCourses(): Promise<void> {
    if (!filters.value.semester) {
      courseOptions.value = []
      filters.value.courseId = undefined
      return
    }
    const list = await fetchCourses(queryBase())
    courseOptions.value = list.map((c) => ({
      label: `${c.courseName}（${c.courseNo}）`,
      value: c.id,
    }))
    filters.value.courseId = keepValidId(courseOptions.value, filters.value.courseId)
  }

  async function loadClasses(clearClass = true, courseId?: number): Promise<void> {
    const resolvedCourseId = normalizeId(courseId ?? filters.value.courseId)
    if (resolvedCourseId === undefined) {
      classOptions.value = []
      if (clearClass) filters.value.classId = undefined
      return
    }
    const majorName = majorOptions.value.find((m) => m.value === filters.value.majorId)?.label
    const list = await fetchClasses({
      ...queryBase(),
      courseId: resolvedCourseId,
      major: majorName,
    })
    classOptions.value = list.map((c) => ({
      label: c.className,
      value: c.id,
    }))
    if (clearClass) {
      filters.value.classId = keepValidId(classOptions.value, filters.value.classId)
    }
  }

  /** 学期变更：重置下游所有选项 */
  async function onSemesterChange(): Promise<void> {
    filters.value.majorId = undefined
    filters.value.grade = ''
    filters.value.courseId = undefined
    filters.value.classId = undefined
    optionsLoading.value = true
    try {
      await loadMajors()
      await loadGrades()
      await loadCourses()
      classOptions.value = []
    } finally {
      optionsLoading.value = false
    }
  }

  /** 专业变更：联动年级、课程、班级 */
  async function onMajorChange(majorId: number | null): Promise<void> {
    filters.value.majorId = normalizeId(majorId)
    filters.value.classId = undefined
    optionsLoading.value = true
    try {
      await loadGrades()
      await loadCourses()
      if (filters.value.courseId != null) {
        await loadClasses(true)
      } else {
        classOptions.value = []
      }
    } finally {
      optionsLoading.value = false
    }
  }

  /** 年级变更：联动课程、班级 */
  async function onGradeChange(grade: string | null): Promise<void> {
    filters.value.grade = grade ?? ''
    filters.value.classId = undefined
    optionsLoading.value = true
    try {
      await loadMajors()
      await loadCourses()
      if (filters.value.courseId != null) {
        await loadClasses(true)
      } else {
        classOptions.value = []
      }
    } finally {
      optionsLoading.value = false
    }
  }

  /** 课程变更：联动班级 */
  async function onCourseChange(courseId: number | null): Promise<void> {
    const resolvedCourseId = normalizeId(courseId)
    filters.value.courseId = resolvedCourseId
    filters.value.classId = undefined
    if (resolvedCourseId === undefined) {
      classOptions.value = []
      return
    }
    optionsLoading.value = true
    try {
      await loadClasses(true, resolvedCourseId)
    } finally {
      optionsLoading.value = false
    }
  }

  function applyFilters(): void {
    if (!filters.value.semester) {
      ElMessage.warning('请先选择学期')
      return
    }
    if (filters.value.courseId == null) {
      ElMessage.warning('请先选择课程')
      return
    }
    if (filters.value.classId == null) {
      ElMessage.warning('请先选择专业班级')
      return
    }
    applied.value = { ...filters.value }
    hasQueried.value = true
    saveState()
  }

  // 恢复上次会话的筛选状态（含已应用的查询条件）
  restoreState()

  onMounted(() => {
    optionsLoading.value = true
    void (async () => {
      try {
        const sems = await fetchSemesters()
        semesterOptions.value = sems.map(s => ({ label: s.semesterName, value: s.semesterCode, id: s.id }))
        // 恢复的学期优先；否则默认当前学期
        const restoredSemester = semesterOptions.value.find(s => s.value === filters.value.semester)
        if (!restoredSemester) {
          const current = semesterOptions.value.find(s => s.value === '2025-2026-1')
          filters.value.semester = current?.value ?? semesterOptions.value[0]?.value ?? ''
        }
        await loadMajors()
        await loadGrades()
        await loadCourses()
        // 恢复态下课程已存在时，补充班级选项并校验恢复的班级
        if (filters.value.courseId != null) {
          await loadClasses()
        }
      } finally {
        optionsLoading.value = false
      }
    })()
  })

  return {
    filters,
    applied,
    hasQueried,
    showDashboard,
    isFilterReady,
    optionsLoading,
    majorOptions,
    gradeOptions,
    courseOptions,
    classOptions,
    semesterOptions,
    applyFilters,
    onSemesterChange,
    onMajorChange,
    onGradeChange,
    onCourseChange,
  }
}
