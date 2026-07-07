<!--
  AI 出题页面
  教师选择知识点、题型、题量，AI 生成练习题并发布
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Edit, Promotion } from '@element-plus/icons-vue'
import {
  fetchQuizAssignments,
  generateQuizQuestions,
  saveQuizAssignment,
  publishQuizAssignment,
} from '@/api/quiz'
import { fetchCourses, fetchClasses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment, QuizQuestion, QuestionType } from '@/types'

const userStore = useUserStore()

const courseOptions = ref<{ label: string; value: number }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const assignmentList = ref<QuizAssignment[]>([])

const form = ref({
  courseId: undefined as number | undefined,
  classId: undefined as number | undefined,
  title: '',
  knowledgePoints: [] as string[],
  questionTypes: ['single', 'multiple'] as QuestionType[],
  questionCount: 5,
})

const knowledgePointOptions = [
  '变量与表达式', '控制结构', '函数定义', '数组操作',
  '面向对象', '链表操作', '二叉树遍历', '栈与队列',
  '进程调度', '死锁', '内存管理', 'TCP协议',
]

const questionTypeOptions = [
  { label: '单选题', value: 'single' },
  { label: '多选题', value: 'multiple' },
  { label: '填空题', value: 'fill' },
  { label: '简答题', value: 'short' },
]

const generating = ref(false)
const previewQuestions = ref<QuizQuestion[]>([])
const editVisible = ref(false)
const editingQuestion = ref<QuizQuestion | null>(null)

onMounted(async () => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) form.value.courseId = courseOptions.value[0]!.value

  const classes = await fetchClasses({ deptId: 1 })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (classOptions.value.length) form.value.classId = classOptions.value[0]!.value

  assignmentList.value = await fetchQuizAssignments()
})

async function handleGenerate(): Promise<void> {
  if (!form.value.courseId || !form.value.classId) {
    ElMessage.warning('请选择课程和班级')
    return
  }
  generating.value = true
  try {
    previewQuestions.value = await generateQuizQuestions({
      courseId: form.value.courseId,
      classId: form.value.classId,
      knowledgePoints: form.value.knowledgePoints,
      questionTypes: form.value.questionTypes,
      questionCount: form.value.questionCount,
    })
    ElMessage.success(`已生成 ${previewQuestions.value.length} 道练习题`)
  } finally {
    generating.value = false
  }
}

function editQuestion(q: QuizQuestion): void {
  editingQuestion.value = { ...q, options: q.options ? [...q.options] : undefined }
  editVisible.value = true
}

function saveQuestionEdit(): void {
  if (!editingQuestion.value) return
  const idx = previewQuestions.value.findIndex((q) => q.id === editingQuestion.value!.id)
  if (idx >= 0) previewQuestions.value[idx] = { ...editingQuestion.value }
  editVisible.value = false
  ElMessage.success('题目已更新')
}

function removeQuestion(id: number): void {
  previewQuestions.value = previewQuestions.value.filter((q) => q.id !== id)
}

async function handleSaveDraft(): Promise<void> {
  if (!previewQuestions.value.length) {
    ElMessage.warning('请先生成题目')
    return
  }
  const course = courseOptions.value.find((c) => c.value === form.value.courseId)
  const cls = classOptions.value.find((c) => c.value === form.value.classId)
  const saved = await saveQuizAssignment({
    title: form.value.title || `${course?.label} - AI 练习`,
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
    ElMessage.warning('请先生成题目')
    return
  }
  const course = courseOptions.value.find((c) => c.value === form.value.courseId)
  const cls = classOptions.value.find((c) => c.value === form.value.classId)
  const saved = await saveQuizAssignment({
    title: form.value.title || `${course?.label} - AI 练习`,
    courseId: form.value.courseId!,
    courseName: course?.label || '',
    classId: form.value.classId!,
    className: cls?.label || '',
    teacherName: userStore.userInfo?.name || '任课教师',
    knowledgePoints: form.value.knowledgePoints,
    status: 'published',
    questions: previewQuestions.value,
  })
  await publishQuizAssignment(saved.id)
  assignmentList.value = await fetchQuizAssignments()
  previewQuestions.value = []
  ElMessage.success('练习已发布，学生可在「在线答题」中作答')
}

const typeLabel: Record<QuestionType, string> = {
  single: '单选',
  multiple: '多选',
  fill: '填空',
  short: '简答',
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
          <div class="content-card__title">AI 出题配置</div>
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
                <el-checkbox v-for="t in questionTypeOptions" :key="t.value" :value="t.value">{{ t.label }}</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="题量">
              <el-input-number v-model="form.questionCount" :min="1" :max="20" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="generating" :icon="MagicStick" @click="handleGenerate">
                AI 生成题目
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">
            题目预览
            <span v-if="previewQuestions.length" class="q-count">共 {{ previewQuestions.length }} 题</span>
          </div>

          <el-empty v-if="!previewQuestions.length" description="配置参数后点击「AI 生成题目」" />

          <div v-for="(q, idx) in previewQuestions" :key="q.id" class="question-card">
            <div class="q-header">
              <span class="q-num">第 {{ idx + 1 }} 题</span>
              <el-tag size="small">{{ typeLabel[q.type] }}</el-tag>
              <el-tag size="small" type="info">{{ q.knowledgePoint }}</el-tag>
              <span class="q-score">{{ q.score }} 分</span>
              <div class="q-actions">
                <el-button type="primary" link size="small" :icon="Edit" @click="editQuestion(q)">编辑</el-button>
                <el-button type="danger" link size="small" @click="removeQuestion(q.id)">删除</el-button>
              </div>
            </div>
            <p class="q-content">{{ q.content }}</p>
            <div v-if="q.options" class="q-options">
              <div v-for="(opt, i) in q.options" :key="i" class="q-option">{{ String.fromCharCode(65 + i) }}. {{ opt }}</div>
            </div>
            <p class="q-answer">参考答案：{{ Array.isArray(q.answer) ? q.answer.join('、') : q.answer }}</p>
          </div>

          <div v-if="previewQuestions.length" class="publish-bar">
            <el-button @click="handleSaveDraft">保存草稿</el-button>
            <el-button type="success" :icon="Promotion" @click="handlePublish">发布给班级</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">已发布练习</div>
      <el-table :data="assignmentList" stripe border>
        <el-table-column prop="title" label="练习标题" min-width="200" />
        <el-table-column prop="courseName" label="课程" width="120" />
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
      </el-table>
    </div>

    <el-dialog v-model="editVisible" title="编辑题目" width="560px">
      <el-form v-if="editingQuestion" label-width="80px">
        <el-form-item label="题目内容">
          <el-input v-model="editingQuestion.content" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="分值">
          <el-input-number v-model="editingQuestion.score" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input v-model="(editingQuestion.answer as string)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveQuestionEdit">保存</el-button>
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

.question-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;

  .q-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .q-num { font-weight: 600; }
    .q-score { margin-left: auto; color: #2563eb; font-size: 13px; }
    .q-actions { display: flex; gap: 4px; }
  }

  .q-content { font-size: 14px; margin-bottom: 8px; }
  .q-options { padding-left: 8px; margin-bottom: 8px; }
  .q-option { font-size: 13px; color: #475569; padding: 2px 0; }
  .q-answer { font-size: 12px; color: #10b981; }
}

.publish-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}
</style>
