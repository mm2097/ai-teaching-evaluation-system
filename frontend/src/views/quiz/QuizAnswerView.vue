<!--
  在线答题页面
  学生可作答教师布置练习，也可通过 AI 自主出题自学
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit, Check, MagicStick, View } from '@element-plus/icons-vue'
import {
  fetchStudentQuizzes,
  submitQuizAnswers,
  submitSelfQuiz,
  startSelfPractice,
} from '@/api/quiz'
import { fetchCourses } from '@/api/dict'
import { fetchCourseKnowledgePoints } from '@/api/questionBank'
import { useUserStore } from '@/stores/user'
import { ALL_EXERCISE_TYPES, difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { DifficultyLevel, ExerciseType, QuizAssignment, QuizQuestion } from '@/types'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

/** 列表 Tab：教师布置 / 自主练习 */
const listTab = ref<'assigned' | 'self'>('assigned')

/** 教师布置练习 */
const quizList = ref<QuizAssignment[]>([])
const activeQuiz = ref<QuizAssignment | null>(null)
const quizMode = ref<'assigned' | 'self'>('assigned')
const lastSubmissionId = ref<number | null>(null)

/** 自主练习配置 */
const courseOptions = ref<{ label: string; value: number }[]>([])
const knowledgePointOptions = ref<string[]>([])
const selfForm = ref({
  courseId: undefined as number | undefined,
  knowledgePoints: [] as string[],
  questionTypes: ['single_choice', 'multi_choice', 'judge', 'fill_blank', 'short_answer'] as ExerciseType[],
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
  correctCount: number
  totalCount: number
  manualRequiredCount: number
  details: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    manualRequired?: boolean
    aiScore?: number | null
    aiReason?: string
  }[]
} | null>(null)

const questionTypeOptions = ALL_EXERCISE_TYPES.map((t) => ({
  label: exerciseTypeLabels[t],
  value: t,
}))

const difficultyOptions = [
  { label: difficultyLabels.easy, value: 'easy' as DifficultyLevel },
  { label: difficultyLabels.medium, value: 'medium' as DifficultyLevel },
  { label: difficultyLabels.hard, value: 'hard' as DifficultyLevel },
]

onMounted(async () => {
  const studentId = userStore.userInfo?.studentId
  if (!studentId) {
    ElMessage.warning('未获取到学生信息，请重新登录')
    return
  }

  const tab = route.query.tab
  if (tab === 'self' || tab === 'assigned') {
    listTab.value = tab
  }

  await refreshQuizList(studentId)

  const courses = await fetchCourses({ deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) {
    selfForm.value.courseId = courseOptions.value[0]!.value
  }
  await syncSelfKnowledgePoints()

  // 支持通过 URL 参数 ?start=taskId 直接打开答题
  const startId = Number(route.query.start)
  if (startId) {
    const quiz = quizList.value.find((q) => q.id === startId)
    if (quiz) {
      if (quiz.submitted) {
        ElMessage.warning('你已完成该答题任务，不可重复作答')
        router.replace('/quiz/answer')
      } else if (isExpired(quiz)) {
        ElMessage.warning('该答题任务已截止，无法作答')
        router.replace('/quiz/answer')
      } else {
        listTab.value = 'assigned'
        startQuiz(quiz)
      }
    }
  }
})

async function refreshQuizList(studentId: number): Promise<void> {
  quizList.value = (await fetchStudentQuizzes(studentId)) as QuizAssignment[]
}

async function syncSelfKnowledgePoints(): Promise<void> {
  if (!selfForm.value.courseId) {
    knowledgePointOptions.value = []
    return
  }
  knowledgePointOptions.value = await fetchCourseKnowledgePoints(selfForm.value.courseId)
  selfForm.value.knowledgePoints = selfForm.value.knowledgePoints.filter((kp) =>
    knowledgePointOptions.value.includes(kp),
  )
}

watch(() => selfForm.value.courseId, () => {
  syncSelfKnowledgePoints()
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

/** 判断任务是否已过截止时间 */
function isExpired(quiz: QuizAssignment): boolean {
  if (!quiz.deadline) return false
  return new Date(quiz.deadline.replace(' ', 'T')) < new Date()
}

function startQuiz(quiz: QuizAssignment): void {
  if (isExpired(quiz)) {
    ElMessage.warning('该答题任务已截止，无法作答')
    return
  }
  if (quiz.submitted) {
    ElMessage.warning('你已完成该答题任务，不可重复作答')
    return
  }
  activeQuiz.value = quiz
  quizMode.value = 'assigned'
  initAnswers(quiz.questions)
  result.value = null
}

function viewQuizResult(quiz: QuizAssignment): void {
  if (quiz.mySubmissionId) {
    router.push(`/student/quiz-result?id=${quiz.mySubmissionId}`)
  } else {
    ElMessage.warning('暂无答题记录，请完成练习后再查看')
  }
}

function viewLastSubmission(): void {
  if (lastSubmissionId.value) {
    router.push(`/student/quiz-result?id=${lastSubmissionId.value}`)
  }
}

function goPracticeRecords(): void {
  router.push('/student/practice-records')
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
    const startResult = await startSelfPractice({
      courseId: selfForm.value.courseId,
      classId: userStore.userInfo?.classId || 0,
      knowledgePoints: selfForm.value.knowledgePoints,
      questionTypes: selfForm.value.questionTypes,
      questionCount: selfForm.value.questionCount,
      difficulty: selfForm.value.difficulty,
      extraRequirements: selfForm.value.extraRequirements,
    })

    if (!startResult.assignment.questions.length) {
      ElMessage.warning('未生成有效题目，请调整参数后重试')
      return
    }

    generateMeta.value = startResult.meta
    activeQuiz.value = startResult.assignment
    quizMode.value = 'self'
    initAnswers(startResult.assignment.questions)
    result.value = null
    ElMessage.success(`已生成 ${startResult.assignment.questions.length} 道练习题，请开始作答`)
  } catch {
    // 请求拦截器会展示后端的具体错误，包括当日额度与题量限制。
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
  manualRequiredCount?: number
  submissionId?: number
  details?: {
    question: QuizQuestion
    correct: boolean
    userAnswer: string | boolean
    manualRequired?: boolean
    aiScore?: number | null
    aiReason?: string
  }[]
}): void {
  const details = submission.details || []
  const totalCount = activeQuiz.value?.questions.length ?? details.length
  result.value = {
    score: submission.score,
    totalScore: submission.totalScore,
    correctCount: submission.correctCount ?? details.filter((d) => d.correct).length,
    totalCount,
    manualRequiredCount: submission.manualRequiredCount ?? details.filter((d) => d.manualRequired).length,
    details,
  }
  // 更新本地 quizList 中的答题状态，避免列表页仍显示为"未答题"
  const currentQuiz = activeQuiz.value
  if (currentQuiz) {
    lastSubmissionId.value = submission.submissionId ?? null
    const idx = quizList.value.findIndex((q) => q.id === currentQuiz.id)
    const listItem = quizList.value[idx]
    if (listItem) {
      quizList.value[idx] = {
        ...listItem,
        submitted: true,
        myScore: submission.score,
        mySubmissionId: submission.submissionId ?? listItem.mySubmissionId,
      }
    }
  }
  ElMessage.success('提交成功')
  if (submission.correctCount !== undefined) {
    const manual = details.filter((detail) => detail.manualRequired).length || 0
    const wrong = totalCount - (submission.correctCount ?? 0) - manual
    if (manual > 0) {
      ElMessage.info(`答对 ${submission.correctCount} 题，答错 ${wrong} 题，${manual} 题待人工批改`)
    } else if (wrong > 0) {
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
    const studentId = userStore.userInfo?.studentId
    if (!studentId) {
      ElMessage.warning('未获取到学生信息，请重新登录')
      return
    }

    if (quizMode.value === 'self') {
      const submission = await submitSelfQuiz({
        studentId,
        taskId: activeQuiz.value.id,
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
    // 请求拦截器已展示后端错误详情
  } finally {
    submitting.value = false
  }
}

const progressPercent = computed(() => {
  const total = activeQuiz.value?.questions.length ?? 0
  if (!total) return 0
  return Math.round((answeredCount.value / total) * 100)
})

const manualCount = computed(() => {
  if (!result.value) return 0
  // 有逐题详情时从详情计算，否则用后端返回值
  return result.value.details.length > 0
    ? result.value.details.filter((d) => d.manualRequired).length
    : result.value.manualRequiredCount
})
const partialCount = computed(
  () => result.value?.details.filter((d) =>
    d.correct && !d.manualRequired && d.aiScore !== null && d.aiScore !== undefined && d.aiScore < 10,
  ).length ?? 0,
)

function isDetailPartial(d: { correct: boolean; manualRequired?: boolean; aiScore?: number | null }): boolean {
  return d.correct && !d.manualRequired && d.aiScore !== null && d.aiScore !== undefined && d.aiScore < 10
}

const resultSubtitle = computed(() => {
  if (!result.value) return ''
  const { correctCount, totalCount } = result.value
  const wrong = totalCount - correctCount - manualCount.value
  const pending = manualCount.value ? `，待人工批改 ${manualCount.value} 题` : ''
  const partial = partialCount.value ? `，部分得分 ${partialCount.value} 题` : ''
  const base = `答对 ${correctCount} 题，答错 ${Math.max(0, wrong)} 题${partial}${pending}`
  if (quizMode.value === 'self' && wrong > 0) {
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
          <div
            v-for="quiz in quizList"
            :key="quiz.id"
            class="quiz-card"
            :class="{
              completed: quiz.submitted,
              expired: !quiz.submitted && isExpired(quiz),
              closed: quiz.status === 'closed',
            }"
          >
            <div class="quiz-info">
              <h3>
                {{ quiz.title }}
                <el-tag v-if="quiz.status === 'closed'" type="info" size="small" effect="plain">已关闭</el-tag>
                <el-tag v-else-if="quiz.submitted" type="success" size="small" effect="plain">已答题</el-tag>
                <el-tag v-else-if="isExpired(quiz)" type="danger" size="small" effect="plain">已截止</el-tag>
              </h3>
              <p>{{ quiz.courseName }} · {{ quiz.className }} · {{ quiz.questionCount }} 题 · 满分 {{ quiz.totalScore }} 分</p>
              <p v-if="quiz.submitted" class="quiz-score">
                得分：<span class="completed-score">{{ quiz.myScore ?? 0 }} / {{ quiz.totalScore }}</span>
              </p>
              <div class="quiz-tags">
                <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">{{ kp }}</el-tag>
              </div>
              <p v-if="quiz.deadline" class="deadline" :class="{ 'deadline--expired': !quiz.submitted && isExpired(quiz) }">
                截止时间：{{ quiz.deadline }}
              </p>
            </div>
            <!-- 已提交：查看结果 -->
            <template v-if="quiz.submitted">
              <el-button
                type="primary"
                :icon="View"
                plain
                @click="viewQuizResult(quiz)"
              >
                查看结果
              </el-button>
            </template>
            <!-- 已截止未提交：不可答题 -->
            <template v-else-if="isExpired(quiz)">
              <el-button type="info" :icon="Edit" disabled>已截止</el-button>
            </template>
            <!-- 正常答题 -->
            <template v-else>
              <el-button type="primary" :icon="Edit" @click="startQuiz(quiz)">开始答题</el-button>
            </template>
          </div>
        </div>

        <!-- 自主练习配置 -->
        <div v-else class="self-quiz-form">
          <el-alert
            title="自主出题仅供个人自学，不会发布给其他同学；作答记录会保存到「练习记录」，并计入个人知识点掌握度，错题自动加入错题本。"
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
                placeholder="选择知识点（可留空，默认综合）"
                style="width: 100%"
              >
                <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
              </el-select>
            </el-form-item>

            <el-form-item label="题型" required>
              <el-checkbox-group v-model="selfForm.questionTypes">
                <el-checkbox v-for="opt in questionTypeOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <el-form-item label="题量">
              <el-input-number v-model="selfForm.questionCount" :min="1" :max="10" />
              <el-text type="info" size="small">单次最多 10 题，每日最多生成 5 次</el-text>
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
    <div v-else class="quiz-answer-page">
      <div class="content-card quiz-header">
        <el-button link @click="backToList">← 返回</el-button>
        <div class="quiz-header__main">
          <h2>
            {{ activeQuiz.title }}
            <el-tag v-if="quizMode === 'self'" size="small" type="warning" effect="plain">自主练习</el-tag>
          </h2>
          <span v-if="!result" class="progress">已答 {{ answeredCount }} / {{ activeQuiz.questions.length }}</span>
        </div>
      </div>

      <div v-if="!result" class="content-card progress-card">
        <div class="progress-row">
          <span>答题进度</span>
          <span>{{ progressPercent }}%</span>
        </div>
        <el-progress :percentage="progressPercent" :stroke-width="10" :show-text="false" />
      </div>

      <template v-if="result">
        <el-result
          icon="success"
          :title="`得分：${result.score} / ${result.totalScore}`"
          :sub-title="resultSubtitle"
        />

        <div v-if="result.details.length" class="content-card">
          <div class="content-card__title">答题解析</div>
          <div
            v-for="(item, idx) in result.details"
            :key="item.question.id"
            class="review-card"
            :class="{ wrong: !item.correct && !item.manualRequired, partial: isDetailPartial(item) }"
          >
            <div class="review-header">
              <span class="question-card__index">{{ idx + 1 }}</span>
              <el-tag size="small" type="info">{{ exerciseTypeLabels[item.question.type] }}</el-tag>
              <el-tag
                :type="item.manualRequired ? 'warning' : isDetailPartial(item) ? 'warning' : item.correct ? 'success' : 'danger'"
                size="small"
              >
                {{ item.manualRequired ? '待批改' : isDetailPartial(item) ? '部分得分' : item.correct ? '正确' : '错误' }}
              </el-tag>
              <el-tag size="small" effect="plain">{{ item.question.knowledgePoint }}</el-tag>
            </div>
            <p class="question-card__stem">{{ item.question.stem }}</p>
            <p class="answer-line">
              你的答案：<strong>{{ formatAnswer(item.question, item.userAnswer) }}</strong>
            </p>
            <p v-if="!item.correct && !item.manualRequired && item.question.type !== 'short_answer'" class="answer-line correct">
              正确答案：<strong>{{ formatCorrectAnswer(item.question) }}</strong>
            </p>
            <p v-else-if="item.question.type === 'short_answer' && item.question.answer && !item.manualRequired" class="answer-line correct">
              参考答案：<strong>{{ formatCorrectAnswer(item.question) }}</strong>
            </p>
            <div v-if="item.question.type === 'short_answer' && item.aiReason" class="ai-judge">
              <div class="ai-judge__header">
                <el-tag size="small" type="warning">{{ item.manualRequired ? '待人工批改' : 'AI 判分' }}</el-tag>
                <span v-if="item.aiScore !== null && item.aiScore !== undefined" class="ai-score">
                  得分：{{ item.aiScore }} / 10
                </span>
              </div>
              <p class="ai-reason">{{ item.aiReason }}</p>
            </div>
            <p v-if="item.question.explanation" class="explanation">解析：{{ item.question.explanation }}</p>
          </div>
          <div class="submit-bar">
            <el-button v-if="lastSubmissionId && (quizMode === 'self' || activeQuiz?.allowReview !== false)" type="success" plain :icon="View" @click="viewLastSubmission">
              查看完整结果页
            </el-button>
            <el-button v-if="quizMode === 'self'" type="primary" @click="goPracticeRecords">
              查看练习记录
            </el-button>
            <el-button v-else type="primary" @click="backToList()">返回练习列表</el-button>
            <el-button v-if="quizMode === 'self'" plain @click="backToList(); listTab = 'self'">
              继续自主练习
            </el-button>
          </div>
        </div>
      </template>

      <template v-else>
        <div v-if="quizMode === 'self' && generateMeta" class="content-card meta-bar">
          <el-tag size="small" type="info">AI 模型：{{ generateMeta.model }}</el-tag>
          <el-tag size="small">生成耗时：{{ generateMeta.elapsedMs }} ms</el-tag>
        </div>

        <div class="answer-sheet">
          <div v-for="(q, idx) in activeQuiz.questions" :key="q.id" class="content-card question-card">
            <div class="question-card__head">
              <span class="question-card__index">{{ idx + 1 }}</span>
              <el-tag size="small" type="info">{{ exerciseTypeLabels[q.type] }}</el-tag>
              <span class="question-card__score">{{ q.score }} 分</span>
            </div>
            <p class="question-card__stem">{{ q.stem }}</p>

            <el-radio-group
              v-if="q.type === 'single_choice'"
              v-model="answers[q.id]"
              class="option-list"
            >
              <el-radio
                v-for="opt in q.options"
                :key="opt.key"
                :value="opt.key"
                class="option-item"
                border
              >
                <span class="option-key">{{ opt.key }}</span>
                <span class="option-text">{{ opt.text }}</span>
              </el-radio>
            </el-radio-group>

            <el-checkbox-group
              v-else-if="q.type === 'multi_choice'"
              v-model="multiAnswers[q.id]"
              class="option-list"
              @change="syncMultiAnswer(q.id)"
            >
              <el-checkbox
                v-for="opt in q.options"
                :key="opt.key"
                :value="opt.key"
                class="option-item"
                border
              >
                <span class="option-key">{{ opt.key }}</span>
                <span class="option-text">{{ opt.text }}</span>
              </el-checkbox>
            </el-checkbox-group>

            <el-radio-group
              v-else-if="q.type === 'judge'"
              v-model="answers[q.id]"
              class="option-list option-list--inline"
            >
              <el-radio :value="true" class="option-item option-item--judge" border>正确</el-radio>
              <el-radio :value="false" class="option-item option-item--judge" border>错误</el-radio>
            </el-radio-group>

            <el-input
              v-else-if="q.type === 'fill_blank'"
              v-model="(answers[q.id] as string)"
              class="answer-input"
              placeholder="请输入答案"
              size="large"
            />

            <el-input
              v-else-if="q.type === 'short_answer'"
              v-model="(answers[q.id] as string)"
              class="answer-input"
              type="textarea"
              :rows="4"
              placeholder="请输入你的解答"
            />
          </div>
        </div>

        <div class="submit-bar content-card sticky-submit">
          <p class="submit-hint">请完成全部题目后提交，提交后可在「练习记录」页面查看历史</p>
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

  &.completed {
    background: #f8fafc;
  }

  &.expired {
    background: #fef2f2;
  }

  &.closed {
    background: #f1f5f9;
  }

  h3 {
    font-size: 16px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  p { font-size: 13px; color: #64748b; margin-bottom: 8px; }
  .quiz-score { font-size: 14px; }
  .completed-score { font-weight: 700; color: #2563eb; }
  .quiz-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; }
  .deadline { font-size: 12px; color: #ef4444; }
  .deadline--expired { font-weight: 700; }
}

.self-quiz-form {
  max-width: 640px;
  padding-top: 8px;
}

.progress-card {
  padding: 16px 20px;

  .progress-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 13px;
    color: #64748b;
  }
}

.quiz-answer-page {
  max-width: 860px;
  margin: 0 auto;
}

.quiz-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;

  &__main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }

  h2 {
    flex: 1;
    font-size: 18px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 1.4;
  }

  .progress {
    color: #64748b;
    font-size: 14px;
    white-space: nowrap;
  }
}

.answer-sheet {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-card {
  padding: 20px 24px;

  &__head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }

  &__index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: #eff6ff;
    color: #2563eb;
    font-weight: 700;
    font-size: 14px;
    flex-shrink: 0;
  }

  &__score {
    margin-left: auto;
    font-size: 13px;
    color: #64748b;
    white-space: nowrap;
  }

  &__stem {
    margin: 0 0 16px;
    font-size: 15px;
    line-height: 1.75;
    color: #1e293b;
    word-break: break-word;
  }
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;

  &--inline {
    flex-direction: row;
    flex-wrap: wrap;
  }

  :deep(.el-radio),
  :deep(.el-checkbox) {
    width: 100%;
    height: auto;
    margin: 0;
    padding: 0;
    white-space: normal;
  }

  :deep(.el-radio__label),
  :deep(.el-checkbox__label) {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    width: 100%;
    padding: 12px 14px;
    line-height: 1.6;
    white-space: normal;
  }

  :deep(.el-radio__input),
  :deep(.el-checkbox__input) {
    margin-top: 3px;
  }

  :deep(.el-radio.is-bordered),
  :deep(.el-checkbox.is-bordered) {
    border-radius: 10px;
    border-color: #e2e8f0;
    transition: border-color 0.2s, background 0.2s;

    &:hover {
      border-color: #93c5fd;
      background: #f8fbff;
    }

    &.is-checked {
      border-color: #2563eb;
      background: #eff6ff;
    }
  }
}

.option-item--judge {
  :deep(.el-radio) {
    width: auto;
    min-width: 120px;
  }
}

.option-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #475569;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
}

.option-text {
  flex: 1;
  color: #334155;
}

.answer-input {
  width: 100%;
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

  &.partial {
    border-color: #fde68a;
    background: #fffbeb;
  }

  .review-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }

  .answer-line { font-size: 13px; color: #475569; margin-bottom: 4px; padding-left: 2px; }
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

  .submit-hint {
    margin: 0 0 12px;
    font-size: 13px;
    color: #64748b;
  }
}

.sticky-submit {
  position: sticky;
  bottom: 16px;
  z-index: 10;
  box-shadow: 0 -4px 16px rgba(15, 23, 42, 0.08);
}
</style>
