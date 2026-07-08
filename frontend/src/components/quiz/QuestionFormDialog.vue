<!--
  题目编辑/新增对话框（题库与 AI 出题复用）
-->
<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { DifficultyLevel, ExerciseType, QuizQuestion } from '@/types'
import { difficultyLabels, exerciseTypeLabels } from '@/utils/exerciseJudge'

const props = defineProps<{
  modelValue: boolean
  question: QuizQuestion | null
  knowledgePointOptions: string[]
  mode?: 'create' | 'edit'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [question: QuizQuestion]
}>()

const form = ref<QuizQuestion | null>(null)

const typeOptions = computed(() =>
  (['single_choice', 'multi_choice', 'judge', 'fill_blank'] as ExerciseType[]).map((t) => ({
    label: exerciseTypeLabels[t],
    value: t,
  })),
)

const difficultyOptions = computed(() =>
  (['easy', 'medium', 'hard'] as DifficultyLevel[]).map((d) => ({
    label: difficultyLabels[d],
    value: d,
  })),
)

watch(
  () => props.question,
  (q) => {
    if (!q) {
      form.value = null
      return
    }
    form.value = {
      ...q,
      options: q.options ? q.options.map((o) => ({ ...o })) : undefined,
      answerList: q.answerList ? [...q.answerList] : undefined,
    }
  },
  { immediate: true },
)

function ensureOptions(): void {
  if (!form.value) return
  if (form.value.type === 'single_choice' || form.value.type === 'multi_choice') {
    if (!form.value.options?.length) {
      form.value.options = [
        { key: 'A', text: '' },
        { key: 'B', text: '' },
        { key: 'C', text: '' },
        { key: 'D', text: '' },
      ]
    }
  }
}

watch(
  () => form.value?.type,
  () => ensureOptions(),
)

function handleSave(): void {
  if (!form.value) return
  emit('save', { ...form.value })
  emit('update:modelValue', false)
}

function close(): void {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="mode === 'create' ? '新增题目' : '编辑题目'"
    width="640px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form v-if="form" label-width="90px">
      <el-form-item label="题型">
        <el-select v-model="form.type" style="width: 100%">
          <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="知识点">
        <el-select v-model="form.knowledgePoint" filterable allow-create style="width: 100%">
          <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
        </el-select>
      </el-form-item>
      <el-form-item label="难度">
        <el-radio-group v-model="form.difficulty">
          <el-radio v-for="d in difficultyOptions" :key="d.value" :value="d.value">{{ d.label }}</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="分值">
        <el-input-number v-model="form.score" :min="1" :max="100" />
      </el-form-item>
      <el-form-item label="题干">
        <el-input v-model="form.stem" type="textarea" :rows="3" />
      </el-form-item>

      <template v-if="form.type === 'single_choice' || form.type === 'multi_choice'">
        <el-form-item v-for="opt in form.options" :key="opt.key" :label="`选项 ${opt.key}`">
          <el-input v-model="opt.text" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input v-model="form.answer" :placeholder="form.type === 'multi_choice' ? '如 ABD' : '如 A'" />
        </el-form-item>
      </template>

      <template v-else-if="form.type === 'judge'">
        <el-form-item label="参考答案">
          <el-radio-group v-model="form.answer">
            <el-radio value="true">正确</el-radio>
            <el-radio value="false">错误</el-radio>
          </el-radio-group>
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="参考答案">
          <el-input v-model="form.answer" />
        </el-form-item>
        <el-form-item label="等价答案">
          <el-input
            :model-value="form.answerList?.join('、') || ''"
            placeholder="多个等价答案用顿号分隔"
            @update:model-value="form.answerList = String($event).split('、').map((s) => s.trim()).filter(Boolean)"
          />
        </el-form-item>
      </template>

      <el-form-item label="解析">
        <el-input v-model="form.explanation" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>
