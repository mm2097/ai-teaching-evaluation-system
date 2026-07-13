<!--
  答题结果页
  展示答题得分、错题列表、对应知识点
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check, Close, Refresh } from '@element-plus/icons-vue'
import { fetchQuizResult } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import type { QuizQuestion } from '@/types'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)

interface QuestionResult {
  question: QuizQuestion
  userAnswer: string | string[]
  isCorrect: boolean
  aiScore?: number | null
  aiReason?: string
}

const submissionId = ref(Number(route.query.id) || 0)
const score = ref(0)
const totalScore = ref(0)
const questionResults = ref<QuestionResult[]>([])
const correctCount = ref(0)
const wrongCount = ref(0)

const accuracy = computed(() =>
  totalScore.value > 0 ? Math.round((score.value / totalScore.value) * 100) : 0,
)

const wrongQuestions = computed(() =>
  questionResults.value.filter((q) => !q.isCorrect),
)

/** 错误知识点统计 */
const wrongKnowledgePoints = computed(() => {
  const map = new Map<string, number>()
  for (const q of wrongQuestions.value) {
    const kp = q.question.knowledgePoint
    map.set(kp, (map.get(kp) || 0) + 1)
  }
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const typeLabel: Record<string, string> = {
  single: '单选题',
  single_choice: '单选题',
  multiple: '多选题',
  multi_choice: '多选题',
  fill: '填空题',
  fill_blank: '填空题',
  judge: '判断题',
  short: '简答题',
  short_answer: '简答题',
}

function getOptionLetter(idx: number): string {
  return String.fromCharCode(65 + idx)
}

onMounted(async () => {
  loading.value = true
  try {
    const result = await fetchQuizResult(
      submissionId.value,
      userStore.userInfo?.studentId || 1,
    )
    score.value = result.score
    totalScore.value = result.totalScore
    questionResults.value = result.questionResults
    correctCount.value = questionResults.value.filter((q) => q.isCorrect).length
    wrongCount.value = questionResults.value.length - correctCount.value
  } finally {
    loading.value = false
  }
})

function backToQuiz(): void {
  router.push('/quiz/answer')
}
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 分数概览 -->
    <div class="content-card result-hero">
      <div class="result-circle" :class="accuracy >= 80 ? 'good' : accuracy >= 60 ? 'ok' : 'bad'">
        <span class="result-num">{{ score }}</span>
        <span class="result-divider">/</span>
        <span class="result-total">{{ totalScore }}</span>
      </div>
      <div class="result-stats">
        <div class="stat-item">
          <el-icon :size="20" color="#10b981"><Check /></el-icon>
          <span>正确 {{ correctCount }} 题</span>
        </div>
        <div class="stat-item">
          <el-icon :size="20" color="#ef4444"><Close /></el-icon>
          <span>错误 {{ wrongCount }} 题</span>
        </div>
        <div class="stat-item">
          <span class="stat-percent">正确率 {{ accuracy }}%</span>
        </div>
      </div>
      <el-button :icon="Refresh" @click="backToQuiz">返回练习列表</el-button>
    </div>

    <!-- 错误知识点分析 -->
    <div v-if="wrongKnowledgePoints.length" class="content-card">
      <div class="content-card__title">需要加强的知识点</div>
      <div class="kp-tags">
        <el-tag
          v-for="kp in wrongKnowledgePoints"
          :key="kp.name"
          type="danger"
          effect="plain"
          size="large"
        >
          {{ kp.name }}（{{ kp.count }}题）
        </el-tag>
      </div>
    </div>

    <!-- 错题详情 -->
    <div v-if="wrongQuestions.length" class="content-card">
      <div class="content-card__title">
        错题回顾
        <span class="wrong-count">共 {{ wrongQuestions.length }} 题</span>
      </div>
      <div v-for="(item, idx) in wrongQuestions" :key="item.question.id" class="error-question">
        <div class="eq-header">
          <span class="eq-num">错题 {{ idx + 1 }}</span>
          <el-tag size="small">{{ typeLabel[item.question.type] }}</el-tag>
          <el-tag size="small" type="info">{{ item.question.knowledgePoint }}</el-tag>
        </div>
        <p class="eq-content">{{ item.question.stem }}</p>

        <!-- 选项 -->
        <div v-if="item.question.options" class="eq-options">
          <div
            v-for="(opt, i) in item.question.options"
            :key="i"
            class="eq-option"
            :class="{
              'is-correct': Array.isArray(item.question.answer)
                ? item.question.answer.includes(opt.key)
                : item.question.answer === opt.key,
              'is-wrong': Array.isArray(item.userAnswer)
                ? item.userAnswer.includes(opt.key) && (Array.isArray(item.question.answer) ? !item.question.answer.includes(opt.key) : item.question.answer !== opt.key)
                : item.userAnswer === opt.key && item.question.answer !== opt.key,
            }"
          >
            {{ getOptionLetter(i) }}. {{ opt.text }}
          </div>
        </div>

        <div class="eq-answers">
          <div class="eq-my-answer">
            <span class="label">你的答案：</span>
            <span class="value wrong">{{ Array.isArray(item.userAnswer) ? item.userAnswer.join('、') : item.userAnswer }}</span>
          </div>
          <div class="eq-correct-answer">
            <span class="label">正确答案：</span>
            <span class="value correct">{{ Array.isArray(item.question.answer) ? item.question.answer.join('、') : item.question.answer }}</span>
          </div>
          <!-- 简答题 AI 判分依据 -->
          <div v-if="item.question.type === 'short_answer' && item.aiReason" class="eq-ai-judge">
            <div class="eq-ai-header">
              <el-tag size="small" type="warning">AI 判分</el-tag>
              <span v-if="item.aiScore !== null && item.aiScore !== undefined" class="eq-ai-score">
                建议分：{{ item.aiScore }} / 10
              </span>
            </div>
            <p class="eq-ai-reason">{{ item.aiReason }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.result-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .result-circle {
    text-align: center;
    padding: 16px 28px;
    border-radius: 50%;
    width: 140px;
    height: 140px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border: 4px solid;

    &.good { border-color: #10b981; color: #10b981; }
    &.ok { border-color: #f59e0b; color: #f59e0b; }
    &.bad { border-color: #ef4444; color: #ef4444; }

    .result-num { font-size: 36px; font-weight: 700; line-height: 1; }
    .result-divider { font-size: 18px; opacity: 0.5; }
    .result-total { font-size: 20px; opacity: 0.7; }
  }

  .result-stats {
    display: flex;
    flex-direction: column;
    gap: 10px;

    .stat-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
    }

    .stat-percent {
      font-size: 20px;
      font-weight: 700;
      color: #2563eb;
    }
  }
}

.kp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.error-question {
  padding: 20px;
  border: 1px solid #fee2e2;
  border-radius: 10px;
  margin-bottom: 16px;
  background: #fef2f2;

  .eq-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;

    .eq-num { font-weight: 600; color: #ef4444; }
  }

  .eq-content { font-size: 15px; margin-bottom: 12px; line-height: 1.6; }

  .eq-options {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
    padding-left: 16px;

    .eq-option {
      font-size: 14px;
      padding: 8px 12px;
      border-radius: 6px;
      border: 1px solid #e2e8f0;

      &.is-correct {
        background: #ecfdf5;
        border-color: #6ee7b7;
        color: #065f46;
      }

      &.is-wrong {
        background: #fef2f2;
        border-color: #fca5a5;
        color: #991b1b;
      }
    }
  }

  .eq-answers {
    .eq-my-answer, .eq-correct-answer {
      margin-bottom: 4px;
      font-size: 14px;

      .label { color: #64748b; }

      .value.wrong { color: #ef4444; font-weight: 600; }
      .value.correct { color: #10b981; font-weight: 600; }
    }

    .eq-ai-judge {
      margin-top: 8px;
      padding: 8px 12px;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 6px;

      .eq-ai-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;

        .eq-ai-score {
          font-size: 13px;
          font-weight: 600;
          color: #d97706;
        }
      }

      .eq-ai-reason {
        font-size: 12px;
        color: #78350f;
        line-height: 1.5;
        margin: 0;
      }
    }
  }
}

.wrong-count {
  font-size: 13px;
  color: #ef4444;
  font-weight: normal;
  margin-left: 8px;
}
</style>
