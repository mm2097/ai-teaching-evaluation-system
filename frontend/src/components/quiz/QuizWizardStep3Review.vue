<!--
  逐题审核 + 组卷发布（精简版）
  顶部：进度 + 全部接受
  左侧：题目卡片列表（watch props 支持流式追加）
  右侧：组卷摘要 + 发布
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import QuestionReviewCard from './QuestionReviewCard.vue'
import QuizPublishSummary from './QuizPublishSummary.vue'
import QuestionFormDialog from './QuestionFormDialog.vue'
import { addQuestionsToBank } from '@/api/questionBank'
import type { QuizQuestion, ReviewStatus, RagReference } from '@/types'

const props = defineProps<{
  questions: QuizQuestion[]
  ragReferences: RagReference[]
  courseId?: number
  generationPending?: boolean
  initialStatus?: ReviewStatus
}>()

const emit = defineEmits<{
  back: []
  saveDraft: [questions: QuizQuestion[]]
  publish: [questions: QuizQuestion[]]
}>()

/** 发布参数：透传给 QuizPublishSummary，并由父组件（QuizManageView）读取 */
const deadline = defineModel<string>('deadline', { default: '' })
const allowReview = defineModel<boolean>('allowReview', { default: false })

interface ReviewedItem {
  question: QuizQuestion
  status: ReviewStatus
  ragSimilarity: number
  ragSource: string
}

const reviewedItems = ref<ReviewedItem[]>([])

function buildReviewedItem(q: QuizQuestion): ReviewedItem {
  const ref = props.ragReferences.find(
    (r) => r.stem && q.stem && r.stem.substring(0, 20) === q.stem.substring(0, 20)
  )
  return {
    question: { ...q },
    status: (props.initialStatus || 'pending') as ReviewStatus,
    ragSimilarity: ref?.similarity ?? 0,
    ragSource: ref ? `题库#${ref.questionId}` : '',
  }
}

// 支持流式追加（保留已有审核状态）
watch(
  () => props.questions,
  (newQs, oldQs) => {
    if (!oldQs || newQs.length < oldQs.length) {
      reviewedItems.value = newQs.map(buildReviewedItem)
    } else if (newQs.length > oldQs.length) {
      for (let i = oldQs.length; i < newQs.length; i++) {
        const q = newQs[i]
        if (q) reviewedItems.value.push(buildReviewedItem(q))
      }
    }
  },
  { immediate: true },
)

const editVisible = ref(false)
const editingQuestion = ref<QuizQuestion | null>(null)
const editingIndex = ref(-1)

function acceptQuestion(idx: number) {
  const item = reviewedItems.value[idx]
  if (item) item.status = 'accepted'
}
function acceptAll() {
  let count = 0
  for (const item of reviewedItems.value) {
    if (item.status === 'pending') {
      item.status = 'accepted'
      count++
    }
  }
  ElMessage.success(count ? `已接受 ${count} 题` : '全部题目已审核')
}
function rejectQuestion(idx: number) {
  const item = reviewedItems.value[idx]
  if (item) item.status = 'rejected'
}
function editQuestion(idx: number) {
  const item = reviewedItems.value[idx]
  if (!item) return
  editingIndex.value = idx
  editingQuestion.value = { ...item.question }
  editVisible.value = true
}
function saveQuestionEdit(question: QuizQuestion) {
  const item = reviewedItems.value[editingIndex.value]
  if (item) {
    item.question = question
    item.status = 'edited'
    ElMessage.success('已更新')
  }
  editVisible.value = false
}

const acceptedQuestions = computed(() =>
  reviewedItems.value
    .filter((item) => item.status === 'accepted' || item.status === 'edited')
    .map((item) => item.question),
)

const pendingCount = computed(() =>
  reviewedItems.value.filter((item) => item.status === 'pending').length,
)

const acceptedCount = computed(() =>
  reviewedItems.value.filter((item) => item.status === 'accepted' || item.status === 'edited').length,
)

const knowledgePointOptions = computed(() => {
  const kps = new Set<string>()
  for (const item of reviewedItems.value) {
    if (item.question.knowledgePoint) kps.add(item.question.knowledgePoint)
  }
  return Array.from(kps)
})

function handleSaveDraft() {
  if (props.generationPending) {
    ElMessage.warning('AI 仍在生成题目，请等待生成完成后再保存')
    return
  }
  if (!acceptedQuestions.value.length) {
    ElMessage.warning('请至少接受一道题')
    return
  }
  emit('saveDraft', acceptedQuestions.value)
}

function handlePublish() {
  if (props.generationPending) {
    ElMessage.warning('AI 仍在生成题目，请等待生成完成后再发布')
    return
  }
  if (!acceptedQuestions.value.length) {
    ElMessage.warning('请至少接受一道题')
    return
  }
  emit('publish', acceptedQuestions.value)
}

const addingToBank = ref(false)
async function handleAddAllToBank() {
  if (props.generationPending) {
    ElMessage.warning('AI 仍在生成题目，请等待生成完成后再加入题库')
    return
  }
  if (!props.courseId || !acceptedQuestions.value.length) return
  addingToBank.value = true
  try {
    const questions = acceptedQuestions.value.map((q) => ({ ...q, courseId: props.courseId! }))
    const result = await addQuestionsToBank(questions, { source: 'ai' })
    ElMessage.success(`已加入题库 ${result.added} 道`)
  } finally {
    addingToBank.value = false
  }
}
</script>

<template>
  <div class="review-area">
    <el-row :gutter="16">
      <!-- 左侧题目 -->
      <el-col :span="16">
        <div class="review-bar">
          <div class="bar-left">
            <span class="bar-count">
              <b>{{ acceptedCount }}</b>/{{ reviewedItems.length }} 已接受
            </span>
            <span v-if="pendingCount" class="bar-pending">{{ pendingCount }} 待审</span>
          </div>
          <el-button type="success" size="small" plain :icon="Check" :disabled="!pendingCount" @click="acceptAll">
            全部接受
          </el-button>
        </div>

        <QuestionReviewCard
          v-for="(item, idx) in reviewedItems"
          :key="idx"
          :question="item.question"
          :index="idx"
          :status="item.status"
          :rag-similarity="item.ragSimilarity"
          :rag-source="item.ragSource"
          @accept="acceptQuestion(idx)"
          @reject="rejectQuestion(idx)"
          @edit="editQuestion(idx)"
          @regenerate="() => {}"
        />
      </el-col>

      <!-- 右侧摘要 -->
      <el-col :span="8">
        <div class="summary-sticky">
          <QuizPublishSummary
            :questions="reviewedItems"
            :generation-pending="props.generationPending"
            v-model:deadline="deadline"
            v-model:allow-review="allowReview"
            @save-draft="handleSaveDraft"
            @publish="handlePublish"
            @add-all-to-bank="handleAddAllToBank"
          />
        </div>
      </el-col>
    </el-row>

    <QuestionFormDialog
      v-model="editVisible"
      :question="editingQuestion"
      :knowledge-point-options="knowledgePointOptions"
      mode="edit"
      @save="saveQuestionEdit"
    />
  </div>
</template>

<style scoped lang="scss">
.review-area {
  .review-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding: 8px 12px;
    background: #f8fafc;
    border-radius: 8px;

    .bar-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .bar-count {
        font-size: 14px;
        color: #1e293b;

        b { color: #67c23a; font-size: 16px; }
      }
      .bar-pending {
        font-size: 12px;
        color: #94a3b8;
      }
    }
  }

  .summary-sticky {
    position: sticky;
    top: 16px;
  }
}
</style>
