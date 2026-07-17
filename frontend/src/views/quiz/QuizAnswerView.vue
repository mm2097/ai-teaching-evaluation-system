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
import { ALL_EXERCISE_TYPES, difficultyLabels, exerciseTypeLabels, formatJudgeAnswer, getQuestionOptions, judgeOptionAnswerValue } from '@/utils/exerciseJudge'
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
  if (quiz.allowReview === false) {
    ElMessage.info('教师已关闭本次练习的题目详情查看')
    return
  }
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
  if (q.type === 'judge') return formatJudgeAnswer(ans)
  return String(ans)
}

function formatCorrectAnswer(q: QuizQuestion): string {
  if (q.type === 'judge') return formatJudgeAnswer(q.answer)
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
  <div class="page-container quiz-page">
    <!-- 列表页：双入口 -->
    <template v-if="!activeQuiz">
      <div class="content-card list-card">
        <div class="content-card__title">在线答题</div>
        <p class="page-desc">完成教师布置的练习，或通过 AI 自主出题进行自学训练。</p>

        <el-tabs v-model="listTab" class="list-tabs">
          <el-tab-pane label="教师布置练习" name="assigned" />
          <el-tab-pane label="自主出题练习" name="self" />
        </el-tabs>

        <!-- 教师布置 -->
        <div v-if="listTab === 'assigned'" class="list-panel">
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
              <h3>{{ quiz.title }}</h3>
              <p class="quiz-meta">
                {{ quiz.courseName }} · {{ quiz.className }} · {{ quiz.questionCount }} 题 · 满分 {{ quiz.totalScore }} 分
              </p>
              <p v-if="quiz.submitted" class="quiz-score">
                得分：<span class="highlight-score">{{ quiz.myScore ?? 0 }} / {{ quiz.totalScore }}</span>
              </p>
              <div v-if="quiz.knowledgePoints.length" class="quiz-tags">
                <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">{{ kp }}</el-tag>
              </div>
              <p v-if="quiz.deadline" class="deadline" :class="{ 'deadline--expired': !quiz.submitted && isExpired(quiz) }">
                截止时间：{{ quiz.deadline }}
              </p>
            </div>
            <div class="quiz-actions">
              <el-tag v-if="quiz.status === 'closed'" type="info" size="small" effect="plain">已关闭</el-tag>
              <el-tag v-else-if="quiz.submitted" type="success" size="small" effect="plain">已答题</el-tag>
              <el-tag v-else-if="isExpired(quiz)" type="danger" size="small" effect="plain">已截止</el-tag>
              <el-tag v-else type="warning" size="small" effect="plain">待完成</el-tag>
              <el-button
                v-if="quiz.submitted && quiz.allowReview !== false"
                type="primary"
                :icon="View"
                plain
                @click="viewQuizResult(quiz)"
              >
                查看结果
              </el-button>
              <el-button
                v-else-if="isExpired(quiz)"
                type="info"
                :icon="Edit"
                disabled
              >
                已截止
              </el-button>
              <el-button
                v-else
                type="primary"
                :icon="Edit"
                @click="startQuiz(quiz)"
              >
                开始答题
              </el-button>
            </div>
          </div>
        </div>

        <!-- 自主练习配置 -->
        <div v-else class="list-panel self-quiz-form">
          <el-alert
            title="自主出题仅供个人自学，不会发布给其他同学；作答记录会保存到「练习记录」，并计入个人知识点掌握度，错题自动加入错题本。"
            type="info"
            :closable="false"
            show-icon
            class="self-alert"
          />

          <el-form label-width="88px" class="self-form">
            <el-form-item label="课程" required>
              <el-select v-model="selfForm.courseId" placeholder="选择课程" class="full-width">
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
                class="full-width"
              >
                <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
              </el-select>
            </el-form-item>

            <el-form-item label="题型" required>
              <el-checkbox-group v-model="selfForm.questionTypes" class="type-grid">
                <el-checkbox v-for="opt in questionTypeOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <el-form-item label="题量">
              <div class="inline-field">
                <el-input-number v-model="selfForm.questionCount" :min="1" :max="10" />
                <span class="form-tip">单次最多 10 题，每日最多生成 5 次</span>
              </div>
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

            <el-form-item class="form-actions">
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
      <div class="content-card answer-top">
        <el-button link class="back-link" @click="backToList">← 返回列表</el-button>
        <div class="answer-top__body">
          <div class="answer-top__info">
            <h2>
              {{ activeQuiz.title }}
              <el-tag v-if="quizMode === 'self'" size="small" type="warning" effect="plain">自主练习</el-tag>
            </h2>
            <p class="answer-top__meta">
              {{ activeQuiz.courseName }} · {{ activeQuiz.questions.length }} 题 · 满分 {{ activeQuiz.totalScore }} 分
            </p>
          </div>
          <div v-if="!result" class="answer-top__progress">
            <div class="progress-row">
              <span>答题进度</span>
              <span>{{ answeredCount }} / {{ activeQuiz.questions.length }} · {{ progressPercent }}%</span>
            </div>
            <el-progress :percentage="progressPercent" :stroke-width="8" :show-text="false" />
          </div>
        </div>
      </div>

      <template v-if="result">
        <div class="content-card result-summary">
          <div class="result-score">
            <span class="score-num">{{ result.score }}</span>
            <span class="score-div">/</span>
            <span class="score-total">{{ result.totalScore }}</span>
          </div>
          <p class="result-subtitle">{{ resultSubtitle }}</p>
        </div>

        <div v-if="result.details.length" class="content-card review-panel">
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
            <div class="answer-block">
              <p class="answer-line">
                <span class="answer-label">你的答案</span>
                <strong>{{ formatAnswer(item.question, item.userAnswer) }}</strong>
              </p>
              <p v-if="!item.correct && !item.manualRequired && item.question.type !== 'short_answer'" class="answer-line correct">
                <span class="answer-label">正确答案</span>
                <strong>{{ formatCorrectAnswer(item.question) }}</strong>
              </p>
              <p v-else-if="item.question.type === 'short_answer' && item.question.answer && !item.manualRequired" class="answer-line correct">
                <span class="answer-label">参考答案</span>
                <strong>{{ formatCorrectAnswer(item.question) }}</strong>
              </p>
            </div>
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
          <div class="action-bar">
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

        <div v-else class="content-card review-panel no-detail-panel">
          <div class="content-card__title">答题记录已保存</div>
          <p class="no-detail-text">教师已关闭本次练习的题目详情查看，你仍可在练习列表和练习记录中查看本次得分。</p>
          <div class="action-bar">
            <el-button type="primary" @click="backToList()">返回练习列表</el-button>
            <el-button plain @click="goPracticeRecords">查看练习记录</el-button>
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
              <el-tag v-if="q.knowledgePoint" size="small" effect="plain">{{ q.knowledgePoint }}</el-tag>
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
              <el-radio
                v-for="opt in getQuestionOptions(q)"
                :key="opt.key"
                :value="judgeOptionAnswerValue(opt)"
                class="option-item option-item--judge"
                border
              >
                {{ opt.text }}
              </el-radio>
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

        <div class="content-card sticky-submit">
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
.page-desc {
  margin: -8px 0 4px;
  font-size: 13px;
  color: #64748b;
}

.list-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }
}

