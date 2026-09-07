<!--
  AI 学情诊断过程区组件
  SSE 流式渲染工具调用过程，仿 AgentChat 的 toolCalls 区
  自带 callId 匹配（step+name 组合键），不复用 streamAgentChat 的脆弱计数器
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Tools } from '@element-plus/icons-vue'
import type { DiagnosisStep } from '@/types'

const props = defineProps<{
  steps: DiagnosisStep[]
  running: boolean
  error?: string
}>()

const expanded = ref<Set<string>>(new Set())

const visibleSteps = computed(() =>
  props.running ? props.steps : props.steps.filter((step) => step.toolCalls.length > 0),
)

function toggle(id: string): void {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
}

const totalTools = computed(() =>
  visibleSteps.value.reduce((sum, s) => sum + s.toolCalls.length, 0),
)

const doneTools = computed(
  () =>
    visibleSteps.value.reduce(
      (sum, s) => sum + s.toolCalls.filter((c) => c.status !== 'running').length,
      0,
    ),
)

function renderResult(result: unknown): string {
  return JSON.stringify(result, null, 2)
}

/** 工具名 → 中文标签（对老师友好，不暴露英文函数名） */
const TOOL_LABELS: Record<string, string> = {
  get_course_overview: '课程总览',
  get_score_list: '成绩列表',
  get_score_trend: '成绩趋势',
  get_attendance: '考勤统计',
  get_knowledge_mastery: '知识点掌握度',
  get_weak_knowledge_points: '薄弱知识点',
  get_warning_students: '预警学生',
  get_student_detail: '学生档案',
  get_exercise_records: '答题记录',
  search_student: '搜索学生',
}

function toolLabel(name: string): string {
  return TOOL_LABELS[name] || name
}

/** 工具参数 → 中文友好描述 */
function toolArgsText(name: string, args: Record<string, unknown>): string {
  const parts: string[] = []
  if ('student_id' in args && args.student_id && args.student_id !== 0) {
    parts.push(`学生 ${args.student_id}`)
  }
  if ('top_k' in args && args.top_k) parts.push(`前 ${args.top_k}`)
  if ('keyword' in args && args.keyword) parts.push(`"${args.keyword}"`)
  return parts.length ? `（${parts.join('、')}）` : ''
}

/** 工具名 → 中文摘要 */
function summarize(name: string, result: unknown): string {
  if (!result || typeof result !== 'object') return ''
  const r = result as Record<string, unknown>
  if ('error' in r) return `失败：${r.error}`
  const map: Record<string, string> = {
    get_course_overview: `${r.student_count ?? 0} 人·均分 ${r.avg_score ?? '-'}·预警 ${r.warning_count ?? 0}`,
    get_score_list: `${(r.scores as unknown[])?.length ?? 0} 条成绩`,
    get_score_trend: `${(r.trend as unknown[])?.length ?? 0} 次考核趋势`,
    get_attendance: `出勤率 ${r.rate ?? r.avg_rate ?? '-'}`,
    get_knowledge_mastery: `${(r.points as unknown[])?.length ?? 0} 个知识点`,
    get_weak_knowledge_points: `薄弱 ${(r.weak_points as unknown[])?.length ?? 0} 个`,
    get_warning_students: `${(r.warning_students as unknown[])?.length ?? 0} 人预警`,
    get_student_detail: `${r.name ?? ''} 综合档案`,
    get_exercise_records: `${r.count ?? 0} 条答题`,
    search_student: `${(r.students as unknown[])?.length ?? 0} 人匹配`,
  }
  return map[name] || ''
}
</script>

