<!--
  知识点掌握度分析页面
  以热力图为核心，支持班级整体 / 学生个人视角切换
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { fetchKnowledgeHeatmap, computeClassKnowledgeStats, type KnowledgeHeatmapResult } from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import { useUserStore } from '@/stores/user'

type ViewMode = 'class' | 'student'

const userStore = useUserStore()
const canViewClass = computed(() => userStore.userInfo?.role !== 'student')

const viewMode = ref<ViewMode>(userStore.userInfo?.role === 'student' ? 'student' : 'class')
const heatmapLoading = ref(false)

const scope = useAnalysisScope('class')
const {
  targetType, semesterId, classId, courseId, targetId,
  studentList, studentLoading,
  semesterOptions, classOptions, courseOptions,
  showClassFilter, showCourseFilter,
  queryParams,
} = scope

const emptyHeatmap = (): KnowledgeHeatmapResult => ({
  knowledgePoints: [],
  students: [],
  data: [],
})

const heatmapData = ref<KnowledgeHeatmapResult>(emptyHeatmap())

const classStats = computed(() => {
  if (viewMode.value === 'class' && heatmapData.value.data.length) {
    return computeClassKnowledgeStats(heatmapData.value)
  }
  return null
})

async function loadHeatmap(): Promise<void> {
  const mode = viewMode.value
  if (targetType.value !== mode) return

  if (mode === 'student') {
    if (!targetId.value) {
      heatmapData.value = emptyHeatmap()
      return
    }
  } else if (!classId.value) {
    return
  }

  heatmapLoading.value = true
  try {
    const params = {
      ...queryParams.value,
      analysisType: '知识点掌握度',
      targetType: viewMode.value,
      targetId: viewMode.value === 'student' ? targetId.value : classId.value,
    }
    heatmapData.value = await fetchKnowledgeHeatmap(params)
  } finally {
    heatmapLoading.value = false
  }
}

watch(viewMode, (mode) => {
  targetType.value = mode === 'class' ? 'class' : 'student'
}, { immediate: true })

watch(
  [semesterId, classId, courseId, targetId, viewMode],
  () => { /* 选项变化时不自动查询，需点击查询按钮 */ },
)

async function handleQuery(): Promise<void> {
  await loadHeatmap()
}

const selectedStudentName = computed(() => {
  if (viewMode.value !== 'student' || !targetId.value) return ''
  const student = studentList.value.find((s) => s.id === targetId.value)
  return student?.studentName ?? heatmapData.value.students[0] ?? ''
})

const heatmapTitle = computed(() => {
  if (viewMode.value === 'class') return '班级知识点掌握度热力图'
  return selectedStudentName.value
    ? `${selectedStudentName.value} · 个人知识点掌握度`
    : '学生个人知识点掌握度热力图'
})

