<!--
  教学数据管理页面
  支持多条件查询、编辑、删除与导出
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, Document, View } from '@element-plus/icons-vue'
import DataFlowNav from '@/components/common/DataFlowNav.vue'
import StudentLinkedPicker from '@/components/common/StudentLinkedPicker.vue'
import { fetchSemesters, fetchDepartments, fetchCourses } from '@/api/dict'
import { fetchTeachingData, updateRowData, exportTeachingData, deleteTeachingData, batchDeleteTeachingDataRecords, clearTeachingDataByType } from '@/api/teachingData'
import { useDictCascade } from '@/composables/useDictCascade'
import { useDataFlowStore } from '@/stores/dataFlow'
import { useUserStore } from '@/stores/user'
import type { LinkedStudentOption, TeachingDataRecord } from '@/types'

const dataFlowStore = useDataFlowStore()
const userStore = useUserStore()
const { deptId, majorId, classId, majorOptions, classOptions } = useDictCascade()

const semesterOptions = ref<{ label: string; value: string }[]>([])
const departmentOptions = ref<{ label: string; value: number; id?: number }[]>([])
const courseOptions = ref<{ label: string; value: number }[]>([])
const courseId = ref<number | undefined>()
const loading = ref(false)
const dataTypeLabels: Record<string, string> = { score: '成绩', attendance: '考勤', participation: '课堂参与' }

