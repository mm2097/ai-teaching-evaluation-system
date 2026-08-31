<!--
  异常学情预警页面
  展示预警名单、等级与原因，支持筛选
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import StudentLinkedPicker from '@/components/common/StudentLinkedPicker.vue'
import { fetchWarnings, updateWarningStatus, sendWarningNotice } from '@/api/analysis'
import { fetchClasses, fetchCourses, fetchSemesters, searchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import { warningLevelType } from '@/utils/auth'
import type { LinkedStudentOption, WarningRecord } from '@/types'

const route = useRoute()
const userStore = useUserStore()
const role = computed(() => userStore.userInfo?.role || 'student')

const levelFilter = ref('')
const typeFilter = ref('')
const semesterId = ref(1)
const courseId = ref<number | undefined>()
const classId = ref<number | undefined>()
const statusFilter = ref<number | ''>('')
const semesterOptions = ref<{ id?: number; label: string; value: string }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const courseOptions = ref<{ label: string; value: number }[]>([])
const warningList = ref<WarningRecord[]>([])
const studentList = ref<LinkedStudentOption[]>([])
const studentLoading = ref(false)
const selectedStudentNo = ref<string | undefined>()

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
      id: s.studentNo,
      studentName: s.studentName,
      studentNo: s.studentNo,
    }))
    if (
      selectedStudentNo.value
      && !studentList.value.some((s) => s.id === selectedStudentNo.value)
    ) {
      selectedStudentNo.value = undefined
    }
  } finally {
    studentLoading.value = false
  }
}

async function loadFilterOptions(): Promise<void> {
  const teacherId = role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: semesterId.value })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseId.value && !courseOptions.value.some((c) => c.value === courseId.value)) {
    courseId.value = courseOptions.value[0]?.value
  }

  const classes = await fetchClasses({ deptId: 1, courseId: courseId.value, teacherId })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (classId.value && !classOptions.value.some((c) => c.value === classId.value)) {
    classId.value = undefined
  }

  await loadStudentOptions()
}

async function loadWarnings(): Promise<void> {
  warningList.value = await fetchWarnings({
    deptId: 1,
    classId: classId.value,
    semesterId: semesterId.value,
    courseId: courseId.value,
    level: levelFilter.value || undefined,
    type: typeFilter.value || undefined,
    status: statusFilter.value === '' ? undefined : statusFilter.value,
    teacherId: role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined,
    studentNo: selectedStudentNo.value,
  })
}

async function loadSemesters(): Promise<void> {
  const sems = await fetchSemesters()
  semesterOptions.value = sems.map(s => ({ label: s.semesterName, value: s.semesterCode, id: s.id }))
}

async function handleQuery(): Promise<void> {
  await loadSemesters()
  await loadFilterOptions()
  await loadWarnings()
}

/**
 * 从路由 query 读取看板下钻携带的筛选条件并应用
 * 支持 courseId / classId / semester（学期编码）
 */
function applyQueryFilters(): void {
  const qSemester = route.query.semester
  if (typeof qSemester === 'string' && qSemester) {
    const sem = semesterOptions.value.find((s) => s.value === qSemester)
    if (sem?.id) semesterId.value = sem.id
  }
  const qCourse = Number(route.query.courseId)
  if (Number.isFinite(qCourse) && qCourse > 0) courseId.value = qCourse
  const qClass = Number(route.query.classId)
  if (Number.isFinite(qClass) && qClass > 0) classId.value = qClass
}

onMounted(async () => {
  // 先加载学期选项，才能把 semester 编码映射为学期 id
  await loadSemesters()
  applyQueryFilters()
  await handleQuery()
})

// 从看板再次下钻时（同一组件复用），重新应用筛选并刷新
watch(
  () => route.query,
  async () => {
    if (!route.query.courseId && !route.query.classId) return
    await loadSemesters()
    applyQueryFilters()
    await handleQuery()
  },
)

let _inited = false
watch([courseId, classId, levelFilter, typeFilter, statusFilter], async () => {
  if (!_inited) { _inited = true; return }
  await loadWarnings()
})

const filteredWarnings = computed(() => warningList.value)

const levelStats = computed(() => ({
  高: filteredWarnings.value.filter((w) => w.level === '高').length,
  中: filteredWarnings.value.filter((w) => w.level === '中').length,
  低: filteredWarnings.value.filter((w) => w.level === '低').length,
}))

const drawerVisible = ref(false)
const currentWarning = ref<WarningRecord | undefined>()

function viewDetail(row: WarningRecord): void {
  currentWarning.value = row
  drawerVisible.value = true
}

const markingResolved = ref(false)

async function markResolved(): Promise<void> {
  if (!currentWarning.value || markingResolved.value) return
  markingResolved.value = true
  try {
    await updateWarningStatus(currentWarning.value.id, 1)
    const idx = warningList.value.findIndex((w) => w.id === currentWarning.value!.id)
    if (idx !== -1) {
      warningList.value[idx] = { ...warningList.value[idx]!, status: 1 }
      currentWarning.value = warningList.value[idx]
    }
    ElMessage.success('已标记为已处理')
  } catch {
    // 错误提示由 request 拦截器统一处理
  } finally {
    markingResolved.value = false
  }
}

