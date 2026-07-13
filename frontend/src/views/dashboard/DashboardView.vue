<!--
  综合数据看板页面
  筛选维度：学期 → 专业 → 年级 → 课程 → 专业班级
  未查询时仅展示欢迎区与筛选栏
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import { DataAnalysis, Search } from '@element-plus/icons-vue'
import StatCard from '@/components/common/StatCard.vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import { computeClassKnowledgeStats } from '@/api/analysis'
import type { KnowledgeHeatmapResult } from '@/api/analysis'
import { useDashboardFilter } from '@/composables/useDashboardFilter'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'

const router = useRouter()
const userStore = useUserStore()

/** 实时看板数据（来自后端） */
const dashboardStats = ref({ studentCount: 0, courseCount: 0, teacherCount: 0, passRate: 0, excellentRate: 0, attendanceRate: 0, warningCount: 0 })
const warnings = ref<unknown[]>([])
const heatmap = ref<KnowledgeHeatmapResult>({ knowledgePoints: [], students: [], data: [] })

async function loadDashboardData(courseId?: number, classId?: number) {
  try {
    const [statsRes, warnRes] = await Promise.all([
      request.get('/v1/dashboard/stats', { params: courseId ? { course_id: courseId } : {} }),
      request.get('/v1/analysis/warnings', { params: { class_id: classId } }),
    ])
    dashboardStats.value = statsRes.data
    warnings.value = warnRes.data
  } catch { /* 首次加载失败时展示空数据 */ }
}

async function loadHeatmap(courseId?: number, classId?: number) {
  if (!courseId || !classId) { heatmap.value = { knowledgePoints: [], students: [], data: [] }; return }
  try {
    const res = await request.get('/v1/analysis/knowledge-heatmap', {
      params: { course_id: courseId, class_id: classId },
    })
    heatmap.value = res.data
  } catch { heatmap.value = { knowledgePoints: [], students: [], data: [] } }
}

const {
  filters,
  applied,
  showDashboard,
  majorOptions,
  courseOptions,
  classOptions,
  semesterOptions,
  gradeOptions,
  applyFilters,
  onSemesterChange,
  onMajorChange,
  onGradeChange,
  onCourseChange,
  optionsLoading,
} = useDashboardFilter()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return '上午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const filterSteps = [
  { label: '学期', desc: '选择教学周期' },
  { label: '专业', desc: '可选，按专业缩小范围' },
  { label: '年级', desc: '可选，按入学年份' },
  { label: '课程', desc: '定位授课课程' },
  { label: '专业班级', desc: '确定分析班级' },
]

const filterFactor = computed(() => {
  return 1 // 后端已返回真实数据，不再需要系数
})

const classStudentCount = computed(() => {
  return heatmap.value.students?.length ?? 0
})

const classWarningCount = computed(() => {
  return warnings.value.length
})

const knowledgeStats = computed(() => {
  return computeClassKnowledgeStats(heatmap.value)
})

