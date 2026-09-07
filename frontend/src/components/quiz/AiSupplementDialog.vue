<!--
  AI 补题弹窗 — 在已有组卷基础上追加 AI 生成题目
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { ExerciseType } from '@/types'

const props = defineProps<{
  visible: boolean
  loading: boolean
  initialConfig?: {
    questionTypes: ExerciseType[]
    extraRequirements: string
    knowledgePoints: string[]
    typeCounts: Record<ExerciseType, number>
  } | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [config: {
    knowledgePoints: string[]
    questionTypes: ExerciseType[]
    questionCount: number
    difficultyDistribution: { easy: number; medium: number; hard: number }
    extraRequirements: string
    typeCounts: Record<ExerciseType, number>
  }]
}>()

const questionTypes = ref<ExerciseType[]>(['single_choice', 'multi_choice', 'judge', 'fill_blank', 'short_answer'])
const typeCounts = ref<Record<ExerciseType, number>>({
  single_choice: 1,
  multi_choice: 1,
  judge: 1,
  fill_blank: 1,
  short_answer: 1,
})
const extraRequirements = ref('')
const knowledgePoints = ref<string[]>([])

const questionTypeOptions = [
  { label: exerciseTypeLabels.single_choice, value: 'single_choice' as ExerciseType },
  { label: exerciseTypeLabels.multi_choice, value: 'multi_choice' as ExerciseType },
  { label: exerciseTypeLabels.judge, value: 'judge' as ExerciseType },
  { label: exerciseTypeLabels.fill_blank, value: 'fill_blank' as ExerciseType },
  { label: exerciseTypeLabels.short_answer, value: 'short_answer' as ExerciseType },
]

const totalCount = computed(() =>
  questionTypes.value.reduce((sum, t) => sum + (typeCounts.value[t] || 0), 0),
)

function ensureTypeCounts(): void {
  questionTypes.value.forEach((t) => {
    if (!typeCounts.value[t] || typeCounts.value[t] <= 0) typeCounts.value[t] = 1
  })
}

watch(
  () => props.visible,
  (open) => {
    if (!open || !props.initialConfig) return
    questionTypes.value = [...props.initialConfig.questionTypes]
    typeCounts.value = { ...props.initialConfig.typeCounts }
    extraRequirements.value = props.initialConfig.extraRequirements
    knowledgePoints.value = [...props.initialConfig.knowledgePoints]
    ensureTypeCounts()
  },
)

function handleConfirm(): void {
  if (!questionTypes.value.length) {
    ElMessage.warning('请至少选择一种题型')
    return
  }
  ensureTypeCounts()
  if (totalCount.value === 0) {
    ElMessage.warning('请至少分配 1 道题')
    return
  }
  emit('confirm', {
    knowledgePoints: knowledgePoints.value,
    questionTypes: questionTypes.value,
    questionCount: totalCount.value,
    // 保留难度占比（沿用原始试卷，仅用于拆分新增题到各难度）
    difficultyDistribution: { easy: 1, medium: 1, hard: 1 },
    extraRequirements: extraRequirements.value,
    typeCounts: { ...typeCounts.value },
  })
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="AI 补题"
    width="560px"
    :close-on-click-modal="!loading"
    @update:model-value="emit('update:visible', $event)"
  >
    <p class="dialog-desc">在现有组卷基础上追加 AI 生成题目，不会替换已选题目。</p>

    <el-form label-width="88px" label-position="right">
      <el-form-item label="题型">
        <el-checkbox-group v-model="questionTypes">
          <el-checkbox v-for="t in questionTypeOptions" :key="t.value" :value="t.value">
            {{ t.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="每题型数量">
        <div class="count-grid">
          <div v-for="t in questionTypeOptions" :key="t.value" v-show="questionTypes.includes(t.value)" class="count-cell">
            <span class="count-label">{{ t.label }}</span>
            <el-input-number v-model="typeCounts[t.value]" :min="0" :max="30" size="small" controls-position="right" />
          </div>
        </div>
        <span class="total">共 {{ totalCount }} 题</span>
      </el-form-item>

      <el-form-item label="补充说明">
        <el-input
          v-model="extraRequirements"
          type="textarea"
          :rows="2"
          placeholder="如：侧重薄弱知识点、避免与已有题目重复"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="loading" @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="loading" :icon="MagicStick" @click="handleConfirm">
        开始补题（{{ totalCount }} 题）
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.dialog-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 16px;
}

.count-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 16px;
  width: 100%;

  .count-cell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;

    .count-label {
      font-size: 13px;
      color: #475569;
      white-space: nowrap;
    }
  }
}

.total {
  display: inline-block;
  margin-top: 8px;
  font-size: 13px;
  color: #64748b;
}
</style>


