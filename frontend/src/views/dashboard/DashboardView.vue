<!--
  综合数据看板页面
  面向计算机学院单课程/单班级学情概览
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import StatCard from '@/components/common/StatCard.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import { fetchClasses, fetchCourses } from '@/api/dict'
import { computeClassKnowledgeStats } from '@/api/analysis'
import { useUserStore } from '@/stores/user'
import {
  buildCourseClassHeatmap,
  dashboardFilterFactors,
  dashboardStats,
  getStudentsInCourseClass,
  gradeOptions,
  semesterOptions,
  warningRecords,
} from '@/mock'

const router = useRouter()
const userStore = useUserStore()

const filters = ref({
  semester: '2025-2026-1',
  courseId: 1,
  classId: 1,
  grade: '',
})

const courseOptions = ref<{ label: string; value: number }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const applied = ref({ ...filters.value })

async function loadFilterOptions(): Promise<void> {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (!courseOptions.value.some((c) => c.value === filters.value.courseId)) {
    filters.value.courseId = courseOptions.value[0]?.value ?? 1
  }

  const classes = await fetchClasses({ deptId: 1, courseId: filters.value.courseId, teacherId })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (!classOptions.value.some((c) => c.value === filters.value.classId)) {
    filters.value.classId = classOptions.value[0]?.value ?? 1
  }
}

watch(() => filters.value.courseId, async (courseId) => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const classes = await fetchClasses({ deptId: 1, courseId, teacherId })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (!classOptions.value.some((c) => c.value === filters.value.classId)) {
    filters.value.classId = classOptions.value[0]?.value
  }
})

function applyFilters(): void {
  applied.value = { ...filters.value }
}

onMounted(async () => {
  await loadFilterOptions()
  applyFilters()
})

const filterFactor = computed(() => {
  const gradeFactor = dashboardFilterFactors.grade[applied.value.grade || ''] ?? 1
  const semFactor = dashboardFilterFactors.semester[applied.value.semester || ''] ?? 1
  return gradeFactor * semFactor
})

const classStudentCount = computed(() =>
  getStudentsInCourseClass(applied.value.courseId, applied.value.classId).length,
)

const classWarningCount = computed(() =>
  warningRecords.filter(
    (w) => w.classId === applied.value.classId && w.courseId === applied.value.courseId,
  ).length,
)

const knowledgeStats = computed(() => {
  const heatmap = buildCourseClassHeatmap(applied.value.courseId, applied.value.classId)
  return computeClassKnowledgeStats(heatmap)
})

const statCards = computed(() => {
  const f = filterFactor.value
  const courseName = courseOptions.value.find((c) => c.value === applied.value.courseId)?.label || '—'
  return [
    { title: '班级学生数', value: classStudentCount.value, icon: 'User', color: '#2563eb', trend: 0 },
    { title: '当前课程', value: courseName, icon: 'Notebook', color: '#6366f1' },
    { title: '课程及格率', value: +(dashboardStats.passRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'CircleCheck', color: '#10b981', trend: 3.2 },
    { title: '优秀率', value: +(dashboardStats.excellentRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'Star', color: '#f59e0b', trend: 1.8 },
    { title: '平均出勤率', value: +(dashboardStats.attendanceRate * (0.98 + f * 0.02)).toFixed(1), unit: '%', icon: 'Calendar', color: '#06b6d4', trend: -0.5 },
    { title: '预警学生', value: classWarningCount.value, icon: 'Bell', color: '#ef4444', trend: -12, link: '/analysis/warning' },
    { title: '知识点薄弱项', value: knowledgeStats.value.weakPoints.length, icon: 'Grid', color: '#8b5cf6', link: '/analysis/knowledge' },
    { title: 'AI 练习完成率', value: 78.5, unit: '%', icon: 'EditPen', color: '#ec4899', link: '/quiz/manage' },
  ]
})

const scorePieOption = computed<EChartsOption>(() => {
  const heatmap = buildCourseClassHeatmap(applied.value.courseId, applied.value.classId)
  const buckets = [0, 0, 0, 0, 0]
  const studentCount = heatmap.students.length
  heatmap.students.forEach((_, sIdx) => {
    const values = heatmap.data.filter((d) => d[1] === sIdx).map((d) => d[2]!)
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    if (avg >= 90) buckets[4]!++
    else if (avg >= 80) buckets[3]!++
    else if (avg >= 70) buckets[2]!++
    else if (avg >= 60) buckets[1]!++
    else buckets[0]!++
  })
  if (!studentCount) {
    buckets.splice(0, buckets.length, 0, 0, 0, 0, 0)
  }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#64748b' } },
    color: ['#10b981', '#2563eb', '#f59e0b', '#ef4444', '#94a3b8'],
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: [
        { name: '优秀 (90+)', value: buckets[4] },
        { name: '良好 (80-89)', value: buckets[3] },
        { name: '中等 (70-79)', value: buckets[2] },
        { name: '合格 (60-69)', value: buckets[1] },
        { name: '不合格 (<60)', value: buckets[0] },
      ],
    }],
  }
})

