<!--
  AI 分析筛选栏
  单课程/单班级维度筛选，支持学生模糊搜索
-->
<script setup lang="ts">
import { ref } from 'vue'
import { targetTypeOptions } from '@/api/analysis'
import type { TargetType } from '@/types'

const props = defineProps<{
  allowedTargetTypes: TargetType[]
  targetType: TargetType
  semesterId: number
  semesterOptions: { label: string; value: number }[]
  showDeptFilter: boolean
  showClassFilter: boolean
  showCourseFilter: boolean
  showTargetTypeFilter: boolean
  showStudentPicker: boolean
  enableStudentSearch?: boolean
  deptId?: number
  classId?: number
  courseId?: number
  targetId?: number
  classOptions: { label: string; value: number }[]
  courseOptions: { label: string; value: number }[]
  targetOptions: { label: string; value: number }[]
}>()

const emit = defineEmits<{
  'update:targetType': [value: TargetType]
  'update:semesterId': [value: number]
  'update:deptId': [value: number | undefined]
  'update:classId': [value: number | undefined]
  'update:courseId': [value: number | undefined]
  'update:targetId': [value: number | undefined]
  'student-search': [keyword: string]
}>()

const studentSearchLoading = ref(false)

const filteredTargetTypes = targetTypeOptions.filter((o) =>
  props.allowedTargetTypes.includes(o.value),
)

async function handleStudentSearch(keyword: string): Promise<void> {
  if (!props.enableStudentSearch) return
  studentSearchLoading.value = true
  emit('student-search', keyword)
  studentSearchLoading.value = false
}
</script>

<template>
  <div class="filter-bar analysis-filter">
    <el-select
      v-if="showTargetTypeFilter"
      :model-value="targetType"
      placeholder="分析对象"
      style="width: 130px"
      @update:model-value="emit('update:targetType', $event)"
    >
      <el-option
        v-for="opt in filteredTargetTypes"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>

    <el-select
      :model-value="semesterId"
      placeholder="学期"
      style="width: 220px"
      @update:model-value="emit('update:semesterId', $event)"
    >
      <el-option
        v-for="opt in semesterOptions"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>

    <el-select
      v-if="showClassFilter"
      :model-value="classId"
      placeholder="班级"
      clearable
      style="width: 140px"
      @update:model-value="emit('update:classId', $event)"
    >
      <el-option
        v-for="opt in classOptions"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>

    <el-select
      v-if="showCourseFilter"
      :model-value="courseId"
      placeholder="课程"
      clearable
      style="width: 160px"
      @update:model-value="emit('update:courseId', $event)"
    >
      <el-option
        v-for="opt in courseOptions"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>

    <el-select
      v-if="showStudentPicker && enableStudentSearch"
      :model-value="targetId"
      placeholder="搜索学生（姓名/学号）"
      filterable
      remote
      :remote-method="handleStudentSearch"
      :loading="studentSearchLoading"
      style="width: 240px"
      @update:model-value="emit('update:targetId', $event)"
    >
      <el-option
        v-for="opt in targetOptions"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>

    <el-select
      v-else-if="showStudentPicker"
      :model-value="targetId"
      placeholder="选择学生"
      style="width: 200px"
      @update:model-value="emit('update:targetId', $event)"
    >
      <el-option
        v-for="opt in targetOptions"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>
  </div>
</template>

<style scoped lang="scss">
.analysis-filter {
  margin-bottom: 0;
}
</style>
