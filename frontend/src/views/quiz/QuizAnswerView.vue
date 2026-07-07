<!--
  在线答题页面
  学生在线作答 AI 练习题，系统自动判分
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Check } from '@element-plus/icons-vue'
import { fetchStudentQuizzes, submitQuizAnswers } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment, QuizQuestion } from '@/types'

const userStore = useUserStore()

const quizList = ref<QuizAssignment[]>([])
const activeQuiz = ref<QuizAssignment | null>(null)
const answers = ref<Record<number, string | string[]>>({})
const submitting = ref(false)
const result = ref<{ score: number; totalScore: number } | null>(null)

onMounted(async () => {
  const studentId = userStore.userInfo?.studentId || 1
  quizList.value = await fetchStudentQuizzes(studentId)
})

const typeLabel: Record<string, string> = {
  single: '单选题',
  multiple: '多选题',
  fill: '填空题',
  short: '简答题',
}

function startQuiz(quiz: QuizAssignment): void {
  activeQuiz.value = quiz
  answers.value = {}
  result.value = null
}

function backToList(): void {
  activeQuiz.value = null
  result.value = null
}

const answeredCount = computed(() =>
  activeQuiz.value?.questions.filter((q) => {
    const ans = answers.value[q.id]
    return ans !== undefined && ans !== '' && !(Array.isArray(ans) && ans.length === 0)
  }).length ?? 0,
)

async function handleSubmit(): Promise<void> {
  if (!activeQuiz.value) return
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
    result.value = { score: submission.score, totalScore: submission.totalScore }
    ElMessage.success('提交成功，知识点掌握度已同步更新')
  } finally {
    submitting.value = false
  }
}

function getOptionLetter(idx: number): string {
  return String.fromCharCode(65 + idx)
}
</script>

<template>
  <div class="page-container">
    <!-- 练习列表 -->
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

    <!-- 答题区 -->
    <div v-else>
      <div class="content-card quiz-header">
        <el-button link @click="backToList">← 返回列表</el-button>
        <h2>{{ activeQuiz.title }}</h2>
        <span class="progress">已答 {{ answeredCount }} / {{ activeQuiz.questions.length }}</span>
      </div>

      <!-- 提交结果 -->
      <el-result
        v-if="result"
        icon="success"
        :title="`得分：${result.score} / ${result.totalScore}`"
        sub-title="答题结果已同步至知识点掌握度分析"
      >
        <template #extra>
          <el-button type="primary" @click="backToList">返回练习列表</el-button>
        </template>
      </el-result>

      <template v-else>
        <div v-for="(q, idx) in activeQuiz.questions" :key="q.id" class="content-card question-block">
          <div class="q-title">
            <span class="q-num">{{ idx + 1 }}.</span>
            <el-tag size="small">{{ typeLabel[q.type] }}</el-tag>
            <span>{{ q.content }}</span>
            <span class="q-score">（{{ q.score }} 分）</span>
          </div>

          <!-- 单选 -->
          <el-radio-group v-if="q.type === 'single'" v-model="answers[q.id]" class="option-group">
            <el-radio v-for="(opt, i) in q.options" :key="i" :value="opt">
              {{ getOptionLetter(i) }}. {{ opt }}
            </el-radio>
          </el-radio-group>

          <!-- 多选 -->
          <el-checkbox-group v-else-if="q.type === 'multiple'" v-model="(answers[q.id] as string[])" class="option-group">
            <el-checkbox v-for="(opt, i) in q.options" :key="i" :value="opt">
              {{ getOptionLetter(i) }}. {{ opt }}
            </el-checkbox>
          </el-checkbox-group>

          <!-- 填空 / 简答 -->
          <el-input
            v-else
            v-model="(answers[q.id] as string)"
            :type="q.type === 'short' ? 'textarea' : 'text'"
            :rows="q.type === 'short' ? 3 : 1"
            placeholder="请输入答案"
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

.submit-bar {
  text-align: center;
  padding: 24px;
}
</style>
