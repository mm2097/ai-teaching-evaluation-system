<!--
  组卷摘要：题型分布 + 知识点覆盖 + 难度分布 + 发布按钮
-->
<script setup lang="ts">
import { computed } from 'vue'
import { Promotion, FolderAdd, EditPen } from '@element-plus/icons-vue'
import { exerciseTypeLabels, difficultyLabels } from '@/utils/exerciseJudge'
import type { ExerciseType, DifficultyLevel, QuizQuestion, ReviewStatus } from '@/types'

interface ReviewedQuestion {
  question: QuizQuestion
  status: ReviewStatus
}

const props = defineProps<{
  questions: ReviewedQuestion[]
  meta?: { model: string; elapsedMs: number } | null
  generationPending?: boolean
}>()

const emit = defineEmits<{
  saveDraft: []
  publish: []
  addAllToBank: []
}>()

/** 发布参数：截止时间（留空默认7天）、是否允许学生交卷后查看详情 */
const deadline = defineModel<string>('deadline', { default: '' })
const allowReview = defineModel<boolean>('allowReview', { default: false })

const acceptedQuestions = computed(() =>
  props.questions.filter((q) => q.status === 'accepted' || q.status === 'edited')
)

const acceptedCount = computed(() => acceptedQuestions.value.length)
const pendingCount = computed(() => props.questions.filter((q) => q.status === 'pending').length)
const rejectedCount = computed(() => props.questions.filter((q) => q.status === 'rejected').length)
const reviewProgress = computed(() => {
  if (!props.questions.length) return 0
  const reviewed = props.questions.length - pendingCount.value
  return Math.round((reviewed / props.questions.length) * 100)
})

const typeDistribution = computed(() => {
  const dist: Record<string, number> = {}
  for (const q of acceptedQuestions.value) {
    const t = q.question.type
    dist[t] = (dist[t] || 0) + 1
  }
  return dist
})

const difficultyDistribution = computed(() => {
  const dist: Record<string, number> = { easy: 0, medium: 0, hard: 0 }
  for (const q of acceptedQuestions.value) {
    dist[q.question.difficulty] = (dist[q.question.difficulty] || 0) + 1
  }
  return dist
})

const knowledgeCoverage = computed(() => {
  const kps = new Set<string>()
  for (const q of acceptedQuestions.value) {
    if (q.question.knowledgePoint) kps.add(q.question.knowledgePoint)
  }
  return Array.from(kps)
})

const totalScore = computed(() =>
  acceptedQuestions.value.reduce((sum, q) => sum + q.question.score, 0)
)

const difficultyColor: Record<DifficultyLevel, string> = {
  easy: '#67c23a',
  medium: '#e6a23c',
  hard: '#f56c6c',
}
</script>

