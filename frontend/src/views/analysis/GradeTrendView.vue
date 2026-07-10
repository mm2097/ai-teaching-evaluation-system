<!--
  成绩趋势与预测分析页面
  展示班级成绩趋势、分布与个人预测结果
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { fetchGradeTrend, fetchGradePredictions } from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'

const scope = useAnalysisScope('class')
const {
  allowedTargetTypes, targetType, semesterId, classId, courseId, targetId,
  studentList, studentLoading,
  semesterOptions, classOptions, courseOptions,
  showClassFilter, showCourseFilter, showTargetTypeFilter, showStudentPicker,
  queryParams,
} = scope

const trendData = ref({ months: [] as string[], avgScore: [] as number[], passRate: [] as number[], maxScore: [] as number[], minScore: [] as number[] })
const predictions = ref<{ name: string; current: number; predicted: string; trend: string; confidence: number }[]>([])
const classFeatures = ref<{ title: string; content: string }[]>([])

async function loadTrend(): Promise<void> {
  if (!queryParams.value.courseId || !queryParams.value.classId) return
  trendData.value = await fetchGradeTrend({ ...queryParams.value, analysisType: '成绩趋势' })
  predictions.value = await fetchGradePredictions(queryParams.value)

  const kps: string[] = []
  const avg = trendData.value.avgScore.at(-1) ?? 0
  classFeatures.value = [
    { title: '整体水平', content: `本课程班级最近一次平均分 ${avg}，${avg >= 80 ? '整体表现良好' : avg >= 70 ? '处于中等水平' : '需加强整体辅导'}` },
    { title: '分化程度', content: `最高分 ${trendData.value.maxScore.at(-1) ?? '-'}、最低分 ${trendData.value.minScore.at(-1) ?? '-'}，存在一定成绩分化` },
    { title: '薄弱知识点', content: kps.length ? `建议重点关注 ${kps.slice(-2).join('、')} 等知识点` : '暂无知识点数据' },
  ]
}

onMounted(async () => {
  await scope.loadOptions()
  await loadTrend()
})

// 切换课程/班级/学生时自动刷新数据
let _initialized = false
watch(queryParams, async (val) => {
  if (!_initialized) { _initialized = true; return }
  if (val.courseId && val.classId) {
    await loadTrend()
  }
}, { deep: true })

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['平均分', '最高分', '最低分', '及格率'], top: 0 },
  grid: { left: 50, right: 50, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: trendData.value.months },
  yAxis: [
    { type: 'value', name: '分数', max: 100 },
    { type: 'value', name: '及格率', max: 100, axisLabel: { formatter: '{value}%' } },
  ],
  series: [
    { name: '平均分', type: 'line', smooth: true, data: trendData.value.avgScore, itemStyle: { color: '#2563eb' } },
    { name: '最高分', type: 'line', smooth: true, data: trendData.value.maxScore, itemStyle: { color: '#10b981' } },
    { name: '最低分', type: 'line', smooth: true, data: trendData.value.minScore, itemStyle: { color: '#ef4444' } },
    { name: '及格率', type: 'line', smooth: true, yAxisIndex: 1, data: trendData.value.passRate, itemStyle: { color: '#f59e0b' }, lineStyle: { type: 'dashed' } },
  ],
}))

const histOption = computed<EChartsOption>(() => {
  const preds = predictions.value
  const counts = [0, 0, 0, 0, 0]
  preds.forEach((p) => {
    if (p.current >= 90) counts[4]!++
    else if (p.current >= 80) counts[3]!++
    else if (p.current >= 70) counts[2]!++
    else if (p.current >= 60) counts[1]!++
    else counts[0]!++
  })
  const total = preds.length || 1
  const percentages = counts.map(b => Math.round((b / total) * 100))
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (params as { dataIndex: number; name: string; marker: string }[])[0]!
        return `${p.name}<br/>${p.marker} 占比: ${percentages[p.dataIndex]}%（${counts[p.dataIndex]}人）`
      },
    },
    grid: { left: 55, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: ['0-59', '60-69', '70-79', '80-89', '90-100'], axisLabel: { interval: 0 } },
    yAxis: { type: 'value', name: '占比', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    series: [{
      type: 'bar',
      data: percentages,
      barMaxWidth: 50,
      barCategoryGap: '20%',
      itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: (params: { dataIndex: number }) => {
          const colors = ['#ef4444', '#f59e0b', '#2563eb', '#10b981', '#6366f1']
          return colors[params.dataIndex] || '#2563eb'
        },
      },
    }],
  }
})

const chartTitle = computed(() =>
  targetType.value === 'student' ? '个人成绩趋势' : '本课程班级成绩趋势',
)
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <AnalysisFilterBar
        v-model:target-type="targetType"
        v-model:semester-id="semesterId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="allowedTargetTypes"
        :semester-options="semesterOptions"
        :show-dept-filter="false"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="showTargetTypeFilter"
        :show-student-picker="showStudentPicker"
        :student-list="studentList"
        :student-loading="studentLoading"
        :show-query-button="true"
        :class-options="classOptions"
        :course-options="courseOptions"
        @query="loadTrend"
      />
    </div>

    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">{{ chartTitle }}</div>
          <BaseChart :option="trendOption" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">成绩分布</div>
          <BaseChart :option="histOption" height="360px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">个人成绩预测（线性回归算法）</div>
          <el-table :data="predictions" stripe border>
            <el-table-column prop="name" label="学生" width="100" />
            <el-table-column prop="current" label="当前成绩" width="100" align="center" />
            <el-table-column prop="predicted" label="预测区间" width="120" align="center">
              <template #default="{ row }">
                <el-tag type="primary" effect="plain">{{ row.predicted }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="trend" label="趋势" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.trend === '上升' ? 'success' : row.trend === '下滑' ? 'danger' : 'info'" size="small">
                  {{ row.trend }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" align="center">
              <template #default="{ row }">
                <el-progress :percentage="row.confidence" :stroke-width="6" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">班级成绩特征分析</div>
          <div v-for="item in classFeatures" :key="item.title" class="feature-item">
            <h4>{{ item.title }}</h4>
            <p>{{ item.content }}</p>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.feature-item {
  padding: 14px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;
  border-left: 3px solid #2563eb;

  h4 {
    font-size: 14px;
    color: #1e293b;
    margin-bottom: 6px;
  }

  p {
    font-size: 13px;
    color: #64748b;
    line-height: 1.6;
  }
}
</style>
