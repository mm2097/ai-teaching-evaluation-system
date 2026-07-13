<!--
  错题本页面
  自动归集学生错题（教师布置 + 自主练习）并支持复习
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchErrorBook, type ErrorBookItem } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import { exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { ExerciseOption } from '@/types'

const userStore = useUserStore()
const loading = ref(true)
const kpFilter = ref('')
const errors = ref<ErrorBookItem[]>([])

const filteredErrors = computed(() => {
  if (!kpFilter.value) return errors.value
  return errors.value.filter((e) => e.knowledgePoint === kpFilter.value)
})

const kpStats = computed(() => {
  const map = new Map<string, number>()
  errors.value.forEach((e) => map.set(e.knowledgePoint, (map.get(e.knowledgePoint) || 0) + 1))
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

function formatOptions(options?: ExerciseOption[]): string[] {
  if (!options?.length) return []
  return options.map((o) => `${o.key}. ${o.text}`)
}

function formatAnswer(val: string | string[] | undefined): string {
  if (!val) return '(未答)'
  if (Array.isArray(val)) return val.join('、') || '(未答)'
  return val
}

onMounted(async () => {
  loading.value = true
  try {
    errors.value = await fetchErrorBook(userStore.userInfo?.studentId || 1)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card">
      <div class="content-card__title">错题知识点分布</div>
      <el-empty v-if="!kpStats.length" description="暂无错题，继续保持！" />
      <div v-else class="kp-stats">
        <div
          v-for="stat in kpStats"
          :key="stat.name"
          class="kp-stat-card"
          :class="{ active: kpFilter === stat.name }"
          @click="kpFilter = kpFilter === stat.name ? '' : stat.name"
        >
          <span class="kp-name">{{ stat.name }}</span>
          <span class="kp-count">{{ stat.count }} 题</span>
        </div>
      </div>
    </div>

    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">
        错题列表
        <el-tag v-if="kpFilter" size="small" closable @close="kpFilter = ''">筛选：{{ kpFilter }}</el-tag>
        <span class="count-tag">共 {{ filteredErrors.length }} 题</span>
      </div>

      <el-empty v-if="!filteredErrors.length" description="暂无错题记录，继续保持！" />

      <div
        v-for="(item, idx) in filteredErrors"
        :key="item.quizQuestion.id + '-' + idx"
        class="error-card"
      >
        <div class="error-header">
          <span class="error-num">第 {{ idx + 1 }} 题</span>
          <el-tag size="small">{{ exerciseTypeLabels[item.quizQuestion.type] }}</el-tag>
          <el-tag size="small" type="danger">{{ item.knowledgePoint }}</el-tag>
          <span class="error-time">{{ item.submitTime }}</span>
        </div>

        <p class="error-content">{{ item.quizQuestion.stem }}</p>

        <div v-if="item.quizQuestion.options?.length" class="error-options">
          <div
            v-for="(opt, i) in formatOptions(item.quizQuestion.options)"
            :key="i"
            class="error-option"
          >
            {{ opt }}
          </div>
        </div>

        <div class="error-answers">
          <div class="answer-row">
            <span class="label">你的答案：</span>
            <span class="value wrong">{{ formatAnswer(item.userAnswer) }}</span>
          </div>
          <div class="answer-row">
            <span class="label">正确答案：</span>
            <span class="value correct">{{ formatAnswer(item.correctAnswer) }}</span>
          </div>
        </div>

        <div v-if="item.quizQuestion.type === 'short_answer' && item.aiReason" class="ai-judge">
          <el-tag size="small" type="warning">AI 判分</el-tag>
          <span v-if="item.aiScore != null" class="ai-score">{{ item.aiScore }} / 10</span>
          <p class="ai-reason">{{ item.aiReason }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.kp-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.kp-stat-card {
  padding: 12px 20px;
  background: #f8fafc;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 12px;

  &:hover { border-color: #93c5fd; }

  &.active {
    border-color: #ef4444;
    background: #fef2f2;
  }

  .kp-name { font-weight: 500; }
  .kp-count { font-weight: 700; color: #ef4444; }
}

.count-tag {
  font-size: 13px;
  color: #64748b;
  font-weight: normal;
  margin-left: 8px;
}

.error-card {
  padding: 20px;
  border: 1px solid #fee2e2;
  border-radius: 10px;
  margin-bottom: 16px;
  background: #fef2f2;

  .error-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;

    .error-num { font-weight: 600; color: #ef4444; }
    .error-time { margin-left: auto; font-size: 12px; color: #94a3b8; }
  }

  .error-content { font-size: 15px; margin-bottom: 12px; line-height: 1.6; }

  .error-options {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
    padding-left: 16px;

    .error-option {
      font-size: 14px;
      padding: 8px 12px;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
      background: #fff;
    }
  }

  .error-answers {
    .answer-row { margin-bottom: 4px; font-size: 14px; }

    .label { color: #64748b; }

    .value.wrong { color: #ef4444; font-weight: 600; }
    .value.correct { color: #10b981; font-weight: 600; }
  }

  .ai-judge {
    margin-top: 10px;
    padding: 10px 12px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;

    .ai-score {
      margin-left: 8px;
      font-weight: 600;
      color: #d97706;
      font-size: 13px;
    }

    .ai-reason {
      font-size: 12px;
      color: #78350f;
      margin: 6px 0 0;
      line-height: 1.5;
    }
  }
}
</style>