const statCards = computed(() => {
  const f = filterFactor.value
  const courseName = courseOptions.value.find((c) => c.value === applied.value.courseId)?.label || '—'
  const className = classOptions.value.find((c) => c.value === applied.value.classId)?.label || '—'
  return [
    { title: '班级学生数', value: classStudentCount.value, icon: 'User', color: '#2563eb', trend: 0 },
    { title: '当前课程', value: courseName, icon: 'Notebook', color: '#6366f1' },
    { title: '当前班级', value: className, icon: 'School', color: '#7c3aed' },
    { title: '课程及格率', value: +(dashboardStats.value.passRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'CircleCheck', color: '#10b981', trend: 3.2 },
    { title: '优秀率', value: +(dashboardStats.value.excellentRate * (0.95 + f * 0.05)).toFixed(1), unit: '%', icon: 'Star', color: '#f59e0b', trend: 1.8 },
    { title: '平均出勤率', value: +(dashboardStats.value.attendanceRate * (0.98 + f * 0.02)).toFixed(1), unit: '%', icon: 'Calendar', color: '#06b6d4', trend: -0.5 },
    { title: '预警学生', value: classWarningCount.value, icon: 'Bell', color: '#ef4444', trend: -12, link: '/analysis/warning' },
    { title: '知识点薄弱项', value: knowledgeStats.value.weakPoints.length, icon: 'Grid', color: '#8b5cf6', link: '/analysis/knowledge' },
    { title: 'AI 智能辅助教学完成率', value: 78.5, unit: '%', icon: 'EditPen', color: '#ec4899', link: '/quiz/manage' },
  ]
})

const scorePieOption = computed<EChartsOption>(() => {
  const kpData = heatmap.value.data ?? []
  const students = heatmap.value.students ?? []
  if (!students.length || !kpData.length) return {}
  const buckets = [0, 0, 0, 0, 0]
  students.forEach((_: string, sIdx: number) => {
    const values = kpData.filter((d: number[]) => d[1] === sIdx).map((d: number[]) => d[2]!)
    const avg = values.length ? values.reduce((a: number, b: number) => a + b, 0) / values.length : 0
    if (avg >= 90) buckets[4]!++
    else if (avg >= 80) buckets[3]!++
    else if (avg >= 70) buckets[2]!++
    else if (avg >= 60) buckets[1]!++
    else buckets[0]!++
  })
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
  const kps = heatmap.value.knowledgePoints ?? []
  if (!kps.length) return {}
  const stats = computeClassKnowledgeStats(heatmap.value)
  const kpStats = kps
    .map((name: string, i: number) => ({ name, rate: stats.classAvgByKp[i] ?? 0 }))
    .sort((a: { name: string; rate: number }, b: { name: string; rate: number }) => a.rate - b.rate)
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
    yAxis: { type: 'category', data: names, axisLabel: { color: '#64748b' } },
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

/** 趋势图数据（从后端获取） */
const trendData = ref({ months: [] as string[], passRate: [] as number[], excellentRate: [] as number[] })

async function loadTrendData(courseId?: number) {
  if (!courseId) return
  try {
    const res = await request.get('/v1/dashboard/grade-trend', { params: { course_id: courseId } })
    const d = res.data
    trendData.value = { months: d.months || [], passRate: d.passRate || [], excellentRate: d.passRate ? d.passRate.map(() => 0) : [] }
  } catch { /* ignore */ }
}

const trendLineOption = computed<EChartsOption>(() => {
  const t = trendData.value
  if (!t.months.length) {
    return {
      title: { text: '暂无趋势数据', left: 'center', top: 'center', textStyle: { color: '#94a3b8', fontSize: 14 } },
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['及格率', '优秀率'], top: 0, textStyle: { color: '#64748b' } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: t.months, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' } },
    series: [
      {
        name: '及格率', type: 'line', smooth: true, data: t.passRate,
        itemStyle: { color: '#2563eb' }, areaStyle: { color: 'rgba(37,99,235,0.08)' },
      },
      {
        name: '优秀率', type: 'line', smooth: true, data: t.excellentRate,
        itemStyle: { color: '#10b981' }, areaStyle: { color: 'rgba(16,185,129,0.08)' },
      },
    ],
  }
})

function handleStatClick(item: { link?: string }): void {
  if (item.link) router.push(item.link)
}

// 查询时加载真实数据
watch(showDashboard, async (show) => {
  if (show) {
    await Promise.all([
      loadDashboardData(applied.value.courseId, applied.value.classId),
      loadHeatmap(applied.value.courseId, applied.value.classId),
      loadTrendData(applied.value.courseId),
    ])
  }
})
</script>

<template>
  <div class="page-container dashboard-page">
    <!-- 筛选栏 -->
    <div class="content-card filter-card">
      <div class="filter-card__header">
        <div class="filter-card__title">
          <el-icon :size="18"><DataAnalysis /></el-icon>
          <span>学情数据筛选</span>
        </div>
        <span class="filter-card__hint">计算机学院 · 按学期、专业、年级、课程、班级维度查询</span>
      </div>
      <div class="filter-bar dashboard-filter">
        <div class="filter-item">
          <span class="filter-item__label">学期</span>
          <el-select
            v-model="filters.semester"
            placeholder="选择学期"
            style="width: 220px"
            @change="onSemesterChange"
          >
            <el-option
              v-for="item in semesterOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>
        <div class="filter-item">
          <span class="filter-item__label">专业</span>
          <el-select
            v-model="filters.majorId"
            placeholder="全部专业"
            clearable
            :loading="optionsLoading"
            style="width: 180px"
            @change="onMajorChange"
          >
            <el-option v-for="m in majorOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </div>
        <div class="filter-item">
          <span class="filter-item__label">年级</span>
          <el-select
            v-model="filters.grade"
            placeholder="全部年级"
            clearable
            :loading="optionsLoading"
            style="width: 120px"
            @change="onGradeChange"
          >
            <el-option
              v-for="item in gradeOptions"
              :key="item.value || 'all'"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>
        <div class="filter-item">
          <span class="filter-item__label">课程</span>
          <el-select
            v-model="filters.courseId"
            placeholder="选择课程"
            clearable
            :loading="optionsLoading"
            style="width: 220px"
            @change="onCourseChange"
          >
            <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </div>
        <div class="filter-item">
          <span class="filter-item__label">专业班级</span>
          <el-select
            v-model="filters.classId"
            :placeholder="filters.courseId != null ? '选择班级' : '请先选择课程'"
            clearable
            :loading="optionsLoading"
            :disabled="filters.courseId == null"
            style="width: 220px"
          >
            <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </div>
        <el-button
          type="primary"
          :icon="Search"
          @click="applyFilters"
        >
          查询
        </el-button>
      </div>
    </div>

    <!-- 欢迎区（未查询时） -->
    <div v-if="!showDashboard" class="welcome-panel">
      <div class="welcome-panel__hero">
        <div class="welcome-panel__icon">
          <el-icon :size="48"><DataAnalysis /></el-icon>
        </div>
        <h2 class="welcome-panel__title">
          {{ greeting }}，{{ userStore.userInfo?.name || '老师' }}
        </h2>
        <p class="welcome-panel__subtitle">
          欢迎使用 AI 数智化教学分析评价系统综合看板
        </p>
        <p class="welcome-panel__desc">
          请在上方完成筛选后点击「查询」，系统将展示对应班级在选定课程下的学情概览、成绩分布与知识点掌握情况。
        </p>
      </div>
      <div class="welcome-panel__steps">
        <div v-for="(step, idx) in filterSteps" :key="step.label" class="welcome-step">
          <div class="welcome-step__num">{{ idx + 1 }}</div>
          <div class="welcome-step__body">
            <div class="welcome-step__label">{{ step.label }}</div>
            <div class="welcome-step__desc">{{ step.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 看板数据区（查询后） -->
    <template v-else>
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
    </template>
  </div>
</template>

<style scoped lang="scss">
.dashboard-page {
  .filter-card {
    margin-bottom: 20px;

    &__header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }

    &__title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
      color: #1e293b;
    }

    &__hint {
      font-size: 13px;
      color: #94a3b8;
    }
  }

  .dashboard-filter {
    margin-bottom: 0;
    gap: 16px;
  }

  .filter-item {
    display: flex;
    flex-direction: column;
    gap: 6px;

    &__label {
      font-size: 12px;
      font-weight: 500;
      color: #64748b;
      line-height: 1;
    }
  }

  .welcome-panel {
    background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 50%, #f0fdf4 100%);
    border-radius: 16px;
    padding: 48px 40px;
    border: 1px solid rgba(37, 99, 235, 0.08);
    box-shadow: 0 4px 24px rgba(37, 99, 235, 0.06);

    &__hero {
      text-align: center;
      max-width: 560px;
      margin: 0 auto 40px;
    }

    &__icon {
      width: 88px;
      height: 88px;
      margin: 0 auto 20px;
      border-radius: 20px;
      background: linear-gradient(135deg, #2563eb, #6366f1);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 24px rgba(37, 99, 235, 0.3);
    }

    &__title {
      font-size: 26px;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 10px;
    }

    &__subtitle {
      font-size: 15px;
      color: #475569;
      margin-bottom: 12px;
    }

    &__desc {
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.7;
    }

    &__steps {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      max-width: 900px;
      margin: 0 auto;
    }
  }

  .welcome-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: rgba(255, 255, 255, 0.85);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(4px);

    &__num {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: #2563eb;
      color: #fff;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    &__label {
      font-size: 14px;
      font-weight: 600;
      color: #1e293b;
      margin-bottom: 4px;
    }

    &__desc {
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.4;
    }
  }

  .clickable {
    cursor: pointer;
  }
}
</style>
