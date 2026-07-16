<!--
  AI 出题页面 - 两步向导式
  Step1 需求配置（AI 出题 + 从题库挑题弹窗）→ Step2 逐题审核发布（SSE 流式逐题展示）
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Back, Loading, Collection, Plus } from '@element-plus/icons-vue'
import QuizWizardStep1Config, { type DifficultyDistribution } from '@/components/quiz/QuizWizardStep1Config.vue'
import QuizWizardStep3Review from '@/components/quiz/QuizWizardStep3Review.vue'
import QuestionBankPickerDialog from '@/components/quiz/QuestionBankPickerDialog.vue'
import AssignmentListPanel from '@/components/quiz/AssignmentListPanel.vue'
import {
  generateQuizStream,
  saveQuizAssignment,
  publishQuizAssignment,
} from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import { difficultyLabels } from '@/utils/exerciseJudge'
import type { QuizQuestion, RagReference, ExerciseType } from '@/types'

const userStore = useUserStore()

const currentStep = ref<1 | 2>(1)
const step1Ref = ref<InstanceType<typeof QuizWizardStep1Config> | null>(null)

const generating = ref(false)
const genError = ref('')
const genStageHint = ref('')

const visibleQuestions = ref<QuizQuestion[]>([])
const ragReferences = ref<RagReference[]>([])

// 发布参数（截止时间 / 学生查看权限），由 Step2 右侧发布区设置
const publishDeadline = ref('')
const publishAllowReview = ref(false)

// 题库挑题弹窗
const bankPickerVisible = ref(false)
const pickerCourseId = computed(() => step1Ref.value?.form?.courseId)
const existingIds = computed(() => visibleQuestions.value.map((q) => q.id))

const assignmentRefreshTrigger = ref(0)
const savedConfig = ref<{
  courseId: number
  classId: number
  courseName: string
  className: string
  title: string
} | null>(null)

// ===== AI 生成（SSE 流式逐题展示） =====
async function handleGenerate(config: {
  courseId: number
  classId: number
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  questionCount: number
  difficultyDistribution: DifficultyDistribution
  extraRequirements: string
  title: string
}) {
  currentStep.value = 2
  generating.value = true
  genError.value = ''
  genStageHint.value = 'AI 正在准备出题…'
  visibleQuestions.value = []
  ragReferences.value = []

  const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === config.courseId)
  const classOpt = step1Ref.value?.classOptions.find((c) => c.value === config.classId)
  savedConfig.value = {
    courseId: config.courseId,
    classId: config.classId,
    courseName: courseOpt?.label || '',
    className: classOpt?.label || '',
    title: config.title || `${courseOpt?.label || ''} - 专项练习`,
  }

  await generateQuizStream(
    {
      courseId: config.courseId,
      classId: config.classId,
      knowledgePoints: config.knowledgePoints,
      questionTypes: config.questionTypes,
      questionCount: config.questionCount,
      difficultyDistribution: config.difficultyDistribution,
      extraRequirements: config.extraRequirements,
    },
    {
      onStage: (stage, difficulty) => {
        genStageHint.value = difficulty
          ? `正在生成${difficultyLabels[difficulty as keyof typeof difficultyLabels] || difficulty}题…`
          : stage
      },
      onQuestion: (q) => {
        // 首题到达即视为进入可审核状态，题目逐条追加
        visibleQuestions.value = [...visibleQuestions.value, q]
        generating.value = false
      },
      onDone: (refs) => {
        ragReferences.value = refs || []
        generating.value = false
      },
      onError: (msg) => {
        genError.value = msg || 'AI 服务暂不可用'
        generating.value = false
      },
    },
  )
  // 流结束兜底
  generating.value = false
}

// ===== 从题库挑题（弹窗式，追加到审核列表） =====
/** 确保有 savedConfig（题库题优先时用当前表单信息构造） */
function ensureSavedConfig(fallbackTitleSuffix: string) {
  if (savedConfig.value) return
  const form = step1Ref.value?.form
  if (!form) return
  const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === form.courseId)
  const classOpt = step1Ref.value?.classOptions.find((c) => c.value === form.classId)
  savedConfig.value = {
    courseId: form.courseId!,
    classId: form.classId!,
    courseName: courseOpt?.label || '',
    className: classOpt?.label || '',
    title: form.title || `${courseOpt?.label || ''} - ${fallbackTitleSuffix}`,
  }
}

function openBankPicker() {
  if (!pickerCourseId.value) {
    ElMessage.warning('请先选择课程')
    return
  }
  bankPickerVisible.value = true
}

function handleBankPicked(picked: QuizQuestion[]) {
  // 按 id 去重后追加（不替换已有题目）
  const existing = new Set(existingIds.value)
  const fresh = picked.filter((q) => !existing.has(q.id))
  if (!fresh.length) {
    ElMessage.info('所选题目均已在组卷中')
    return
  }
  ensureSavedConfig('题库组卷')
  visibleQuestions.value = [...visibleQuestions.value, ...fresh]
  genError.value = ''
  generating.value = false
  currentStep.value = 2
  ElMessage.success(`已添加 ${fresh.length} 道题`)
}

