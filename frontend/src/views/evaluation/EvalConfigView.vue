<!--
  评价体系配置页面
  管理员配置学生学习质量评价指标、权重与评分规则
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const evalIndicatorConfig = [
  { id: 1, name: '学业成绩', dimension: '学生评价', weight: 40, rule: '基于本课程加权平均分' },
  { id: 2, name: '学习态度', dimension: '学生评价', weight: 25, rule: '基于考勤率与作业提交率' },
  { id: 3, name: '学习进步', dimension: '学生评价', weight: 20, rule: '基于近三次测验/考试成绩变化' },
  { id: 4, name: '知识掌握', dimension: '学生评价', weight: 15, rule: '基于知识点掌握度与 AI 练习得分' },
]

const STUDENT_DIMENSION = '学生评价'

/** 指标列表（可编辑） */
const indicators = ref([...evalIndicatorConfig])

/** 当前选中的评价方案 */
const currentScheme = ref('default')

/** 权重总和校验 */
const totalWeight = computed(() => indicators.value.reduce((sum, item) => sum + item.weight, 0))

/** 编辑对话框 */
const dialogVisible = ref(false)
const editForm = ref({ id: 0, name: '', weight: 0, rule: '' })
const isEdit = ref(false)

/**
 * 新增指标
 */
function handleAdd(): void {
  isEdit.value = false
  editForm.value = { id: 0, name: '', weight: 0, rule: '' }
  dialogVisible.value = true
}

/**
 * 编辑指标
 * @param row 指标行数据
 */
function handleEdit(row: (typeof evalIndicatorConfig)[0]): void {
  isEdit.value = true
  editForm.value = { id: row.id, name: row.name, weight: row.weight, rule: row.rule }
  dialogVisible.value = true
}

/**
 * 删除指标
 */
function handleDelete(id: number): void {
  indicators.value = indicators.value.filter((item) => item.id !== id)
  ElMessage.success('指标已删除')
}

/**
 * 保存指标
 */
function saveIndicator(): void {
  const indicator = { ...editForm.value, dimension: STUDENT_DIMENSION }
  if (isEdit.value) {
    const idx = indicators.value.findIndex((item) => item.id === editForm.value.id)
    if (idx !== -1) indicators.value[idx] = indicator
  } else {
    indicators.value.push({ ...indicator, id: Date.now() })
  }
  dialogVisible.value = false
  ElMessage.success('保存成功')
}

/**
 * 保存评价方案
 */
function saveScheme(): void {
  if (totalWeight.value !== 100) {
    ElMessage.warning(`权重总和为 ${totalWeight.value}%，需调整为 100%`)
    return
  }
  ElMessage.success('评价方案保存成功')
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="table-toolbar">
        <div class="filter-bar" style="margin-bottom: 0">
          <span>评价方案：</span>
          <el-select v-model="currentScheme" style="width: 200px">
            <el-option label="默认评价方案" value="default" />
            <el-option label="2025春季方案" value="2025-spring" />
          </el-select>
          <el-tag type="info" effect="plain">学生评价</el-tag>
          <el-tag :type="totalWeight === 100 ? 'success' : 'danger'" effect="plain">
            权重合计：{{ totalWeight }}%
          </el-tag>
        </div>
        <div>
          <el-button type="primary" @click="handleAdd">新增指标</el-button>
          <el-button type="success" @click="saveScheme">保存方案</el-button>
        </div>
      </div>

      <el-table :data="indicators" stripe border>
        <el-table-column prop="name" label="指标名称" />
        <el-table-column prop="weight" label="权重 (%)" width="120" align="center">
          <template #default="{ row }">
            <el-input-number v-model="row.weight" :min="0" :max="100" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="rule" label="评分规则" show-overflow-tooltip />
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑指标' : '新增指标'" width="500px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="指标名称"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="权重 (%)"><el-input-number v-model="editForm.weight" :min="0" :max="100" /></el-form-item>
        <el-form-item label="评分规则"><el-input v-model="editForm.rule" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveIndicator">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
