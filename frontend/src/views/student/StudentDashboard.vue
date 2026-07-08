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
import { fetchGradeTrend } from '@/api/analysis'

const userStore = useUserStore()
const loading = ref(true)

/** 成绩趋势数据（从 API 获取） */
const gradeTrendData = ref<{ months: string[]; avgScore: number[] }>({ months: [], avgScore: [] })

/** 学生个人课程概览 */
const courses = ref([
  { id: 1, name: '数据结构', teacher: '王教授', progress: 72, score: 88, avgScore: 76, rank: '前15%' },
  { id: 2, name: '操作系统', teacher: '李副教授', progress: 65, score: 82, avgScore: 74, rank: '前25%' },
  { id: 3, name: '计算机网络', teacher: '张讲师', progress: 80, score: 78, avgScore: 72, rank: '前35%' },
])

const statCards = computed(() => [
  { title: '课程数', value: courses.value.length, icon: 'Notebook', color: '#2563eb' },
  { title: '平均成绩', value: +(courses.value.reduce((s, c) => s + c.score, 0) / courses.value.length).toFixed(1), unit: '分', icon: 'DataLine', color: '#10b981', trend: 2.5 },
  { title: '总出勤率', value: 94.8, unit: '%', icon: 'Calendar', color: '#06b6d4' },
  { title: '待完成练习', value: 2, icon: 'EditPen', color: '#f59e0b', link: '/quiz/answer' },
  { title: '薄弱知识点', value: 3, icon: 'Grid', color: '#ef4444', link: '/student/knowledge' },
  { title: '班级排名', value: '前15%', icon: 'Trophy', color: '#8b5cf6' },
])

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

/** 成绩趋势 */
const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: gradeTrendData.value.months, axisLabel: { color: '#64748b' } },
  yAxis: { type: 'value', max: 100, name: '分数' },
  series: [{
    name: '平均分',
    type: 'line',
    smooth: true,
    data: gradeTrendData.value.avgScore,
    itemStyle: { color: '#2563eb' },
    areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
  }],
  grid: { left: 50, right: 20, top: 20, bottom: 30 },
}))

onMounted(async () => {
  try {
    const trend = await fetchGradeTrend({
      targetType: 'student',
      targetId: userStore.userInfo?.studentId || 1,
    })
    gradeTrendData.value = { months: trend.months || [], avgScore: trend.avgScore || [] }
  } catch {
    // 保持默认空数据
  }
  loading.value = false
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 欢迎区 -->
    <div class="content-card welcome-card">
      <div class="welcome-info">
        <h2>欢迎回来，{{ userStore.userInfo?.name || '同学' }}</h2>
        <p>{{ userStore.userInfo?.department || '计算机学院' }} · 学号 {{ userStore.userInfo?.studentNo || '—' }}</p>
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
      <div class="course-grid">
        <div v-for="course in courses" :key="course.id" class="course-card">
          <div class="course-header">
            <h3>{{ course.name }}</h3>
            <el-tag size="small" type="success">{{ course.rank }}</el-tag>
          </div>
          <p class="course-teacher">任课教师：{{ course.teacher }}</p>
          <div class="course-score">
            <span class="score-label">我的成绩</span>
            <span class="score-value">{{ course.score }} 分</span>
          </div>
          <div class="course-progress">
            <span class="progress-label">课程进度</span>
            <el-progress :percentage="course.progress" :stroke-width="8" :color="course.progress >= 70 ? '#10b981' : '#f59e0b'" />
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">各课程成绩对比</div>
          <BaseChart :option="scoreBarOption" height="300px" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">成绩变化趋势</div>
          <BaseChart :option="trendOption" height="300px" />
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
  }

  .course-progress {
    .progress-label { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 6px; }
  }
}
</style>
