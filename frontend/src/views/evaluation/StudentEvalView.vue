<!--
  学生学习质量评价页面（教师/管理员）
  对接 evaluations.py：/evaluations、/evaluations/distribution
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { fetchClasses, fetchCourses, searchStudents } from '@/api/dict'
import {
  evalGradeTagType,
  fetchEvaluationDistribution,
  fetchEvaluations,
  type EvaluationDistribution,
  type StudentEvaluationItem,
} from '@/api/evaluations'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const role = computed(() => userStore.userInfo?.role || 'teacher')

const loading = ref(false)
const courseId = ref<number>()
const classId = ref<number>()
const evalLevel = ref('')
const courseOptions = ref<{ label: string; value: number }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const allEvalList = ref<StudentEvaluationItem[]>([])
const distribution = ref<EvaluationDistribution | null>(null)

/** 与数据库 eval_level 一致（seed：优秀/良好/中等/不及格） */
const levelOptions = [
  { label: '全部', value: '' },
  { label: '优秀', value: '优秀' },
  { label: '良好', value: '良好' },
  { label: '中等', value: '中等' },
  { label: '不及格', value: '不及格' },
]

/** 将 10 分档合并为 5 档，避免横坐标拥挤 */
function aggregateScoreBuckets(buckets: EvaluationDistribution['scoreDistribution']) {
  const groups = [
    { label: '<60', lows: [0, 10, 20, 30, 40, 50] },
    { label: '60-69', lows: [60] },
    { label: '70-79', lows: [70] },
    { label: '80-89', lows: [80] },
    { label: '90-100', lows: [90] },
  ]
  const total = buckets?.reduce((sum, b) => sum + b.count, 0) ?? 0
  return groups.map((g) => {
    const matched = (buckets ?? []).filter((b) => g.lows.includes(b.low))
    const count = matched.reduce((sum, b) => sum + b.count, 0)
    return {
      label: g.label,
      count,
      ratio: total ? Math.round((count / total) * 1000) / 10 : 0,
    }
  })
}

const scoreBuckets = computed(() => aggregateScoreBuckets(distribution.value?.scoreDistribution))

const classStudentIds = ref<Set<number>>(new Set())

/** 班级筛选：/evaluations 无 class_id，前端按班级学生 ID 过滤 */
const studentEvalList = computed(() => {
  if (!classId.value) return allEvalList.value
  return allEvalList.value.filter((item) => classStudentIds.value.has(item.studentDbId))
})

const distributionTitle = computed(() => {
  if (!distribution.value) return '等级分布'
  const cls = classOptions.value.find((c) => c.value === classId.value)
  return cls ? `${cls.label} · 等级分布` : `${distribution.value.courseName} · 等级分布`
})

async function loadClassStudentIds(): Promise<void> {
  if (!classId.value || !courseId.value) {
    classStudentIds.value = new Set()
    return
  }
  const teacherId = role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const students = await searchStudents({
    classId: classId.value,
    courseId: courseId.value,
    teacherId,
  })
  classStudentIds.value = new Set(students.map((s) => s.id))
}

async function loadFilterOptions(preserveCourse = false): Promise<void> {
  const teacherId = role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))

  if (!courseOptions.value.length) {
    courseId.value = undefined
    classOptions.value = []
    classId.value = undefined
    return
  }

  if (!courseId.value || !courseOptions.value.some((c) => c.value === courseId.value)) {
    courseId.value = courseOptions.value[0]!.value
  }

  if (!preserveCourse) {
    classId.value = undefined
  }
  const classes = await fetchClasses({ deptId: 1, courseId: courseId.value, teacherId })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
}

async function loadData(): Promise<void> {
  if (!courseId.value) {
    allEvalList.value = []
    distribution.value = null
    return
  }

  loading.value = true
  try {
    await loadClassStudentIds()
    const [list, dist] = await Promise.all([
      fetchEvaluations({
        courseId: courseId.value,
        evalLevel: evalLevel.value || undefined,
      }),
      fetchEvaluationDistribution({
        courseId: courseId.value,
        classId: classId.value,
      }),
    ])
    allEvalList.value = list
    distribution.value = dist
  } catch {
    allEvalList.value = []
    distribution.value = null
  } finally {
    loading.value = false
  }
}

async function onCourseChange(): Promise<void> {
  classId.value = undefined
  evalLevel.value = ''
  const teacherId = role.value === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const classes = await fetchClasses({ deptId: 1, courseId: courseId.value, teacherId })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  await loadData()
}

async function onQuery(): Promise<void> {
  await loadData()
}

const pieOption = computed<EChartsOption>(() => {
  const dist = distribution.value?.levelDistribution ?? {}
  const ratio = distribution.value?.levelRatio ?? {}
  const data = Object.entries(dist)
    .filter(([, count]) => count > 0)
    .map(([name, value]) => ({ name, value, ratio: ratio[name] }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; data?: { ratio?: number } }
        const pct = p.data?.ratio ?? 0
        return `${p.name}<br/>${p.value} 人（${pct}%）`
      },
    },
    legend: { bottom: 0 },
    color: ['#10b981', '#2563eb', '#f59e0b', '#ef4444'],
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%' },
      data: data.length ? data : [{ name: '暂无数据', value: 1 }],
    }],
  }
})

