<!--
  在线答题页面
  学生可作答教师布置练习，也可通过 AI 自主出题自学
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Check, MagicStick } from '@element-plus/icons-vue'
import {
  fetchStudentQuizzes,
  submitQuizAnswers,
  submitSelfQuiz,
  generateQuizQuestions,
} from '@/api/quiz'
import { fetchCourses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import { difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { DifficultyLevel, ExerciseType, QuizAssignment, QuizQuestion } from '@/types'

const userStore = useUserStore()

/** 列表 Tab：教师布置 / 自主练习 */
const listTab = ref<'assigned' | 'self'>('assigned')

/** 教师布置练习 */
const quizList = ref<QuizAssignment[]>([])
const activeQuiz = ref<QuizAssignment | null>(null)
const quizMode = ref<'assigned' | 'self'>('assigned')

/** 自主练习配置 */
const courseOptions = ref<{ label: string; value: number }[]>([])
const selfForm = ref({
  courseId: undefined as number | undefined,
  knowledgePoints: [] as string[],
  questionTypes: ['single_choice', 'multi_choice', 'judge', 'fill_blank'] as ExerciseType[],
  questionCount: 5,
  difficulty: 'medium' as DifficultyLevel,
  extraRequirements: '',
})
const generating = ref(false)
const generateMeta = ref<{ model: string; elapsedMs: number } | null>(null)

/** 作答状态 */
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

const questionTypeOptions = [
  { label: exerciseTypeLabels.single_choice, value: 'single_choice' as ExerciseType },
  { label: exerciseTypeLabels.multi_choice, value: 'multi_choice' as ExerciseType },
  { label: exerciseTypeLabels.judge, value: 'judge' as ExerciseType },
  { label: exerciseTypeLabels.fill_blank, value: 'fill_blank' as ExerciseType },
  { label: exerciseTypeLabels.short_answer, value: 'short_answer' as ExerciseType },
]

const difficultyOptions = [
  { label: difficultyLabels.easy, value: 'easy' as DifficultyLevel },
  { label: difficultyLabels.medium, value: 'medium' as DifficultyLevel },
  { label: difficultyLabels.hard, value: 'hard' as DifficultyLevel },
]

onMounted(async () => {
  const studentId = userStore.userInfo?.studentId || 1
  quizList.value = (await fetchStudentQuizzes(studentId)) as QuizAssignment[]

  const courses = await fetchCourses({ deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) {
    selfForm.value.courseId = courseOptions.value[0]!.value
  }
})

function initAnswers(questions: QuizQuestion[]): void {
  answers.value = {}
  multiAnswers.value = {}
  questions.forEach((q) => {
    if (q.type === 'multi_choice') {
      multiAnswers.value[q.id] = []
    }
  })
}

function startQuiz(quiz: QuizAssignment): void {
  activeQuiz.value = quiz
  quizMode.value = 'assigned'
  initAnswers(quiz.questions)
  result.value = null
}

async function handleGenerateSelfQuiz(): Promise<void> {
  if (!selfForm.value.courseId) {
    ElMessage.warning('请选择课程')
    return
  }
  if (!selfForm.value.questionTypes.length) {
    ElMessage.warning('请至少选择一种题型')
    return
  }

  generating.value = true
  generateMeta.value = null
  try {
    const course = courseOptions.value.find((c) => c.value === selfForm.value.courseId)
    const genResult = await generateQuizQuestions({
      courseId: selfForm.value.courseId,
      classId: userStore.userInfo?.classId || 0,
      knowledgePoints: selfForm.value.knowledgePoints,
      questionTypes: selfForm.value.questionTypes,
      questionCount: selfForm.value.questionCount,
      difficulty: selfForm.value.difficulty,
      extraRequirements: selfForm.value.extraRequirements,
    })

    if (!genResult.questions.length) {
      ElMessage.warning('未生成有效题目，请调整参数后重试')
      return
    }

    generateMeta.value = genResult.meta
    activeQuiz.value = {
      id: 0,
      title: '自主练习',
      courseId: selfForm.value.courseId,
      courseName: course?.label || '',
      classId: userStore.userInfo?.classId || 0,
      className: '',
      teacherName: '',
      knowledgePoints: selfForm.value.knowledgePoints,
      questionCount: genResult.questions.length,
      totalScore: 100,
      status: 'published',
      questions: genResult.questions,
    }
    quizMode.value = 'self'
    initAnswers(genResult.questions)
    result.value = null
    ElMessage.success(`已生成 ${genResult.questions.length} 道练习题，请开始作答`)
  } catch {
    ElMessage.error('AI 服务暂不可用，请稍后重试')
  } finally {
    generating.value = false
  }
}

function backToList(): void {
  activeQuiz.value = null
  result.value = null
  quizMode.value = 'assigned'
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

function applySubmissionResult(submission: {
  score: number
  totalScore: number
  correctCount?: number
  details?: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    aiScore?: number | null
    aiReason?: string
  }[]
}): void {
  result.value = {
    score: submission.score,
    totalScore: submission.totalScore,
    details: submission.details || [],
  }
  ElMessage.success('提交成功')
  if (submission.correctCount !== undefined) {
    const wrong = (submission.details?.length || 0) - submission.correctCount
    if (wrong > 0) {
      ElMessage.info(`答对 ${submission.correctCount} 题，${wrong} 道错题已加入错题本`)
    } else {
      ElMessage.info(`全部答对，共 ${submission.correctCount} 题`)
    }
  }
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
    const studentId = userStore.userInfo?.studentId || 1

    if (quizMode.value === 'self') {
      const submission = await submitSelfQuiz({
        studentId,
        courseId: activeQuiz.value.courseId,
        courseName: activeQuiz.value.courseName,
        knowledgePoints: activeQuiz.value.knowledgePoints,
        questions: activeQuiz.value.questions,
        answers: answers.value,
      })
      applySubmissionResult(submission)
    } else {
      const submission = await submitQuizAnswers(
        activeQuiz.value.id,
        studentId,
        userStore.userInfo?.name || '学生',
        answers.value,
        activeQuiz.value.questions,
      )
      applySubmissionResult(submission)
    }
  } catch {
    ElMessage.error('提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

const wrongCount = computed(() => result.value?.details.filter((d) => !d.correct).length ?? 0)

const resultSubtitle = computed(() => {
  const correct = (result.value?.details.length ?? 0) - wrongCount.value
  const base = `答对 ${correct} 题，答错 ${wrongCount.value} 题 · 结果已同步至知识点掌握度`
  if (quizMode.value === 'self' && wrongCount.value > 0) {
    return `${base} · 错题已加入错题本`
  }
  return base
})
</script>

<template>
  <div class="page-container">
    <!-- 列表页：双入口 -->
    <template v-if="!activeQuiz">
      <div class="content-card">
        <div class="content-card__title">在线答题</div>
        <el-tabs v-model="listTab">
          <el-tab-pane label="教师布置练习" name="assigned" />
          <el-tab-pane label="自主出题练习" name="self" />
        </el-tabs>

        <!-- 教师布置 -->
        <div v-if="listTab === 'assigned'">
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

        <!-- 自主练习配置 -->
        <div v-else class="self-quiz-form">
          <el-alert
            title="自主出题仅供个人自学使用，不会发布给其他同学；作答结果与教师布置练习一样统计，错题自动加入错题本。"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 20px"
          />

          <el-form label-width="100px">
            <el-form-item label="课程" required>
              <el-select v-model="selfForm.courseId" placeholder="选择课程" style="width: 100%">
                <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>

            <el-form-item label="知识点">
              <el-select
                v-model="selfForm.knowledgePoints"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入或选择知识点（可留空）"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="题型" required>
              <el-checkbox-group v-model="selfForm.questionTypes">
                <el-checkbox v-for="opt in questionTypeOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <el-form-item label="题量">
              <el-input-number v-model="selfForm.questionCount" :min="1" :max="20" />
            </el-form-item>

            <el-form-item label="难度">
              <el-radio-group v-model="selfForm.difficulty">
                <el-radio v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="补充要求">
              <el-input
                v-model="selfForm.extraRequirements"
                type="textarea"
                :rows="2"
                placeholder="可选：如侧重某章节、避免某类题等"
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :icon="MagicStick"
                :loading="generating"
                @click="handleGenerateSelfQuiz"
              >
                AI 生成并开始练习
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </template>

    <!-- 作答页 -->
    <div v-else>
      <div class="content-card quiz-header">
        <el-button link @click="backToList">← 返回</el-button>
        <h2>
          {{ activeQuiz.title }}
          <el-tag v-if="quizMode === 'self'" size="small" type="warning" effect="plain">自主练习</el-tag>
        </h2>
        <span v-if="!result" class="progress">已答 {{ answeredCount }} / {{ activeQuiz.questions.length }}</span>
      </div>

      <template v-if="result">
        <el-result
          icon="success"
          :title="`得分：${result.score} / ${result.totalScore}`"
          :sub-title="resultSubtitle"
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
            <el-button v-if="quizMode === 'self'" type="primary" @click="backToList(); listTab = 'self'">
              继续自主练习
            </el-button>
            <el-button v-else type="primary" @click="backToList()">返回练习列表</el-button>
          </div>
        </div>
      </template>

      <template v-else>
        <div v-if="quizMode === 'self' && generateMeta" class="content-card meta-bar">
          <el-tag size="small" type="info">AI 模型：{{ generateMeta.model }}</el-tag>
          <el-tag size="small">生成耗时：{{ generateMeta.elapsedMs }} ms</el-tag>
        </div>

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

.self-quiz-form {
  max-width: 640px;
  padding-top: 8px;
}

.quiz-header {
  display: flex;
  align-items: center;
  gap: 16px;

  h2 {
    flex: 1;
    font-size: 18px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .progress { color: #64748b; font-size: 14px; }
}

.meta-bar {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
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