const heatmapOption = computed<EChartsOption>(() => {
  const isPersonal = viewMode.value === 'student'
  const hasCompareRow = isPersonal && heatmapData.value.classAvgByKp?.length
  const yLabels = isPersonal
    ? (hasCompareRow ? ['班级均值', heatmapData.value.students[0] ?? '个人'] : [heatmapData.value.students[0] ?? '个人'])
    : heatmapData.value.students

  let chartData = heatmapData.value.data
  if (isPersonal && hasCompareRow && heatmapData.value.data.length) {
    const classRow = heatmapData.value.classAvgByKp!.map((val, kpIdx) => [kpIdx, 0, val] as number[])
    const personalRow = heatmapData.value.data.map(([kpIdx, , val]) => [kpIdx, 1, val!] as number[])
    chartData = [...classRow, ...personalRow]
  }

  return {
    tooltip: {
      position: 'top',
      formatter: (params: unknown) => {
        const p = params as { value: number[] }
        const [x, y, val] = p.value
        const kp = heatmapData.value.knowledgePoints[x!] ?? ''
        if (isPersonal && hasCompareRow) {
          const label = y === 0 ? '班级均值' : (heatmapData.value.students[0] ?? '个人')
          return `${label} · ${kp}<br/>掌握度: ${val}%`
        }
        if (isPersonal) {
          return `${kp}<br/>掌握度: ${val}%`
        }
        return `${heatmapData.value.students[y!]} · ${kp}<br/>掌握度: ${val}%`
      },
    },
    grid: { left: isPersonal ? 90 : 80, right: 40, top: 10, bottom: 80 },
    xAxis: {
      type: 'category',
      data: heatmapData.value.knowledgePoints,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      splitArea: { show: true },
      inverse: Boolean(isPersonal && hasCompareRow),
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#fef2f2', '#fca5a5', '#f59e0b', '#86efac', '#10b981'] },
    },
    series: [{
      type: 'heatmap',
      data: chartData,
      label: { show: true, fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  }
})

const weakPoints = computed(() => {
  if (viewMode.value === 'student' && heatmapData.value.data.length) {
    return heatmapData.value.data
      .map(([x, , val]) => {
        const classAvg = heatmapData.value.classAvgByKp?.[x!]
        return {
          name: heatmapData.value.knowledgePoints[x!]!,
          rate: val!,
          classRate: classAvg,
          level: val! < 60 ? '严重' as const : val! < 75 ? '中等' as const : '轻微' as const,
        }
      })
      .filter((p) => p.rate < 75)
      .sort((a, b) => a.rate - b.rate)
  }
  return classStats.value?.weakPoints ?? []
})

function handleViewModeChange(mode: ViewMode): void {
  viewMode.value = mode
}

onMounted(async () => {
  await scope.loadOptions()
  await loadHeatmap()
})
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="view-mode-bar">
        <span class="mode-label">分析视角：</span>
        <el-radio-group :model-value="viewMode" size="default" @update:model-value="handleViewModeChange">
          <el-radio-button v-if="canViewClass" value="class">班级整体</el-radio-button>
          <el-radio-button value="student">学生个人</el-radio-button>
        </el-radio-group>
      </div>

      <AnalysisFilterBar
        v-model:target-type="targetType"
        v-model:semester-id="semesterId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="viewMode === 'class' ? ['class'] : ['student']"
        :semester-options="semesterOptions"
        :show-dept-filter="false"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="false"
        :show-student-picker="viewMode === 'student' && canViewClass"
        :student-list="studentList"
        :student-loading="studentLoading"
        :class-options="classOptions"
        :course-options="courseOptions"
        :show-query-button="true"
        @query="handleQuery"
      />
    </div>

    <div v-loading="heatmapLoading" class="content-card">
      <div class="content-card__title">{{ heatmapTitle }}</div>
      <p v-if="viewMode === 'student' && !targetId" class="hint-text">请先选择一名学生，查看个人知识点掌握情况。</p>
      <p v-else-if="viewMode === 'student'" class="hint-text">下方热力图第一行展示班级均值，第二行展示该学生个人掌握度，便于对比。</p>
      <BaseChart
        v-if="heatmapData.data.length"
        :option="heatmapOption"
        :height="viewMode === 'student' ? '240px' : '400px'"
      />
    </div>

    <el-row :gutter="16">
      <el-col :span="viewMode === 'class' ? 12 : 24">
        <div class="content-card">
          <div class="content-card__title">{{ viewMode === 'class' ? '班级薄弱知识点' : '个人薄弱知识点' }}</div>
          <el-empty v-if="!weakPoints.length" description="暂无薄弱知识点" :image-size="64" />
          <el-table v-else :data="weakPoints" stripe border>
            <el-table-column prop="name" label="知识点" />
            <el-table-column prop="rate" label="掌握率" width="120" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.rate < 70 ? '#ef4444' : '#f59e0b' }">
                  {{ row.rate }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column
              v-if="viewMode === 'student'"
              prop="classRate"
              label="班级均值"
              width="100"
              align="center"
            >
              <template #default="{ row }">
                {{ row.classRate ?? '-' }}%
              </template>
            </el-table-column>
            <el-table-column v-if="viewMode === 'class'" prop="weakCount" label="薄弱人数" width="100" align="center" />
            <el-table-column prop="level" label="严重程度" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.level === '严重' ? 'danger' : row.level === '中等' ? 'warning' : 'info'" size="small">
                  {{ row.level }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col v-if="viewMode === 'class' && classStats" :span="12">
        <div class="content-card">
          <div class="content-card__title">班级知识点掌握度概览</div>
          <p class="hint-text">热力图颜色越绿表示掌握度越高，红色区域需重点关注。点击上方「学生个人」可查看单个学生的知识点掌握情况。</p>
          <el-descriptions :column="2" border style="margin-top: 12px">
            <el-descriptions-item label="班级平均掌握度">{{ classStats.avgRate }}%</el-descriptions-item>
            <el-descriptions-item label="最高掌握知识点">{{ classStats.highest.name }} ({{ classStats.highest.rate }}%)</el-descriptions-item>
            <el-descriptions-item label="最低掌握知识点">{{ classStats.lowest.name }} ({{ classStats.lowest.rate }}%)</el-descriptions-item>
            <el-descriptions-item label="需关注学生">{{ classStats.needAttentionCount }} 人</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.view-mode-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;

  .mode-label {
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
  }
}

.hint-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  margin: 0 0 8px;
}
</style>
