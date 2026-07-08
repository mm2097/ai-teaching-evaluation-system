<!--
  AI 分析筛选栏
  单课程/单班级维度筛选，学生通过姓名/学号关联下拉选择
-->
<script setup lang="ts">
import { targetTypeOptions } from '@/api/analysis'
import StudentLinkedPicker from '@/components/common/StudentLinkedPicker.vue'
import type { LinkedStudentOption, TargetType } from '@/types'

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
  showQueryButton?: boolean
  studentList?: LinkedStudentOption[]
  studentLoading?: boolean
  deptId?: number
  classId?: number
  courseId?: number
  targetId?: number
  classOptions: { label: string; value: number }[]
  courseOptions: { label: string; value: number }[]
}>()

const emit = defineEmits<{
  'update:targetType': [value: TargetType]
  'update:semesterId': [value: number]
  'update:deptId': [value: number | undefined]
  'update:classId': [value: number | undefined]
  'update:courseId': [value: number | undefined]
  'update:targetId': [value: number | undefined]
  query: []
}>()

const filteredTargetTypes = targetTypeOptions.filter((o) =>
  props.allowedTargetTypes.includes(o.value),
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

    <StudentLinkedPicker
      v-if="showStudentPicker"
      :model-value="targetId"
      :students="studentList ?? []"
      :loading="studentLoading"
      @update:model-value="emit('update:targetId', $event)"
    />

    <el-button v-if="showQueryButton" type="primary" @click="emit('query')">查询</el-button>
  </div>
</template>

<style scoped lang="scss">
.analysis-filter {
  margin-bottom: 0;
}
</style>
