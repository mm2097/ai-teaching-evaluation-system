<!--
  AI 出题页面 - 两步向导式
  Step1 组卷配置（AI 生成 + 从题库选题并列）→ Step2 审核发布（支持 AI 补题 + 继续选题）
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Back, Loading, Collection, Plus, MagicStick } from '@element-plus/icons-vue'
import QuizWizardStep1Config, {
  type DifficultyDistribution,
  type GenerateConfig,
} from '@/components/quiz/QuizWizardStep1Config.vue'
import QuizWizardStep3Review from '@/components/quiz/QuizWizardStep3Review.vue'
import QuestionBankPickerDialog from '@/components/quiz/QuestionBankPickerDialog.vue'
import AiSupplementDialog from '@/components/quiz/AiSupplementDialog.vue'
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
const genMeta = ref<{ model: string; elapsedMs: number } | null>(null)

const publishDeadline = ref('')
const publishAllowReview = ref(false)

const bankPickerVisible = ref(false)
const supplementVisible = ref(false)

const pickerCourseId = computed(() => savedConfig.value?.courseId ?? step1Ref.value?.form?.courseId)
const existingIds = computed(() => visibleQuestions.value.map((q) => q.id))

const assignmentRefreshTrigger = ref(0)
const savedConfig = ref<{
  courseId: number
  classId: number
  courseName: string
  className: string
  title: string
} | null>(null)

const lastGenerateConfig = ref<Omit<GenerateConfig, 'courseId' | 'classId' | 'title'> | null>(null)

function resolveCourseClassLabels(courseId: number, classId: number) {
  const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === courseId)
  const classOpt = step1Ref.value?.classOptions.find((c) => c.value === classId)
  return {
    courseName: courseOpt?.label || savedConfig.value?.courseName || '',
    className: classOpt?.label || savedConfig.value?.className || '',
  }
}

function applySavedConfig(config: GenerateConfig) {
  const { courseName, className } = resolveCourseClassLabels(config.courseId, config.classId)
  savedConfig.value = {
    courseId: config.courseId,
    classId: config.classId,
    courseName,
    className,
    title: config.title || `${courseName} - 专项练习`,
  }
  lastGenerateConfig.value = {
    knowledgePoints: config.knowledgePoints,
    questionTypes: config.questionTypes,
    questionCount: config.questionCount,
    difficultyDistribution: config.difficultyDistribution,
    extraRequirements: config.extraRequirements,
  }
}

// ===== AI 生成（SSE 流式，支持追加到已有组卷） =====
async function handleGenerate(
  config: GenerateConfig,
  options: { append?: boolean } = {},
) {
  const append = options.append ?? visibleQuestions.value.length > 0

  currentStep.value = 2
  generating.value = true
  genError.value = ''
  genStageHint.value = append ? 'AI 正在补题…' : 'AI 正在准备出题…'

  if (!append) {
    visibleQuestions.value = []
    ragReferences.value = []
    genMeta.value = null
  }

  applySavedConfig(config)

  try {
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
          visibleQuestions.value = [...visibleQuestions.value, q]
        },
        onDone: (refs, _total, meta) => {
          if (append && refs?.length) {
            ragReferences.value = [...ragReferences.value, ...refs]
          } else {
            ragReferences.value = refs || []
          }
          if (meta) genMeta.value = meta
          generating.value = false
          supplementVisible.value = false
        },
        onError: (msg) => {
          genError.value = msg || 'AI 服务暂不可用'
          generating.value = false
        },
      },
    )
  } catch (e) {
    genError.value = e instanceof Error ? e.message : 'AI 服务暂不可用'
  } finally {
    generating.value = false
  }
}

function openSupplementDialog() {
  if (!savedConfig.value) {
    ElMessage.warning('请先完成组卷配置（选择课程与班级）')
    return
  }
  supplementVisible.value = true
}

function handleSupplementConfirm(partial: {
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  questionCount: number
  difficultyDistribution: DifficultyDistribution
  extraRequirements: string
}) {
  if (!savedConfig.value) return
  handleGenerate(
    {
      courseId: savedConfig.value.courseId,
      classId: savedConfig.value.classId,
      title: savedConfig.value.title,
      ...partial,
    },
    { append: true },
  )
}

