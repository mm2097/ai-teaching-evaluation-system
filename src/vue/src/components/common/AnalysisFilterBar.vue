<!--
  AI 分析筛选栏
  根据用户角色展示不同的 target_type 及级联筛选条件
-->
<script setup lang="ts">
import { computed } from 'vue'
import { targetTypeOptions } from '@/api/analysis'
import { departmentOptions } from '@/mock'
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
}>()

const filteredTargetTypes = computed(() =>
  targetTypeOptions.filter((o) => props.allowedTargetTypes.includes(o.value)),
)

const deptSelectOptions = computed(() =>
  departmentOptions.filter((d) => d.value !== ''),
)
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
      v-if="showDeptFilter"
      :model-value="deptId"
      placeholder="院系"
      clearable
      style="width: 160px"
      @update:model-value="emit('update:deptId', $event)"
    >
      <el-option
        v-for="opt in deptSelectOptions"
        :key="opt.id"
        :label="opt.label"
        :value="opt.id"
      />
    </el-select>

    <el-select
      v-if="showClassFilter && targetType !== 'teacher'"
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
      v-if="showStudentPicker"
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
  margin-bottom: 16px;
}
</style>
