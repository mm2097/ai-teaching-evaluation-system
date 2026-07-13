<!--
  AI 出题页面 - 两步向导式
  Step1 需求配置 → Step2 逐题审核发布
-->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Back, Loading } from '@element-plus/icons-vue'
import QuizWizardStep1Config, { type DifficultyDistribution } from '@/components/quiz/QuizWizardStep1Config.vue'
import QuizWizardStep3Review from '@/components/quiz/QuizWizardStep3Review.vue'
import AssignmentListPanel from '@/components/quiz/AssignmentListPanel.vue'
import {
  generateQuizQuestions,
  saveQuizAssignment,
  publishQuizAssignment,
} from '@/api/quiz'
import { fetchQuestionBank } from '@/api/questionBank'
import { useUserStore } from '@/stores/user'
import { difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { QuizQuestion, RagReference, ExerciseType } from '@/types'

const userStore = useUserStore()

const currentStep = ref<1 | 2>(1)
const createMode = ref<'ai' | 'bank'>('ai')
const step1Ref = ref<InstanceType<typeof QuizWizardStep1Config> | null>(null)

const generating = ref(false)
const genError = ref('')

const visibleQuestions = ref<QuizQuestion[]>([])
const ragReferences = ref<RagReference[]>([])

const bankQuestions = ref<QuizQuestion[]>([])
const bankSelectedIds = ref<number[]>([])
const bankLoading = ref(false)

const assignmentRefreshTrigger = ref(0)
const savedConfig = ref<{
  courseId: number
  classId: number
  courseName: string
  className: string
  title: string
} | null>(null)

// ===== AI 生成（同步批量） =====
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
  visibleQuestions.value = []
  ragReferences.value = []

  try {
    const result = await generateQuizQuestions({
      courseId: config.courseId,
      classId: config.classId,
      knowledgePoints: config.knowledgePoints,
      questionTypes: config.questionTypes,
      questionCount: config.questionCount,
      difficultyDistribution: config.difficultyDistribution,
      extraRequirements: config.extraRequirements,
    } as any)

    visibleQuestions.value = result.questions
    ragReferences.value = result.ragReferences || []

    const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === config.courseId)
    const classOpt = step1Ref.value?.classOptions.find((c) => c.value === config.classId)
    savedConfig.value = {
      courseId: config.courseId,
      classId: config.classId,
      courseName: courseOpt?.label || '',
      className: classOpt?.label || '',
      title: config.title || `${courseOpt?.label || ''} - 专项练习`,
    }
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || e?.message || 'AI 服务暂不可用'
  } finally {
    generating.value = false
  }
}

// ===== 从题库选题 =====
function loadBankQuestions() {
  const courseId = step1Ref.value?.form?.courseId
  if (!courseId) return
  bankLoading.value = true
  fetchQuestionBank({ courseId, status: 'published' })
    .then((data) => { bankQuestions.value = data })
    .finally(() => { bankLoading.value = false })
}

function handleBankSelectionChange(rows: QuizQuestion[]) {
  bankSelectedIds.value = rows.map((r) => r.id)
}

function addFromBankToReview() {
  if (!bankSelectedIds.value.length) {
    ElMessage.warning('请从题库勾选题目')
    return
  }
  const selected = bankQuestions.value.filter((q) => bankSelectedIds.value.includes(q.id))
  visibleQuestions.value = selected.map((q) => ({ ...q }))
  ragReferences.value = []
  generating.value = false

  const form = step1Ref.value?.form
  if (form) {
    const courseOpt = step1Ref.value?.courseOptions.find((c) => c.value === form.courseId)
    const classOpt = step1Ref.value?.classOptions.find((c) => c.value === form.classId)
    savedConfig.value = {
      courseId: form.courseId!,
      classId: form.classId!,
      courseName: courseOpt?.label || '',
      className: classOpt?.label || '',
      title: form.title || `${courseOpt?.label || ''} - 题库组卷`,
    }
  }
  currentStep.value = 2
  ElMessage.success(`已选择 ${selected.length} 道题，进入审核`)
}

watch(() => step1Ref.value?.form?.courseId, () => {
  if (createMode.value === 'bank') loadBankQuestions()
})
watch(createMode, (mode) => {
  if (mode === 'bank') loadBankQuestions()
})

