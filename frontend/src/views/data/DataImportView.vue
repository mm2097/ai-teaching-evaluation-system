<!--
  多源数据接入页面
  支持数据库直连与 Excel/Txt 文件上传导入
-->
<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Connection, Upload, Document, Right } from '@element-plus/icons-vue'
import DataFlowNav from '@/components/common/DataFlowNav.vue'
import { executeImport, fetchImportLogs } from '@/api/import'
import { useDataFlowStore } from '@/stores/dataFlow'
import { useUserStore } from '@/stores/user'
import { importTypeOptions } from '@/mock'
import type { ImportLog, ImportType } from '@/types'
import { delay } from '@/utils/auth'

const router = useRouter()
const dataFlowStore = useDataFlowStore()
const userStore = useUserStore()

const activeTab = ref('database')
const importType = ref<ImportType>('score')
const importHistory = ref<ImportLog[]>([])

const dbForm = reactive({
  type: 'mysql',
  host: '127.0.0.1',
  port: 3306,
  username: 'root',
  password: '',
  database: 'ai_teaching_analysis',
  table: '',
})

const dbTesting = ref(false)
const dbConnected = ref(false)
const uploadFileList = ref<{ name: string; size: number }[]>([])
const fieldPreview = ref([
  { source: 'student_id', target: '学号', mapped: true },
  { source: 'student_name', target: '姓名', mapped: true },
  { source: 'course_code', target: '课程号', mapped: true },
  { source: 'score', target: '分数', mapped: true },
  { source: 'exam_date', target: '考试时间', mapped: true },
])

const importing = ref(false)
const importResult = ref<ImportLog | null>(null)

onMounted(async () => {
  importHistory.value = await fetchImportLogs()
})

async function testConnection(): Promise<void> {
  dbTesting.value = true
  await delay(1000)
  dbConnected.value = true
  dbTesting.value = false
  ElMessage.success('数据库连接成功！')
}

function getFileName(): string {
  if (activeTab.value === 'file' && uploadFileList.value.length) {
    return uploadFileList.value[0]!.name
  }
  if (activeTab.value === 'database' && dbForm.table) {
    const tableLabels: Record<string, string> = {
      t_score: 't_score（成绩表）',
      t_attendance: 't_attendance（考勤表）',
      t_assignment_submission: 't_assignment_submission（作业提交表）',
      t_student: 't_student（学生表）',
    }
    return tableLabels[dbForm.table] || dbForm.table
  }
  return ''
}

async function handleImport(): Promise<void> {
  const fileName = getFileName()
  if (!fileName) {
    ElMessage.warning('请先选择数据源或上传文件')
    return
  }

  importing.value = true
  importResult.value = null

  const log = await executeImport({
    importType: importType.value,
    dataSource: activeTab.value === 'database' ? 'database' : uploadFileList.value[0]?.name.endsWith('.txt') ? 'txt' : 'excel',
    fileName,
    totalCount: 9868,
    operatorName: userStore.userInfo?.name || '未知',
  })

  importResult.value = log
  dataFlowStore.setLastImportResult(log)
  importHistory.value = await fetchImportLogs()
  importing.value = false
  ElMessage.success('数据导入完成！')
}

function beforeUpload(file: File): boolean {
  uploadFileList.value = [{ name: file.name, size: file.size }]
  ElMessage.success(`文件 "${file.name}" 解析成功，请配置字段映射`)
  return false
}

function selectHistoryLog(log: ImportLog): void {
  dataFlowStore.setCurrentImportLog(log)
  ElMessage.info(`已选中导入任务：${log.fileName}`)
}

function goToClean(): void {
  if (importResult.value) {
    router.push('/data/clean')
  } else {
    ElMessage.warning('请先完成数据导入')
  }
}

function goToManage(): void {
  router.push('/data/manage')
}

const statusMap: Record<number, { label: string; type: 'success' | 'warning' | 'danger' }> = {
  0: { label: '导入中', type: 'warning' },
  1: { label: '成功', type: 'success' },
  2: { label: '失败', type: 'danger' },
}
</script>