// ===== 保存 / 发布 =====
function buildSavePayload(questions: QuizQuestion[], status: 'draft') {
  return {
    title: savedConfig.value!.title,
    courseId: savedConfig.value!.courseId,
    courseName: savedConfig.value!.courseName,
    classId: savedConfig.value!.classId,
    className: savedConfig.value!.className,
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: Array.from(
      new Set(questions.map((q) => q.knowledgePoint).filter(Boolean)),
    ) as string[],
    status,
    questions,
    deadline: publishDeadline.value || undefined,
    allowReview: publishAllowReview.value,
  }
}

async function handleSaveDraft(questions: QuizQuestion[]) {
  if (!savedConfig.value) return
  await saveQuizAssignment(buildSavePayload(questions, 'draft'))
  assignmentRefreshTrigger.value++
  ElMessage.success(`练习「${savedConfig.value.title}」已保存为草稿`)
}

async function handlePublish(questions: QuizQuestion[]) {
  if (!savedConfig.value) return
  const saved = await saveQuizAssignment(buildSavePayload(questions, 'draft'))
  await publishQuizAssignment(saved.id)
  assignmentRefreshTrigger.value++
  resetWizard()
  ElMessage.success('练习已发布，学生可在「在线答题」中作答')
}

function resetWizard() {
  currentStep.value = 1
  visibleQuestions.value = []
  ragReferences.value = []
  genError.value = ''
  generating.value = false
  publishDeadline.value = ''
  publishAllowReview.value = false
}
</script>

<template>
  <div class="page-container">
    <div class="wizard-steps">
      <el-steps :active="currentStep - 1" align-center>
        <el-step title="需求配置" description="填写出题要求" />
        <el-step title="逐题审核" description="生成 + 审核 + 发布" />
      </el-steps>
    </div>

    <!-- Step 1 -->
    <div v-if="currentStep === 1" class="wizard-content">
      <QuizWizardStep1Config ref="step1Ref" :loading="false" @generate="handleGenerate" />

      <!-- 题库挑题入口 -->
      <div class="bank-entry">
        <span class="bank-entry-hint">已有合适的题？</span>
        <el-button :icon="Collection" plain @click="openBankPicker">从题库挑题加入</el-button>
      </div>
    </div>

    <!-- Step 2: 审核 -->
    <div v-else-if="currentStep === 2" class="wizard-content">
      <div class="step2-toolbar">
        <el-button :icon="Back" :disabled="generating" @click="currentStep = 1">返回配置</el-button>
        <el-button :icon="Plus" :disabled="generating" @click="openBankPicker">从题库添加</el-button>
      </div>

      <!-- 错误 -->
      <div v-if="genError" class="error-block">
        <p>{{ genError }}</p>
        <el-button type="primary" :icon="Back" @click="currentStep = 1">返回配置</el-button>
      </div>

      <!-- 加载中（尚无题目到达） -->
      <div v-else-if="generating && !visibleQuestions.length" class="loading-block">
        <el-icon class="loading-spin is-loading"><Loading /></el-icon>
        <p>{{ genStageHint || 'AI 正在生成题目，预计 10-30 秒…' }}</p>
      </div>

      <!-- 审核列表（流式追加：有题即渲染，生成中继续追加） -->
      <QuizWizardStep3Review
        v-else-if="visibleQuestions.length"
        :questions="visibleQuestions"
        :rag-references="ragReferences"
        :course-id="savedConfig?.courseId"
        v-model:deadline="publishDeadline"
        v-model:allow-review="publishAllowReview"
        @save-draft="handleSaveDraft"
        @publish="handlePublish"
      />

      <el-empty v-else description="未生成有效题目，请返回重试" />
    </div>

    <QuestionBankPickerDialog
      v-model="bankPickerVisible"
      :course-id="pickerCourseId"
      :exclude-ids="existingIds"
      @confirm="handleBankPicked"
    />

    <AssignmentListPanel :refresh-trigger="assignmentRefreshTrigger" />
  </div>
</template>

<style scoped lang="scss">
.page-container {
  .wizard-steps {
    background: white;
    padding: 20px 24px;
    border-radius: 8px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  .wizard-content {
    background: white;
    padding: 24px;
    border-radius: 8px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    min-height: 400px;
  }

  .bank-entry {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 8px;
    padding-top: 20px;
    border-top: 1px dashed #e2e8f0;

    .bank-entry-hint {
      font-size: 13px;
      color: #94a3b8;
    }
  }

  .step2-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }

  .loading-block {
    text-align: center;
    padding: 80px 0;
    color: #64748b;

    .loading-spin {
      font-size: 36px;
      color: #409eff;
      margin-bottom: 12px;
    }
    p { font-size: 14px; }
  }

  .error-block {
    text-align: center;
    padding: 32px;
    p { color: #ef4444; font-size: 14px; margin-bottom: 16px; }
  }
}
</style>
