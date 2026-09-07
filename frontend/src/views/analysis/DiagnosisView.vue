<!--
  AI 学情分析主视图
  老师选班级或学生 → 点开始 → SSE 流式渲染诊断过程 + 结构化报告 → 可追问/导出/干预
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import DiagnosisProcess from '@/components/analysis/DiagnosisProcess.vue'
import DiagnosisReportCard from '@/components/analysis/DiagnosisReport.vue'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import {
  DIAGNOSIS_DIMENSIONS,
  streamDiagnosis,
  saveDiagnosisReport,
} from '@/api/analysis'
import { streamAgentChat } from '@/api/agent'
import { downloadReportFile } from '@/api/report'
import type {
  DiagnosisReport,
  DiagnosisStep,
  DiagnosisToolHint,
  AgentStreamEvent,
} from '@/types'

const router = useRouter()
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
  allowedTargetTypes,
  showClassFilter,
  showCourseFilter,
  showTargetTypeFilter,
  showStudentPicker,
} = scope

// 维度与深度
const dimensions = ref<string[]>(['score', 'knowledge', 'warning'])
const depth = ref<'detail' | 'brief'>('detail')

const dimensionOptions = DIAGNOSIS_DIMENSIONS

// 运行状态
const running = ref(false)
const processSteps = ref<DiagnosisStep[]>([])
const processError = ref<string>('')
const report = ref<DiagnosisReport | null>(null)
const rawContent = ref<string>('') // 兜底用原始文本

// 追问
const askVisible = ref(false)
const askInput = ref('')
const askMessages = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
const asking = ref(false)

const diagnosisScope = computed<'class' | 'student'>(() =>
  targetType.value === 'student' ? 'student' : 'class',
)

const studentId = computed(() =>
  diagnosisScope.value === 'student' ? targetId.value : undefined,
)

const sessionId = computed(() => `diagnosis_c${courseId.value ?? 0}`)

const canStart = computed(
  () => !running.value && !!courseId.value && (diagnosisScope.value === 'class' || !!studentId.value),
)

/** 从 LLM 输出中提取诊断 JSON。
 * LLM 偶发在 JSON 前后附带说明文字（如"我已收集数据...{...}"），
 * 用正则匹配第一个 { 到最后一个 } 的片段再做 JSON.parse，提高容错。 */
function parseDiagnosis(content: string): DiagnosisReport | null {
  if (!content) return null
  // 先尝试整体解析（理想情况：纯 JSON）
  const tryParse = (s: string): DiagnosisReport | null => {
    try {
      const obj = JSON.parse(s) as DiagnosisReport
      if (obj && obj.scope && obj.overall) return obj
      return null
    } catch {
      return null
    }
  }
  // 去 markdown 代码块包裹
  const stripped = content
    .trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim()
  const whole = tryParse(stripped)
  if (whole) return whole
  // 提取第一个 { 到最后一个 } 的子串（LLM 前后带说明文字时）
  const first = stripped.indexOf('{')
  const last = stripped.lastIndexOf('}')
  if (first !== -1 && last > first) {
    const fragment = stripped.slice(first, last + 1)
    return tryParse(fragment)
  }
  return null
}

/** 重置一次新诊断的状态 */
function resetState(): void {
  processSteps.value = []
  processError.value = ''
  report.value = null
  rawContent.value = ''
}

