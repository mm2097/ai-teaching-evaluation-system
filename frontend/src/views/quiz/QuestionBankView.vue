<!--
  题库管理页面
  支持浏览、筛选、CRUD、模板导入
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Search, Delete, Edit } from '@element-plus/icons-vue'
import QuestionFormDialog from '@/components/quiz/QuestionFormDialog.vue'
import QuestionBankImportDialog from '@/components/quiz/QuestionBankImportDialog.vue'
import {
  fetchQuestionBank,
  fetchQuestionBankStats,
  fetchCourseKnowledgePoints,
  createQuestion,
  updateQuestion,
  deleteQuestion,
} from '@/api/questionBank'
import { fetchCourses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import { difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'
import type {
  DifficultyLevel,
  ExerciseSource,
  ExerciseStatus,
  ExerciseType,
  QuestionBankStats,
  QuizQuestion,
} from '@/types'

const userStore = useUserStore()

const courseOptions = ref<{ label: string; value: number }[]>([])
const questions = ref<QuizQuestion[]>([])
const stats = ref<QuestionBankStats | null>(null)
const loading = ref(false)
const importVisible = ref(false)

const filters = ref({
  courseId: undefined as number | undefined,
  knowledgePoint: '',
  type: '' as ExerciseType | '',
  difficulty: '' as DifficultyLevel | '',
  source: '' as ExerciseSource | '',
  status: 'published' as ExerciseStatus | '',
  keyword: '',
})

const knowledgePointOptions = ref<string[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const selectedIds = ref<number[]>([])

const formVisible = ref(false)
const editingQuestion = ref<QuizQuestion | null>(null)
const formMode = ref<'create' | 'edit'>('edit')

const sourceLabels: Record<ExerciseSource, string> = {
  ai: 'AI 生成',
  manual: '手动录入',
  import: '模板导入',
}

const statusMap: Record<string, { label: string; type: 'success' | 'info' | 'warning' }> = {
  published: { label: '已入库', type: 'success' },
  closed: { label: '已归档', type: 'warning' },
}

const filteredQuestions = computed(() => questions.value)

const pagedQuestions = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredQuestions.value.slice(start, start + pageSize.value)
})

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const params = {
      courseId: filters.value.courseId,
      knowledgePoint: filters.value.knowledgePoint || undefined,
      type: filters.value.type || undefined,
      difficulty: filters.value.difficulty || undefined,
      source: filters.value.source || undefined,
      status: filters.value.status || undefined,
      keyword: filters.value.keyword || undefined,
    }
    const [list, stat] = await Promise.all([
      fetchQuestionBank(params),
      fetchQuestionBankStats(filters.value.courseId),
    ])
    questions.value = list
    stats.value = stat
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) {
    filters.value.courseId = courseOptions.value[0]!.value
  }
  await syncKnowledgePoints()
  await loadData()
})

async function syncKnowledgePoints(): Promise<void> {
  if (!filters.value.courseId) {
    knowledgePointOptions.value = []
    return
  }
  knowledgePointOptions.value = await fetchCourseKnowledgePoints(filters.value.courseId)
}

watch(() => filters.value.courseId, async () => {
  await syncKnowledgePoints()
  filters.value.knowledgePoint = ''
  currentPage.value = 1
  loadData()
})

watch(
  () => [filters.value.knowledgePoint, filters.value.type, filters.value.difficulty, filters.value.source, filters.value.status],
  () => {
    currentPage.value = 1
    loadData()
  },
)

function handleSearch(): void {
  currentPage.value = 1
  loadData()
}

function openCreate(): void {
  if (!filters.value.courseId) {
    ElMessage.warning('请先选择课程')
    return
  }
  formMode.value = 'create'
  editingQuestion.value = {
    id: 0,
    courseId: filters.value.courseId,
    type: 'single_choice',
    stem: '',
    options: [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
      { key: 'C', text: '' },
      { key: 'D', text: '' },
    ],
    answer: 'A',
    explanation: '',
    difficulty: 'medium',
    knowledgePoint: knowledgePointOptions.value[0] || '',
    score: 5,
    status: 'published',
    source: 'manual',
  }
  formVisible.value = true
}

