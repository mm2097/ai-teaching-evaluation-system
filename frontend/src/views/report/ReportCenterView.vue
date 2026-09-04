<!--
  报告生成与导出中心
  统计指标由后端计算，分析结论与建议由 LLM 生成
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, View } from '@element-plus/icons-vue'
import type { EChartsOption } from 'echarts'
import type { ReportCharts, ReportResponse } from '@/api/ai'
import BaseChart from '@/components/charts/BaseChart.vue'
import {
  downloadReportFile,
  fetchReportHistory,
  fetchReportHistoryDetail,
  generateAndSaveReport,
  type DashboardStatsSnapshot,
  type ReportHistoryDetail,
  type ReportHistoryItem,
} from '@/api/report'
import { fetchSemesters, fetchCourses, fetchClasses, fetchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'
import type { ClassInfo, Course, Student } from '@/types'

const userStore = useUserStore()

type DashboardStats = DashboardStatsSnapshot

interface RequestError {
  name?: string
  message?: string
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

type ReportTypeId = 1 | 2 | 3 | 4

interface ReportTypeOption {
  id: ReportTypeId
  name: string
  desc: string
  roles?: string[]
}

const isStudent = computed(() => userStore.userRole === 'student')

// 是否显示学生选择器（学生角色自动匹配，不显示）
const showStudentPicker = computed(() => {
  if (genParams.value.reportType !== 2 && genParams.value.reportType !== 4) return false
  return !isStudent.value
})

const semesterOptions = ref<{ label: string; value: string }[]>([])
const courses = ref<Course[]>([])
const classes = ref<ClassInfo[]>([])
const students = ref<Student[]>([])

onMounted(async () => {
  await loadHistoryReports()
  try {
    const [semRes, courseRes, classRes] = await Promise.all([
      fetchSemesters(),
      fetchCourses({ deptId: 1 }),
      fetchClasses({ deptId: 1 }),
    ])
    semesterOptions.value = semRes.map((s) => ({ label: s.semesterName, value: s.semesterCode }))
    courses.value = courseRes
    classes.value = classRes
  } catch { /* empty */ }

  // 学生用户自动匹配个人信息
  if (userStore.userInfo?.studentId && userStore.userRole === 'student') {
    genParams.value.studentId = userStore.userInfo.studentId
    genParams.value.classId = userStore.userInfo.classId ?? genParams.value.classId
    // 学生自动设置课程（取所选课程列表第一门）
    const firstCourse = courses.value[0]
    if (firstCourse) {
      genParams.value.courseId = firstCourse.id
    }
  }
})

const reportTypes: ReportTypeOption[] = [
  { id: 1, name: '班级学情分析报告', desc: '侧重班级人数、历次考核、分档与预警', roles: ['teacher'] },
  { id: 2, name: '学生个人学情报告', desc: '侧重个人轨迹、画像标签与教师配置维度' },
  { id: 3, name: '课程知识点分析报告', desc: '侧重模块/知识点掌握度，不展开班级均分' },
  { id: 4, name: '学生学习质量报告', desc: '按教师自定义评价维度、指标权重出分' },
]

const visibleReportTypes = computed(() =>
  reportTypes.filter((t) => !t.roles || t.roles.includes(userStore.userRole!))
)

const genParams = ref<{
  reportType: ReportTypeId
  semester: string
  courseId: number
  classId?: number
  studentId?: number
  format: 'pdf' | 'excel'
}>({
  reportType: 1,
  semester: '2025-2026-1',
  courseId: 1,
  classId: userStore.userInfo?.classId ?? 1,
  studentId: userStore.userInfo?.studentId ?? undefined,
  format: 'pdf',
})

const generating = ref(false)
const previewVisible = ref(false)
const chartsReady = ref(false)
const reportData = ref<ReportResponse | null>(null)
const dashboardStats = ref<DashboardStats>({})

const reportCharts = computed<ReportCharts>(() => {
  return reportData.value?.charts || dashboardStats.value.charts || {}
})

const chartFocus = computed(() => reportCharts.value.focus || 'class')
const hasScoreChart = computed(() =>
  ['class'].includes(chartFocus.value)
  && (reportCharts.value.scoreBuckets ?? []).some((item) => (item.count ?? 0) > 0),
)
const hasKnowledgeChart = computed(() =>
  ['knowledge', 'student'].includes(chartFocus.value)
  && (reportCharts.value.knowledge ?? []).length > 0,
)
const hasRadarChart = computed(() =>
  ['student', 'quality'].includes(chartFocus.value)
  && Object.keys(reportCharts.value.radar ?? {}).length > 0,
)
const hasRateChart = computed(() => {
  if (!['class'].includes(chartFocus.value)) return false
  const rates = reportCharts.value.rates
  const stats = dashboardStats.value
  return [rates?.passRate, rates?.excellentRate, stats.passRate, stats.excellentRate, stats.attendanceRate]
    .some((value) => typeof value === 'number')
})
const hasHistoryChart = computed(() =>
  ['class', 'student'].includes(chartFocus.value)
  && (reportCharts.value.scoreHistory ?? []).length >= 2,
)
const hasIndexChart = computed(() =>
  chartFocus.value === 'quality' && (reportCharts.value.evalIndexes ?? []).length > 0,
)
const hasPartsChart = computed(() =>
  chartFocus.value === 'quality'
  && (reportCharts.value.academicParts ?? []).some((item) => item.score != null),
)
const hasAnyChart = computed(() =>
  hasScoreChart.value
  || hasKnowledgeChart.value
  || hasRadarChart.value
  || hasRateChart.value
  || hasHistoryChart.value
  || hasIndexChart.value
  || hasPartsChart.value,
)

const reportMetrics = computed(() => ({
  ...dashboardStats.value,
  ...(reportData.value?.metrics ?? {}),
}))

const reportFindings = computed(() => reportData.value?.findings ?? [])
const reportWarnings = computed(() => reportData.value?.warnings ?? [])
const hasFindings = computed(() => reportFindings.value.length > 0)
const hasWarnings = computed(() => reportWarnings.value.length > 0)

const reportEvalScheme = computed(() => reportData.value?.evalScheme ?? [])
const hasEvalScheme = computed(() => reportEvalScheme.value.length > 0)

const cnNums = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
const sectionNums = computed(() => {
  let index = 0
  const next = () => cnNums[index++] || String(index)
  return {
    core: isStudent.value || chartFocus.value === 'knowledge' ? '' : next(),
    chart: hasAnyChart.value ? next() : '',
    scheme: hasEvalScheme.value && ['quality', 'student'].includes(chartFocus.value) ? next() : '',
    findings: hasFindings.value ? next() : '',
    warnings: hasWarnings.value ? next() : '',
    summary: next(),
    conclusion: next(),
    suggestion: next(),
  }
})

const rateBarOption = computed<EChartsOption>(() => {
  const rates = reportCharts.value.rates
  const stats = dashboardStats.value
  const items = [
    { name: '及格率', value: Number(rates?.passRate ?? stats.passRate ?? 0) },
    { name: '优秀率', value: Number(rates?.excellentRate ?? stats.excellentRate ?? 0) },
    { name: '出勤率', value: Number(rates?.attendanceRate ?? stats.attendanceRate ?? 0) },
  ]
  return {
    tooltip: { trigger: 'axis', formatter: '{b}：{c}%' },
    grid: { left: 56, right: 24, top: 16, bottom: 24 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#64748b', formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: items.map((item) => item.name),
      axisLabel: { color: '#64748b' },
    },
    series: [{
      type: 'bar',
      data: items.map((item) => ({
        value: item.value,
        itemStyle: {
          color: item.value >= 85 ? '#10b981' : item.value >= 70 ? '#2563eb' : '#f59e0b',
          borderRadius: [0, 6, 6, 0],
        },
      })),
      barWidth: 16,
    }],
  }
})

const scorePieOption = computed<EChartsOption>(() => {
  const buckets = reportCharts.value.scoreBuckets ?? []
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c}人 ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#64748b' } },
    color: ['#ef4444', '#f97316', '#f59e0b', '#2563eb', '#10b981'],
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{d}%' },
      data: buckets.map((item) => ({ name: item.label, value: item.count })),
    }],
  }
})

