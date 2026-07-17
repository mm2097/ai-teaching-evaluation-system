<!--
  题库挑题弹窗
  顶部：知识点 / 题型 / 难度筛选 + 题干搜索
  列表：多选表格（展开行预览完整题目），已加入的题标记为「已添加」不可再选
  底部：已选计数 + 加入组卷
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { fetchQuestionBank } from '@/api/questionBank'
import { exerciseTypeLabels, difficultyLabels, formatJudgeAnswer, getQuestionOptions } from '@/utils/exerciseJudge'
import type { QuizQuestion, ExerciseType, DifficultyLevel } from '@/types'

const props = defineProps<{
  modelValue: boolean
  courseId?: number
  excludeIds?: number[]
}>()

const emit = defineEmits<{
  'update:modelValue': [visible: boolean]
  confirm: [questions: QuizQuestion[]]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const allQuestions = ref<QuizQuestion[]>([])

// 筛选条件
const filterKnowledge = ref('')
const filterType = ref<ExerciseType | ''>('')
const filterDifficulty = ref<DifficultyLevel | ''>('')
const searchText = ref('')

// 勾选的题目
const selectedRows = ref<QuizQuestion[]>([])
const tableRef = ref()

const excludeSet = computed(() => new Set(props.excludeIds || []))

const knowledgeOptions = computed(() => {
  const kps = new Set<string>()
  for (const q of allQuestions.value) {
    if (q.knowledgePoint) kps.add(q.knowledgePoint)
  }
  return Array.from(kps)
})

const typeOptions = computed(() => {
  const types = new Set<ExerciseType>()
  for (const q of allQuestions.value) types.add(q.type)
  return Array.from(types)
})

const filteredQuestions = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  return allQuestions.value.filter((q) => {
    if (filterKnowledge.value && q.knowledgePoint !== filterKnowledge.value) return false
    if (filterType.value && q.type !== filterType.value) return false
    if (filterDifficulty.value && q.difficulty !== filterDifficulty.value) return false
    if (kw && !q.stem.toLowerCase().includes(kw)) return false
    return true
  })
})

function isAdded(row: QuizQuestion): boolean {
  return excludeSet.value.has(row.id)
}

function selectable(row: QuizQuestion): boolean {
  return !isAdded(row)
}

function handleSelectionChange(rows: QuizQuestion[]) {
  selectedRows.value = rows
}

async function loadQuestions() {
  if (!props.courseId) {
    allQuestions.value = []
    return
  }
  loading.value = true
  try {
    allQuestions.value = await fetchQuestionBank({
      course_id: props.courseId,
      status: 'published',
    })
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filterKnowledge.value = ''
  filterType.value = ''
  filterDifficulty.value = ''
  searchText.value = ''
  selectedRows.value = []
}

// 弹窗打开时加载题库
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      resetFilters()
      loadQuestions()
    }
  },
)

function handleConfirm() {
  if (!selectedRows.value.length) {
    ElMessage.warning('请至少勾选一道题')
    return
  }
  emit('confirm', selectedRows.value.map((q) => ({ ...q })))
  visible.value = false
}

function handleCancel() {
  visible.value = false
}

function answerText(row: QuizQuestion): string {
  if (row.type === 'judge') return formatJudgeAnswer(row.answer)
  if (row.answerList?.length) return row.answerList.join('、')
  return row.answer || '—'
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="从题库挑题"
    width="900px"
    top="6vh"
    :close-on-click-modal="false"
  >
    <!-- 筛选栏 -->
    <div class="picker-filters">
      <el-select
        v-model="filterKnowledge"
        placeholder="知识点"
        clearable
        size="small"
        class="filter-item"
      >
        <el-option v-for="kp in knowledgeOptions" :key="kp" :label="kp" :value="kp" />
      </el-select>
      <el-select
        v-model="filterType"
        placeholder="题型"
        clearable
        size="small"
        class="filter-item"
      >
        <el-option
          v-for="t in typeOptions"
          :key="t"
          :label="exerciseTypeLabels[t]"
          :value="t"
        />
      </el-select>
      <el-select
        v-model="filterDifficulty"
        placeholder="难度"
        clearable
        size="small"
        class="filter-item"
      >
        <el-option
          v-for="d in (['easy', 'medium', 'hard'] as DifficultyLevel[])"
          :key="d"
          :label="difficultyLabels[d]"
          :value="d"
        />
      </el-select>
      <el-input
        v-model="searchText"
        placeholder="搜索题干关键词"
        clearable
        size="small"
        :prefix-icon="Search"
        class="filter-search"
      />
    </div>

    <!-- 题目列表 -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="filteredQuestions"
      max-height="440"
      size="small"
      row-key="id"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="42" :selectable="selectable" />
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="q-detail">
            <p class="q-stem">{{ row.stem }}</p>
            <ul v-if="getQuestionOptions(row).length" class="q-options">
              <li v-for="opt in getQuestionOptions(row)" :key="opt.key">
                <b>{{ opt.key }}.</b> {{ opt.text }}
              </li>
            </ul>
            <p class="q-answer"><b>答案：</b>{{ answerText(row) }}</p>
            <p v-if="row.explanation" class="q-explain"><b>解析：</b>{{ row.explanation }}</p>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="题干" prop="stem" show-overflow-tooltip min-width="220">
        <template #default="{ row }">
          <span>{{ row.stem }}</span>
          <el-tag v-if="isAdded(row)" size="small" type="info" class="added-tag">已添加</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="题型" width="90">
        <template #default="{ row }">{{ exerciseTypeLabels[row.type as ExerciseType] }}</template>
      </el-table-column>
      <el-table-column prop="knowledgePoint" label="知识点" width="130" show-overflow-tooltip />
      <el-table-column label="难度" width="80">
        <template #default="{ row }">{{ difficultyLabels[row.difficulty] || row.difficulty }}</template>
      </el-table-column>
    </el-table>

    <template #footer>
      <div class="picker-footer">
        <span class="selected-hint">已选 <b>{{ selectedRows.length }}</b> 题</span>
        <div>
          <el-button @click="handleCancel">取消</el-button>
          <el-button
            type="primary"
            :icon="Plus"
            :disabled="!selectedRows.length"
            @click="handleConfirm"
          >
            加入组卷（{{ selectedRows.length }}）
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.picker-filters {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;

  .filter-item {
    width: 150px;
  }
  .filter-search {
    flex: 1;
    min-width: 200px;
  }
}

.q-detail {
  padding: 8px 16px;
  color: #475569;
  font-size: 13px;
  line-height: 1.7;

  .q-stem {
    font-weight: 500;
    color: #1e293b;
    margin-bottom: 6px;
  }
  .q-options {
    margin: 0 0 6px;
    padding-left: 18px;
    li { margin-bottom: 2px; }
  }
  .q-answer { color: #16a34a; }
  .q-explain { color: #64748b; margin-top: 4px; }
}

.added-tag {
  margin-left: 8px;
}

.picker-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .selected-hint {
    font-size: 13px;
    color: #64748b;
    b { color: #2563eb; font-size: 15px; }
  }
}
</style>
