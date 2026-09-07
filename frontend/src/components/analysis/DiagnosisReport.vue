<!--
  AI 学情诊断报告区组件
  班级版 + 学生版两套布局，含总体评估/关键发现/归因/干预建议
  干预建议按 toolHint 渲染动作按钮，emit act 交由父组件路由跳转
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import type { DiagnosisReport, DiagnosisToolHint } from '@/types'

const props = defineProps<{
  report: DiagnosisReport
}>()

const emit = defineEmits<{
  ask: []
  export: [format: 'pdf' | 'xlsx']
  act: [hint: DiagnosisToolHint, suggestion: DiagnosisReport['suggestions'][number]]
}>()

const isStudent = computed(() => props.report.scope === 'student')

const radarIndicators = [
  { name: '成绩', max: 100 },
  { name: '考勤', max: 100 },
  { name: '互动', max: 100 },
  { name: '进步', max: 100 },
  { name: '综合', max: 100 },
]

const radarValues = computed(() => {
  const r = props.report.radar || {}
  return [r['成绩'], r['考勤'], r['互动'], r['进步'], r['综合']].map((v) =>
    typeof v === 'number' ? v : 0,
  )
})

const radarOption = computed<EChartsOption>(() => ({
  tooltip: {},
  radar: {
    indicator: radarIndicators,
    shape: 'polygon',
    splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
    axisName: { color: '#64748b' },
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: radarValues.value,
          name: isStudent.value
            ? props.report.studentInfo?.name || '学生'
            : '班级',
          areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
        },
      ],
    },
  ],
}))

const gradeColor = computed(() => {
  const g = props.report.overall.grade
  if (g === 'A') return '#10b981'
  if (g === 'B') return '#2563eb'
  if (g === 'C') return '#f59e0b'
  return '#ef4444'
})

const priorityType = (p: string): 'danger' | 'warning' | 'info' => {
  if (p === '高') return 'danger'
  if (p === '中') return 'warning'
  return 'info'
}

const riskType = (level: string): 'danger' | 'warning' | 'info' => {
  if (level === '高') return 'danger'
  if (level === '中') return 'warning'
  return 'info'
}

const toolHintLabel: Record<DiagnosisToolHint, string> = {
  weakness_driven_quiz: '生成练习',
  notify: '发通知',
  talk: '约谈',
}

function scoreHistoryValues(): { name: string; value: number }[] {
  return (props.report.scoreHistory || []).map((h) => ({
    name: h.assessment,
    value: h.score,
  }))
}

const trendOption = computed<EChartsOption>(() => {
  const hist = scoreHistoryValues()
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 32, right: 16, top: 24, bottom: 28 },
    xAxis: {
      type: 'category',
      data: hist.map((h) => h.name),
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    series: [
      {
        type: 'line',
        data: hist.map((h) => h.value),
        smooth: true,
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
        areaStyle: { color: 'rgba(37, 99, 235, 0.12)' },
      },
    ],
  }
})

function onExport(fmt: 'pdf' | 'xlsx'): void {
  emit('export', fmt)
}
</script>

