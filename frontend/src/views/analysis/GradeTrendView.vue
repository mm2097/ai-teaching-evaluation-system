<!--
  成绩趋势与预测分析页面
  支持班级整体 / 学生个人双视角
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import {
  User, School, Top, Bottom, Minus, MagicStick,
} from '@element-plus/icons-vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import StatCard from '@/components/common/StatCard.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import {
  fetchGradeTrend,
  fetchGradePredictions,
  fetchStudentGradeTrend,
  fetchStudentGradePrediction,
} from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import { useUserStore } from '@/stores/user'
import type {
  GradePredictionItem,
  GradeTrendData,
  StudentGradePrediction,
  StudentGradeTrendData,
} from '@/types'

type ViewMode = 'class' | 'student'

const userStore = useUserStore()
const canViewClass = computed(() => userStore.userInfo?.role !== 'student')

const viewMode = ref<ViewMode>(userStore.userInfo?.role === 'student' ? 'student' : 'class')
const loading = ref(false)

const scope = useAnalysisScope('class')
const {
  targetType,
  semesterId,
  classId,
  courseId,
  targetId,
  studentList,
  studentLoading,
  semesterOptions,
  classOptions,
  courseOptions,
  showClassFilter,
  showCourseFilter,
  queryParams,
} = scope

const classTrend = ref<GradeTrendData>({
  months: [], avgScore: [], passRate: [], maxScore: [], minScore: [],
})
const predictions = ref<GradePredictionItem[]>([])
const classFeatures = ref<{ title: string; content: string }[]>([])

const studentTrend = ref<StudentGradeTrendData>({ months: [], scores: [], classAvgScores: [] })
const studentPrediction = ref<StudentGradePrediction | null>(null)

function trendTagType(trend: string): 'success' | 'danger' | 'info' {
  if (trend === '上升') return 'success'
  if (trend === '下滑') return 'danger'
  return 'info'
}

function scoreColor(score: number): string {
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#2563eb'
  return '#ef4444'
}

async function loadTrend(): Promise<void> {
  if (!queryParams.value.courseId) return

  loading.value = true
  try {
    if (viewMode.value === 'class') {
      if (!queryParams.value.classId) return
      classTrend.value = await fetchGradeTrend({ ...queryParams.value, analysisType: '成绩趋势' })
      predictions.value = await fetchGradePredictions(queryParams.value)

      const avg = classTrend.value.avgScore.at(-1) ?? 0
      const pass = classTrend.value.passRate.at(-1) ?? 0
      classFeatures.value = [
        {
          title: '整体水平',
          content: `本课程班级最近一次平均分 ${avg}，${avg >= 80 ? '整体表现良好' : avg >= 70 ? '处于中等水平' : '需加强整体辅导'}`,
        },
        {
          title: '及格情况',
          content: `当前班级及格率 ${pass}%，${pass >= 90 ? '达标情况优秀' : pass >= 80 ? '基本达标' : '需关注后进学生'}`,
        },
        {
          title: '分化程度',
          content: `最高分 ${classTrend.value.maxScore.at(-1) ?? '-'}、最低分 ${classTrend.value.minScore.at(-1) ?? '-'}，${(classTrend.value.maxScore.at(-1) ?? 0) - (classTrend.value.minScore.at(-1) ?? 0) >= 30 ? '成绩分化较为明显' : '整体水平较均衡'}`,
        },
        {
          title: '薄弱知识点',
          content: '暂无知识点数据',
        },
      ]
      studentTrend.value = { months: [], scores: [], classAvgScores: [] }
      studentPrediction.value = null
    } else {
      if (!queryParams.value.targetId) {
        studentTrend.value = { months: [], scores: [], classAvgScores: [] }
        studentPrediction.value = null
        return
      }
      studentTrend.value = await fetchStudentGradeTrend({
        ...queryParams.value,
        analysisType: '成绩趋势',
        targetType: 'student',
      })
      studentPrediction.value = await fetchStudentGradePrediction({
        ...queryParams.value,
        analysisType: '成绩趋势',
        targetType: 'student',
      })
      classTrend.value = { months: [], avgScore: [], passRate: [], maxScore: [], minScore: [] }
      predictions.value = []
      classFeatures.value = []
    }
  } finally {
    loading.value = false
  }
}

watch(viewMode, (mode) => {
  targetType.value = mode === 'class' ? 'class' : 'student'
}, { immediate: true })

function handleViewModeChange(mode: ViewMode): void {
  viewMode.value = mode
}

// 切换课程/班级/学生时自动刷新数据
let _initialized = false
watch(queryParams, async (val) => {
  if (!_initialized) { _initialized = true; return }
  if (val.courseId && val.classId) {
    await loadTrend()
  }
}, { deep: true })