function openEdit(q: QuizQuestion): void {
  formMode.value = 'edit'
  editingQuestion.value = q
  formVisible.value = true
}

async function handleSave(question: QuizQuestion): Promise<void> {
  if (formMode.value === 'create') {
    const { id: _id, ...rest } = question
    await createQuestion(rest)
    ElMessage.success('题目已添加至题库')
  } else {
    await updateQuestion(question.id, question)
    ElMessage.success('题目已更新')
  }
  await loadData()
  await syncKnowledgePoints()
}

async function handleDelete(q: QuizQuestion): Promise<void> {
  await ElMessageBox.confirm(`确定删除题目「${q.stem.slice(0, 30)}…」？`, '删除确认', { type: 'warning' })
  await deleteQuestion(q.id)
  ElMessage.success('已删除')
  await loadData()
}

function handleSelectionChange(rows: QuizQuestion[]): void {
  selectedIds.value = rows.map((r) => r.id)
}

function typeLabel(type: ExerciseType): string {
  return exerciseTypeLabels[type]
}

function sourceLabel(source?: ExerciseSource): string {
  return sourceLabels[source || 'manual']
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="content-card__title">题库管理</div>
      <p class="page-desc">管理课程练习题库，支持手动录入、模板批量导入、AI 生成题入库。智能组卷 Agent 将复用本题库数据。</p>

      <el-row :gutter="12" class="stat-row">
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.total ?? 0 }}</span>
            <span class="stat-label">题库总量</span>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.byType.single_choice ?? 0 }}</span>
            <span class="stat-label">单选题</span>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.byType.multi_choice ?? 0 }}</span>
            <span class="stat-label">多选题</span>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.byType.judge ?? 0 }}</span>
            <span class="stat-label">判断题</span>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.byType.fill_blank ?? 0 }}</span>
            <span class="stat-label">填空题</span>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-item">
            <span class="stat-value">{{ stats?.byType.short_answer ?? 0 }}</span>
            <span class="stat-label">简答题</span>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="content-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="课程">
          <el-select v-model="filters.courseId" style="width: 160px">
            <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="知识点">
          <el-select v-model="filters.knowledgePoint" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="filters.type" clearable placeholder="全部" style="width: 110px">
            <el-option v-for="(label, key) in exerciseTypeLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="filters.difficulty" clearable placeholder="全部" style="width: 100px">
            <el-option v-for="(label, key) in difficultyLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.source" clearable placeholder="全部" style="width: 110px">
            <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
            <el-option label="已入库" value="published" />
            <el-option label="已归档" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索题干" clearable style="width: 160px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <div class="toolbar">
        <el-button type="primary" :icon="Plus" @click="openCreate">新增题目</el-button>
        <el-button :icon="Upload" @click="importVisible = true">批量导入</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="pagedQuestions"
        stripe
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column label="题干" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ row.stem }}</template>
        </el-table-column>
        <el-table-column label="题型" width="90" align="center">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="knowledgePoint" label="知识点" width="120" />
        <el-table-column label="难度" width="80" align="center">
          <template #default="{ row }">{{ difficultyLabels[row.difficulty] }}</template>
        </el-table-column>
        <el-table-column prop="score" label="分值" width="70" align="center" />
        <el-table-column label="来源" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ sourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status || 'published']?.type" size="small">
              {{ statusMap[row.status || 'published']?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="filteredQuestions.length"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </div>

    <QuestionFormDialog
      v-model="formVisible"
      :question="editingQuestion"
      :knowledge-point-options="knowledgePointOptions"
      :mode="formMode"
      @save="handleSave"
    />

    <QuestionBankImportDialog
      v-model="importVisible"
      :course-id="filters.courseId"
      @imported="async () => { await loadData(); await syncKnowledgePoints() }"
    />
  </div>
</template>

<style scoped lang="scss">
.page-desc {
  font-size: 13px;
  color: #64748b;
  margin: -8px 0 16px;
}

.stat-row {
  margin-top: 8px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;

  .stat-value {
    display: block;
    font-size: 24px;
    font-weight: 700;
    color: #2563eb;
  }

  .stat-label {
    font-size: 12px;
    color: #64748b;
  }
}

.filter-form {
  margin-bottom: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
</style>
