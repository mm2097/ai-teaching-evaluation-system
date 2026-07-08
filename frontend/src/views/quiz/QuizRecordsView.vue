<!--
  答题记录页面
  教师查看学生练习提交情况与得分
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchQuizAssignments, fetchQuizSubmissions } from '@/api/quiz'
import { fetchCourses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment, QuizSubmission } from '@/types'

const userStore = useUserStore()

const courseOptions = ref<{ label: string; value: number }[]>([])
const assignments = ref<QuizAssignment[]>([])
const submissions = ref<QuizSubmission[]>([])
const loading = ref(false)

const filters = ref({
  courseId: undefined as number | undefined,
  assignmentId: undefined as number | undefined,
})

const assignmentOptions = computed(() =>
  assignments.value
    .filter((a) => !filters.value.courseId || a.courseId === filters.value.courseId)
    .map((a) => ({ label: `${a.title}（${a.className}）`, value: a.id })),
)

const filteredSubmissions = computed(() => {
  return submissions.value.filter((s) => {
    if (filters.value.assignmentId && s.assignmentId !== filters.value.assignmentId) return false
    if (filters.value.courseId) {
      const assignment = assignments.value.find((a) => a.id === s.assignmentId)
      if (assignment && assignment.courseId !== filters.value.courseId) return false
    }
    return true
  })
})

const stats = computed(() => {
  const list = filteredSubmissions.value
  if (!list.length) return { count: 0, avgScore: 0, passRate: 0 }
  const total = list.reduce((s, item) => s + item.score, 0)
  const passed = list.filter((item) => item.score / item.totalScore >= 0.6).length
  return {
    count: list.length,
    avgScore: Math.round((total / list.length) * 10) / 10,
    passRate: Math.round((passed / list.length) * 100),
  }
})

async function loadAssignments(): Promise<void> {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  assignments.value = await fetchQuizAssignments({ teacherId, courseId: filters.value.courseId })
}

async function loadSubmissions(): Promise<void> {
  loading.value = true
  try {
    submissions.value = await fetchQuizSubmissions(filters.value.assignmentId)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  await loadAssignments()
  await loadSubmissions()
})

async function handleCourseChange(): Promise<void> {
  filters.value.assignmentId = undefined
  await loadAssignments()
  await loadSubmissions()
}

async function handleAssignmentChange(): Promise<void> {
  await loadSubmissions()
}

function scoreRate(row: QuizSubmission): number {
  return Math.round((row.score / row.totalScore) * 100)
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="content-card__title">答题记录</div>
      <p class="page-desc">查看学生在线练习提交记录，答题结果已同步至知识点掌握度分析。</p>

      <el-row :gutter="12" class="stat-row">
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-value">{{ stats.count }}</span>
            <span class="stat-label">提交人次</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-value">{{ stats.avgScore }}</span>
            <span class="stat-label">平均得分</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-value">{{ stats.passRate }}%</span>
            <span class="stat-label">及格率（≥60%）</span>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="content-card">
      <el-form :inline="true">
        <el-form-item label="课程">
          <el-select v-model="filters.courseId" clearable placeholder="全部课程" style="width: 180px" @change="handleCourseChange">
            <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="练习">
          <el-select v-model="filters.assignmentId" clearable placeholder="全部练习" style="width: 260px" @change="handleAssignmentChange">
            <el-option v-for="a in assignmentOptions" :key="a.value" :label="a.label" :value="a.value" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="filteredSubmissions" stripe border>
        <el-table-column prop="studentName" label="学生" width="120" />
        <el-table-column prop="studentId" label="学生ID" width="90" align="center" />
        <el-table-column label="练习" min-width="200">
          <template #default="{ row }">
            {{ assignments.find((a) => a.id === row.assignmentId)?.title || `练习 #${row.assignmentId}` }}
          </template>
        </el-table-column>
        <el-table-column label="得分" width="120" align="center">
          <template #default="{ row }">
            <span :class="{ 'score-pass': scoreRate(row) >= 60, 'score-fail': scoreRate(row) < 60 }">
              {{ row.score }} / {{ row.totalScore }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="正确率" width="100" align="center">
          <template #default="{ row }">{{ scoreRate(row) }}%</template>
        </el-table-column>
        <el-table-column prop="submitTime" label="提交时间" width="180" />
      </el-table>

      <el-empty v-if="!loading && !filteredSubmissions.length" description="暂无答题记录" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-desc {
  font-size: 13px;
  color: #64748b;
  margin: -8px 0 16px;
}

.stat-row { margin-top: 8px; }

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;

  .stat-value {
    display: block;
    font-size: 24px;
    font-weight: 700;
    color: #2563eb;
  }

  .stat-label {
    font-size: 12px;
    color: #64748b;
  }
}

.score-pass { color: #10b981; font-weight: 600; }
.score-fail { color: #ef4444; font-weight: 600; }
</style>