async function loadTeachingData(): Promise<void> {
  if (!courseId.value) {
    tableData.value = []
    return
  }
  const courseName = courseOptions.value.find((c) => c.value === courseId.value)?.label || ''
  loading.value = true
  try {
    const { list } = await fetchTeachingData(
      {
        courseId: courseId.value,
        dataType: query.value.dataType === 'score'
          || query.value.dataType === 'attendance'
          || query.value.dataType === 'participation'
          ? query.value.dataType
          : undefined,
        pageSize: 10000,  // 一次性加载全部数据，确保客户端学期筛选覆盖所有记录
      },
      courseName,
    )
    tableData.value = list
    enrichRowIds()
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

/** 用院系/专业字典把行数据的名称字段映射为筛选 ID（后端只返回班级 ID 与名称） */
function enrichRowIds(): void {
  const deptIdByName = new Map(departmentOptions.value.map((d) => [d.label, d.value]))
  const majorIdByName = new Map(majorOptions.value.map((m) => [m.label, m.value]))
  tableData.value = tableData.value.map((row) => ({
    ...row,
    deptId: row.college ? (deptIdByName.get(row.college) ?? 0) : 0,
    majorId: row.major ? (majorIdByName.get(row.major) ?? 0) : 0,
  }))
}

onMounted(async () => {
  try {
    const [semRes, deptRes, courses] = await Promise.all([
      fetchSemesters(),
      fetchDepartments(),
      fetchCourses({
        teacherId: userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined,
      }),
    ])
    semesterOptions.value = semRes.map(s => ({ label: s.semesterName, value: s.semesterCode }))
    departmentOptions.value = deptRes.map(d => ({ label: d.deptName, value: d.id, id: d.id }))
    courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
    if (courseOptions.value.length) {
      courseId.value = courseOptions.value[0]!.value
      await loadTeachingData()
    }
  } catch { /* empty */ }
})

const query = ref({
  courseName: '',
  semester: '',
  dataType: '' as '' | 'score' | 'attendance' | 'participation',
  sourceFile: '',
})

/**
 * 课程筛选（合并下拉选择与名称输入）：
 * - 下拉选中课程，或输入内容与课程名完全一致 → 切换 courseId 并重新加载数据
 * - 输入其他文本 → 作为课程名称关键词，过滤当前已加载的数据
 */
const courseQuery = computed<string | number | undefined>({
  get: () => query.value.courseName || courseId.value,
  set: (val) => {
    if (val === undefined || val === null || val === '') {
      courseId.value = undefined
      query.value.courseName = ''
      return
    }
    if (typeof val === 'number') {
      courseId.value = val
      query.value.courseName = ''
      return
    }
    const matched = courseOptions.value.find((c) => c.label === val)
    if (matched) {
      courseId.value = matched.value
      query.value.courseName = ''
    } else {
      query.value.courseName = val
    }
  },
})

const selectedStudentId = ref<string | number | undefined>()

const tableData = ref<TeachingDataRecord[]>([])

/** 字典加载完成后重新补全行数据的院系/专业 ID（避免与字典接口的加载时序竞争） */
watch([departmentOptions, majorOptions], () => enrichRowIds())

/** 是否属于各题扣分子行（如"期中考试-第1大题"），这类行只在详情弹窗中展示 */
function isQuestionDetailRow(row: TeachingDataRecord): boolean {
  return row.dataType === 'score' && /-第\d+\s*大题/.test(row.batchName || '')
}

/** 主表格展示的数据：隐藏各题扣分子行和重复考勤行，只保留汇总行 */
const displayData = computed(() => {
  const seenAttendance = new Set<string>()
  return tableData.value.filter((row) => {
    // 隐藏各题扣分子行
    if (isQuestionDetailRow(row)) return false
    // 考勤：按 sourceData 去重（同一上传行只显示一条）
    if (row.dataType === 'attendance' && row.sourceData) {
      if (seenAttendance.has(row.sourceData)) return false
      seenAttendance.add(row.sourceData)
    }
    return true
  })
})

/** 从考勤行的 sourceData 中解析到课率（0-1 的小数） */
function getAttendanceRate(row: TeachingDataRecord): number {
  if (!row.sourceData) return 0
  try {
    const obj = JSON.parse(row.sourceData) as Record<string, unknown>
    const raw = obj['到课率']
    if (raw === null || raw === undefined || raw === '') return 0
    const num = Number(raw)
    // 如果是 >1 的百分比值（如 93.75），转为小数
    return num > 1 ? num / 100 : num
  } catch {
    return 0
  }
}

/** 格式化到课率为百分比显示 */
function formatRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

/** 编辑弹窗中不可修改的字段（标识信息） */
const READONLY_FIELDS = new Set(['编号', '课程号', '课程名称', '学期', '测试名称', '学号', '姓名', '来源文件'])

function isReadonlyField(key: string): boolean {
  return READONLY_FIELDS.has(key)
}

const currentPage = ref(1)
const pageSize = ref(10)

const studentPickerOptions = computed<LinkedStudentOption[]>(() => {
  const map = new Map<string, LinkedStudentOption>()
  for (const item of displayData.value) {
    if (deptId.value && item.deptId !== deptId.value) continue
    if (majorId.value && item.majorId !== majorId.value) continue
    if (classId.value && item.classId !== classId.value) continue
    if (!map.has(item.studentId)) {
      map.set(item.studentId, {
        id: item.studentId,
        studentName: item.studentName,
        studentNo: item.studentId,
      })
    }
  }
  return [...map.values()].sort((a, b) => a.studentName.localeCompare(b.studentName, 'zh-CN'))
})

const filteredData = computed(() => {
  return displayData.value.filter((item) => {
    if (selectedStudentId.value && item.studentId !== selectedStudentId.value) return false
    if (query.value.courseName) {
      const courseKw = query.value.courseName.toLowerCase()
      if (!item.courseName.toLowerCase().includes(courseKw)) return false
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
  const files = [...new Set(displayData.value.map((d) => d.sourceFileName).filter(Boolean))]
  return files as string[]
})

watch(courseId, async () => {
  currentPage.value = 1
  await loadTeachingData()
})

watch([query, deptId, majorId, classId, selectedStudentId], () => {
  currentPage.value = 1
}, { deep: true })

watch(() => query.value.dataType, async () => {
  await loadTeachingData()
})

watch([deptId, majorId, classId], () => {
  if (
    selectedStudentId.value
    && !studentPickerOptions.value.some((s) => s.id === selectedStudentId.value)
  ) {
    selectedStudentId.value = undefined
  }
})

const editVisible = ref(false)
const editRecordId = ref(0)
const editTitle = ref('')
/** 可编辑的字段列表 [{ key, value }] */
const editFields = ref<{ key: string; value: string }[]>([])
const selectedRows = ref<TeachingDataRecord[]>([])

function handleEdit(row: TeachingDataRecord): void {
  editRecordId.value = row.id
  editTitle.value = `${row.studentName}（${row.studentId}）- ${row.batchName || row.courseName || ''}`

  if (row.sourceData) {
    try {
      const obj = JSON.parse(row.sourceData) as Record<string, unknown>
      editFields.value = Object.entries(obj).map(([key, val]) => ({
        key,
        value: val === null || val === undefined ? '' : String(val),
      }))
    } catch {
      editFields.value = []
    }
  }
  if (editFields.value.length === 0) {
    editFields.value = [
      { key: '学号', value: row.studentId },
      { key: '姓名', value: row.studentName },
      { key: '分数', value: row.score !== undefined ? String(row.score) : '' },
    ]
  }
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  const srcData: Record<string, unknown> = {}
  for (const f of editFields.value) {
    srcData[f.key] = f.value
  }

  try {
    await updateRowData(editRecordId.value, srcData)
    await loadTeachingData()
    editVisible.value = false
    ElMessage.success('数据修改成功')
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { detail?: unknown } } }
    const detail = axiosErr?.response?.data?.detail
    console.error('[saveEdit] response.data:', axiosErr?.response?.data)
    console.error('[saveEdit] error:', err)
    const msg = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg).join('; ')
      : typeof detail === 'string' ? detail : (err as Error)?.message || '请稍后重试'
    ElMessage.error(`修改失败：${msg}`)
  }
}

/** 将记录映射为后端删除接口所需的 recordType */
function recordTypeOf(row: TeachingDataRecord): string {
  if (row.subType) return row.subType
  return row.dataType === 'score' ? 'score' : 'attendance'
}

async function handleDelete(row: TeachingDataRecord): Promise<void> {
  await ElMessageBox.confirm(`确定删除 ${row.studentName} 的 ${row.courseName} 记录吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteTeachingData(recordTypeOf(row), row.id)
    ElMessage.success('删除成功')
    await loadTeachingData()
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  }
}

async function handleBatchDelete(): Promise<void> {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的数据')
    return
  }
  await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 条数据吗？`, '批量删除', { type: 'warning' })
  try {
    await batchDeleteTeachingDataRecords(selectedRows.value.map((row) => ({ recordType: row.recordType, recordId: row.id })))
    selectedRows.value = []
    ElMessage.success(`已删除选中数据`)
    await loadTeachingData()
  } catch {
    ElMessage.error('部分数据删除失败，请稍后重试')
  }
}

/** 一键清空当前课程某一数据类型的全部记录（需先在筛选栏选择数据类型） */
async function handleClearAll(): Promise<void> {
  if (!courseId.value) {
    ElMessage.warning('请先选择课程')
    return
  }
  if (!query.value.dataType) {
    ElMessage.warning('请先在「数据类型」筛选中选择要清空的类型（成绩/考勤/课堂参与）')
    return
  }
  const typeName = dataTypeLabels[query.value.dataType]
  const courseName = courseOptions.value.find((c) => c.value === courseId.value)?.label || ''
  await ElMessageBox.confirm(
    `将删除课程「${courseName}」的全部「${typeName}」数据（含各考核批次下的记录），该操作不可恢复，是否继续？`,
    '清空确认',
    { type: 'warning', confirmButtonText: '确认清空', cancelButtonText: '取消' },
  )
  try {
    const { deleted } = await clearTeachingDataByType(courseId.value, query.value.dataType)
    selectedRows.value = []
    ElMessage.success(`已清空「${typeName}」数据（${deleted} 条）`)
    await loadTeachingData()
  } catch {
    ElMessage.error('清空失败，请稍后重试')
  }
}

// --------------------------------------------------------------------------
// 详情弹窗
// --------------------------------------------------------------------------
const detailVisible = ref(false)
const detailTitle = ref('')
/** 解析后的原始上传行数据 [{ key, value }] */
const detailFields = ref<{ key: string; value: string }[]>([])

function handleDetail(row: TeachingDataRecord): void {
  detailTitle.value = `${row.studentName}（${row.studentId}）- ${row.batchName || row.courseName || ''}`
  detailFields.value = []
  if (row.sourceData) {
    try {
      const obj = JSON.parse(row.sourceData) as Record<string, unknown>
      detailFields.value = Object.entries(obj).map(([key, val]) => ({
        key,
        value: val === null || val === undefined ? '' : String(val),
      }))
    } catch {
      detailFields.value = []
    }
  }
  // 如果无 sourceData，回退显示当前行的基本字段
  if (detailFields.value.length === 0) {
    detailFields.value = [
      { key: '学号', value: row.studentId },
      { key: '姓名', value: row.studentName },
      { key: '课程', value: row.courseName || String(row.courseId) },
      { key: '数据类型', value: dataTypeLabels[row.dataType] || row.dataType },
      { key: '分数', value: row.score !== undefined ? String(row.score) : '-' },
      { key: '考勤', value: row.attendance || '-' },
      { key: '备注', value: row.remark || '-' },
    ]
  }
  detailVisible.value = true
}

const exporting = ref(false)

async function handleExport(): Promise<void> {
  if (!courseId.value) {
    ElMessage.warning('请先选择课程')
    return
  }
  exporting.value = true
  try {
    const { blob, filename } = await exportTeachingData({
      courseId: courseId.value,
      // 学生下拉选项的 id 即学号，交给后端做姓名/学号模糊匹配
      keyword: selectedStudentId.value !== undefined ? String(selectedStudentId.value) : undefined,
      dataType: query.value.dataType === 'score'
        || query.value.dataType === 'attendance'
        || query.value.dataType === 'participation'
        ? query.value.dataType
        : undefined,
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('数据导出成功，文件已保存至下载目录')
  } catch {
    ElMessage.error('数据导出失败')
  } finally {
    exporting.value = false
  }
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
          <el-select
            v-model="courseQuery"
            placeholder="课程（可下拉或输入名称）"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 240px"
          >
            <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
          <StudentLinkedPicker
            v-model="selectedStudentId"
            :students="studentPickerOptions"
          />
          <el-select v-model="query.semester" placeholder="学期" clearable style="width: 200px">
            <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-select v-model="query.dataType" placeholder="数据类型" clearable style="width: 120px">
            <el-option label="成绩" value="score" />
            <el-option label="考勤" value="attendance" />
            <el-option label="课堂参与" value="participation" />
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
          <el-button type="danger" :icon="Delete" plain @click="handleClearAll">清空全部</el-button>
          <el-button type="primary" :icon="Download" :loading="exporting" @click="handleExport">导出 Excel</el-button>
        </div>
      </div>

      <el-table
        v-loading="loading"
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
        <el-table-column prop="dataType" label="类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.dataType === 'score'" size="small" type="success">
              {{ row.batchName || '成绩' }}
            </el-tag>
            <el-tag v-else-if="row.dataType === 'participation'" size="small" type="warning">
              {{ dataTypeLabels[row.dataType] }}
            </el-tag>
            <el-tag v-else size="small">{{ dataTypeLabels[row.dataType] }}</el-tag>
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
        <el-table-column label="到课率" width="90" align="center">
          <template #default="{ row }">
            <template v-if="row.dataType === 'attendance' && row.sourceData">
              <span :style="{ color: getAttendanceRate(row) >= 0.9 ? '#67c23a' : getAttendanceRate(row) >= 0.7 ? '#e6a23c' : '#f56c6c' }">
                {{ formatRate(getAttendanceRate(row)) }}
              </span>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="课堂参与度" width="100" align="center">
          <template #default="{ row }">
            <template v-if="row.dataType === 'participation' && row.participationRate != null">
              <span :style="{ color: row.participationRate >= 0.9 ? '#67c23a' : row.participationRate >= 0.7 ? '#e6a23c' : '#f56c6c' }">
                {{ formatRate(row.participationRate) }}
              </span>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="success" link size="small" :icon="View" @click="handleDetail(row)">详情</el-button>
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

    <!-- 编辑弹窗：全字段可编辑 -->
    <el-dialog v-model="editVisible" :title="editTitle" width="650px" destroy-on-close>
      <template v-if="editFields.length === 0">
        <el-empty description="无可编辑字段" />
      </template>
      <el-form v-else label-width="180px" style="max-height: 500px; overflow-y: auto">
        <el-form-item
          v-for="(field, idx) in editFields"
          :key="idx"
          :label="field.key"
        >
          <el-input
            v-model="field.value"
            :placeholder="field.key"
            :disabled="isReadonlyField(field.key)"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗：显示原始上传行数据（表头-值对照） -->
    <el-dialog v-model="detailVisible" :title="detailTitle" width="650px" destroy-on-close>
      <template v-if="detailFields.length === 0">
        <el-empty description="暂无原始行数据" />
      </template>
      <el-table v-else :data="detailFields" border size="small" max-height="500">
        <el-table-column prop="key" label="字段" width="200" />
        <el-table-column prop="value" label="值">
          <template #default="{ row: r }">
            <span :style="{ color: r.value === '' ? '#c0c4cc' : '' }">{{ r.value || '（空）' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