const knowledgeBarOption = computed<EChartsOption>(() => {
  const points = [...(reportCharts.value.knowledge ?? [])].sort((a, b) => a.accuracy - b.accuracy)
  return {
    tooltip: { trigger: 'axis', formatter: '{b}：{c}%' },
    grid: { left: 108, right: 24, top: 16, bottom: 24 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#64748b', formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: points.map((item) => item.name),
      axisLabel: { color: '#64748b', width: 96, overflow: 'truncate' },
    },
    series: [{
      type: 'bar',
      data: points.map((item) => ({
        value: item.accuracy,
        itemStyle: {
          color: item.accuracy < 60 ? '#ef4444' : item.accuracy < 80 ? '#f59e0b' : '#10b981',
          borderRadius: [0, 6, 6, 0],
        },
      })),
      barWidth: 14,
    }],
  }
})

const radarOption = computed<EChartsOption>(() => {
  const radar = reportCharts.value.radar ?? {}
  const names = Object.keys(radar)
  const values = names.map((name) => Number(radar[name] ?? 0))
  return {
    tooltip: {},
    radar: {
      indicator: names.map((name) => ({ name, max: 100 })),
      shape: 'polygon',
      center: ['50%', '55%'],
      radius: '62%',
      splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
      axisName: { color: '#64748b' },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '能力维度',
        areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
      }],
    }],
  }
})