<template>
  <div class="page-container">
    <DataFlowNav />

    <el-tabs v-model="activeTab" type="border-card" class="import-tabs">
      <el-tab-pane label="数据库直连" name="database">
        <template #label>
          <span class="tab-label"><el-icon><Connection /></el-icon> 数据库直连</span>
        </template>

        <el-form :model="dbForm" label-width="100px" style="max-width: 600px">
          <el-form-item label="导入类型">
            <el-select v-model="importType" style="width: 100%">
              <el-option v-for="opt in importTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据库类型">
            <el-select v-model="dbForm.type" style="width: 100%">
              <el-option label="MySQL" value="mysql" />
              <el-option label="PostgreSQL" value="pgsql" />
            </el-select>
          </el-form-item>
          <el-form-item label="主机地址">
            <el-input v-model="dbForm.host" placeholder="如 127.0.0.1" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="dbForm.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="dbForm.username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="dbForm.password" type="password" show-password />
          </el-form-item>
          <el-form-item label="数据库名">
            <el-input v-model="dbForm.database" />
          </el-form-item>
          <el-form-item label="目标数据表">
            <el-select v-model="dbForm.table" placeholder="请先测试连接" :disabled="!dbConnected" style="width: 100%">
              <el-option label="t_score（成绩表）" value="t_score" />
              <el-option label="t_attendance（考勤表）" value="t_attendance" />
              <el-option label="t_assignment_submission（作业提交表）" value="t_assignment_submission" />
              <el-option label="t_student（学生表）" value="t_student" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="dbTesting" @click="testConnection">测试连接</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="文件上传" name="file">
        <template #label>
          <span class="tab-label"><el-icon><Upload /></el-icon> 文件上传</span>
        </template>

        <el-form label-width="100px" style="max-width: 600px; margin-bottom: 16px">
          <el-form-item label="导入类型">
            <el-select v-model="importType" style="width: 100%">
              <el-option v-for="opt in importTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
        </el-form>

        <el-upload
          drag
          :before-upload="beforeUpload"
          accept=".xlsx,.xls,.txt,.csv"
          :file-list="uploadFileList.map(f => ({ name: f.name }))"
          :limit="1"
        >
          <el-icon class="el-icon--upload" :size="48"><Document /></el-icon>
          <div class="el-upload__text">将 Excel / Txt 文件拖到此处，或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 .xlsx / .xls / .txt / .csv 格式，单次不超过 10000 条</div>
          </template>
        </el-upload>
      </el-tab-pane>
    </el-tabs>

    <div v-if="uploadFileList.length || dbForm.table" class="content-card" style="margin-top: 16px">
      <div class="content-card__title">字段映射配置</div>
      <el-table :data="fieldPreview" stripe border>
        <el-table-column prop="source" label="源字段" />
        <el-table-column label="映射状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.mapped ? 'success' : 'danger'" size="small">
              {{ row.mapped ? '已映射' : '未映射' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标标准字段">
          <template #default="{ row }">
            <el-select v-model="row.target" style="width: 100%">
              <el-option label="学号" value="学号" />
              <el-option label="姓名" value="姓名" />
              <el-option label="课程号" value="课程号" />
              <el-option label="分数" value="分数" />
              <el-option label="考试时间" value="考试时间" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end; gap: 12px">
        <el-button type="primary" :loading="importing" @click="handleImport">开始导入</el-button>
        <el-button v-if="importResult" type="success" @click="goToClean">
          下一步：数据清洗 <el-icon><Right /></el-icon>
        </el-button>
      </div>

      <el-result v-if="importResult" icon="success" title="导入完成" style="margin-top: 16px">
        <template #sub-title>
          文件 <strong>{{ importResult.fileName }}</strong> —
          成功导入 <strong>{{ importResult.successCount }}</strong> 条，
          失败 <strong style="color: #ef4444">{{ importResult.failCount }}</strong> 条
        </template>
      </el-result>
    </div>

    <!-- 导入历史 -->
    <div class="content-card">
      <div class="content-card__title">导入历史记录</div>
      <el-table :data="importHistory" stripe border highlight-current-row @row-click="selectHistoryLog">
        <el-table-column prop="fileName" label="文件名/数据表" min-width="200">
          <template #default="{ row }">
            <el-icon style="vertical-align: -2px"><Document /></el-icon>
            {{ row.fileName }}
          </template>
        </el-table-column>
        <el-table-column prop="importType" label="导入类型" width="110">
          <template #default="{ row }">
            {{ importTypeOptions.find(o => o.value === row.importType)?.label }}
          </template>
        </el-table-column>
        <el-table-column prop="dataSource" label="数据来源" width="100">
          <template #default="{ row }">
            {{ row.dataSource === 'database' ? '数据库' : row.dataSource === 'excel' ? 'Excel' : 'Txt' }}
          </template>
        </el-table-column>
        <el-table-column label="导入结果" width="160">
          <template #default="{ row }">
            成功 {{ row.successCount }} / 失败 {{ row.failCount }}
          </template>
        </el-table-column>
        <el-table-column prop="operatorName" label="操作人" width="100" />
        <el-table-column prop="importTime" label="导入时间" width="170" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="selectHistoryLog(row)">选中</el-button>
            <el-button type="success" link size="small" @click.stop="() => { selectHistoryLog(row); goToClean() }">清洗</el-button>
            <el-button type="info" link size="small" @click.stop="goToManage">管理</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.import-tabs {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);

  .tab-label {
    display: flex;
    align-items: center;
    gap: 6px;
  }
}
</style>