.list-panel {
  padding-top: 16px;
}

.quiz-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 12px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 12px rgba(37, 99, 235, 0.08);
  }

  &.completed {
    background: #f8fafc;
  }

  &.expired {
    background: #fef2f2;
  }

  &.closed {
    background: #f1f5f9;
  }

  .quiz-info {
    flex: 1;
    min-width: 0;
  }

  h3 {
    font-size: 16px;
    margin-bottom: 6px;
    line-height: 1.4;
  }

  .quiz-meta {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 8px;
  }

  .quiz-score {
    font-size: 14px;
    margin-bottom: 8px;
  }

  .highlight-score {
    font-weight: 700;
    color: #2563eb;
  }

  .quiz-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 6px;
  }

  .deadline {
    font-size: 12px;
    color: #ef4444;
    margin-bottom: 0;

    &--expired {
      font-weight: 600;
    }
  }
}

.quiz-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

.self-quiz-form {
  max-width: 720px;
}

.self-alert {
  margin-bottom: 20px;
}

.self-form {
  .full-width {
    width: 100%;
  }

  .type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px 16px;
    width: 100%;
  }

  .inline-field {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .form-tip {
    font-size: 12px;
    color: #94a3b8;
  }

  .form-actions {
    margin-bottom: 0;
    padding-top: 4px;
  }
}

.quiz-answer-page {
  max-width: 860px;
  margin: 0 auto;
}

.answer-top {
  .back-link {
    padding: 0;
    margin-bottom: 12px;
    font-size: 13px;
  }

  &__body {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
  }

  &__info {
    flex: 1;
    min-width: 240px;
  }

  h2 {
    font-size: 18px;
    margin: 0 0 6px;
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 1.4;
  }

  &__meta {
    font-size: 13px;
    color: #64748b;
    margin: 0;
  }

  &__progress {
    width: 240px;
    flex-shrink: 0;
  }
}

.progress-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #64748b;
}

.result-summary {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.result-score {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: #2563eb;

  .score-num {
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
  }

  .score-div {
    font-size: 20px;
    opacity: 0.5;
  }

  .score-total {
    font-size: 22px;
    opacity: 0.7;
  }
}

.result-subtitle {
  flex: 1;
  min-width: 200px;
  margin: 0;
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;
}

.no-detail-text {
  margin: 0 0 16px;
  color: #64748b;
  line-height: 1.7;
}

.answer-sheet {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-card {
  &__head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
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
  flex-wrap: wrap;
  padding: 12px 20px;
}

.review-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
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

  .answer-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }

  .answer-line {
    display: flex;
    align-items: baseline;
    gap: 12px;
    font-size: 13px;
    color: #475569;
    margin: 0;

    .answer-label {
      flex-shrink: 0;
      width: 64px;
      color: #94a3b8;
    }

    &.correct strong {
      color: #10b981;
    }
  }

  .explanation {
    font-size: 12px;
    color: #64748b;
    margin: 10px 0 0;
    padding-top: 10px;
    border-top: 1px dashed #e2e8f0;
  }

  .ai-judge {
    margin-top: 10px;
    padding: 10px 12px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;

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

.action-bar,
.sticky-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 8px;
}

.sticky-submit {
  position: sticky;
  bottom: 16px;
  z-index: 10;
  justify-content: space-between;
  padding: 16px 24px;
  box-shadow: 0 -4px 16px rgba(15, 23, 42, 0.08);

  .submit-hint {
    margin: 0;
    font-size: 13px;
    color: #64748b;
    text-align: left;
  }
}

@media (max-width: 768px) {
  .quiz-card {
    flex-direction: column;
    align-items: stretch;
  }

  .quiz-actions {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .answer-top__progress {
    width: 100%;
  }

  .sticky-submit {
    flex-direction: column;
    align-items: stretch;

    .submit-hint {
      text-align: center;
    }
  }
}
</style>