async function startDiagnosis(): Promise<void> {
  if (!canStart.value) return
  resetState()
  running.value = true

  let currentStep = 0
  let toolCallCounter = 0

  try {
    const stream = streamDiagnosis({
      courseId: courseId.value!,
      studentId: studentId.value,
      scope: diagnosisScope.value,
      dimensions: dimensions.value,
      depth: depth.value,
      sessionId: sessionId.value,
    })

    for await (const evt of stream) {
      if (evt.type === 'thinking') {
        currentStep += 1
        processSteps.value.push({ step: currentStep, toolCalls: [], status: 'running' })

      } else if (evt.type === 'tool_call') {
        const step = processSteps.value[processSteps.value.length - 1]
        if (!step) continue
        const id = `tc-${currentStep}_${++toolCallCounter}`
        const call: DiagnosisStep['toolCalls'][number] = {
          id,
          name: evt.call.tool,
          arguments: evt.call.params,
          status: 'running',
        }
        step.toolCalls.push(call)

      } else if (evt.type === 'tool_result') {
        // 用 name 精确匹配最后一个同名 running 工具（修正 streamAgentChat 的 callId 脆弱性，D5）
        // 跨 step 查找：tool_result 可能在新 step_start 之后才到达
        const allSteps = processSteps.value
        for (let i = allSteps.length - 1; i >= 0; i--) {
          const match = [...allSteps[i].toolCalls]
            .reverse()
            .find((c) => c.name === evt.name && c.status === 'running')
          if (match) {
            match.status = 'done'
            match.result = evt.result
            match.summary = evt.summary
            break
          }
        }
        // 标记所有工具都已完成的 step 为 done
        for (const s of allSteps) {
          if (s.status === 'running' && s.toolCalls.length && s.toolCalls.every((c) => c.status !== 'running')) {
            s.status = 'done'
          }
        }

      } else if (evt.type === 'content_done') {
        rawContent.value = evt.content
        const parsed = parseDiagnosis(evt.content)
        if (parsed) {
          report.value = parsed
          processError.value = '' // 解析成功，清掉之前可能的瞬时 error
        } else if (!processError.value) {
          // 非 JSON 但无 error：保留原文展示，不标"诊断失败"
          rawContent.value = evt.content
        }

      } else if (evt.type === 'error') {
        // 仅当还没收到 content 时才记 error；content 已到则忽略后续 error
        if (!report.value && !rawContent.value) {
          processError.value = evt.message || '诊断服务暂不可用'
        }
      }
    }

    // truncated 兜底：无 content 且无 error
    if (!report.value && !processError.value && !rawContent.value) {
      processError.value = '诊断未完成（已达最大推理步数），可重试或缩小维度'
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '诊断失败'
    processError.value = msg
    ElMessage.error(msg)
  } finally {
    running.value = false
  }
}

// ============ 追问 ============
function toggleAsk(): void {
  askVisible.value = !askVisible.value
  if (!askVisible.value) {
    askInput.value = ''
  }
}

async function sendAsk(): Promise<void> {
  const text = askInput.value.trim()
  if (!text || asking.value) return
  if (!courseId.value) {
    ElMessage.warning('请先选择课程')
    return
  }
  askInput.value = ''
  asking.value = true
  askMessages.value.push({ role: 'user', content: text })
  const assistantMsg = { role: 'assistant' as const, content: '思考中…' }
  askMessages.value.push(assistantMsg)

  try {
    const stream = streamAgentChat({
      agentType: 'qa',
      courseId: courseId.value,
      message: text,
      sessionId: sessionId.value, // 同诊断 sessionId，继承文本上下文
    })
    let got = false
    for await (const evt of stream) {
      if (evt.type === 'tool_call') {
        assistantMsg.content = '正在查询学情数据…'
      } else if (evt.type === 'content_done') {
        assistantMsg.content = evt.content || '（无回复）'
        got = true
      } else if (evt.type === 'error') {
        assistantMsg.content = evt.message || '追问失败，请重试'
        got = true
      }
    }
    if (!got) assistantMsg.content = '未收到有效回复，请重试'
  } catch (err) {
    assistantMsg.content = err instanceof Error ? err.message : '追问失败'
  } finally {
    asking.value = false
  }
}

// ============ 导出 ============
async function onExport(format: 'pdf' | 'xlsx'): Promise<void> {
  if (!report.value || !courseId.value) return
  try {
    const res = await saveDiagnosisReport({
      courseId: courseId.value,
      studentId: studentId.value,
      scope: diagnosisScope.value,
      diagnosisJson: report.value as unknown as Record<string, unknown>,
      exportFormat: format,
    })
    const blob = await downloadReportFile(res.id, format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${res.name}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('已导出报告')
  } catch {
    ElMessage.error('导出失败，请重试')
  }
}

// ============ 干预联动 ============
async function onAct(
  hint: DiagnosisToolHint,
  suggestion: DiagnosisReport['suggestions'][number],
): Promise<void> {
  if (hint === 'weakness_driven_quiz') {
    router.push({
      path: '/quiz/manage',
      query: { knowledgePoints: suggestion.knowledgePoints.join(',') },
    })
  } else if (hint === 'talk') {
    router.push({
      path: '/analysis/warning',
      query: suggestion.target ? { student: suggestion.target } : {},
    })
  } else if (hint === 'notify') {
    // 发通知需要 warningId，这里简化提示
    ElMessage.info('请到「异常学情预警」页选择学生发送通知')
    router.push({ path: '/analysis/warning' })
  }
}

// ============ 重置（切课程时） ============
function onFilterQuery(): void {
  // AnalysisFilterBar 的 @query 用于重置诊断区
  if (!running.value) {
    resetState()
    askVisible.value = false
    askMessages.value = []
  }
}
</script>

<template>
  <div class="page-container">
    <!-- 筛选栏 -->
    <div class="content-card">
      <AnalysisFilterBar
        v-model:target-type="targetType"
        v-model:semester-id="semesterId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="allowedTargetTypes"
        :semester-options="semesterOptions"
        :show-dept-filter="false"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="showTargetTypeFilter"
        :show-student-picker="showStudentPicker"
        :student-list="studentList"
        :student-loading="studentLoading"
        :class-options="classOptions"
        :course-options="courseOptions"
        :show-query-button="true"
        @query="onFilterQuery"
      />
    </div>

    <!-- 维度 + 深度 + 开始按钮 -->
    <div class="content-card filter-row">
      <div class="dim-block">
        <span class="dim-label">分析维度</span>
        <el-checkbox-group v-model="dimensions">
          <el-checkbox
            v-for="d in dimensionOptions"
            :key="d.key"
            :label="d.label"
            :value="d.key"
          >
            {{ d.label }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <div class="depth-block">
        <span class="dim-label">深度</span>
        <el-radio-group v-model="depth">
          <el-radio value="detail">详细</el-radio>
          <el-radio value="brief">概览</el-radio>
        </el-radio-group>
      </div>
      <el-button
        type="primary"
        :icon="MagicStick"
        :loading="running"
        :disabled="!canStart"
        @click="startDiagnosis"
      >
        {{ running ? 'AI 分析中…' : '🤖 开始 AI 分析' }}
      </el-button>
    </div>

    <!-- 过程区 -->
    <div class="content-card">
      <div class="content-card__title">诊断过程</div>
      <DiagnosisProcess
        :steps="processSteps"
        :running="running"
        :error="processError"
      />
      <div v-if="processError && !report" class="retry-row">
        <el-button type="primary" plain :disabled="running" @click="startDiagnosis">
          重新分析
        </el-button>
      </div>
    </div>

    <!-- 报告区 -->
    <div v-if="report" class="content-card">
      <DiagnosisReportCard
        :report="report"
        @ask="toggleAsk"
        @export="onExport"
        @act="onAct"
      />
    </div>

    <!-- 非 JSON 降级展示 -->
    <div v-else-if="rawContent && processError" class="content-card">
      <div class="content-card__title">诊断原始内容</div>
      <div class="raw-content">{{ rawContent }}</div>
      <el-button type="primary" plain size="small" @click="toggleAsk">💬 追问 AI</el-button>
    </div>

    <!-- 空状态引导 -->
    <div v-else-if="!running && !processError" class="content-card empty-card">
      <el-empty description="选择分析对象与维度，点击开始 AI 分析">
        <div class="quick-prompts">
          <el-button size="small" @click="dimensions = ['knowledge']; depth = 'detail'; startDiagnosis()">
            诊断班级薄弱知识点
          </el-button>
          <el-button size="small" @click="dimensions = ['score']; depth = 'detail'; startDiagnosis()">
            分析成绩下滑学生
          </el-button>
        </div>
      </el-empty>
    </div>

    <!-- 追问区 -->
    <div v-if="askVisible" class="content-card ask-card">
      <div class="content-card__title">💬 追问 AI</div>
      <div class="ask-messages">
        <div
          v-for="(m, i) in askMessages"
          :key="i"
          class="ask-msg"
          :class="m.role"
        >
          <div class="ask-avatar">{{ m.role === 'user' ? '师' : 'AI' }}</div>
          <div class="ask-bubble">{{ m.content }}</div>
        </div>
        <div v-if="!askMessages.length" class="ask-empty">
          基于本次诊断上下文，可继续追问细节，例如「张三为什么下滑」「图论怎么补」。
        </div>
      </div>
      <div class="ask-input">
        <el-input
          v-model="askInput"
          placeholder="追问诊断细节，回车发送"
          :disabled="asking"
          @keydown.enter.exact.prevent="sendAsk"
        />
        <el-button type="primary" :loading="asking" :disabled="!askInput.trim()" @click="sendAsk">
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.filter-row {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.dim-label {
  font-size: 14px;
  color: #1e293b;
  font-weight: 500;
  margin-right: 8px;
}

.dim-block,
.depth-block {
  display: flex;
  align-items: center;
}

.retry-row {
  margin-top: 12px;
}

.empty-card {
  text-align: center;
}

.quick-prompts {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
}

.raw-content {
  white-space: pre-wrap;
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  margin-bottom: 8px;
}

.ask-card {
  .ask-messages {
    max-height: 320px;
    overflow-y: auto;
    margin-bottom: 12px;
  }

  .ask-msg {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;

    &.assistant { flex-direction: row; }
    &.user { flex-direction: row-reverse; }

    .ask-avatar {
      flex-shrink: 0;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563eb, #6366f1);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
    }

    .ask-bubble {
      max-width: 70%;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
      background: #f1f5f9;
      color: #1e293b;
    }

    &.user .ask-bubble {
      background: #2563eb;
      color: #fff;
    }
  }

  .ask-empty {
    text-align: center;
    color: #94a3b8;
    font-size: 13px;
    padding: 16px;
  }

  .ask-input {
    display: flex;
    gap: 8px;
  }
}
</style>
