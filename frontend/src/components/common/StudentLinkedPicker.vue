<!--
  姓名 / 学号关联下拉选择
  两个下拉框共享同一选中值，选姓名联动学号，选学号联动姓名
-->
<script setup lang="ts">
import type { LinkedStudentOption } from '@/types'

defineProps<{
  modelValue?: number | string
  students: LinkedStudentOption[]
  loading?: boolean
  nameWidth?: string
  noWidth?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | string | undefined]
}>()
</script>

<template>
  <el-select
    :model-value="modelValue"
    placeholder="姓名"
    filterable
    clearable
    :loading="loading"
    :style="{ width: nameWidth ?? '120px' }"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-option
      v-for="s in students"
      :key="`name-${s.id}`"
      :label="s.studentName"
      :value="s.id"
    />
  </el-select>
  <el-select
    :model-value="modelValue"
    placeholder="学号"
    filterable
    clearable
    :loading="loading"
    :style="{ width: noWidth ?? '140px' }"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-option
      v-for="s in students"
      :key="`no-${s.id}`"
      :label="s.studentNo"
      :value="s.id"
    />
  </el-select>
</template>