<template>
  <div class="publish-summary">
    <div class="summary-header">
      <span class="summary-title">组卷摘要</span>
    </div>

    <!-- 审核进度条 -->
    <div class="review-progress">
      <div class="progress-labels">
        <span>审核进度</span>
        <span>{{ props.questions.length - pendingCount }}/{{ props.questions.length }}</span>
      </div>
      <el-progress :percentage="reviewProgress" :stroke-width="8" />
      <div class="status-summary">
        <el-tag size="small" type="success">已接受 {{ acceptedCount }}</el-tag>
        <el-tag size="small" type="info">已拒绝 {{ rejectedCount }}</el-tag>
        <el-tag size="small" type="warning" v-if="pendingCount">待审核 {{ pendingCount }}</el-tag>
      </div>
    </div>

    <!-- 题型分布 -->
    <div class="summary-section" v-if="acceptedCount">
      <div class="section-title">题型分布</div>
      <div class="distribution-tags">
        <el-tag
          v-for="(count, type) in typeDistribution"
          :key="type"
          size="small"
          type="primary"
        >
          {{ exerciseTypeLabels[type as ExerciseType] }}: {{ count }} 题
        </el-tag>
      </div>
    </div>

    <!-- 难度分布 -->
    <div class="summary-section" v-if="acceptedCount">
      <div class="section-title">难度分布</div>
      <div class="difficulty-bar">
        <div
          v-for="diff in ['easy', 'medium', 'hard'] as DifficultyLevel[]"
          :key="diff"
          class="diff-item"
          :style="{ opacity: difficultyDistribution[diff] ? 1 : 0.3 }"
        >
          <div class="diff-dot" :style="{ background: difficultyColor[diff] }" />
          <span>{{ difficultyLabels[diff] }}</span>
          <span class="diff-count">{{ difficultyDistribution[diff] }} 题</span>
        </div>
      </div>
    </div>

    <!-- 知识点覆盖 -->
    <div class="summary-section" v-if="knowledgeCoverage.length">
      <div class="section-title">知识点覆盖（{{ knowledgeCoverage.length }} 个）</div>
      <div class="kp-tags">
        <el-tag v-for="kp in knowledgeCoverage" :key="kp" size="small" type="info">
          {{ kp }}
        </el-tag>
      </div>
    </div>

    <!-- 总分 -->
    <div class="summary-section" v-if="acceptedCount">
      <div class="section-title">总分</div>
      <span class="total-score">{{ totalScore.toFixed(1) }} 分</span>
    </div>

    <!-- 发布设置 -->
    <div class="summary-section publish-options">
      <div class="section-title">发布设置</div>
      <div class="option-row">
        <span class="option-label">截止时间</span>
        <el-date-picker
          v-model="deadline"
          type="datetime"
          placeholder="留空默认7天后"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DD HH:mm"
          size="small"
          style="width: 100%"
        />
      </div>
      <div class="option-row">
        <span class="option-label">查看权限</span>
        <el-switch
          v-model="allowReview"
          active-text="允许查看详情"
          inactive-text="禁止查看详情"
          inline-prompt
        />
      </div>
      <el-text type="info" size="small">学生交卷后能否查看题目及答案解析</el-text>
    </div>

    <el-alert
      v-if="props.generationPending"
      title="AI is still generating questions. Save and publish will be available when generation finishes."
      type="info"
      :closable="false"
      show-icon
      class="pending-alert"
    />

    <!-- 操作按钮 -->
    <div class="summary-actions">
      <el-button
        type="warning"
        plain
        :icon="FolderAdd"
        :disabled="props.generationPending || !acceptedCount"
        @click="emit('addAllToBank')"
      >
        全部加入题库
      </el-button>
      <el-button
        :icon="EditPen"
        :disabled="props.generationPending || !acceptedCount"
        @click="emit('saveDraft')"
      >
        保存草稿
      </el-button>
      <el-button
        type="success"
        :icon="Promotion"
        :disabled="props.generationPending || !acceptedCount"
        @click="emit('publish')"
      >
        发布给班级（{{ acceptedCount }} 题）
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.publish-summary {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fafbfc;

  .summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    .summary-title {
      font-weight: 600;
      font-size: 14px;
      color: #1e293b;
    }
  }

  .review-progress {
    margin-bottom: 16px;

    .progress-labels {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #64748b;
      margin-bottom: 4px;
    }

    .status-summary {
      display: flex;
      gap: 6px;
      margin-top: 6px;
    }
  }

  .summary-section {
    margin-bottom: 12px;

    .section-title {
      font-size: 12px;
      color: #64748b;
      margin-bottom: 6px;
    }

    .distribution-tags, .kp-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .difficulty-bar {
      display: flex;
      gap: 16px;

      .diff-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #475569;

        .diff-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .diff-count { color: #94a3b8; }
      }
    }

    .total-score {
      font-size: 18px;
      font-weight: 700;
      color: #2563eb;
    }
  }

  .publish-options {
    padding: 12px;
    background: #f0f5ff;
    border-radius: 6px;

    .option-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;

      .option-label {
        font-size: 12px;
        color: #475569;
        flex-shrink: 0;
        width: 60px;
      }
    }
  }

  .summary-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;
  }
}
</style>