// ===== 从题库挑题（追加到审核列表） =====
function ensureSavedConfig(fallbackTitleSuffix: string) {
  if (savedConfig.value) return
  const form = step1Ref.value?.form
  if (!form?.courseId || !form?.classId) return
  const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === form.courseId)
  const classOpt = step1Ref.value?.classOptions.find((c) => c.value === form.classId)
  savedConfig.value = {
    courseId: form.courseId,
    classId: form.classId,
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
  const existing = new Set(existingIds.value)
  const fresh = picked.filter((q) => !existing.has(q.id))
  if (!fresh.length) {
    ElMessage.info('所选题目均已在组卷中')
    return
  }
  ensureSavedConfig('题库组卷')
  visibleQuestions.value = [...visibleQuestions.value, ...fresh]
  genError.value = ''
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
  genMeta.value = null
  genError.value = ''
  generating.value = false
  publishDeadline.value = ''
  publishAllowReview.value = false
  savedConfig.value = null
  lastGenerateConfig.value = null
}
</script>

<template>
  <div class="page-container">
    <div class="wizard-steps">
      <el-steps :active="currentStep - 1" align-center>
        <el-step title="组卷配置" description="AI 生成 / 题库选题" />
        <el-step title="审核发布" description="混合组卷 + 发布" />
      </el-steps>
    </div>

    <!-- Step 1 -->
    <div v-if="currentStep === 1" class="wizard-content">
      <QuizWizardStep1Config
        ref="step1Ref"
        :loading="generating"
        @generate="handleGenerate"
        @pick-from-bank="openBankPicker"
      />
      <p v-if="visibleQuestions.length" class="draft-hint">
        当前已选 {{ visibleQuestions.length }} 题，继续 AI 生成将追加到组卷中。
        <el-button link type="primary" @click="currentStep = 2">前往审核</el-button>
      </p>
    </div>

    <!-- Step 2: 审核 -->
    <div v-else-if="currentStep === 2" class="wizard-content">
      <div class="step2-toolbar">
        <el-button :icon="Back" :disabled="generating" @click="currentStep = 1">返回配置</el-button>
        <el-button
          type="primary"
          :icon="MagicStick"
          :loading="generating"
          :disabled="generating"
          @click="openSupplementDialog"
        >
          AI 补题
        </el-button>
        <el-button :icon="Plus" :disabled="generating" @click="openBankPicker">从题库添加</el-button>
        <span v-if="visibleQuestions.length" class="compose-count">共 {{ visibleQuestions.length }} 题</span>
        <span v-if="generating" class="gen-hint">{{ genStageHint }}</span>
      </div>

      <div v-if="genError && !visibleQuestions.length" class="error-block">
        <p>{{ genError }}</p>
        <el-button type="primary" :icon="Back" @click="currentStep = 1">返回配置</el-button>
      </div>

      <div v-else-if="generating && !visibleQuestions.length" class="loading-block">
        <el-icon class="loading-spin is-loading"><Loading /></el-icon>
        <p>{{ genStageHint || 'AI 正在生成题目，预计 10-30 秒…' }}</p>
      </div>

      <QuizWizardStep3Review
        v-else-if="visibleQuestions.length"
        :questions="visibleQuestions"
        :rag-references="ragReferences"
        :course-id="savedConfig?.courseId"
        :generation-pending="generating"
        v-model:deadline="publishDeadline"
        v-model:allow-review="publishAllowReview"
        @save-draft="handleSaveDraft"
        @publish="handlePublish"
      />

      <el-empty v-else description="组卷为空，请返回配置页 AI 生成或从题库选题" />

      <el-alert
        v-if="genError && visibleQuestions.length"
        type="warning"
        :title="genError"
        show-icon
        :closable="false"
        class="gen-error-alert"
      />
    </div>

    <QuestionBankPickerDialog
      v-model="bankPickerVisible"
      :course-id="pickerCourseId"
      :exclude-ids="existingIds"
      @confirm="handleBankPicked"
    />

    <AiSupplementDialog
      v-model:visible="supplementVisible"
      :loading="generating"
      :initial-config="lastGenerateConfig"
      @confirm="handleSupplementConfirm"
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

  .draft-hint {
    text-align: center;
    font-size: 13px;
    color: #64748b;
    margin-top: 8px;
  }

  .step2-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .compose-count {
      font-size: 13px;
      color: #475569;
      margin-left: 4px;
    }

    .gen-hint {
      font-size: 13px;
      color: #409eff;
      margin-left: auto;
    }
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

  .gen-error-alert {
    margin-top: 16px;
  }
}
</style>
