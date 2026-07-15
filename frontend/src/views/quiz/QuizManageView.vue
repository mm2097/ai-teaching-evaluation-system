<!--
  AI 出题页面
  教师 AI 生成 / 从题库选题，预览编辑后发布练习
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Edit, Promotion, Collection, View, CircleClose, FolderAdd } from '@element-plus/icons-vue'
import QuestionFormDialog from '@/components/quiz/QuestionFormDialog.vue'
import {
  fetchQuizAssignments,
  generateQuizQuestions,
  saveQuizAssignment,
  publishQuizAssignment,
  closeQuizAssignment,
} from '@/api/quiz'
import { fetchQuestionBank, addQuestionsToBank, checkQuestionsInBank, fetchCourseKnowledgePoints } from '@/api/questionBank'
import { fetchCourses, fetchClasses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import { ALL_EXERCISE_TYPES, difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import { isSelfPracticeTask } from '@/utils/errorBookStorage'
import type { DifficultyLevel, ExerciseType, QuizAssignment, QuizQuestion } from '@/types'

const userStore = useUserStore()

const createMode = ref<'ai' | 'bank'>('ai')
const courseOptions = ref<{ label: string; value: number }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const assignmentList = ref<QuizAssignment[]>([])

const form = ref({
  courseId: undefined as number | undefined,
  classId: undefined as number | undefined,
  title: '',
  knowledgePoints: [] as string[],
  questionTypes: ['single_choice', 'multi_choice'] as ExerciseType[],
  questionCount: 5,
  difficulty: 'medium' as DifficultyLevel,
  extraRequirements: '',
})

const knowledgePointOptions = ref<string[]>([])
const bankQuestions = ref<QuizQuestion[]>([])
const bankSelectedIds = ref<number[]>([])
const bankLoading = ref(false)

async function loadClassOptions(): Promise<void> {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const classes = await fetchClasses({
    deptId: 1,
    courseId: form.value.courseId,
    teacherId,
  })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (!classOptions.value.some((c) => c.value === form.value.classId)) {
    form.value.classId = classOptions.value[0]?.value
  }
}

async function syncKnowledgePoints(): Promise<void> {
  if (!form.value.courseId) {
    knowledgePointOptions.value = []
    form.value.knowledgePoints = []
    return
  }
  knowledgePointOptions.value = await fetchCourseKnowledgePoints(form.value.courseId)
  form.value.knowledgePoints = form.value.knowledgePoints.filter((kp) =>
    knowledgePointOptions.value.includes(kp),
  )
}

async function loadBankQuestions(): Promise<void> {
  if (!form.value.courseId) return
  bankLoading.value = true
  try {
    bankQuestions.value = await fetchQuestionBank({
      course_id: form.value.courseId,
      status: 'published',
    })
  } finally {
    bankLoading.value = false
  }
}

onMounted(async () => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) form.value.courseId = courseOptions.value[0]!.value

  await loadClassOptions()
  await syncKnowledgePoints()
  await loadBankQuestions()
  assignmentList.value = (await fetchQuizAssignments({ teacherId }))
    .filter((t) => !isSelfPracticeTask(t.title)) as QuizAssignment[]
})

const questionTypeOptions = ALL_EXERCISE_TYPES.map((t) => ({
  label: exerciseTypeLabels[t],
  value: t,
}))

const difficultyOptions = [
  { label: difficultyLabels.easy, value: 'easy' as DifficultyLevel },
  { label: difficultyLabels.medium, value: 'medium' as DifficultyLevel },
  { label: difficultyLabels.hard, value: 'hard' as DifficultyLevel },
]

watch(() => form.value.courseId, async () => {
  await loadClassOptions()
  await syncKnowledgePoints()
  await loadBankQuestions()
  bankSelectedIds.value = []
})

