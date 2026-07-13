<!--
  单题审核卡片（精简版）
  干净的卡片：题号+标签 → 题干 → 选项 → 可折叠答案/解析
  操作：点击卡片右侧开关切换接受/拒绝，编辑图标打开弹窗
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { Check, Close, Edit, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { DifficultyLevel, ExerciseType, QuizQuestion, ReviewStatus } from '@/types'

const props = defineProps<{
  question: QuizQuestion
  index: number
  status: ReviewStatus
  ragSimilarity?: number
  ragSource?: string
}>()

const emit = defineEmits<{
  accept: []
  reject: []
  edit: []
  regenerate: []
}>()

const expanded = ref(false)

const difficultyTag = computed(() => {
  const map: Record<DifficultyLevel, { type: string; icon: string }> = {
    easy: { type: 'success', icon: '▲' },
    medium: { type: 'warning', icon: '◆' },
    hard: { type: 'danger', icon: '★' },
  }
  return map[props.question.difficulty] || map.medium
})

const cardBorderClass = computed(() => {
  const map: Record<ReviewStatus, string> = {
    accepted: 'border-accepted',
    rejected: 'border-rejected',
    pending: '',
    edited: 'border-edited',
  }
  return map[props.status]
})

const statusLabel = computed(() => {
  const map: Record<ReviewStatus, string> = {
    accepted: '已接受',
    rejected: '已拒绝',
    pending: '待审核',
    edited: '已编辑',
  }
  return map[props.status]
})

const statusColor = computed(() => {
  const map: Record<ReviewStatus, string> = {
    accepted: '#67c23a',
    rejected: '#c0c4cc',
    pending: '#409eff',
    edited: '#e6a23c',
  }
  return map[props.status]
})
</script>

<template>
  <div class="q-card" :class="cardBorderClass">
    <!-- 标题行 -->
    <div class="q-head">
      <span class="q-index">{{ index + 1 }}</span>
      <el-tag size="small" effect="plain">{{ exerciseTypeLabels[question.type as ExerciseType] }}</el-tag>
      <el-tag size="small" :type="difficultyTag.type as any" effect="light">
        {{ difficultyLabels[question.difficulty] }}
      </el-tag>
      <el-tag v-if="question.knowledgePoint" size="small" type="info" effect="plain">
        {{ question.knowledgePoint }}
      </el-tag>
      <span class="q-status" :style="{ color: statusColor }">{{ statusLabel }}</span>
    </div>

    <!-- 题干 -->
    <p class="q-stem">{{ question.stem }}</p>

    <!-- 选项 -->
    <div v-if="question.options?.length" class="q-options">
      <span v-for="opt in question.options" :key="opt.key" class="q-opt">
        <b>{{ opt.key }}.</b> {{ opt.text }}
      </span>
    </div>

    <!-- 答案 + 解析（折叠） -->
    <div class="q-detail-toggle" @click="expanded = !expanded">
      {{ expanded ? '收起' : '查看答案与解析' }}
      <el-icon><ArrowUp v-if="expanded" /><ArrowDown v-else /></el-icon>
    </div>
    <transition name="expand">
      <div v-show="expanded" class="q-detail">
        <p><b>答案：</b><span class="q-answer">{{ question.answer }}</span></p>
        <p v-if="question.explanation"><b>解析：</b>{{ question.explanation }}</p>
      </div>
    </transition>

    <!-- 操作按钮 -->
    <div class="q-actions">
      <el-button
        size="small"
        type="success"
        :plain="status !== 'accepted'"
        :icon="Check"
        @click="emit('accept')"
      >
        接受
      </el-button>
      <el-button
        size="small"
        type="danger"
        :plain="status !== 'rejected'"
        :icon="Close"
        @click="emit('reject')"
      >
        拒绝
      </el-button>
      <el-button size="small" text :icon="Edit" @click="emit('edit')">编辑</el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.q-card {
  padding: 14px 16px;
  border: 1px solid #e8eaed;
  border-radius: 10px;
  margin-bottom: 10px;
  transition: all 0.25s;
  background: #fff;

  &:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); }

  &.border-accepted { border-color: #b3e19d; background: #f0f9eb; }
  &.border-rejected { opacity: 0.45; }
  &.border-edited { border-color: #f3d19e; background: #fdf6ec; }

  .q-head {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;

    .q-index {
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 600;
      color: #64748b;
      background: #f1f5f9;
      border-radius: 6px;
    }

    .q-status {
      margin-left: auto;
      font-size: 12px;
      font-weight: 500;
    }
  }

  .q-stem {
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 8px;
    color: #1e293b;
  }

  .q-options {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 8px;
    padding-left: 4px;

    .q-opt {
      font-size: 13px;
      color: #475569;
    }
  }

  .q-detail-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #64748b;
    cursor: pointer;
    padding: 2px 0;
    user-select: none;

    &:hover { color: #409eff; }
  }

  .q-detail {
    margin-top: 8px;
    padding: 8px 12px;
    background: #f8fafc;
    border-radius: 6px;
    font-size: 13px;
    color: #475569;
    line-height: 1.5;

    p { margin: 0 0 4px; }
    p:last-child { margin: 0; }
    .q-answer { color: #16a34a; font-weight: 600; }
  }

  .q-actions {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #f5f5f5;
  }
}

.expand-enter-active, .expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.expand-enter-from, .expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
