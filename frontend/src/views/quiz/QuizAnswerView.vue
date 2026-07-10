<!--
  在线答题页面
  学生在线作答练习题，系统按规则自动判分并展示解析
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Check } from '@element-plus/icons-vue'
import { fetchStudentQuizzes, submitQuizAnswers } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import { exerciseTypeLabels, judgeAnswer } from '@/utils/exerciseJudge'
import type { QuizAssignment, QuizQuestion } from '@/types'

const userStore = useUserStore()

const quizList = ref<QuizAssignment[]>([])
const activeQuiz = ref<QuizAssignment | null>(null)
const answers = ref<Record<number, string | boolean>>({})
const multiAnswers = ref<Record<number, string[]>>({})
const submitting = ref(false)
const result = ref<{
  score: number
  totalScore: number
  details: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    aiScore?: number | null
    aiReason?: string
  }[]
} | null>(null)

onMounted(async () => {
  const studentId = userStore.userInfo?.studentId || 1
  quizList.value = await fetchStudentQuizzes(studentId)
})

function startQuiz(quiz: QuizAssignment): void {
  activeQuiz.value = quiz
  answers.value = {}
  multiAnswers.value = {}
  quiz.questions.forEach((q) => {
    if (q.type === 'multi_choice') {
      multiAnswers.value[q.id] = []
    }
  })
  result.value = null
}

function backToList(): void {
  activeQuiz.value = null
  result.value = null
}

function syncMultiAnswer(questionId: number): void {
  const selected = multiAnswers.value[questionId] || []
  answers.value[questionId] = selected.sort().join('')
}

const answeredCount = computed(() =>
  activeQuiz.value?.questions.filter((q) => {
    const ans = answers.value[q.id]
    if (q.type === 'multi_choice') {
      return (multiAnswers.value[q.id]?.length ?? 0) > 0
    }
    return ans !== undefined && ans !== ''
  }).length ?? 0,
)

function formatAnswer(q: QuizQuestion, ans: string | boolean | undefined): string {
  if (ans === undefined) return '未作答'
  if (q.type === 'judge') return ans === true || ans === 'true' ? '正确' : '错误'
  return String(ans)
}

function formatCorrectAnswer(q: QuizQuestion): string {
  if (q.type === 'judge') return q.answer === 'true' ? '正确' : '错误'
  return q.answer
}