const knowledgeBarOption = computed<EChartsOption>(() => {
  const heatmap = buildCourseClassHeatmap(applied.value.courseId, applied.value.classId)
  const stats = computeClassKnowledgeStats(heatmap)
  const kpStats = heatmap.knowledgePoints
    .map((name, i) => ({ name, rate: stats.classAvgByKp[i] ?? 0 }))
    .sort((a, b) => a.rate - b.rate)
    .slice(0, 6)
  const names = kpStats.map((p) => p.name)
  const rates = kpStats.map((p) => p.rate)

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 100, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#64748b', formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#64748b' },
    },
    series: [{
      type: 'bar',
      data: rates,
      barWidth: 16,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: (params: { dataIndex: number }) => {
          const val = rates[params.dataIndex] ?? 0
          return val < 70 ? '#ef4444' : val < 80 ? '#f59e0b' : '#10b981'
        },
      },
    }],
  }
})

const trendLineOption = computed<EChartsOption>(() => {
  const semFactor = dashboardFilterFactors.semester[applied.value.semester] ?? 1
  const passBase = [82, 84, 85, 83, 87, 89]
  const excBase = [20, 21, 22, 21, 23, 24]
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['及格率', '优秀率'], top: 0, textStyle: { color: '#64748b' } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: ['9月', '10月', '11月', '12月', '1月', '2月'],
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#64748b', formatter: '{value}%' },
    },
    series: [
      {
        name: '及格率',
        type: 'line',
        smooth: true,
        data: passBase.map((v) => +(v * (0.95 + semFactor * 0.05)).toFixed(1)),
        itemStyle: { color: '#2563eb' },
        areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
      },
      {
        name: '优秀率',
        type: 'line',
        smooth: true,
        data: excBase.map((v) => +(v * (0.95 + semFactor * 0.05)).toFixed(1)),
        itemStyle: { color: '#10b981' },
        areaStyle: { color: 'rgba(16, 185, 129, 0.08)' },
      },
    ],
  }
})

function handleStatClick(item: { link?: string }): void {
  if (item.link) router.push(item.link)
}
</script>

<template>
  <div class="page-container dashboard-page">
    <div class="content-card">
      <div class="filter-bar">
        <span class="filter-label">计算机学院 · </span>
        <el-select v-model="filters.semester" placeholder="选择学期" style="width: 220px">
          <el-option v-for="item in semesterOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.courseId" placeholder="选择课程" style="width: 160px">
          <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="filters.classId" placeholder="选择班级" style="width: 140px">
          <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="filters.grade" placeholder="选择年级" clearable style="width: 120px">
          <el-option v-for="item in gradeOptions.filter(g => g.value)" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <StatCard
        v-for="item in statCards"
        :key="item.title"
        v-bind="item"
        :class="{ clickable: item.link }"
        @click="handleStatClick(item)"
      />
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">班级成绩等级分布</div>
          <BaseChart :option="scorePieOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">课程知识点掌握度</div>
          <BaseChart :option="knowledgeBarOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">课程质量趋势</div>
          <BaseChart :option="trendLineOption" height="320px" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.dashboard-page {
  .filter-label {
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
  }

  .clickable {
    cursor: pointer;
  }
}
</style>