const generating = ref(false)
const generateMeta = ref<{ model: string; elapsedMs: number } | null>(null)
const previewQuestions = ref<QuizQuestion[]>([])
const bankedStems = ref<Set<string>>(new Set())
const addingToBank = ref(false)
const editVisible = ref(false)
const editingQuestion = ref<QuizQuestion | null>(null)
const detailVisible = ref(false)
const detailAssignment = ref<QuizAssignment | null>(null)

async function handleGenerate(): Promise<void> {
  if (!form.value.courseId || !form.value.classId) {
    ElMessage.warning('请选择课程和班级')
    return
  }
  if (!form.value.questionTypes.length) {
    ElMessage.warning('请至少选择一种题型')
    return
  }
  generating.value = true
  generateMeta.value = null
  try {
    const result = await generateQuizQuestions({
      courseId: form.value.courseId,
      classId: form.value.classId,
      knowledgePoints: form.value.knowledgePoints,
      questionTypes: form.value.questionTypes,
      questionCount: form.value.questionCount,
      difficulty: form.value.difficulty,
      extraRequirements: form.value.extraRequirements,
    })
    previewQuestions.value = result.questions
    generateMeta.value = { model: result.meta.model, elapsedMs: result.meta.elapsedMs }
    await refreshBankedStatus()
    ElMessage.success(`已生成 ${previewQuestions.value.length} 道练习题，可审核后发布或加入题库`)
  } catch {
    ElMessage.error('AI 服务暂不可用，请稍后重试')
  } finally {
    generating.value = false
  }
}

async function addFromBank(): Promise<void> {
  if (!bankSelectedIds.value.length) {
    ElMessage.warning('请从题库勾选题目')
    return
  }
  const selected = bankQuestions.value.filter((q) => bankSelectedIds.value.includes(q.id))
  const existingIds = new Set(previewQuestions.value.map((q) => q.id))
  const toAdd = selected.filter((q) => !existingIds.has(q.id))
  previewQuestions.value = [...previewQuestions.value, ...toAdd.map((q) => ({ ...q }))]
  await refreshBankedStatus()
  ElMessage.success(`已从题库添加 ${toAdd.length} 道题目`)
}

function editQuestion(q: QuizQuestion): void {
  editingQuestion.value = q
  editVisible.value = true
}

function saveQuestionEdit(question: QuizQuestion): void {
  const idx = previewQuestions.value.findIndex((q) => q.id === question.id)
  if (idx >= 0) previewQuestions.value[idx] = { ...question }
  void refreshBankedStatus()
  ElMessage.success('题目已更新')
}

function removeQuestion(id: number): void {
  previewQuestions.value = previewQuestions.value.filter((q) => q.id !== id)
  void refreshBankedStatus()
}

async function refreshBankedStatus(): Promise<void> {
  if (!previewQuestions.value.length || !form.value.courseId) {
    bankedStems.value = new Set()
    return
  }
  const stems = previewQuestions.value.map((q) => q.stem)
  const status = await checkQuestionsInBank(stems, form.value.courseId)
  bankedStems.value = new Set(stems.filter((s) => status[s]))
}

function isInBank(q: QuizQuestion): boolean {
  return bankedStems.value.has(q.stem)
}

function isDuplicateInPreview(q: QuizQuestion): boolean {
  if (isInBank(q)) return false
  const firstIdx = previewQuestions.value.findIndex((item) => item.stem === q.stem)
  const currentIdx = previewQuestions.value.findIndex((item) => item.id === q.id)
  return firstIdx >= 0 && currentIdx > firstIdx
}

/** 预览区中实际可入库的题目（排除已在题库 + 预览区内重复题干） */
function getAddableToBankQuestions(): QuizQuestion[] {
  const seen = new Set<string>()
  return previewQuestions.value.filter((q) => {
    if (bankedStems.value.has(q.stem)) return false
    if (seen.has(q.stem)) return false
    seen.add(q.stem)
    return true
  })
}

const notBankedCount = computed(() => getAddableToBankQuestions().length)