const trendLineOption = computed<EChartsOption>(() => {
  const history = reportCharts.value.scoreHistory ?? []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 20, top: 24, bottom: 28 },
    xAxis: {
      type: 'category',
      data: history.map((item) => item.name),
      axisLabel: { color: '#64748b', rotate: history.length > 5 ? 20 : 0 },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#64748b', formatter: '{value}分' },
    },
    series: [{
      name: '成绩',
      type: 'line',
      smooth: true,
      data: history.map((item) => item.score),
      itemStyle: { color: '#2563eb' },
      areaStyle: { color: 'rgba(37,99,235,0.08)' },
    }],
  }
})

function warningTagType(level: string): 'danger' | 'warning' | 'info' {
  if (level === '高') return 'danger'
  if (level === '中') return 'warning'
  return 'info'
}

const indexBarOption = computed<EChartsOption>(() => {
  const rows = [...(reportCharts.value.evalIndexes ?? [])].reverse()
  return {
    tooltip: { trigger: 'axis', formatter: '{b}：{c}分' },
    grid: { left: 128, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b', formatter: '{value}' } },
    yAxis: {
      type: 'category',
      data: rows.map((item) => item.name),
      axisLabel: { color: '#64748b', width: 118, overflow: 'truncate' },
    },
    series: [{
      type: 'bar',
      data: rows.map((item) => ({
        value: item.score,
        itemStyle: {
          color: item.score < 60 ? '#ef4444' : item.score < 80 ? '#f59e0b' : '#10b981',
          borderRadius: [0, 6, 6, 0],
        },
      })),
      barWidth: 14,
    }],
  }
})

const partsBarOption = computed<EChartsOption>(() => {
  const rows = reportCharts.value.academicParts ?? []
  return {
    tooltip: { trigger: 'axis', formatter: '{b}：{c}分' },
    grid: { left: 88, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b' } },
    yAxis: {
      type: 'category',
      data: rows.map((item) => `${item.name}`),
      axisLabel: { color: '#64748b' },
    },
    series: [{
      type: 'bar',
      data: rows.map((item) => ({
        value: item.score ?? 0,
        itemStyle: {
          color: (item.score ?? 0) < 60 ? '#ef4444' : (item.score ?? 0) < 80 ? '#f59e0b' : '#2563eb',
          borderRadius: [0, 6, 6, 0],
        },
      })),
      barWidth: 16,
    }],
  }
})

const csCourses = computed(() => courses.value)
const csClasses = computed(() => classes.value)

const reportSourceLabel = computed(() => {
  if (!reportData.value) return ''
  return reportData.value.source === 'llm' ? 'AI 增强' : '模板生成'
})
const reportSourceTag = computed(() => {
  if (!reportData.value) return ''
  return reportData.value.source === 'llm' ? 'warning' : 'info' as const
})

const previewTitle = computed(() => {
  return reportData.value?.report_type_name
    || reportTypes.find((t) => t.id === genParams.value.reportType)?.name
    || '学情分析报告'
})

const historyReports = ref<ReportHistoryItem[]>([])
const activeHistory = ref<ReportHistoryDetail | null>(null)

async function loadHistoryReports(): Promise<void> {
  try {
    historyReports.value = await fetchReportHistory()
  } catch {
    historyReports.value = []
  }
}

// 确保默认选中的报告类型对当前角色可见
watch(
  visibleReportTypes,
  (types) => {
    if (types.length > 0 && !types.find((t) => t.id === genParams.value.reportType)) {
      genParams.value.reportType = types[0]!.id
    }
  },
  { immediate: true },
)

// 学生用户选择类型 2/4 时自动匹配个人信息
watch(
  [() => genParams.value.reportType, isStudent, () => userStore.userInfo],
  ([type, student, info]) => {
    if (student && info && (type === 2 || type === 4)) {
      genParams.value.studentId = info.studentId
      genParams.value.classId = info.classId ?? genParams.value.classId
    }
  },
  { immediate: true },
)

// 切换报告类型或班级时加载学生列表（仅非学生角色）
watch(
  [() => genParams.value.reportType, () => genParams.value.classId],
  async ([type, classId]) => {
    if ((type === 2 || type === 4) && classId) {
      try {
        students.value = await fetchStudents({ classId: classId as number })
      } catch { students.value = [] }
    }
  },
)

async function loadDashboardStats() {
  try {
    const { data } = await request.get('/v1/dashboard/stats', {
      params: { course_id: genParams.value.courseId },
    })
    dashboardStats.value = data as DashboardStats
  } catch { dashboardStats.value = {} }
}

async function generateReport(): Promise<void> {
  generating.value = true
  try {
    // 看板统计仅教师可访问，学生跳过
    if (!isStudent.value) {
      await loadDashboardStats()
    }

    // 学生个人报告/学习质量报告需要验证 studentId
    if ((genParams.value.reportType === 2 || genParams.value.reportType === 4) && !genParams.value.studentId) {
      ElMessage.warning('请先选择学生')
      generating.value = false
      return
    }

    const history = await generateAndSaveReport({
      courseId: genParams.value.courseId,
      reportType: genParams.value.reportType,
      classId: genParams.value.classId ?? undefined,
      studentId: (genParams.value.reportType === 2 || genParams.value.reportType === 4) ? genParams.value.studentId : undefined,
      semester: genParams.value.semester,
      exportFormat: genParams.value.format === 'pdf' ? 'pdf' : 'xlsx',
      dashboardStats: dashboardStats.value,
    })
    activeHistory.value = history
    reportData.value = history.data
    dashboardStats.value = history.stats
    await loadHistoryReports()
    ElMessage.success('报告生成成功！')
  } catch (error: unknown) {
    const requestError = error as RequestError
    const msg = requestError.response?.data?.detail
      || requestError.message
      || '报告生成失败，请确认已选择课程和班级'
    ElMessage.error(typeof msg === 'string' ? msg : '报告生成失败')
  } finally {
    generating.value = false
  }
}

function previewReport(): void {
  if (!reportData.value) {
    ElMessage.info('请先生成报告')
    return
  }
  previewVisible.value = true
}

async function exportReport(): Promise<void> {
  if (!reportData.value || !activeHistory.value) {
    ElMessage.info('请先生成报告')
    return
  }

  try {
    const history = activeHistory.value
    const fileName = `${history.name}_${history.created_at.slice(0, 10)}`

    const format = genParams.value.format === 'pdf' ? 'pdf' : 'xlsx'
    const blob = await downloadReportFile(history.id, format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${fileName}.${format}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`${format === 'pdf' ? 'PDF' : 'Excel'} 报告已导出`)
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '未知错误'
    ElMessage.error('导出失败：' + message)
  }
}

async function previewHistoryReport(row: ReportHistoryItem): Promise<void> {
  try {
    const history = await fetchReportHistoryDetail(row.id)
    activeHistory.value = history
    reportData.value = history.data
    dashboardStats.value = history.stats
    previewVisible.value = true
  } catch {
    ElMessage.error('历史报告读取失败')
  }
}

async function downloadHistoryReport(row: ReportHistoryItem): Promise<void> {
  try {
    const history = await fetchReportHistoryDetail(row.id)
    activeHistory.value = history
    reportData.value = history.data
    dashboardStats.value = history.stats
    genParams.value.format = row.format === 'PDF' ? 'pdf' : 'excel'
    await exportReport()
  } catch {
    ElMessage.error('历史报告下载失败')
  }
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">报告生成</div>

          <div class="report-type-grid">
            <div
              v-for="item in visibleReportTypes"
              :key="item.id"
              class="report-type-card"
              :class="{ active: genParams.reportType === item.id }"
              @click="genParams.reportType = item.id"
            >
              <el-icon :size="24"><Document /></el-icon>
              <h4>{{ item.name }}</h4>
              <p>{{ item.desc }}</p>
            </div>
          </div>

          <el-divider />

          <el-form label-width="80px">
            <el-form-item label="学期">
              <el-select v-model="genParams.semester" style="width: 100%">
                <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="课程">
              <el-select v-model="genParams.courseId" style="width: 100%">
                <el-option v-for="c in csCourses" :key="c.id" :label="c.courseName" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="班级">
              <el-select v-model="genParams.classId" style="width: 100%">
                <el-option v-for="c in csClasses" :key="c.id" :label="c.className" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="showStudentPicker" label="学生">
              <el-select
                v-model="genParams.studentId"
                style="width: 100%"
                placeholder="请先选择班级"
                :disabled="!genParams.classId"
              >
                <el-option
                  v-for="s in students"
                  :key="s.id"
                  :label="`${s.studentName}（${s.studentNo}）`"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="导出格式">
              <el-radio-group v-model="genParams.format">
                <el-radio value="pdf">PDF</el-radio>
                <el-radio value="excel">Excel</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <div style="display: flex; gap: 12px">
            <el-button type="primary" :loading="generating" :icon="Document" @click="generateReport">
              生成报告
            </el-button>
            <el-button :icon="View" @click="previewReport">在线预览</el-button>
            <el-button :icon="Download" @click="exportReport">导出</el-button>
          </div>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">历史报告</div>
          <el-table :data="historyReports" stripe border>
            <el-table-column prop="name" label="报告名称" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="format" label="格式" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.format === 'PDF' ? 'danger' : 'success'">{{ row.format }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="time" label="生成时间" width="170" />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="previewHistoryReport(row)">预览</el-button>
                <el-button type="success" link size="small" @click="downloadHistoryReport(row)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <div v-if="reportData && (hasAnyChart || hasFindings)" class="content-card report-charts-panel">
      <div class="content-card__title">{{ hasAnyChart ? '报告数据可视化' : '现状要点' }}</div>
      <p class="report-charts-hint">根据本次报告快照生成，便于快速对照成绩、知识点和能力维度。</p>
      <el-row :gutter="16">
        <el-col v-if="hasRateChart" :xs="24" :md="hasScoreChart || hasRadarChart ? 12 : 24">
          <div class="chart-block">
            <h4>核心比率</h4>
            <BaseChart :option="rateBarOption" height="260px" />
          </div>
        </el-col>
        <el-col v-if="hasScoreChart" :xs="24" :md="12">
          <div class="chart-block">
            <h4>成绩分布</h4>
            <BaseChart :option="scorePieOption" height="260px" />
          </div>
        </el-col>
        <el-col v-if="hasKnowledgeChart" :xs="24" :md="hasRadarChart ? 12 : 24">
          <div class="chart-block">
            <h4>知识点掌握度</h4>
            <BaseChart :option="knowledgeBarOption" height="300px" />
          </div>
        </el-col>
        <el-col v-if="hasRadarChart" :xs="24" :md="12">
          <div class="chart-block">
            <h4>能力雷达</h4>
            <BaseChart :option="radarOption" height="300px" />
          </div>
        </el-col>
        <el-col v-if="hasHistoryChart" :xs="24" :md="12">
          <div class="chart-block">
            <h4>成绩走势</h4>
            <BaseChart :option="trendLineOption" height="260px" />
          </div>
        </el-col>
        <el-col v-if="hasIndexChart" :xs="24" :md="12">
          <div class="chart-block">
            <h4>教师配置指标得分</h4>
            <BaseChart :option="indexBarOption" height="300px" />
          </div>
        </el-col>
        <el-col v-if="hasPartsChart" :xs="24" :md="12">
          <div class="chart-block">
            <h4>学业构成（教师配比）</h4>
            <BaseChart :option="partsBarOption" height="300px" />
          </div>
        </el-col>
      </el-row>
      <ol v-if="hasFindings" class="findings-list findings-list--page">
        <li v-for="(item, index) in reportFindings" :key="index">{{ item }}</li>
      </ol>
    </div>

    <el-dialog
      v-model="previewVisible"
      title="报告预览"
      width="920px"
      top="4vh"
      @opened="chartsReady = true"
      @closed="chartsReady = false"
    >
      <div v-if="reportData" class="report-preview">
        <h2 style="text-align: center; margin-bottom: 20px">{{ previewTitle }}</h2>

        <template v-if="!isStudent && chartFocus !== 'knowledge'">
        <h3>{{ sectionNums.core }}、核心指标概览</h3>
        <el-descriptions :column="2" border style="margin: 16px 0">
          <el-descriptions-item label="学生人数">{{ reportMetrics.studentCount ?? '-' }} 人</el-descriptions-item>
          <el-descriptions-item label="最近考核">{{ reportMetrics.latestExam || '-' }}</el-descriptions-item>
          <el-descriptions-item label="均分">{{ reportMetrics.avgScore ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="中位数">{{ reportMetrics.scoreMedian ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="分数区间">
            {{ reportMetrics.scoreMin ?? '-' }} – {{ reportMetrics.scoreMax ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="及格率">{{ reportMetrics.passRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="优秀率">{{ reportMetrics.excellentRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="平均出勤率">{{ reportMetrics.attendanceRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="预警学生">{{ reportMetrics.warningCount ?? '-' }} 人</el-descriptions-item>
        </el-descriptions>
        </template>

        <template v-if="hasAnyChart">
          <h3>{{ sectionNums.chart }}、图形化数据</h3>
          <el-row v-if="chartsReady" :gutter="12">
            <el-col v-if="hasRateChart" :span="hasScoreChart || hasRadarChart ? 12 : 24">
              <div class="chart-block chart-block--compact">
                <h4>核心比率</h4>
                <BaseChart :option="rateBarOption" height="220px" />
              </div>
            </el-col>
            <el-col v-if="hasScoreChart" :span="12">
              <div class="chart-block chart-block--compact">
                <h4>成绩分布</h4>
                <BaseChart :option="scorePieOption" height="220px" />
              </div>
            </el-col>
            <el-col v-if="hasKnowledgeChart" :span="hasRadarChart ? 12 : 24">
              <div class="chart-block chart-block--compact">
                <h4>知识点掌握度</h4>
                <BaseChart :option="knowledgeBarOption" height="240px" />
              </div>
            </el-col>
            <el-col v-if="hasRadarChart" :span="12">
              <div class="chart-block chart-block--compact">
                <h4>能力雷达</h4>
                <BaseChart :option="radarOption" height="240px" />
              </div>
            </el-col>
            <el-col v-if="hasHistoryChart" :span="12">
              <div class="chart-block chart-block--compact">
                <h4>成绩走势</h4>
                <BaseChart :option="trendLineOption" height="220px" />
              </div>
            </el-col>
            <el-col v-if="hasIndexChart" :span="12">
              <div class="chart-block chart-block--compact">
                <h4>教师配置指标得分</h4>
                <BaseChart :option="indexBarOption" height="240px" />
              </div>
            </el-col>
            <el-col v-if="hasPartsChart" :span="12">
              <div class="chart-block chart-block--compact">
                <h4>学业构成（教师配比）</h4>
                <BaseChart :option="partsBarOption" height="240px" />
              </div>
            </el-col>
          </el-row>
        </template>

        <template v-if="hasEvalScheme && sectionNums.scheme">
          <h3>{{ sectionNums.scheme }}、教师评价方案</h3>
          <el-table :data="reportEvalScheme" border size="small" style="margin: 8px 0 16px">
            <el-table-column prop="name" label="维度" width="120" />
            <el-table-column label="得分" width="80" align="center">
              <template #default="{ row }">{{ row.score ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="指标（权重 / 得分）">
              <template #default="{ row }">
                {{
                  (row.indexes || [])
                    .map((item: { name: string; weight?: number; score?: number | null }) =>
                      `${item.name} ${item.weight ?? 0}%${item.score != null ? ` / ${item.score}分` : ''}`,
                    )
                    .join('；') || '—'
                }}
              </template>
            </el-table-column>
          </el-table>
        </template>

        <template v-if="hasFindings">
          <h3>{{ sectionNums.findings }}、现状要点</h3>
          <ol class="findings-list">
            <li v-for="(item, index) in reportFindings" :key="index">{{ item }}</li>
          </ol>
        </template>

        <template v-if="hasWarnings">
          <h3>{{ sectionNums.warnings }}、预警学生</h3>
          <el-table :data="reportWarnings" border size="small" style="margin: 8px 0 16px">
            <el-table-column prop="name" label="学生" width="110" />
            <el-table-column label="等级" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="warningTagType(row.level)">{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="原因">
              <template #default="{ row }">{{ (row.reasons || []).join('；') || '—' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <h3>{{ sectionNums.summary }}、总体概述 <el-tag size="small" :type="reportSourceTag">{{ reportSourceLabel }}</el-tag></h3>
        <p class="report-text">{{ reportData.summary }}</p>

        <h3>{{ sectionNums.conclusion }}、关键结论</h3>
        <p class="report-text">{{ reportData.conclusion }}</p>

        <h3>{{ sectionNums.suggestion }}、建议措施</h3>
        <p class="report-text">{{ reportData.suggestion }}</p>

        <el-alert
          v-if="reportData.source === 'llm'"
          title="本报告由 AI 增强生成，结论与建议仅供参考"
          type="info"
          show-icon
          :closable="false"
          style="margin-top: 16px"
        />
      </div>
      <el-empty v-else description="暂无报告数据" />
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.report-type-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.report-type-card {
  padding: 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;

  h4 {
    font-size: 14px;
    margin: 8px 0 4px;
  }

  p {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.4;
  }

  &:hover {
    border-color: #93c5fd;
    background: #f8fafc;
  }

  &.active {
    border-color: #2563eb;
    background: #eff6ff;

    .el-icon {
      color: #2563eb;
    }
  }
}

.report-preview {
  h3 {
    font-size: 15px;
    margin: 16px 0 8px;
    color: #1e293b;
  }

  p, ol {
    font-size: 14px;
    color: #475569;
    line-height: 1.8;
  }

  .report-text {
    white-space: pre-wrap;
  }

  ol {
    padding-left: 20px;
  }
}

.findings-list {
  margin: 8px 0 12px;
  padding-left: 22px;
  color: #334155;
  line-height: 1.7;

  li {
    margin-bottom: 6px;
  }

  &--page {
    margin-top: 16px;
    font-size: 14px;
  }
}

.report-charts-panel {
  margin-top: 16px;
}

.report-charts-hint {
  margin: -4px 0 12px;
  font-size: 13px;
  color: #64748b;
}

.chart-block {
  margin-bottom: 8px;
  padding: 12px 12px 4px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;

  h4 {
    margin: 0 0 4px;
    font-size: 13px;
    color: #334155;
    font-weight: 600;
  }

  &--compact {
    margin-bottom: 12px;
  }
}
</style>




