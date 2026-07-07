<!--
  综合数据看板页面
  面向计算机学院单课程/单班级学情概览
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import StatCard from '@/components/common/StatCard.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import { dashboardStats, gradeOptions, semesterOptions, dashboardFilterFactors, courses } from '@/mock'

const router = useRouter()

const filters = ref({
  semester: '2025-2026-1',
  courseId: 1,
  classId: 1,
  grade: '',
})

const csCourses = computed(() => courses.filter((c) => c.deptId === 1))
const csClasses = [
  { label: '计科2401', value: 1 },
  { label: '计科2402', value: 2 },
  { label: '软工2401', value: 3 },
]

const filterFactor = computed(() => {
  const gradeFactor = dashboardFilterFactors.grade[filters.value.grade || ''] ?? 1
  const semFactor = dashboardFilterFactors.semester[filters.value.semester || ''] ?? 1
  return gradeFactor * semFactor * 0.35
})

const statCards = computed(() => {
  const f = filterFactor.value
  return [
    { title: '班级学生数', value: Math.round(42 * f * 3), icon: 'User', color: '#2563eb', trend: 0 },
    { title: '当前课程', value: csCourses.value.find((c) => c.id === filters.value.courseId)?.courseName || '—', icon: 'Notebook', color: '#6366f1' },
    { title: '课程及格率', value: +(dashboardStats.passRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'CircleCheck', color: '#10b981', trend: 3.2 },
    { title: '优秀率', value: +(dashboardStats.excellentRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'Star', color: '#f59e0b', trend: 1.8 },
    { title: '平均出勤率', value: +(dashboardStats.attendanceRate * (0.98 + f * 0.02)).toFixed(1), unit: '%', icon: 'Calendar', color: '#06b6d4', trend: -0.5 },
    { title: '预警学生', value: Math.max(1, Math.round(12 * f)), icon: 'Bell', color: '#ef4444', trend: -12, link: '/analysis/warning' },
    { title: '知识点薄弱项', value: 4, icon: 'Grid', color: '#8b5cf6', link: '/analysis/knowledge' },
    { title: 'AI 练习完成率', value: 78.5, unit: '%', icon: 'EditPen', color: '#ec4899', link: '/quiz/manage' },
  ]
})

const scorePieOption = computed<EChartsOption>(() => {
  const f = filterFactor.value
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
        { name: '优秀 (90+)', value: Math.round(12 * f) },
        { name: '良好 (80-89)', value: Math.round(15 * f) },
        { name: '中等 (70-79)', value: Math.round(10 * f) },
        { name: '合格 (60-69)', value: Math.round(4 * f) },
        { name: '不合格 (<60)', value: Math.round(3 * f) },
      ],
    }],
  }
})

const knowledgeBarOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 100, right: 20, top: 30, bottom: 30 },
  xAxis: {
    type: 'value',
    max: 100,
    axisLabel: { color: '#64748b', formatter: '{value}%' },
  },
  yAxis: {
    type: 'category',
    data: ['面向对象', '异常处理', '文件IO', '控制结构', '函数定义', '数组操作'],
    axisLabel: { color: '#64748b' },
  },
  series: [{
    type: 'bar',
    data: [62, 66, 70, 78, 82, 85],
    barWidth: 16,
    itemStyle: {
      borderRadius: [0, 4, 4, 0],
      color: (params: { dataIndex: number }) => {
        const val = [62, 66, 70, 78, 82, 85][params.dataIndex]!
        return val < 70 ? '#ef4444' : val < 80 ? '#f59e0b' : '#10b981'
      },
    },
  }],
}))

const trendLineOption = computed<EChartsOption>(() => {
  const semFactor = dashboardFilterFactors.semester[filters.value.semester] ?? 1
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
          <el-option v-for="c in csCourses" :key="c.id" :label="c.courseName" :value="c.id" />
        </el-select>
        <el-select v-model="filters.classId" placeholder="选择班级" style="width: 140px">
          <el-option v-for="c in csClasses" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="filters.grade" placeholder="选择年级" clearable style="width: 120px">
          <el-option v-for="item in gradeOptions.filter(g => g.value)" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
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