// ===== 保存 / 发布 =====
async function handleSaveDraft(questions: QuizQuestion[]) {
  if (!savedConfig.value) return
  await saveQuizAssignment({
    title: savedConfig.value.title,
    courseId: savedConfig.value.courseId,
    courseName: savedConfig.value.courseName,
    classId: savedConfig.value.classId,
    className: savedConfig.value.className,
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: Array.from(new Set(questions.map((q) => q.knowledgePoint).filter(Boolean))) as string[],
    status: 'draft',
    questions,
  })
  assignmentRefreshTrigger.value++
  ElMessage.success(`练习「${savedConfig.value.title}」已保存为草稿`)
}

async function handlePublish(questions: QuizQuestion[]) {
  if (!savedConfig.value) return
  const saved = await saveQuizAssignment({
    title: savedConfig.value.title,
    courseId: savedConfig.value.courseId,
    courseName: savedConfig.value.courseName,
    classId: savedConfig.value.classId,
    className: savedConfig.value.className,
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: Array.from(new Set(questions.map((q) => q.knowledgePoint).filter(Boolean))) as string[],
    status: 'draft',
    questions,
  })
  await publishQuizAssignment(saved.id)
  assignmentRefreshTrigger.value++
  resetWizard()
  ElMessage.success('练习已发布')
}

function resetWizard() {
  currentStep.value = 1
  visibleQuestions.value = []
  ragReferences.value = []
  genError.value = ''
  generating.value = false
  bankSelectedIds.value = []
}

function typeLabel(type: ExerciseType): string {
  return exerciseTypeLabels[type] || type
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
      <el-radio-group v-model="createMode" class="mode-toggle">
        <el-radio-button value="ai">AI 智能出题</el-radio-button>
        <el-radio-button value="bank">从题库选题</el-radio-button>
      </el-radio-group>

      <QuizWizardStep1Config ref="step1Ref" :loading="false" @generate="handleGenerate" />

      <div v-if="createMode === 'bank'" class="bank-select-section">
        <div class="bank-divider" />
        <el-table
          v-loading="bankLoading"
          :data="bankQuestions"
          max-height="360"
          size="small"
          @selection-change="handleBankSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column label="题干" prop="stem" show-overflow-tooltip />
          <el-table-column label="题型" width="80">
            <template #default="{ row }">{{ typeLabel(row.type) }}</template>
          </el-table-column>
          <el-table-column prop="knowledgePoint" label="知识点" width="120" />
          <el-table-column prop="difficulty" label="难度" width="80">
            <template #default="{ row }">{{ difficultyLabels[row.difficulty] || row.difficulty }}</template>
          </el-table-column>
        </el-table>
        <el-button type="primary" :icon="Collection" style="margin-top: 12px" @click="addFromBankToReview">
          进入审核（已选 {{ bankSelectedIds.length }}）
        </el-button>
      </div>
    </div>

    <!-- Step 2: 审核 -->
    <div v-else-if="currentStep === 2" class="wizard-content">
      <div class="step2-toolbar">
        <el-button :icon="Back" :disabled="generating" @click="currentStep = 1">返回配置</el-button>
      </div>

      <!-- 加载中 -->
      <div v-if="generating" class="loading-block">
        <el-icon class="loading-spin is-loading"><Loading /></el-icon>
        <p>AI 正在生成题目，预计 10-30 秒…</p>
      </div>

      <!-- 错误 -->
      <div v-else-if="genError" class="error-block">
        <p>{{ genError }}</p>
        <el-button type="primary" :icon="Back" @click="currentStep = 1">返回配置</el-button>
      </div>

      <!-- 审核列表 -->
      <QuizWizardStep3Review
        v-else-if="visibleQuestions.length"
        :questions="visibleQuestions"
        :rag-references="ragReferences"
        :course-id="savedConfig?.courseId"
        @save-draft="handleSaveDraft"
        @publish="handlePublish"
      />

      <el-empty v-else description="未生成有效题目，请返回重试" />
    </div>

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

  .mode-toggle {
    display: flex;
    justify-content: center;
    margin-bottom: 8px;
  }

  .bank-select-section {
    margin-top: 24px;
    .bank-divider { border-top: 1px dashed #e2e8f0; margin-bottom: 16px; }
  }

  .step2-toolbar {
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
