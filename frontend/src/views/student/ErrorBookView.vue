<!--
  错题本页面
  自动归集学生错题并支持复习
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchErrorBook } from '@/api/quiz'
import { searchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(true)
const kpFilter = ref('')

interface ErrorItem {
  quizQuestion: { id: number; type: string; content: string; options?: string[]; answer: string | string[]; knowledgePoint: string; score: number }
  userAnswer: string | string[]
  correctAnswer: string | string[]
  submitTime: string
  knowledgePoint: string
}

const errors = ref<ErrorItem[]>([])

const knowledgePointOptions = computed(() =>
  [...new Set(errors.value.map((e) => e.knowledgePoint))],
)

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

const typeLabel: Record<string, string> = {
  single: '单选',
  multiple: '多选',
  fill: '填空',
  short: '简答',
}

function getOptionLetter(idx: number): string {
  return String.fromCharCode(65 + idx)
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
    <!-- 知识点统计 -->
    <div class="content-card">
      <div class="content-card__title">错题知识点分布</div>
      <div class="kp-stats">
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

    <!-- 错题列表 -->
    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">
        错题列表
        <el-tag v-if="kpFilter" size="small" closable @close="kpFilter = ''">筛选：{{ kpFilter }}</el-tag>
        <span class="count-tag">共 {{ filteredErrors.length }} 题</span>
      </div>

      <el-empty v-if="!filteredErrors.length" description="暂无错题记录，继续保持！" />

      <div v-for="(item, idx) in filteredErrors" :key="item.quizQuestion.id + '-' + idx" class="error-card">
        <div class="error-header">
          <span class="error-num">第 {{ idx + 1 }} 题</span>
          <el-tag size="small">{{ typeLabel[item.quizQuestion.type] }}</el-tag>
          <el-tag size="small" type="danger">{{ item.knowledgePoint }}</el-tag>
          <span class="error-time">{{ item.submitTime }}</span>
        </div>

        <p class="error-content">{{ item.quizQuestion.content }}</p>

        <div v-if="item.quizQuestion.options" class="error-options">
          <div
            v-for="(opt, i) in item.quizQuestion.options"
            :key="i"
            class="error-option"
            :class="{
              'is-correct': Array.isArray(item.correctAnswer)
                ? item.correctAnswer.includes(opt)
                : item.correctAnswer === opt,
              'is-wrong': Array.isArray(item.userAnswer)
                ? item.userAnswer.includes(opt) && !(Array.isArray(item.correctAnswer) ? item.correctAnswer.includes(opt) : item.correctAnswer === opt)
                : item.userAnswer === opt && item.correctAnswer !== opt,
            }"
          >
            {{ getOptionLetter(i) }}. {{ opt }}
          </div>
        </div>

        <div class="error-answers">
          <div class="answer-row">
            <span class="label">你的答案：</span>
            <span class="value wrong">{{ Array.isArray(item.userAnswer) ? item.userAnswer.join('、') || '(未答)' : item.userAnswer || '(未答)' }}</span>
          </div>
          <div class="answer-row">
            <span class="label">正确答案：</span>
            <span class="value correct">{{ Array.isArray(item.correctAnswer) ? item.correctAnswer.join('、') : item.correctAnswer }}</span>
          </div>
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

      &.is-correct { background: #ecfdf5; border-color: #6ee7b7; color: #065f46; }
      &.is-wrong { background: #ffe4e4; border-color: #fca5a5; color: #991b1b; }
    }
  }

  .error-answers {
    .answer-row { margin-bottom: 4px; font-size: 14px; }

    .label { color: #64748b; }

    .value.wrong { color: #ef4444; font-weight: 600; }
    .value.correct { color: #10b981; font-weight: 600; }
  }
}
</style>