const scoreBucketOption = computed<EChartsOption>(() => {
  const buckets = scoreBuckets.value
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (params as { name: string; marker: string; data: number }[])[0]!
        const bucket = buckets.find((b) => b.label === p.name)
        return `${p.name} 分<br/>${p.marker} ${bucket?.count ?? 0} 人（${p.data}%）`
      },
    },
    grid: { left: 42, right: 12, top: 28, bottom: 32 },
    xAxis: {
      type: 'category',
      data: buckets.map((b) => b.label),
      axisLabel: { fontSize: 11, color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: '占比',
      max: 100,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { formatter: '{value}%', fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: buckets.map((b) => b.ratio),
      barMaxWidth: 40,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: (params: { dataIndex: number }) => {
          const label = buckets[params.dataIndex]?.label ?? ''
          if (label.startsWith('90')) return '#10b981'
          if (label.startsWith('80')) return '#2563eb'
          if (label.startsWith('70')) return '#f59e0b'
          if (label.startsWith('60')) return '#f97316'
          return '#ef4444'
        },
      },
    }],
  }
})

onMounted(async () => {
  await loadFilterOptions()
  await loadData()
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card filter-bar">
      <el-select
        v-model="courseId"
        placeholder="选择课程"
        style="width: 220px"
        :disabled="!courseOptions.length"
        @change="onCourseChange"
      >
        <el-option v-for="opt in courseOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-select
        v-model="classId"
        placeholder="全部班级"
        clearable
        style="width: 200px"
        :disabled="!courseId"
        @change="onQuery"
      >
        <el-option v-for="opt in classOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-select
        v-model="evalLevel"
        placeholder="等级"
        clearable
        style="width: 110px"
        :disabled="!courseId"
        @change="onQuery"
      >
        <el-option v-for="opt in levelOptions" :key="opt.value || 'all'" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-button type="primary" :disabled="!courseId" @click="onQuery">查询</el-button>
      <span v-if="classId" class="filter-hint">列表与分布均按所选班级筛选</span>
    </div>

    <el-empty v-if="!courseOptions.length" description="暂无授课课程" />

    <template v-else>
      <el-row v-if="distribution" :gutter="16" class="summary-row">
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-card__label">评价人数</div>
            <div class="summary-card__value">{{ distribution.totalStudents }}</div>
            <div class="summary-card__sub">{{ distribution.courseName }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-card__label">平均分</div>
            <div class="summary-card__value">{{ distribution.statistics.mean ?? '—' }}</div>
            <div class="summary-card__sub">中位数 {{ distribution.statistics.median ?? '—' }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-card__label">主流等级</div>
            <div class="summary-card__value">{{ distribution.dominantLevel ?? '—' }}</div>
            <div class="summary-card__sub">标准差 {{ distribution.statistics.stdDev ?? '—' }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-card__label">班级特征</div>
            <div class="summary-card__value summary-card__value--sm">{{ distribution.characteristic }}</div>
            <div class="summary-card__sub">
              最高 {{ distribution.statistics.maxScore ?? '—' }} / 最低 {{ distribution.statistics.minScore ?? '—' }}
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="16">
          <div class="content-card">
            <div class="content-card__title">学生学习质量评价</div>
            <el-empty v-if="!studentEvalList.length" description="暂无评价数据" />
            <el-table v-else :data="studentEvalList" stripe border>
              <el-table-column prop="studentId" label="学号" width="130" />
              <el-table-column prop="studentName" label="学生姓名" width="100" />
              <el-table-column prop="totalScore" label="综合得分" width="100" align="center" sortable>
                <template #default="{ row }">
                  <span class="score-num">{{ row.totalScore }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="grade" label="评价等级" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="evalGradeTagType(row.grade)" effect="dark" size="small">{{ row.grade }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="各维度得分" min-width="220">
                <template #default="{ row }">
                  <div class="dim-scores">
                    <div v-for="d in row.dimensions" :key="d.dimensionId" class="dim-score-item">
                      <span class="dim-name">{{ d.name }}</span>
                      <el-progress :percentage="d.score" :stroke-width="6" :show-text="false" style="width: 72px" />
                      <span class="dim-val">{{ d.score }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="content-card">
            <div class="content-card__title">{{ distributionTitle }}</div>
            <BaseChart :option="pieOption" height="260px" />
          </div>
          <div class="content-card" style="margin-top: 16px">
            <div class="content-card__title">分数段分布</div>
            <BaseChart :option="scoreBucketOption" height="260px" />
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped lang="scss">
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.filter-hint {
  font-size: 12px;
  color: #94a3b8;
}

.summary-row {
  margin-bottom: 16px;
}

.summary-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);

  &__label {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
  }

  &__value {
    font-size: 20px;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.3;

    &--sm {
      font-size: 14px;
      font-weight: 500;
    }
  }

  &__sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
  }
}

.score-num {
  font-weight: 600;
  color: #2563eb;
  font-size: 16px;
}

.dim-scores {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.dim-score-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;

  .dim-name {
    color: #64748b;
    width: 56px;
  }

  .dim-val {
    font-weight: 600;
    color: #2563eb;
    width: 24px;
  }
}
</style>
