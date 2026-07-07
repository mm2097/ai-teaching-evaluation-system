<!--
  综合数据看板页面
  展示核心教学指标概览，支持学期/院系/年级筛选
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { EChartsOption } from 'echarts'
import StatCard from '@/components/common/StatCard.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import { dashboardStats, departmentOptions, gradeOptions, semesterOptions } from '@/mock'

/** 筛选条件 */
const filters = ref({
  semester: '2025-1',
  department: '',
  grade: '',
})

/** 顶部统计卡片数据 */
const statCards = computed(() => [
  { title: '学生总数', value: dashboardStats.studentCount, icon: 'User', color: '#2563eb', trend: 2.3 },
  { title: '课程总数', value: dashboardStats.courseCount, icon: 'Notebook', color: '#6366f1', trend: 1.5 },
  { title: '教师总数', value: dashboardStats.teacherCount, icon: 'Avatar', color: '#8b5cf6', trend: 0.8 },
  { title: '整体及格率', value: dashboardStats.passRate, unit: '%', icon: 'CircleCheck', color: '#10b981', trend: 3.2 },
  { title: '优秀率', value: dashboardStats.excellentRate, unit: '%', icon: 'Star', color: '#f59e0b', trend: 1.8 },
  { title: '平均出勤率', value: dashboardStats.attendanceRate, unit: '%', icon: 'Calendar', color: '#06b6d4', trend: -0.5 },
  { title: '预警学生', value: dashboardStats.warningCount, icon: 'Bell', color: '#ef4444', trend: -12 },
  { title: '优秀教师', value: dashboardStats.excellentTeacherCount, icon: 'Trophy', color: '#ec4899' },
])

/** 成绩分布饼图配置 */
const scorePieOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: '#64748b' } },
  color: ['#10b981', '#2563eb', '#f59e0b', '#ef4444', '#94a3b8'],
  series: [
    {
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: [
        { name: '优秀 (90+)', value: 667 },
        { name: '良好 (80-89)', value: 854 },
        { name: '中等 (70-79)', value: 712 },
        { name: '合格 (60-69)', value: 398 },
        { name: '不合格 (<60)', value: 215 },
      ],
    },
  ],
}))

/** 各院系及格率柱状图 */
const deptBarOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 30, bottom: 30 },
  xAxis: {
    type: 'category',
    data: ['计算机学院', '数学学院', '外国语学院', '经管学院', '物理学院'],
    axisLabel: { color: '#64748b' },
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: { color: '#64748b', formatter: '{value}%' },
  },
  series: [
    {
      type: 'bar',
      data: [89.2, 85.6, 91.3, 83.8, 87.1],
      barWidth: 32,
      itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#2563eb' },
            { offset: 1, color: '#93c5fd' },
          ],
        },
      },
    },
  ],
}))

/** 月度趋势折线图 */
const trendLineOption = computed<EChartsOption>(() => ({
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
      data: [82, 84, 85, 83, 87, 89],
      itemStyle: { color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
    },
    {
      name: '优秀率',
      type: 'line',
      smooth: true,
      data: [20, 21, 22, 21, 23, 24],
      itemStyle: { color: '#10b981' },
      areaStyle: { color: 'rgba(16, 185, 129, 0.08)' },
    },
  ],
}))
</script>

<template>
  <div class="page-container dashboard-page">
    <!-- 筛选栏 -->
    <div class="content-card">
      <div class="filter-bar">
        <span class="filter-label">数据筛选：</span>
        <el-select v-model="filters.semester" placeholder="选择学期" style="width: 220px">
          <el-option
            v-for="item in semesterOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="filters.department" placeholder="选择院系" style="width: 160px">
          <el-option
            v-for="item in departmentOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="filters.grade" placeholder="选择年级" style="width: 140px">
          <el-option
            v-for="item in gradeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <StatCard
        v-for="item in statCards"
        :key="item.title"
        v-bind="item"
      />
    </div>

    <!-- 图表区域 -->
    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">成绩等级分布</div>
          <BaseChart :option="scorePieOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">各院系及格率对比</div>
          <BaseChart :option="deptBarOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">质量指标趋势</div>
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
}
</style>
