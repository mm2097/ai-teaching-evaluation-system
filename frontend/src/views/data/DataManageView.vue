<!--
  教学数据管理页面
  支持多条件查询、编辑、删除与导出
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download, Delete } from '@element-plus/icons-vue'
import { teachingDataList, semesterOptions } from '@/mock'

/** 查询条件 */
const query = ref({
  keyword: '',
  semester: '',
  dataType: '',
})

/** 表格数据（支持前端筛选演示） */
const tableData = ref([...teachingDataList])

/** 分页 */
const currentPage = ref(1)
const pageSize = ref(10)

/** 筛选后的数据 */
const filteredData = computed(() => {
  return tableData.value.filter((item) => {
    if (query.value.keyword) {
      const kw = query.value.keyword.toLowerCase()
      if (!item.studentName.includes(kw) && !item.studentId.includes(kw) && !item.courseName.includes(kw)) {
        return false
      }
    }
    if (query.value.semester && item.semester !== query.value.semester) return false
    if (query.value.dataType && item.dataType !== query.value.dataType) return false
    return true
  })
})

/** 分页数据 */
const pagedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

/** 编辑对话框 */
const editVisible = ref(false)
const editForm = ref({ ...teachingDataList[0]! })

/** 选中行 */
const selectedRows = ref<typeof teachingDataList>([])

/**
 * 打开编辑对话框
 * @param row 当前行数据
 */
function handleEdit(row: (typeof teachingDataList)[0]): void {
  editForm.value = { ...row }
  editVisible.value = true
}

/**
 * 保存编辑
 */
function saveEdit(): void {
  const idx = tableData.value.findIndex((item) => item.id === editForm.value.id)
  if (idx !== -1) {
    tableData.value[idx] = { ...editForm.value }
  }
  editVisible.value = false
  ElMessage.success('数据修改成功')
}

/**
 * 删除单条数据
 */
async function handleDelete(row: (typeof teachingDataList)[0]): Promise<void> {
  await ElMessageBox.confirm(`确定删除 ${row.studentName} 的 ${row.courseName} 记录吗？`, '删除确认', { type: 'warning' })
  tableData.value = tableData.value.filter((item) => item.id !== row.id)
  ElMessage.success('删除成功')
}

/**
 * 批量删除
 */
async function handleBatchDelete(): Promise<void> {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的数据')
    return
  }
  await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 条数据吗？`, '批量删除', { type: 'warning' })
  const ids = selectedRows.value.map((r) => r.id)
  tableData.value = tableData.value.filter((item) => !ids.includes(item.id))
  ElMessage.success('批量删除成功')
}

/**
 * 导出 Excel（演示提示）
 */
function handleExport(): void {
  ElMessage.success('数据导出成功，文件已保存至下载目录')
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <!-- 查询栏 -->
      <div class="table-toolbar">
        <div class="filter-bar" style="margin-bottom: 0">
          <el-input
            v-model="query.keyword"
            placeholder="搜索学号/姓名/课程"
            :prefix-icon="Search"
            clearable
            style="width: 240px"
          />
          <el-select v-model="query.semester" placeholder="学期" clearable style="width: 180px">
            <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-select v-model="query.dataType" placeholder="数据类型" clearable style="width: 140px">
            <el-option label="成绩" value="成绩" />
            <el-option label="考勤" value="考勤" />
            <el-option label="作业" value="作业" />
          </el-select>
        </div>
        <div>
          <el-button type="danger" :icon="Delete" plain @click="handleBatchDelete">批量删除</el-button>
          <el-button type="primary" :icon="Download" @click="handleExport">导出 Excel</el-button>
        </div>
      </div>

      <!-- 数据表格 -->
      <el-table
        :data="pagedData"
        stripe
        border
        @selection-change="(rows: typeof teachingDataList) => (selectedRows = rows)"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="studentId" label="学号" width="130" />
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="courseId" label="课程号" width="100" />
        <el-table-column prop="courseName" label="课程名" />
        <el-table-column prop="semester" label="学期" width="100" />
        <el-table-column prop="score" label="分数" width="80" align="center" />
        <el-table-column prop="attendance" label="考勤" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.attendance === '正常' ? 'success' : row.attendance === '缺勤' ? 'danger' : 'warning'" size="small">
              {{ row.attendance }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="homework" label="作业" width="90" align="center" />
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="filteredData.length"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editVisible" title="编辑数据" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="学号"><el-input v-model="editForm.studentId" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="editForm.studentName" /></el-form-item>
        <el-form-item label="分数"><el-input-number v-model="editForm.score" :min="0" :max="100" /></el-form-item>
        <el-form-item label="考勤">
          <el-select v-model="editForm.attendance" style="width: 100%">
            <el-option label="正常" value="正常" />
            <el-option label="迟到" value="迟到" />
            <el-option label="缺勤" value="缺勤" />
          </el-select>
        </el-form-item>
        <el-form-item label="作业">
          <el-select v-model="editForm.homework" style="width: 100%">
            <el-option label="已提交" value="已提交" />
            <el-option label="未提交" value="未提交" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
