<!--
  学生首页
  展示个人课程概览、核心学习指标
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import StatCard from '@/components/common/StatCard.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'
import {
  fetchStudentDashboardOverview,
  type StudentDashboardCourse,
  type StudentDashboardOverview,
} from '@/api/studentDashboard'

const userStore = useUserStore()
const loading = ref(true)
const overview = ref<StudentDashboardOverview | null>(null)

/** 学生个人课程概览 */
const courses = computed<StudentDashboardCourse[]>(() => overview.value?.courses ?? [])
const trendMonths = ref<string[]>([])
const trendAvgScore = ref<number[]>([])

const welcomeMeta = computed(() => {
  const student = overview.value?.student
  return [
    student?.college || userStore.userInfo?.department,
    student?.className,
    `学号 ${student?.studentNo || userStore.userInfo?.studentNo || '—'}`,
  ].filter(Boolean).join(' · ')
})

/** 最近两次成绩的相对变化率 */
const scoreTrend = computed<number | undefined>(() => {
  if (trendAvgScore.value.length < 2) return undefined
  const previous = trendAvgScore.value.at(-2)
  const current = trendAvgScore.value.at(-1)
  if (previous === undefined || current === undefined || previous === 0) return undefined
  return +(((current - previous) / previous) * 100).toFixed(1)
})

interface StatCardItem {
  title: string
  value: number | string
  unit?: string
  icon: string
  color: string
  trend?: number
}

const statCards = computed<StatCardItem[]>(() => {
  const summary = overview.value?.summary
  const hasAverage = summary?.averageScore != null
  const hasAttendance = summary?.attendanceRate != null
  return [
    { title: '课程数', value: summary?.courseCount ?? 0, icon: 'Notebook', color: '#2563eb' },
    {
      title: '平均成绩',
      value: summary?.averageScore ?? '—',
      unit: hasAverage ? '分' : undefined,
      icon: 'DataLine',
      color: '#10b981',
      trend: scoreTrend.value,
    },
    {
      title: '总出勤率',
      value: summary?.attendanceRate ?? '—',
      unit: hasAttendance ? '%' : undefined,
      icon: 'Calendar',
      color: '#06b6d4',
    },
    { title: '待完成练习', value: summary?.pendingQuizCount ?? 0, icon: 'EditPen', color: '#f59e0b' },
    { title: '薄弱知识点', value: summary?.weakKnowledgeCount ?? 0, icon: 'Grid', color: '#ef4444' },
    { title: '班级排名', value: summary?.classRankText ?? '暂无', icon: 'Trophy', color: '#8b5cf6' },
  ]
})

/** 各课程成绩柱状图 */
const scoreBarOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: courses.value.map((c) => c.name),
    axisLabel: { color: '#64748b' },
  },
  yAxis: { type: 'value', max: 100, name: '分数', axisLabel: { color: '#64748b' } },
  series: [
    {
      name: '我的成绩',
      type: 'bar',
      data: courses.value.map((c) => c.score),
      barWidth: 28,
      itemStyle: { color: '#2563eb', borderRadius: [6, 6, 0, 0] },
    },
    {
      name: '班级均分',
      type: 'bar',
      data: courses.value.map((c) => c.avgScore),
      barWidth: 28,
      itemStyle: { color: '#94a3b8', borderRadius: [6, 6, 0, 0] },
    },
  ],
  legend: { top: 0, textStyle: { color: '#64748b' } },
  grid: { left: 50, right: 20, top: 40, bottom: 30 },
}))

const hasCourseScores = computed(() => courses.value.some(
  (course) => course.score !== null || course.avgScore !== null,
))
const hasTrendScores = computed(() => trendAvgScore.value.length > 0)

function formatScore(score: number | null): string {
  return score === null ? '暂无' : `${score} 分`
}

/** 成绩趋势 */
const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: trendMonths.value, axisLabel: { color: '#64748b' } },
  yAxis: { type: 'value', max: 100, name: '分数' },
  series: [{
    name: '平均分',
    type: 'line',
    smooth: true,
    data: trendAvgScore.value,
    itemStyle: { color: '#2563eb' },
    areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
  }],
  grid: { left: 50, right: 20, top: 20, bottom: 30 },
}))