async function handleAddAllToBank(): Promise<void> {
  if (!form.value.courseId || !previewQuestions.value.length) return
  const toAdd = getAddableToBankQuestions()
  if (!toAdd.length) {
    ElMessage.info('预览区题目均已在题库中')
    return
  }
  addingToBank.value = true
  try {
    const courseId = form.value.courseId
    const questions = toAdd.map((q) => ({ ...q, courseId }))
    const result = await addQuestionsToBank(questions, { source: 'ai' })
    await refreshBankedStatus()
    await loadBankQuestions()
    ElMessage.success(
      `已加入题库 ${result.added} 道${result.skipped ? `，跳过重复 ${result.skipped} 道` : ''}，可在「从题库选题」中组卷`,
    )
  } finally {
    addingToBank.value = false
  }
}

async function handleAddOneToBank(q: QuizQuestion): Promise<void> {
  if (!form.value.courseId || isInBank(q)) return
  const result = await addQuestionsToBank([{ ...q, courseId: form.value.courseId }], { source: 'ai' })
  if (result.added > 0) {
    bankedStems.value.add(q.stem)
    await loadBankQuestions()
    ElMessage.success('已加入题库')
  } else {
    ElMessage.info('该题已在题库中')
  }
}

async function handleSaveDraft(): Promise<void> {
  if (!previewQuestions.value.length) {
    ElMessage.warning('请先生成或选择题目')
    return
  }
  const course = courseOptions.value.find((c) => c.value === form.value.courseId)
  const cls = classOptions.value.find((c) => c.value === form.value.classId)
  const saved = await saveQuizAssignment({
    title: form.value.title || `${course?.label} - 专项练习`,
    courseId: form.value.courseId!,
    courseName: course?.label || '',
    classId: form.value.classId!,
    className: cls?.label || '',
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: form.value.knowledgePoints,
    status: 'draft',
    questions: previewQuestions.value,
  })
  assignmentList.value = await fetchQuizAssignments()
  ElMessage.success(`练习「${saved.title}」已保存为草稿`)
}

async function handlePublish(): Promise<void> {
  if (!previewQuestions.value.length) {
    ElMessage.warning('请先生成或选择题目')
    return
  }
  const course = courseOptions.value.find((c) => c.value === form.value.courseId)
  const cls = classOptions.value.find((c) => c.value === form.value.classId)
  const saved = await saveQuizAssignment({
    title: form.value.title || `${course?.label} - 专项练习`,
    courseId: form.value.courseId!,
    courseName: course?.label || '',
    classId: form.value.classId!,
    className: cls?.label || '',
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: form.value.knowledgePoints,
    status: 'draft',
    questions: previewQuestions.value,
  })
  await publishQuizAssignment(saved.id)
  assignmentList.value = await fetchQuizAssignments()
  previewQuestions.value = []
  generateMeta.value = null
  bankSelectedIds.value = []
  ElMessage.success('练习已发布，学生可在「在线答题」中作答')
}

async function handleCloseAssignment(row: QuizAssignment): Promise<void> {
  await ElMessageBox.confirm(`确定关闭练习「${row.title}」？关闭后学生将无法继续作答。`, '关闭确认', {
    type: 'warning',
  })
  await closeQuizAssignment(row.id)
  assignmentList.value = await fetchQuizAssignments()
  ElMessage.success('练习已关闭')
}

function viewAssignment(row: QuizAssignment): void {
  detailAssignment.value = row
  detailVisible.value = true
}

function typeLabel(type: ExerciseType): string {
  return exerciseTypeLabels[type]
}