<template>
  <div class="diagnosis-report">
    <!-- 总体评估 -->
    <div class="report-section">
      <div class="section-title">📊 总体评估</div>
      <div class="overall-card">
        <div class="overall-grade">
          <span class="grade-letter" :style="{ color: gradeColor }">{{
            report.overall.grade || '-'
          }}</span>
          <span class="grade-score">{{ report.overall.score }}<small>/100</small></span>
          <span class="grade-label">综合评级</span>
        </div>
        <div class="overall-radar">
          <BaseChart :option="radarOption" height="180px" />
        </div>
        <div class="overall-summary">{{ report.overall.summary }}</div>
      </div>
    </div>

    <!-- 学生版：个人信息 + 成绩趋势 + 态度 -->
    <el-row v-if="isStudent" :gutter="12" class="student-extra">
      <el-col :xs="24" :md="8">
        <div class="mini-card">
          <div class="mini-title">个人信息</div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="姓名">{{
              report.studentInfo?.name || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="学号">{{
              report.studentInfo?.studentNo || '-'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="mini-card">
          <div class="mini-title">历次成绩趋势</div>
          <BaseChart :option="trendOption" height="160px" />
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="mini-card">
          <div class="mini-title">学习态度</div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="出勤率">
              {{ report.attitudeDetail?.attendanceRate ?? '-' }}%
            </el-descriptions-item>
            <el-descriptions-item label="薄弱知识点">
              {{ report.attitudeDetail?.weakPoints?.join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="优势知识点">
              {{ report.attitudeDetail?.strongPoints?.join('、') || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
    </el-row>

    <!-- 关键发现 -->
    <div class="report-section">
      <div class="section-title">🔍 关键发现</div>
      <div class="findings">
        <div v-if="report.findings.strengths.length" class="findings-block success">
          <div class="block-label">✅ 优势</div>
          <div
            v-for="(s, i) in report.findings.strengths"
            :key="i"
            class="find-item"
          >
            <span class="find-point">{{ s.point }}</span>
            <span class="find-value">{{ s.value }}</span>
          </div>
        </div>
        <div v-if="report.findings.risks.length" class="findings-block danger">
          <div class="block-label">⚠️ 风险</div>
          <div
            v-for="(r, i) in report.findings.risks"
            :key="i"
            class="find-item risk-item"
          >
            <el-tag :type="riskType(r.level)" size="small" effect="dark">{{ r.level }}</el-tag>
            <span class="find-point">{{ r.subject }}</span>
            <span class="find-value">{{ r.evidence }}</span>
            <span v-if="r.students.length" class="find-students">
              涉及：{{ r.students.join('、') }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 归因分析 -->
    <div v-if="report.causes.length" class="report-section">
      <div class="section-title">🧠 归因分析</div>
      <div class="causes">
        <div v-for="(c, i) in report.causes" :key="i" class="cause-item">
          <div class="cause-issue">{{ c.issue }}</div>
          <div class="cause-root">← {{ c.rootCause }}</div>
          <el-tag size="small" type="info" effect="plain">数据：{{ c.dataRef }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 干预建议 -->
    <div v-if="report.suggestions.length" class="report-section">
      <div class="section-title">💡 干预建议</div>
      <div class="suggestions">
        <div
          v-for="(s, i) in report.suggestions"
          :key="i"
          class="suggestion-item"
        >
          <el-tag :type="priorityType(s.priority)" size="small" effect="dark">{{
            s.priority
          }}</el-tag>
          <div class="sug-main">
            <div class="sug-action">{{ i + 1 }}. {{ s.action }}</div>
            <div class="sug-meta">
              对象：{{ s.target }}
              <span v-if="s.knowledgePoints.length">
                · 知识点：{{ s.knowledgePoints.join('、') }}
              </span>
            </div>
          </div>
          <el-button
            size="small"
            type="primary"
            plain
            @click="emit('act', s.toolHint, s)"
          >
            {{ toolHintLabel[s.toolHint] }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 底部操作 -->
    <div class="report-actions">
      <el-button size="small" @click="emit('ask')">💬 追问 AI</el-button>
      <el-button size="small" @click="onExport('pdf')">📄 导出 PDF</el-button>
      <el-button size="small" @click="onExport('xlsx')">📄 导出 Excel</el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.diagnosis-report {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-section {
  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 10px;
    padding-left: 8px;
    border-left: 3px solid #2563eb;
  }
}

.overall-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  align-items: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.overall-grade {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 90px;

  .grade-letter {
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
  }
  .grade-score {
    font-size: 24px;
    font-weight: 600;
    color: #1e293b;
    small { font-size: 12px; color: #94a3b8; font-weight: 400; }
  }
  .grade-label {
    font-size: 12px;
    color: #64748b;
  }
}

.overall-radar {
  width: 100%;
}

.overall-summary {
  grid-column: 1 / -1;
  font-size: 14px;
  color: #475569;
  line-height: 1.7;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.student-extra {
  margin-bottom: 0;
}

.mini-card {
  height: 100%;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;

  .mini-title {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 8px;
  }
}

.findings {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.findings-block {
  padding: 10px 12px;
  border-radius: 8px;

  &.success { background: #ecfdf5; }
  &.danger { background: #fef2f2; }

  .block-label {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  &.success .block-label { color: #10b981; }
  &.danger .block-label { color: #ef4444; }
}

.find-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
  padding: 2px 0;
  flex-wrap: wrap;

  .find-point { font-weight: 500; color: #1e293b; }
  .find-value { color: #64748b; }
  .find-students { color: #ef4444; font-size: 12px; }
}

.causes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cause-item {
  padding: 10px 12px;
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  font-size: 13px;

  .cause-issue { font-weight: 500; color: #1e293b; }
  .cause-root { color: #64748b; margin: 2px 0 4px; }
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #eff6ff;
  border-radius: 6px;

  .sug-main { flex: 1; min-width: 0; }
  .sug-action { font-size: 14px; color: #1e293b; font-weight: 500; }
  .sug-meta { font-size: 12px; color: #64748b; margin-top: 2px; }
}

.report-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
}
</style>
