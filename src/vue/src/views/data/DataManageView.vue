<!--
  教学数据管理页面
  支持多条件查询、编辑、删除与导出
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download, Delete, Document } from '@element-plus/icons-vue'
import DataFlowNav from '@/components/common/DataFlowNav.vue'
import { teachingDataList, semesterOptions, departmentOptions, dataTypeLabels } from '@/mock'
import { useDictCascade } from '@/composables/useDictCascade'
import { useDataFlowStore } from '@/stores/dataFlow'
import type { TeachingDataRecord } from '@/types'

const dataFlowStore = useDataFlowStore()
const { deptId, majorId, classId, majorOptions, classOptions } = useDictCascade()

const query = ref({
  keyword: '',
  semester: '',
  dataType: '' as '' | 'score' | 'attendance' | 'assignment',
  sourceFile: '',
})

const tableData = ref<TeachingDataRecord[]>([...teachingDataList])
const currentPage = ref(1)
const pageSize = ref(10)

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
    if (deptId.value && item.deptId !== deptId.value) return false
    if (majorId.value && item.majorId !== majorId.value) return false
    if (classId.value && item.classId !== classId.value) return false
    if (query.value.sourceFile === 'current' && dataFlowStore.currentImportLog) {
      if (item.sourceFileName !== dataFlowStore.currentImportLog.fileName) return false
    } else if (query.value.sourceFile && query.value.sourceFile !== 'current') {
      if (item.sourceFileName !== query.value.sourceFile) return false
    }
    return true
  })
})

const pagedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const sourceFileOptions = computed(() => {
  const files = [...new Set(tableData.value.map((d) => d.sourceFileName).filter(Boolean))]
  return files as string[]
})

watch([query, deptId, majorId, classId], () => {
  currentPage.value = 1
}, { deep: true })

const editVisible = ref(false)
const editForm = ref<TeachingDataRecord>({ ...teachingDataList[0]! })
const selectedRows = ref<TeachingDataRecord[]>([])

function handleEdit(row: TeachingDataRecord): void {
  editForm.value = { ...row }
  editVisible.value = true
}

function saveEdit(): void {
  const idx = tableData.value.findIndex((item) => item.id === editForm.value.id)
  if (idx !== -1) {
    tableData.value[idx] = { ...editForm.value }
  }
  editVisible.value = false
  ElMessage.success('数据修改成功')
}

async function handleDelete(row: TeachingDataRecord): Promise<void> {
  await ElMessageBox.confirm(`确定删除 ${row.studentName} 的 ${row.courseName} 记录吗？`, '删除确认', { type: 'warning' })
  tableData.value = tableData.value.filter((item) => item.id !== row.id)
  ElMessage.success('删除成功')
}

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

function handleExport(): void {
  ElMessage.success('数据导出成功，文件已保存至下载目录')
}

function filterByCurrentFile(): void {
  query.value.sourceFile = query.value.sourceFile === 'current' ? '' : 'current'
}
</script>

<template>
  <div class="page-container">
    <DataFlowNav />

    <div class="content-card">
      <div class="table-toolbar">
        <div class="filter-bar" style="margin-bottom: 0">
          <el-input
            v-model="query.keyword"
            placeholder="搜索学号/姓名/课程"
            :prefix-icon="Search"
            clearable
            style="width: 200px"
          />
          <el-select v-model="query.semester" placeholder="学期" clearable style="width: 200px">
            <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-select v-model="query.dataType" placeholder="数据类型" clearable style="width: 120px">
            <el-option label="成绩" value="score" />
            <el-option label="考勤" value="attendance" />
            <el-option label="作业" value="assignment" />
          </el-select>
          <el-select v-model="deptId" placeholder="院系" clearable style="width: 140px">
            <el-option v-for="d in departmentOptions.filter(d => d.id)" :key="d.id" :label="d.label" :value="d.id!" />
          </el-select>
          <el-select v-model="majorId" placeholder="专业" clearable style="width: 160px">
            <el-option v-for="m in majorOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
          <el-select v-model="classId" placeholder="班级" clearable style="width: 130px">
            <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
          <el-select v-model="query.sourceFile" placeholder="来源文件" clearable style="width: 200px">
            <el-option label="当前导入文件" value="current" />
            <el-option v-for="f in sourceFileOptions" :key="f" :label="f" :value="f" />
          </el-select>
        </div>
        <div>
          <el-button
            v-if="dataFlowStore.currentImportLog"
            :type="query.sourceFile === 'current' ? 'primary' : 'default'"
            :icon="Document"
            plain
            @click="filterByCurrentFile"
          >
            {{ dataFlowStore.currentImportLog.fileName }}
          </el-button>
          <el-button type="danger" :icon="Delete" plain @click="handleBatchDelete">批量删除</el-button>
          <el-button type="primary" :icon="Download" @click="handleExport">导出 Excel</el-button>
        </div>
      </div>

      <el-table
        :data="pagedData"
        stripe
        border
        @selection-change="(rows: TeachingDataRecord[]) => (selectedRows = rows)"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="sourceFileName" label="来源文件" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-icon style="vertical-align: -2px"><Document /></el-icon>
            {{ row.sourceFileName || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="dataType" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ dataTypeLabels[row.dataType] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="studentId" label="学号" width="130" />
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="courseId" label="课程号" width="100" />
        <el-table-column prop="courseName" label="课程名" />
        <el-table-column prop="semester" label="学期" width="130" />
        <el-table-column prop="score" label="分数" width="80" align="center">
          <template #default="{ row }">{{ row.score ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="attendance" label="考勤" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.attendance" :type="row.attendance === '正常' ? 'success' : row.attendance === '缺勤' ? 'danger' : 'warning'" size="small">
              {{ row.attendance }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="homework" label="作业" width="90" align="center">
          <template #default="{ row }">{{ row.homework || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

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

    <el-dialog v-model="editVisible" title="编辑数据" width="500px" destroy-on-close>
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="学号"><el-input v-model="editForm.studentId" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="editForm.studentName" /></el-form-item>
        <el-form-item v-if="editForm.dataType === 'score'" label="分数">
          <el-input-number v-model="editForm.score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item v-if="editForm.dataType === 'attendance'" label="考勤">
          <el-select v-model="editForm.attendance" style="width: 100%">
            <el-option label="正常" value="正常" />
            <el-option label="迟到" value="迟到" />
            <el-option label="缺勤" value="缺勤" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.dataType === 'assignment'" label="作业">
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
