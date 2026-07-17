<!--
  AI 补题弹窗 — 在已有组卷基础上追加 AI 生成题目
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { ExerciseType } from '@/types'
import type { DifficultyDistribution } from './QuizWizardStep1Config.vue'

const props = defineProps<{
  visible: boolean
  loading: boolean
  initialConfig?: {
    questionTypes: ExerciseType[]
    difficultyDistribution: DifficultyDistribution
    extraRequirements: string
    knowledgePoints: string[]
  } | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [config: {
    knowledgePoints: string[]
    questionTypes: ExerciseType[]
    questionCount: number
    difficultyDistribution: DifficultyDistribution
    extraRequirements: string
  }]
}>()

const questionTypes = ref<ExerciseType[]>(['single_choice', 'multi_choice', 'judge', 'fill_blank'])
const difficultyDistribution = ref<DifficultyDistribution>({ easy: 2, medium: 2, hard: 1 })
const extraRequirements = ref('')
const knowledgePoints = ref<string[]>([])

const questionTypeOptions = [
  { label: exerciseTypeLabels.single_choice, value: 'single_choice' as ExerciseType },
  { label: exerciseTypeLabels.multi_choice, value: 'multi_choice' as ExerciseType },
  { label: exerciseTypeLabels.judge, value: 'judge' as ExerciseType },
  { label: exerciseTypeLabels.fill_blank, value: 'fill_blank' as ExerciseType },
]

const totalCount = computed(() =>
  difficultyDistribution.value.easy +
  difficultyDistribution.value.medium +
  difficultyDistribution.value.hard,
)

watch(
  () => props.visible,
  (open) => {
    if (!open || !props.initialConfig) return
    questionTypes.value = [...props.initialConfig.questionTypes]
    difficultyDistribution.value = { ...props.initialConfig.difficultyDistribution }
    extraRequirements.value = props.initialConfig.extraRequirements
    knowledgePoints.value = [...props.initialConfig.knowledgePoints]
  },
)

function handleConfirm(): void {
  if (!questionTypes.value.length) {
    ElMessage.warning('请至少选择一种题型')
    return
  }
  if (totalCount.value === 0) {
    ElMessage.warning('请至少分配 1 道题')
    return
  }
  emit('confirm', {
    knowledgePoints: knowledgePoints.value,
    questionTypes: questionTypes.value,
    questionCount: totalCount.value,
    difficultyDistribution: { ...difficultyDistribution.value },
    extraRequirements: extraRequirements.value,
  })
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="AI 补题"
    width="520px"
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

      <el-form-item label="难度分布">
        <div class="diff-row">
          <span class="diff easy">简单</span>
          <el-input-number v-model="difficultyDistribution.easy" :min="0" :max="20" size="small" />
          <span class="diff medium">中等</span>
          <el-input-number v-model="difficultyDistribution.medium" :min="0" :max="20" size="small" />
          <span class="diff hard">困难</span>
          <el-input-number v-model="difficultyDistribution.hard" :min="0" :max="20" size="small" />
          <span class="total">共 {{ totalCount }} 题</span>
        </div>
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

.diff-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;

  .diff {
    font-size: 13px;
    &.easy { color: #67c23a; }
    &.medium { color: #e6a23c; }
    &.hard { color: #f56c6c; }
  }

  .total {
    font-size: 13px;
    color: #64748b;
    margin-left: 4px;
  }
}
</style>