onMounted(async () => {
  const studentId = userStore.userInfo?.studentId
  const overviewPromise = fetchStudentDashboardOverview()
  const trendPromise = studentId
    ? request.get('/v1/dashboard/grade-trend', { params: { student_id: studentId } })
    : Promise.resolve(null)

  const [overviewResult, trendResult] = await Promise.allSettled([
    overviewPromise,
    trendPromise,
  ])

  if (overviewResult.status === 'fulfilled') {
    overview.value = overviewResult.value
  }
  if (trendResult.status === 'fulfilled' && trendResult.value) {
    const trendRes = trendResult.value
    if (trendRes.data?.months) {
      trendMonths.value = trendRes.data.months
      trendAvgScore.value = trendRes.data.avgScore ?? trendRes.data.avg_score ?? []
    } else if (trendRes.data?.labels) {
      // 兼容 mock 数据格式
      trendMonths.value = trendRes.data.labels
      trendAvgScore.value = trendRes.data.avgScore ?? trendRes.data.avg_score ?? []
    }
  }
  loading.value = false
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 欢迎区 -->
    <div class="content-card welcome-card">
      <div class="welcome-info">
        <h2>欢迎回来，{{ overview?.student.name || userStore.userInfo?.name || '同学' }}</h2>
        <p>{{ welcomeMeta }}</p>
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="stat-grid">
      <StatCard
        v-for="item in statCards"
        :key="item.title"
        v-bind="item"
      />
    </div>

    <!-- 课程列表 -->
    <div class="content-card">
      <div class="content-card__title">我的课程</div>
      <div v-if="courses.length" class="course-grid">
        <div v-for="course in courses" :key="course.id" class="course-card">
          <div class="course-header">
            <h3>{{ course.name }}</h3>
            <el-tag v-if="course.rank !== null" size="small" type="success">{{ course.rankText }}</el-tag>
          </div>
          <p class="course-teacher">任课教师：{{ course.teacher }}</p>
          <div class="course-score">
            <span class="score-label">我的成绩</span>
            <span class="score-value" :class="{ 'score-value--empty': course.score === null }">
              {{ formatScore(course.score) }}
            </span>
          </div>
          <div class="course-progress">
            <span class="progress-label">练习完成度</span>
            <el-progress
              v-if="course.progress !== null"
              :percentage="course.progress"
              :stroke-width="8"
              :color="course.progress >= 70 ? '#10b981' : '#f59e0b'"
            />
            <span v-else class="no-progress">暂无练习数据</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无已选课程" />
    </div>

    <!-- 图表区 -->
    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <div class="content-card">
          <div class="content-card__title">各课程成绩对比</div>
          <BaseChart v-if="hasCourseScores" :option="scoreBarOption" height="300px" />
          <el-empty v-else class="chart-empty" description="暂无课程成绩" />
        </div>
      </el-col>
      <el-col :xs="24" :md="12">
        <div class="content-card">
          <div class="content-card__title">成绩变化趋势</div>
          <BaseChart v-if="hasTrendScores" :option="trendOption" height="300px" />
          <el-empty v-else class="chart-empty" description="暂无成绩趋势" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.welcome-card {
  background: linear-gradient(135deg, #2563eb, #6366f1);
  color: #fff;
  padding: 28px 32px;

  h2 { font-size: 22px; margin-bottom: 6px; }
  p { font-size: 14px; opacity: 0.85; }
}

.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.course-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  transition: box-shadow 0.2s;

  &:hover { box-shadow: 0 2px 12px rgba(37, 99, 235, 0.1); }

  .course-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    h3 { font-size: 16px; }
  }

  .course-teacher {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 16px;
  }

  .course-score {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .score-label { font-size: 13px; color: #64748b; }
    .score-value { font-size: 20px; font-weight: 700; color: #2563eb; }
    .score-value--empty { font-size: 14px; font-weight: 500; color: #94a3b8; }
  }

  .course-progress {
    .progress-label { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 6px; }
    .no-progress { font-size: 12px; color: #94a3b8; line-height: 16px; }
  }
}

.chart-empty {
  min-height: 300px;
}
</style>