const sendingNotice = ref(false)

async function sendNotice(): Promise<void> {
  if (!currentWarning.value || sendingNotice.value) return
  sendingNotice.value = true
  try {
    await sendWarningNotice(currentWarning.value.id)
    const idx = warningList.value.findIndex((w) => w.id === currentWarning.value!.id)
    if (idx !== -1) {
      warningList.value[idx] = { ...warningList.value[idx]!, notified: true }
      currentWarning.value = warningList.value[idx]
    }
    ElMessage.success(`预警通知已发送给 ${currentWarning.value.studentName}，学生可在消息通知中查看`)
  } catch {
    // 错误提示（含重复发送 409）由 request 拦截器统一处理
  } finally {
    sendingNotice.value = false
  }
}

const statusOptions = [
  { label: '待处理', value: 0 },
  { label: '已处理', value: 1 },
]
</script>

<template>
  <div class="page-container">
    <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr)">
      <div class="warning-stat high">
        <div class="stat-num">{{ levelStats.高 }}</div>
        <div class="stat-label">高级预警</div>
      </div>
      <div class="warning-stat medium">
        <div class="stat-num">{{ levelStats.中 }}</div>
        <div class="stat-label">中级预警</div>
      </div>
      <div class="warning-stat low">
        <div class="stat-num">{{ levelStats.低 }}</div>
        <div class="stat-label">低级预警</div>
      </div>
    </div>

    <div class="content-card">
      <div class="filter-bar">
        <el-select v-model="semesterId" placeholder="学期" style="width: 200px">
          <el-option v-for="s in semesterOptions" :key="s.id" :label="s.label" :value="s.id!" />
        </el-select>
        <el-select v-model="courseId" placeholder="课程" clearable style="width: 150px">
          <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="classId" placeholder="班级" clearable style="width: 140px">
          <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <StudentLinkedPicker
          v-model="selectedStudentNo"
          :students="studentList"
          :loading="studentLoading"
        />
        <el-select v-model="levelFilter" placeholder="预警等级" clearable style="width: 120px">
          <el-option label="高" value="高" />
          <el-option label="中" value="中" />
          <el-option label="低" value="低" />
        </el-select>
        <el-select v-model="typeFilter" placeholder="预警类型" clearable style="width: 140px">
          <el-option label="成绩下滑" value="成绩下滑" />
          <el-option label="缺勤异常" value="缺勤异常" />
          <el-option label="作业未交" value="作业未交" />
          <el-option label="综合异常" value="综合异常" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="处理状态" clearable style="width: 120px">
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button type="primary" @click="handleQuery">查询</el-button>
      </div>

      <el-table :data="filteredWarnings" stripe border>
        <el-table-column prop="studentId" label="学号" width="130" />
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="className" label="班级" width="120" />
        <el-table-column prop="courseName" label="课程" width="120">
          <template #default="{ row }">{{ row.courseName || '-' }}</template>
        </el-table-column>
        <el-table-column prop="type" label="预警类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="预警等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="warningLevelType(row.level)" size="small" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="预警原因" show-overflow-tooltip />
        <el-table-column prop="warningTime" label="预警时间" width="120" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 1 ? 'success' : 'danger'">
              {{ statusOptions.find(s => s.value === row.status)?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawerVisible" title="预警详情" size="400px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="学号">{{ currentWarning?.studentId }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ currentWarning?.studentName }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ currentWarning?.className }}</el-descriptions-item>
        <el-descriptions-item label="课程">{{ currentWarning?.courseName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="预警类型">{{ currentWarning?.type }}</el-descriptions-item>
        <el-descriptions-item label="预警等级">
          <el-tag :type="warningLevelType(currentWarning?.level || '')" size="small">
            {{ currentWarning?.level }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预警原因">{{ currentWarning?.reason }}</el-descriptions-item>
        <el-descriptions-item label="预警时间">{{ currentWarning?.warningTime }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 20px">
        <el-button
          type="primary"
          :loading="markingResolved"
          :disabled="currentWarning?.status === 1"
          @click="markResolved"
        >{{ currentWarning?.status === 1 ? '已处理' : '标记已处理' }}</el-button>
        <el-button
          :loading="sendingNotice"
          :disabled="currentWarning?.notified === true"
          @click="sendNotice"
        >{{ currentWarning?.notified ? '已通知' : '发送通知' }}</el-button>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.warning-stat {
  text-align: center;
  padding: 24px;
  border-radius: 12px;
  color: #fff;

  .stat-num {
    font-size: 36px;
    font-weight: 700;
  }

  .stat-label {
    font-size: 14px;
    margin-top: 4px;
    opacity: 0.9;
  }

  &.high { background: linear-gradient(135deg, #ef4444, #dc2626); }
  &.medium { background: linear-gradient(135deg, #f59e0b, #d97706); }
  &.low { background: linear-gradient(135deg, #6366f1, #4f46e5); }
}
</style>