// ── 班级视角图表 ──
const classTrendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['平均分', '最高分', '最低分', '及格率'], top: 0, textStyle: { color: '#64748b' } },
  grid: { left: 50, right: 50, top: 40, bottom: 30 },
  xAxis: {
    type: 'category',
    data: classTrend.value.months,
    axisLabel: { color: '#64748b' },
  },
  yAxis: [
    { type: 'value', name: '分数', max: 100, axisLabel: { color: '#64748b' } },
    { type: 'value', name: '及格率', max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' } },
  ],
  series: [
    {
      name: '平均分', type: 'line', smooth: true,
      data: classTrend.value.avgScore,
      itemStyle: { color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.06)' },
    },
    {
      name: '最高分', type: 'line', smooth: true,
      data: classTrend.value.maxScore,
      itemStyle: { color: '#10b981' },
    },
    {
      name: '最低分', type: 'line', smooth: true,
      data: classTrend.value.minScore,
      itemStyle: { color: '#ef4444' },
    },
    {
      name: '及格率', type: 'line', smooth: true, yAxisIndex: 1,
      data: classTrend.value.passRate,
      itemStyle: { color: '#f59e0b' },
      lineStyle: { type: 'dashed' },
    },
  ],
}))

const histOption = computed<EChartsOption>(() => {
  const buckets = [0, 0, 0, 0, 0]
  predictions.value.forEach((p) => {
    if (p.current >= 90) buckets[4]!++
    else if (p.current >= 80) buckets[3]!++
    else if (p.current >= 70) buckets[2]!++
    else if (p.current >= 60) buckets[1]!++
    else buckets[0]!++
  })
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: ['0-59', '60-69', '70-79', '80-89', '90-100'],
      axisLabel: { color: '#64748b' },
    },
    yAxis: { type: 'value', name: '人数', axisLabel: { color: '#64748b' } },
    series: [{
      type: 'bar',
      data: buckets,
      barWidth: 36,
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

const classStatCards = computed(() => {
  const avg = classTrend.value.avgScore.at(-1) ?? 0
  const pass = classTrend.value.passRate.at(-1) ?? 0
  const rising = predictions.value.filter((p) => p.trend === '上升').length
  const falling = predictions.value.filter((p) => p.trend === '下滑').length
  return [
    { title: '班级平均分', value: avg, unit: '分', icon: 'TrendCharts', color: '#2563eb' },
    { title: '及格率', value: pass, unit: '%', icon: 'CircleCheck', color: '#10b981' },
    { title: '预测上升', value: rising, unit: '人', icon: 'Top', color: '#6366f1' },
    { title: '预测下滑', value: falling, unit: '人', icon: 'Bottom', color: '#ef4444' },
  ]
})

// ── 学生视角图表 ──
const studentTrendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['个人成绩', '班级均值'], top: 0, textStyle: { color: '#64748b' } },
  grid: { left: 50, right: 30, top: 40, bottom: 30 },
  xAxis: {
    type: 'category',
    data: studentTrend.value.months,
    axisLabel: { color: '#64748b' },
  },
  yAxis: {
    type: 'value', name: '分数', max: 100,
    axisLabel: { color: '#64748b' },
  },
  series: [
    {
      name: '个人成绩', type: 'line', smooth: true,
      data: studentTrend.value.scores,
      itemStyle: { color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.1)' },
      lineStyle: { width: 3 },
    },
    {
      name: '班级均值', type: 'line', smooth: true,
      data: studentTrend.value.classAvgScores,
      itemStyle: { color: '#94a3b8' },
      lineStyle: { type: 'dashed', width: 2 },
    },
  ],
}))

const compareBarOption = computed<EChartsOption>(() => {
  const p = studentPrediction.value
  if (!p) return {}
  const classAvg = p.current - p.vsClassAvg
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b' } },
    yAxis: {
      type: 'category',
      data: ['班级均值', '个人成绩'],
      axisLabel: { color: '#64748b' },
    },
    series: [{
      type: 'bar',
      data: [classAvg, p.current],
      barWidth: 20,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: (params: { dataIndex: number }) => (params.dataIndex === 1 ? '#2563eb' : '#94a3b8'),
      },
      label: { show: true, position: 'right', formatter: '{c} 分', color: '#64748b' },
    }],
  }
})

onMounted(async () => {
  await scope.loadOptions()
  await loadTrend()
})
</script>