<template>
  <div class="diagnosis-process">
    <div class="process-header">
      <el-icon v-if="running" class="is-loading" color="#2563eb"><Tools /></el-icon>
      <el-icon v-else-if="error" color="#ef4444"><Tools /></el-icon>
      <el-icon v-else color="#10b981"><Tools /></el-icon>
      <span v-if="running" class="process-title running">AI 正在诊断…</span>
      <span v-else-if="error" class="process-title error">诊断失败</span>
      <span v-else-if="visibleSteps.length" class="process-title done">
        诊断完成，共调用 {{ totalTools }} 个工具
      </span>
      <span v-else class="process-title idle">等待开始诊断</span>
      <span v-if="visibleSteps.length" class="process-count">{{ doneTools }}/{{ totalTools }}</span>
    </div>

    <div v-if="!visibleSteps.length && !running" class="process-empty">
      选择分析对象与维度，点击「开始 AI 分析」，系统将自动调用学情数据生成诊断报告。
    </div>

    <div v-for="s in visibleSteps" :key="s.step" class="step">
      <div class="step-no">step{{ s.step }}</div>
      <div class="step-body">
        <div
          v-for="call in s.toolCalls"
          :key="call.id"
          class="tool-call"
          :class="{ error: call.status === 'error' }"
        >
          <div class="tool-call-header" @click="toggle(call.id)">
            <span class="tool-status">
              <span v-if="call.status === 'running'" class="dot running"></span>
              <span v-else-if="call.status === 'error'" class="dot error">✕</span>
              <span v-else class="dot done">✓</span>
            </span>
            <span class="tool-name">{{ toolLabel(call.name) }}</span>
            <span class="tool-args">{{ toolArgsText(call.name, call.arguments) }}</span>
            <el-tag
              v-if="call.status === 'running'"
              size="small"
              type="warning"
            >执行中</el-tag>
            <el-tag
              v-else-if="call.status === 'error'"
              size="small"
              type="danger"
            >失败</el-tag>
            <el-tag v-else size="small" type="success">完成</el-tag>
          </div>
          <div v-if="call.summary" class="tool-summary">返回：{{ call.summary }}</div>
          <el-collapse-transition>
            <pre v-if="expanded.has(call.id)" class="tool-json">{{
              renderResult(call.result)
            }}</pre>
          </el-collapse-transition>
        </div>
      </div>
    </div>

    <div v-if="error" class="process-error">{{ error }}</div>
  </div>
</template>

<style scoped lang="scss">
.diagnosis-process {
  min-height: 120px;
}

.process-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
  margin-bottom: 12px;

  .process-title {
    font-size: 15px;
    font-weight: 600;
    &.running { color: #2563eb; }
    &.done { color: #10b981; }
    &.error { color: #ef4444; }
    &.idle { color: #64748b; font-weight: 400; }
  }
  .process-count {
    margin-left: auto;
    font-size: 13px;
    color: #64748b;
  }
}

.is-loading {
  animation: rotating 1.5s linear infinite;
}
@keyframes rotating {
  to { transform: rotate(360deg); }
}

.process-empty {
  padding: 24px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.8;
}

.step {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.step-no {
  flex-shrink: 0;
  width: 44px;
  font-size: 12px;
  color: #94a3b8;
  padding-top: 2px;
}

.step-body {
  flex: 1;
  min-width: 0;
}

.tool-call {
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 6px;

  &.error {
    background: #fef2f2;
  }
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 13px;

  .tool-status .dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    font-size: 11px;

    &.running {
      border: 2px solid #2563eb;
      border-top-color: transparent;
      border-radius: 50%;
      animation: rotating 0.8s linear infinite;
    }
    &.done { color: #10b981; }
    &.error { color: #ef4444; }
  }

  .tool-name {
    color: #1e293b;
    font-weight: 500;
  }
  .tool-args {
    color: #94a3b8;
    font-size: 12px;
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.tool-summary {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
  padding-left: 22px;
}

.tool-json {
  margin-top: 8px;
  padding: 10px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 4px;
  font-size: 12px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.process-error {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fef2f2;
  color: #ef4444;
  border-radius: 6px;
  font-size: 13px;
}
</style>
