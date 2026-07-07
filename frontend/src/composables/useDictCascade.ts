/**
 * 院系-专业-班级级联筛选 composable
 */
import { computed, onMounted, ref, watch } from 'vue'
import { fetchClasses, fetchMajors } from '@/api/dict'
import type { ClassInfo, Major } from '@/types'

export function useDictCascade(initial?: { deptId?: number; majorId?: number; classId?: number; grade?: string }) {
  const deptId = ref<number | undefined>(initial?.deptId)
  const majorId = ref<number | undefined>(initial?.majorId)
  const classId = ref<number | undefined>(initial?.classId)
  const grade = ref(initial?.grade || '')

  const majorList = ref<Major[]>([])
  const classList = ref<ClassInfo[]>([])

  async function loadMajors(): Promise<void> {
    majorList.value = await fetchMajors(deptId.value)
    if (majorId.value && !majorList.value.some((m) => m.id === majorId.value)) {
      majorId.value = undefined
      classId.value = undefined
    }
  }

  async function loadClasses(): Promise<void> {
    classList.value = await fetchClasses({
      deptId: deptId.value,
      majorId: majorId.value,
      grade: grade.value || undefined,
    })
    if (classId.value && !classList.value.some((c) => c.id === classId.value)) {
      classId.value = undefined
    }
  }

  const majorOptions = computed(() => majorList.value.map((m) => ({ label: m.majorName, value: m.id })))
  const classOptions = computed(() => classList.value.map((c) => ({ label: c.className, value: c.id })))

  watch(deptId, async () => {
    majorId.value = undefined
    classId.value = undefined
    await loadMajors()
    await loadClasses()
  })

  watch([majorId, grade], async () => {
    classId.value = undefined
    await loadClasses()
  })

  onMounted(async () => {
    await loadMajors()
    await loadClasses()
  })

  function reset(): void {
    deptId.value = undefined
    majorId.value = undefined
    classId.value = undefined
    grade.value = ''
  }

  return {
    deptId,
    majorId,
    classId,
    grade,
    majorOptions,
    classOptions,
    reset,
  }
}