<template>
  <div class="page-container trend-page">
    <!-- 筛选栏 -->
    <div class="content-card">
      <div class="view-mode-bar">
        <span class="mode-label">分析视角</span>
        <el-radio-group :model-value="viewMode" size="default" @update:model-value="handleViewModeChange">
          <el-radio-button v-if="canViewClass" value="class">班级成绩趋势</el-radio-button>
          <el-radio-button value="student">个人成绩趋势</el-radio-button>
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
        @query="loadTrend"
      />
    </div>

    <!-- ═══ 班级视角 ═══ -->
    <template v-if="viewMode === 'class'">
      <div v-loading="loading">
        <template v-if="classTrend.months.length">
          <div class="stat-grid">
            <StatCard v-for="item in classStatCards" :key="item.title" v-bind="item" />
          </div>

          <el-row :gutter="16">
            <el-col :xs="24" :lg="16">
              <div class="content-card">
                <div class="content-card__title">本课程班级成绩趋势</div>
                <BaseChart :option="classTrendOption" height="360px" />
              </div>
            </el-col>
            <el-col :xs="24" :lg="8">
              <div class="content-card">
                <div class="content-card__title">班级成绩等级分布</div>
                <BaseChart :option="histOption" height="360px" />
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :xs="24" :lg="16">
              <div class="content-card">
                <div class="content-card__title">全班成绩预测（线性回归算法）</div>
                <el-table :data="predictions" stripe border>
                  <el-table-column prop="name" label="学生" width="100" />
                  <el-table-column prop="current" label="当前成绩" width="100" align="center">
                    <template #default="{ row }">
                      <span :style="{ color: scoreColor(row.current), fontWeight: 600 }">{{ row.current }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="predicted" label="预测区间" width="120" align="center">
                    <template #default="{ row }">
                      <el-tag type="primary" effect="plain">{{ row.predicted }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="trend" label="趋势" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="trendTagType(row.trend)" size="small">{{ row.trend }}</el-tag>
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
            <el-col :xs="24" :lg="8">
              <div class="content-card">
                <div class="content-card__title">班级成绩特征分析</div>
                <div v-for="item in classFeatures" :key="item.title" class="feature-item">
                  <h4>{{ item.title }}</h4>
                  <p>{{ item.content }}</p>
                </div>
              </div>
            </el-col>
          </el-row>
        </template>

        <div v-else-if="!loading" class="empty-state">
          <el-icon :size="48" color="#cbd5e1"><School /></el-icon>
          <p>请选择课程与班级后点击「查询」，查看班级成绩趋势与预测</p>
        </div>
      </div>
    </template>

    <!-- ═══ 个人视角 ═══ -->
    <template v-else>
      <div v-loading="loading">
        <template v-if="studentPrediction && studentTrend.months.length">
          <!-- 个人预测 Hero -->
          <div class="student-hero">
            <div class="student-hero__bg" />
            <div class="student-hero__body">
              <div class="student-hero__left">
                <el-avatar :size="64" class="student-hero__avatar">
                  {{ studentPrediction.studentName.charAt(0) }}
                </el-avatar>
                <div>
                  <h2 class="student-hero__title">{{ studentPrediction.studentName }}</h2>
                  <p class="student-hero__meta">
                    学号 {{ studentPrediction.studentNo }} · {{ studentPrediction.className }} · {{ studentPrediction.courseName }}
                  </p>
                  <div class="hero-tags">
                    <el-tag effect="dark" size="small" class="hero-tag">
                      班级排名 {{ studentPrediction.classRank }}/{{ studentPrediction.classSize }}
                    </el-tag>
                    <el-tag
                      effect="dark" size="small" class="hero-tag"
                      :type="trendTagType(studentPrediction.trend)"
                    >
                      趋势 {{ studentPrediction.trend }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <div class="student-hero__metrics">
                <div class="metric-block">
                  <span class="metric-block__num">{{ studentPrediction.current }}</span>
                  <span class="metric-block__label">当前成绩</span>
                </div>
                <div class="metric-divider" />
                <div class="metric-block">
                  <span class="metric-block__num">{{ studentPrediction.predicted }}</span>
                  <span class="metric-block__label">预测区间</span>
                </div>
                <div class="metric-divider" />
                <div class="metric-block">
                  <span class="metric-block__num">{{ studentPrediction.confidence }}%</span>
                  <span class="metric-block__label">置信度</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 趋势 + 对比 -->
          <el-row :gutter="16">
            <el-col :xs="24" :lg="16">
              <div class="content-card">
                <div class="content-card__title">个人成绩趋势（对比班级均值）</div>
                <BaseChart :option="studentTrendOption" height="360px" />
              </div>
            </el-col>
            <el-col :xs="24" :lg="8">
              <div class="content-card">
                <div class="content-card__title">与班级均值对比</div>
                <BaseChart :option="compareBarOption" height="360px" />
                <div class="vs-class-hint">
                  <el-icon v-if="studentPrediction.vsClassAvg >= 0" color="#10b981"><Top /></el-icon>
                  <el-icon v-else color="#ef4444"><Bottom /></el-icon>
                  <span :class="studentPrediction.vsClassAvg >= 0 ? 'up' : 'down'">
                    {{ studentPrediction.vsClassAvg >= 0 ? '高于' : '低于' }}班级均值
                    {{ Math.abs(studentPrediction.vsClassAvg) }} 分
                  </span>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- 分析 + 建议 -->
          <el-row :gutter="16">
            <el-col :xs="24" :lg="14">
              <div class="content-card">
                <div class="content-card__title">个人成绩特征分析</div>
                <div class="feature-grid">
                  <div v-for="item in studentPrediction.analysisItems" :key="item.title" class="feature-item">
                    <h4>{{ item.title }}</h4>
                    <p>{{ item.content }}</p>
                  </div>
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :lg="10">
              <div class="content-card ai-panel">
                <div class="ai-panel__header">
                  <div class="ai-panel__icon">
                    <el-icon :size="20"><MagicStick /></el-icon>
                  </div>
                  <div>
                    <h3>学习建议</h3>
                    <p class="ai-panel__sub">基于个人趋势与班级对比生成</p>
                  </div>
                </div>
                <p class="ai-panel__summary">{{ studentPrediction.suggestion }}</p>
                <div class="trend-indicator">
                  <span class="trend-indicator__label">预测趋势</span>
                  <el-tag :type="trendTagType(studentPrediction.trend)" size="large" effect="plain">
                    <el-icon v-if="studentPrediction.trend === '上升'"><Top /></el-icon>
                    <el-icon v-else-if="studentPrediction.trend === '下滑'"><Bottom /></el-icon>
                    <el-icon v-else><Minus /></el-icon>
                    {{ studentPrediction.trend }}
                  </el-tag>
                  <span class="trend-indicator__range">
                    预测区间 <strong>{{ studentPrediction.predicted }}</strong> 分
                  </span>
                </div>
              </div>
            </el-col>
          </el-row>
        </template>

        <div v-else-if="!loading" class="empty-state">
          <el-icon :size="48" color="#cbd5e1"><User /></el-icon>
          <p>{{ canViewClass ? '请选择学生后点击「查询」，查看个人成绩趋势与预测' : '暂无成绩趋势数据' }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.trend-page {
  .view-mode-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid #f1f5f9;
  }

  .mode-label {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
    flex-shrink: 0;
  }
}

.feature-item {
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 12px;
  border-left: 3px solid #2563eb;

  h4 {
    font-size: 14px;
    color: #1e293b;
    margin-bottom: 6px;
    font-weight: 600;
  }

  p {
    font-size: 13px;
    color: #64748b;
    line-height: 1.6;
  }
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;

  .feature-item {
    margin-bottom: 0;
  }
}

// ── 个人 Hero ──
.student-hero {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(37, 99, 235, 0.15);

  &__bg {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 50%, #3b82f6 100%);
  }

  &__body {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28px 32px;
    gap: 24px;
    flex-wrap: wrap;
  }

  &__left {
    display: flex;
    align-items: center;
    gap: 18px;
  }

  &__avatar {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
    font-size: 24px;
    font-weight: 700;
    border: 2px solid rgba(255, 255, 255, 0.4);
    flex-shrink: 0;
  }

  &__title {
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 4px;
  }

  &__meta {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.75);
    margin-bottom: 10px;
  }

  &__metrics {
    display: flex;
    align-items: center;
    gap: 20px;
    background: rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(8px);
    border-radius: 14px;
    padding: 16px 24px;
  }
}

.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-tag {
  background: rgba(255, 255, 255, 0.18) !important;
  border-color: rgba(255, 255, 255, 0.3) !important;
  color: #fff !important;
}

.metric-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 72px;

  &__num {
    font-size: 26px;
    font-weight: 800;
    color: #fff;
    line-height: 1;
  }

  &__label {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
  }
}

.metric-divider {
  width: 1px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
}

.vs-class-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 13px;

  .up { color: #10b981; font-weight: 500; }
  .down { color: #ef4444; font-weight: 500; }
}

// ── AI 建议面板 ──
.ai-panel {
  background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
  border: 1px solid rgba(37, 99, 235, 0.12);
  height: 100%;

  &__header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;

    h3 {
      font-size: 15px;
      font-weight: 600;
      color: #1e293b;
    }
  }

  &__icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, #2563eb, #6366f1);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 2px;
  }

  &__summary {
    font-size: 14px;
    color: #334155;
    line-height: 1.8;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.7);
    border-radius: 10px;
    margin-bottom: 16px;
  }
}

.trend-indicator {
  display: flex;
  flex-direction: column;
  gap: 10px;

  &__label {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
  }

  &__range {
    font-size: 13px;
    color: #64748b;

    strong {
      color: #2563eb;
      font-size: 15px;
    }
  }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;

  p {
    margin-top: 16px;
    font-size: 14px;
  }
}
</style>
