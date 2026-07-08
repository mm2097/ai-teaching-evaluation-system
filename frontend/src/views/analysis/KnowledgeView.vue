<!--
  知识点掌握度分析页面
  以热力图为核心，支持班级整体 / 学生个人视角切换
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { fetchKnowledgeHeatmap } from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'

type ViewMode = 'class' | 'student'

const viewMode = ref<ViewMode>('class')

const scope = useAnalysisScope('class')
const {
  targetType, semesterId, classId, courseId, targetId, studentKeyword,
  semesterOptions, classOptions, courseOptions, targetOptions,
  showClassFilter, showCourseFilter, showStudentPicker,
  queryParams, loadStudentOptions,
} = scope

const heatmapData = ref({
  knowledgePoints: [] as string[],
  students: [] as string[],
  data: [] as number[][],
})

async function loadHeatmap(): Promise<void> {
  const params = {
    ...queryParams.value,
    analysisType: '知识点掌握度',
    targetType: viewMode.value === 'class' ? 'class' as const : 'student' as const,
    targetId: viewMode.value === 'student' ? targetId.value : classId.value,
  }
  heatmapData.value = await fetchKnowledgeHeatmap(params)
}

watch([queryParams, viewMode], () => {
  // 关键参数未就绪时跳过，避免无效请求
  if (viewMode.value === 'class' && classId.value == null) return
  if (viewMode.value === 'student' && targetId.value == null) return
  loadHeatmap()
}, { immediate: true })

watch(viewMode, (mode) => {
  targetType.value = mode === 'class' ? 'class' : 'student'
})

const heatmapTitle = computed(() =>
  viewMode.value === 'class' ? '班级知识点掌握度热力图' : '学生个人知识点掌握度热力图',
)

const heatmapOption = computed<EChartsOption>(() => {
  const isPersonal = viewMode.value === 'student'
  return {
    tooltip: {
      position: 'top',
      formatter: (params: unknown) => {
        const p = params as { value: number[] }
        const [x, y, val] = p.value
        if (isPersonal) {
          return `${heatmapData.value.knowledgePoints[x!]}<br/>掌握度: ${val}%`
        }
        return `${heatmapData.value.students[y!]} - ${heatmapData.value.knowledgePoints[x!]}<br/>掌握度: ${val}%`
      },
    },
    grid: { left: isPersonal ? 20 : 80, right: 40, top: 10, bottom: 60 },
    xAxis: {
      type: 'category',
      data: heatmapData.value.knowledgePoints,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: isPersonal
      ? { type: 'category', data: [''], show: false } as EChartsOption['yAxis']
      : {
          type: 'category',
          data: heatmapData.value.students,
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
      data: heatmapData.value.data,
      label: { show: false },
    }],
  }
})

const weakPoints = computed(() => {
  if (viewMode.value === 'student' && heatmapData.value.data.length) {
    return heatmapData.value.data
      .map(([x, , val]) => ({
        name: heatmapData.value.knowledgePoints[x!]!,
        rate: val!,
        level: val! < 60 ? '严重' : val! < 75 ? '中等' : '轻微',
      }))
      .filter((p) => p.rate < 75)
      .sort((a, b) => a.rate - b.rate)
  }
  return [
    { name: '面向对象', rate: 62, weakCount: 18, level: '严重' },
    { name: '异常处理', rate: 66, weakCount: 15, level: '中等' },
    { name: '文件IO', rate: 70, weakCount: 12, level: '中等' },
    { name: '控制结构', rate: 78, weakCount: 8, level: '轻微' },
  ]
})

async function handleStudentSearch(keyword: string): Promise<void> {
  studentKeyword.value = keyword
  await loadStudentOptions(keyword)
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="view-mode-bar">
        <span class="mode-label">分析视角：</span>
        <el-radio-group v-model="viewMode" size="default">
          <el-radio-button value="class">班级整体</el-radio-button>
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
        :show-student-picker="viewMode === 'student'"
        :class-options="classOptions"
        :course-options="courseOptions"
        :target-options="targetOptions"
        :enable-student-search="viewMode === 'student'"
        @student-search="handleStudentSearch"
      />
    </div>

    <div class="content-card">
      <div class="content-card__title">{{ heatmapTitle }}</div>
      <el-skeleton v-if="heatmapData.data.length === 0" :rows="5" animated style="padding: 20px" />
      <BaseChart
        v-else
        :option="heatmapOption"
        :height="viewMode === 'student' ? '200px' : '400px'"
      />
    </div>

    <el-row :gutter="16">
      <el-col :span="viewMode === 'class' ? 12 : 24">
        <div class="content-card">
          <div class="content-card__title">{{ viewMode === 'class' ? '班级薄弱知识点' : '个人薄弱知识点' }}</div>
          <el-table :data="weakPoints" stripe border>
            <el-table-column prop="name" label="知识点" />
            <el-table-column :prop="viewMode === 'class' ? 'classRate' : 'rate'" label="掌握率" width="120" align="center">
              <template #default="{ row }">
                <span :style="{ color: (row.rate ?? row.classRate) < 70 ? '#ef4444' : '#f59e0b' }">
                  {{ row.rate ?? row.classRate }}%
                </span>
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
      <el-col v-if="viewMode === 'class'" :span="12">
        <div class="content-card">
          <div class="content-card__title">班级知识点掌握度概览</div>
          <p class="hint-text">热力图颜色越绿表示掌握度越高，红色区域需重点关注。点击上方「学生个人」可查看单个学生的知识点掌握情况。</p>
          <el-descriptions :column="2" border style="margin-top: 12px">
            <el-descriptions-item label="班级平均掌握度">76.8%</el-descriptions-item>
            <el-descriptions-item label="最高掌握知识点">变量与表达式 (92%)</el-descriptions-item>
            <el-descriptions-item label="最低掌握知识点">面向对象 (62%)</el-descriptions-item>
            <el-descriptions-item label="需关注学生">18 人</el-descriptions-item>
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
}
</style>