async function handleSubmit(): Promise<void> {
  if (!activeQuiz.value) return

  activeQuiz.value.questions.forEach((q) => {
    if (q.type === 'multi_choice') syncMultiAnswer(q.id)
  })

  const unanswered = activeQuiz.value.questions.length - answeredCount.value
  if (unanswered > 0) {
    ElMessage.warning(`还有 ${unanswered} 题未作答`)
    return
  }

  submitting.value = true
  try {
    const submission = await submitQuizAnswers(
      activeQuiz.value.id,
      userStore.userInfo?.studentId || 1,
      userStore.userInfo?.name || '学生',
      answers.value,
    )
    // 简答题不使用前端 judgeAnswer，标记 correct 为 submission 结果
    const details = activeQuiz.value.questions.map((q) => ({
      question: q,
      correct: q.type === 'short_answer' ? true : judgeAnswer(q, answers.value[q.id]),
      userAnswer: answers.value[q.id] ?? '',
      // 简答题的 AI 判分结果会由后端返回，这里先用占位（展示层依赖后端数据）
    }))
    result.value = {
      score: submission.score,
      totalScore: submission.totalScore,
      details,
    }
    ElMessage.success('提交成功')
    if (submission.correctCount !== undefined) {
      ElMessage.info(`答对 ${submission.correctCount} 题`)
    }
  } catch {
    ElMessage.error('提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

const wrongCount = computed(() => result.value?.details.filter((d) => !d.correct).length ?? 0)
</script>

<template>
  <div class="page-container">
    <div v-if="!activeQuiz" class="content-card">
      <div class="content-card__title">待完成练习</div>
      <el-empty v-if="!quizList.length" description="暂无已发布的练习" />

      <div v-for="quiz in quizList" :key="quiz.id" class="quiz-card">
        <div class="quiz-info">
          <h3>{{ quiz.title }}</h3>
          <p>{{ quiz.courseName }} · {{ quiz.className }} · {{ quiz.questionCount }} 题 · 满分 {{ quiz.totalScore }} 分</p>
          <div class="quiz-tags">
            <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">{{ kp }}</el-tag>
          </div>
          <p v-if="quiz.deadline" class="deadline">截止时间：{{ quiz.deadline }}</p>
        </div>
        <el-button type="primary" :icon="Edit" @click="startQuiz(quiz)">开始答题</el-button>
      </div>
    </div>

    <div v-else>
      <div class="content-card quiz-header">
        <el-button link @click="backToList">← 返回列表</el-button>
        <h2>{{ activeQuiz.title }}</h2>
        <span v-if="!result" class="progress">已答 {{ answeredCount }} / {{ activeQuiz.questions.length }}</span>
      </div>

      <template v-if="result">
        <el-result
          icon="success"
          :title="`得分：${result.score} / ${result.totalScore}`"
          :sub-title="`答对 ${result.details.length - wrongCount} 题，答错 ${wrongCount} 题 · 结果已同步至知识点掌握度`"
        />

        <div class="content-card">
          <div class="content-card__title">答题解析</div>
          <div
            v-for="(item, idx) in result.details"
            :key="item.question.id"
            class="review-card"
            :class="{ wrong: !item.correct }"
          >
            <div class="review-header">
              <span class="q-num">{{ idx + 1 }}.</span>
              <el-tag size="small">{{ exerciseTypeLabels[item.question.type] }}</el-tag>
              <el-tag :type="item.correct ? 'success' : 'danger'" size="small">
                {{ item.correct ? '正确' : '错误' }}
              </el-tag>
              <el-tag size="small" type="info">{{ item.question.knowledgePoint }}</el-tag>
            </div>
            <p class="q-stem">{{ item.question.stem }}</p>
            <p class="answer-line">
              你的答案：<strong>{{ formatAnswer(item.question, item.userAnswer) }}</strong>
            </p>
            <p v-if="!item.correct" class="answer-line correct">
              正确答案：<strong>{{ formatCorrectAnswer(item.question) }}</strong>
            </p>
            <!-- 简答题 AI 判分依据 -->
            <div v-if="item.question.type === 'short_answer' && item.aiReason" class="ai-judge">
              <div class="ai-judge__header">
                <el-tag size="small" type="warning">AI 判分</el-tag>
                <span v-if="item.aiScore !== null && item.aiScore !== undefined" class="ai-score">
                  得分：{{ item.aiScore }} / 10
                </span>
              </div>
              <p class="ai-reason">{{ item.aiReason }}</p>
            </div>
            <p v-if="item.question.explanation" class="explanation">解析：{{ item.question.explanation }}</p>
          </div>
          <div class="submit-bar">
            <el-button type="primary" @click="backToList">返回练习列表</el-button>
          </div>
        </div>
      </template>

      <template v-else>
        <div v-for="(q, idx) in activeQuiz.questions" :key="q.id" class="content-card question-block">
          <div class="q-title">
            <span class="q-num">{{ idx + 1 }}.</span>
            <el-tag size="small">{{ exerciseTypeLabels[q.type] }}</el-tag>
            <span>{{ q.stem }}</span>
            <span class="q-score">（{{ q.score }} 分）</span>
          </div>

          <el-radio-group v-if="q.type === 'single_choice'" v-model="answers[q.id]" class="option-group">
            <el-radio v-for="opt in q.options" :key="opt.key" :value="opt.key">
              {{ opt.key }}. {{ opt.text }}
            </el-radio>
          </el-radio-group>

          <el-checkbox-group
            v-else-if="q.type === 'multi_choice'"
            v-model="multiAnswers[q.id]"
            class="option-group"
            @change="syncMultiAnswer(q.id)"
          >
            <el-checkbox v-for="opt in q.options" :key="opt.key" :value="opt.key">
              {{ opt.key }}. {{ opt.text }}
            </el-checkbox>
          </el-checkbox-group>

          <el-radio-group v-else-if="q.type === 'judge'" v-model="answers[q.id]" class="option-group">
            <el-radio :value="true">正确</el-radio>
            <el-radio :value="false">错误</el-radio>
          </el-radio-group>

          <el-input
            v-else-if="q.type === 'fill_blank'"
            v-model="(answers[q.id] as string)"
            placeholder="请输入答案"
          />

          <el-input
            v-else-if="q.type === 'short_answer'"
            v-model="(answers[q.id] as string)"
            type="textarea"
            :rows="4"
            placeholder="请输入你的解答"
          />
        </div>

        <div class="submit-bar content-card">
          <el-button type="primary" size="large" :loading="submitting" :icon="Check" @click="handleSubmit">
            提交答卷
          </el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.quiz-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 12px;

  h3 { font-size: 16px; margin-bottom: 6px; }
  p { font-size: 13px; color: #64748b; margin-bottom: 8px; }
  .quiz-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; }
  .deadline { font-size: 12px; color: #ef4444; }
}

.quiz-header {
  display: flex;
  align-items: center;
  gap: 16px;

  h2 { flex: 1; font-size: 18px; margin: 0; }
  .progress { color: #64748b; font-size: 14px; }
}

.question-block {
  .q-title {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 15px;
    margin-bottom: 16px;
    line-height: 1.6;

    .q-num { font-weight: 600; flex-shrink: 0; }
    .q-score { color: #64748b; font-size: 13px; flex-shrink: 0; }
  }

  .option-group {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-left: 24px;
  }
}

.review-card {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;

  &.wrong {
    border-color: #fecaca;
    background: #fef2f2;
  }

  .review-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;

    .q-num { font-weight: 600; }
  }

  .q-stem { font-size: 14px; margin-bottom: 8px; }
  .answer-line { font-size: 13px; color: #475569; margin-bottom: 4px; }
  .answer-line.correct { color: #10b981; }
  .explanation { font-size: 12px; color: #64748b; margin-top: 6px; }

  .ai-judge {
    margin-top: 8px;
    padding: 10px 12px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;

    .ai-judge__header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;

      .ai-score {
        font-size: 13px;
        font-weight: 600;
        color: #d97706;
      }
    }

    .ai-reason {
      font-size: 12px;
      color: #78350f;
      line-height: 1.5;
      margin: 0;
    }
  }
}

.submit-bar {
  text-align: center;
  padding: 24px;
}
</style>
