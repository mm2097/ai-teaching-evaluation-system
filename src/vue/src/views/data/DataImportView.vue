<!--
  多源数据接入页面
  支持数据库直连与 Excel/Txt 文件上传导入
-->
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Upload, Document } from '@element-plus/icons-vue'
import { delay } from '@/utils/auth'

/** 当前激活的数据源 Tab */
const activeTab = ref('database')

/** 数据库连接表单 */
const dbForm = reactive({
  type: 'mysql',
  host: '127.0.0.1',
  port: 3306,
  username: 'root',
  password: '',
  database: 'teaching_db',
  table: '',
})

/** 数据库连接测试状态 */
const dbTesting = ref(false)
const dbConnected = ref(false)

/** 文件上传相关 */
const uploadFileList = ref<{ name: string }[]>([])
const fieldPreview = ref([
  { source: 'student_id', target: '学号', mapped: true },
  { source: 'student_name', target: '姓名', mapped: true },
  { source: 'course_code', target: '课程号', mapped: true },
  { source: 'score', target: '分数', mapped: true },
  { source: 'exam_date', target: '考试时间', mapped: true },
])

/** 导入进度 */
const importing = ref(false)
const importResult = ref<{ success: number; fail: number } | null>(null)

/**
 * 测试数据库连接
 */
async function testConnection(): Promise<void> {
  dbTesting.value = true
  await delay(1000)
  dbConnected.value = true
  dbTesting.value = false
  ElMessage.success('数据库连接成功！')
}

/**
 * 执行数据导入
 */
async function handleImport(): Promise<void> {
  importing.value = true
  importResult.value = null
  await delay(2000)
  importResult.value = { success: 9856, fail: 12 }
  importing.value = false
  ElMessage.success('数据导入完成！')
}

/**
 * 文件上传前的处理（演示模式拦截实际上传）
 */
function beforeUpload(file: File): boolean {
  uploadFileList.value = [{ name: file.name }]
  ElMessage.success(`文件 "${file.name}" 解析成功，请配置字段映射`)
  return false
}
</script>

<template>
  <div class="page-container">
    <el-tabs v-model="activeTab" type="border-card" class="import-tabs">
      <!-- 数据库直连 -->
      <el-tab-pane label="数据库直连" name="database">
        <template #label>
          <span class="tab-label"><el-icon><Connection /></el-icon> 数据库直连</span>
        </template>

        <el-form :model="dbForm" label-width="100px" style="max-width: 600px">
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
              <el-option label="student_scores（成绩表）" value="student_scores" />
              <el-option label="attendance_records（考勤表）" value="attendance_records" />
              <el-option label="homework_submissions（作业表）" value="homework_submissions" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="dbTesting" @click="testConnection">测试连接</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 文件上传 -->
      <el-tab-pane label="文件上传" name="file">
        <template #label>
          <span class="tab-label"><el-icon><Upload /></el-icon> 文件上传</span>
        </template>

        <el-upload
          drag
          :before-upload="beforeUpload"
          accept=".xlsx,.xls,.txt,.csv"
          :file-list="uploadFileList"
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

    <!-- 字段映射 -->
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

      <div style="margin-top: 16px; text-align: right">
        <el-button type="primary" :loading="importing" @click="handleImport">
          开始导入
        </el-button>
      </div>

      <!-- 导入结果 -->
      <el-result
        v-if="importResult"
        icon="success"
        title="导入完成"
        style="margin-top: 16px"
      >
        <template #sub-title>
          成功导入 <strong>{{ importResult.success }}</strong> 条，
          失败 <strong style="color: #ef4444">{{ importResult.fail }}</strong> 条
        </template>
      </el-result>
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