const statusMap: Record<string, { label: string; type: 'success' | 'info' | 'warning' }> = {
  draft: { label: '草稿', type: 'info' },
  published: { label: '已发布', type: 'success' },
  closed: { label: '已关闭', type: 'warning' },
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">创建练习</div>
          <el-tabs v-model="createMode">
            <el-tab-pane label="AI 生成" name="ai">
              <el-form label-width="90px">
                <el-form-item label="练习标题">
                  <el-input v-model="form.title" placeholder="如：数据结构专项练习" />
                </el-form-item>
                <el-form-item label="课程">
                  <el-select v-model="form.courseId" style="width: 100%">
                    <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="班级">
                  <el-select v-model="form.classId" style="width: 100%">
                    <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="知识点">
                  <el-select v-model="form.knowledgePoints" multiple placeholder="选择知识点范围" style="width: 100%">
                    <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
                  </el-select>
                </el-form-item>
                <el-form-item label="题型">
                  <el-checkbox-group v-model="form.questionTypes">
                    <el-checkbox v-for="t in questionTypeOptions" :key="t.value" :value="t.value">
                      {{ t.label }}
                    </el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="难度">
                  <el-radio-group v-model="form.difficulty">
                    <el-radio v-for="d in difficultyOptions" :key="d.value" :value="d.value">{{ d.label }}</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="题量">
                  <el-input-number v-model="form.questionCount" :min="1" :max="30" />
                </el-form-item>
                <el-form-item label="其他要求">
                  <el-input
                    v-model="form.extraRequirements"
                    type="textarea"
                    :rows="2"
                    placeholder="如：面向初学者，干扰项要合理"
                    maxlength="200"
                    show-word-limit
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="generating" :icon="MagicStick" @click="handleGenerate">
                    AI 生成题目
                  </el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="从题库选题" name="bank">
              <el-form label-width="90px">
                <el-form-item label="课程">
                  <el-select v-model="form.courseId" style="width: 100%">
                    <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="班级">
                  <el-select v-model="form.classId" style="width: 100%">
                    <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="练习标题">
                  <el-input v-model="form.title" placeholder="如：计算机网络期中复习" />
                </el-form-item>
              </el-form>
              <p class="bank-tip">从题库勾选题目后点击「添加到预览区」，可在右侧编辑后发布。</p>
              <el-table
                v-loading="bankLoading"
                :data="bankQuestions"
                max-height="320"
                size="small"
                @selection-change="(rows: QuizQuestion[]) => (bankSelectedIds = rows.map((r) => r.id))"
              >
                <el-table-column type="selection" width="40" />
                <el-table-column label="题干" prop="stem" show-overflow-tooltip />
                <el-table-column label="题型" width="80">
                  <template #default="{ row }">{{ typeLabel(row.type) }}</template>
                </el-table-column>
                <el-table-column prop="knowledgePoint" label="知识点" width="100" />
              </el-table>
              <el-button type="primary" :icon="Collection" style="margin-top: 12px" @click="addFromBank">
                添加到预览区（已选 {{ bankSelectedIds.length }}）
              </el-button>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">
            题目预览
            <span v-if="previewQuestions.length" class="q-count">共 {{ previewQuestions.length }} 题</span>
            <el-tag v-if="generateMeta" size="small" type="info" style="margin-left: 8px">
              {{ generateMeta.model }} · {{ generateMeta.elapsedMs }}ms
            </el-tag>
          </div>

          <el-empty v-if="!previewQuestions.length" description="AI 生成或从题库选题后在此预览" />

          <div v-for="(q, idx) in previewQuestions" :key="q.id" class="question-card">
            <div class="q-header">
              <span class="q-num">第 {{ idx + 1 }} 题</span>
              <el-tag size="small">{{ exerciseTypeLabels[q.type] }}</el-tag>
              <el-tag size="small" type="warning">{{ difficultyLabels[q.difficulty] }}</el-tag>
              <el-tag size="small" type="info">{{ q.knowledgePoint }}</el-tag>
              <el-tag v-if="isInBank(q)" size="small" type="success">已入库</el-tag>
              <el-tag v-else-if="isDuplicateInPreview(q)" size="small" type="info">预览重复</el-tag>
              <span class="q-score">{{ q.score }} 分</span>
              <div class="q-actions">
                <el-button
                  v-if="!isInBank(q) && !isDuplicateInPreview(q)"
                  type="success"
                  link
                  size="small"
                  :icon="FolderAdd"
                  @click="handleAddOneToBank(q)"
                >
                  入库
                </el-button>
                <el-button type="primary" link size="small" :icon="Edit" @click="editQuestion(q)">编辑</el-button>
                <el-button type="danger" link size="small" @click="removeQuestion(q.id)">删除</el-button>
              </div>
            </div>
            <p class="q-content">{{ q.stem }}</p>
            <div v-if="q.options?.length" class="q-options">
              <div v-for="opt in q.options" :key="opt.key" class="q-option">
                {{ opt.key }}. {{ opt.text }}
              </div>
            </div>
            <p class="q-answer">
              参考答案：{{ q.type === 'judge' ? (q.answer === 'true' ? '正确' : '错误') : q.answer }}
            </p>
            <p v-if="q.explanation" class="q-explanation">解析：{{ q.explanation }}</p>
          </div>

          <div v-if="previewQuestions.length" class="publish-bar">
            <el-button
              type="warning"
              :icon="FolderAdd"
              :loading="addingToBank"
              :disabled="!notBankedCount"
              @click="handleAddAllToBank"
            >
              全部加入题库（{{ notBankedCount }}）
            </el-button>
            <el-button @click="handleSaveDraft">保存草稿</el-button>
            <el-button type="success" :icon="Promotion" @click="handlePublish">发布给班级</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">练习列表</div>
      <el-table :data="assignmentList" stripe border>
        <el-table-column prop="title" label="练习标题" min-width="200" />
        <el-table-column prop="courseName" label="课程" width="140" />
        <el-table-column prop="className" label="班级" width="110" />
        <el-table-column prop="questionCount" label="题量" width="70" align="center" />
        <el-table-column prop="totalScore" label="总分" width="70" align="center" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="publishTime" label="发布时间" width="170">
          <template #default="{ row }">{{ row.publishTime || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="View" @click="viewAssignment(row)">详情</el-button>
            <el-button
              v-if="row.status === 'published'"
              type="warning"
              link
              size="small"
              :icon="CircleClose"
              @click="handleCloseAssignment(row)"
            >
              关闭
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <QuestionFormDialog
      v-model="editVisible"
      :question="editingQuestion"
      :knowledge-point-options="knowledgePointOptions"
      mode="edit"
      @save="saveQuestionEdit"
    />

    <el-dialog v-model="detailVisible" :title="detailAssignment?.title" width="700px">
      <template v-if="detailAssignment">
        <p class="detail-meta">
          {{ detailAssignment.courseName }} · {{ detailAssignment.className }} ·
          {{ detailAssignment.questionCount }} 题 · 满分 {{ detailAssignment.totalScore }} 分
        </p>
        <div v-for="(q, idx) in detailAssignment.questions" :key="q.id" class="question-card compact">
          <p><strong>{{ idx + 1 }}.</strong> {{ q.stem }}（{{ q.score }}分）</p>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.q-count {
  font-size: 13px;
  color: #64748b;
  font-weight: normal;
  margin-left: 8px;
}

.bank-tip {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.question-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;

  &.compact {
    padding: 10px 12px;
    font-size: 13px;
  }

  .q-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;

    .q-num { font-weight: 600; }
    .q-score { margin-left: auto; color: #2563eb; font-size: 13px; }
    .q-actions { display: flex; gap: 4px; }
  }

  .q-content { font-size: 14px; margin-bottom: 8px; }
  .q-options { padding-left: 8px; margin-bottom: 8px; }
  .q-option { font-size: 13px; color: #475569; padding: 2px 0; }
  .q-answer { font-size: 12px; color: #10b981; }
  .q-explanation { font-size: 12px; color: #64748b; margin-top: 4px; }
}

.publish-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.detail-meta {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
}
</style>
