<!--
  数据上传页面
  任课教师下载标准模板、填写后上传，系统校验格式
  模板列表由后端 GET /teaching-data/templates 动态获取，后端有几种前端就展示几种。
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Upload, Document, Right, Warning } from '@element-plus/icons-vue'
import DataFlowNav from '@/components/common/DataFlowNav.vue'
import { executeImport, fetchImportLogs } from '@/api/import'
import { fetchCourses } from '@/api/dict'
import { fetchTemplateList } from '@/api/teachingData'
import type { TemplateMeta } from '@/api/teachingData'
import { useDataFlowStore } from '@/stores/dataFlow'
import { useUserStore } from '@/stores/user'
import { downloadExcelTemplate, downloadTxtTemplate } from '@/utils/templateDownload'
import { validateUploadFile, readHeadersFromFile } from '@/utils/templateValidator'
import type { DataTemplateType, ImportLog, ValidationError } from '@/types'

const router = useRouter()
const dataFlowStore = useDataFlowStore()
const userStore = useUserStore()

// --------------------------------------------------------------------------
// 模板列表 — 从后端动态获取
// --------------------------------------------------------------------------
const templateList = ref<TemplateMeta[]>([])
const templateId = ref<string>('')

/** 当前选中的模板元信息 */
const selectedTemplate = computed<TemplateMeta | undefined>(() =>
  templateList.value.find((t) => t.templateId === templateId.value),
)

/**
 * 将后端 template_id 映射为前端 validator 所需的 DataTemplateType。
 * 用于上传前客户端格式校验。
 */
function toDataTemplateType(id: string): DataTemplateType {
  // 根据后端 dataType 字段判定：考勤 → attendance，其余归入 score
  const t = templateList.value.find((m) => m.templateId === id)
  return t?.dataType === '考勤' ? 'attendance' : 'score'
}

/**
 * 按列名集合匹配（不要求顺序一致），统计实际表头中包含多少个期望列名。
 */
function countMatchingColumns(actual: string[], expected: string[]): number {
  const actualSet = new Set(actual.filter((h) => h !== ''))
  return expected.filter((h) => actualSet.has(h)).length
}

/** 检测到的模板名称，用于给用户提示 */
const detectedName = ref<string>('')

/**
 * 自动检测上传文件最可能匹配哪个模板（按列名集合比对数）。
 * 匹配列数 ≥ 期望列数 × 50% 即视为命中，取匹配数最多的模板。
 * 返回匹配的 headers，无命中则回退到当前选中模板。
 */
async function detectHeaders(file: File): Promise<string[] | null> {
  const actual = await readHeadersFromFile(file)
  if (!actual?.length) return null

  let best: { headers: string[]; name: string; count: number } | null = null

  for (const tpl of templateList.value) {
    const count = countMatchingColumns(actual, tpl.headers)
    if (best === null || count > best.count) {
      best = { headers: tpl.headers, name: tpl.name, count }
    }
  }

  // 至少匹配半数以上列名才算有效命中
  if (best && best.count >= best.headers.length * 0.5) {
    detectedName.value = best.name
    return best.headers
  }

  // 无命中时回退到当前选中模板
  detectedName.value = ''
  return selectedTemplate.value?.headers ?? null
}

onMounted(async () => {
  // 并行拉取模板列表、导入历史、课程列表
  const [templates, logs] = await Promise.all([
    fetchTemplateList(),
    fetchImportLogs(),
  ])
  templateList.value = templates
  importHistory.value = logs

  // 默认选中第一个模板
  if (templates.length > 0) {
    templateId.value = templates[0]!.templateId
  }

  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) courseId.value = courseOptions.value[0]!.value
})

// --------------------------------------------------------------------------
// 下载
// --------------------------------------------------------------------------
async function handleDownloadExcel(): Promise<void> {
  if (!templateId.value) return
  try {
    await downloadExcelTemplate(templateId.value)
    ElMessage.success('Excel 模板已下载')
  } catch {
    ElMessage.error('Excel 模板下载失败，请稍后重试')
  }
}

async function handleDownloadTxt(): Promise<void> {
  if (!templateId.value) return
  try {
    await downloadTxtTemplate(templateId.value)
    ElMessage.success('Txt 模板已下载')
  } catch {
    ElMessage.error('Txt 模板下载失败，请稍后重试')
  }
}

// --------------------------------------------------------------------------
// 上传 & 校验
// --------------------------------------------------------------------------
const courseId = ref<number | undefined>()
const courseOptions = ref<{ label: string; value: number }[]>([])
const uploadFile = ref<File | null>(null)
const validationErrors = ref<ValidationError[]>([])
const validating = ref(false)
const importing = ref(false)
const importResult = ref<ImportLog | null>(null)
const importHistory = ref<ImportLog[]>([])

async function beforeUpload(file: File): Promise<boolean> {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext !== 'xlsx' && ext !== 'txt') {
    ElMessage.error('仅支持 .xlsx（Excel）或 .txt（UTF-8 英文逗号分隔）格式')
    return false
  }

  if (!courseId.value) {
    ElMessage.warning('请先选择所属课程')
    return false
  }

  validating.value = true
  validationErrors.value = []
  uploadFile.value = file

  try {
    const headers = await detectHeaders(file)
    if (!headers?.length) {
      ElMessage.warning('无法识别文件表头，请在左侧确认已选择正确的模板类型')
      validating.value = false
      return false
    }
    if (detectedName.value) {
      ElMessage.success(`已自动识别为「${detectedName.value}」模板`)
    }
    const result = await validateUploadFile(file, headers)
    validationErrors.value = result.errors
    if (result.valid) {
      ElMessage.success(`格式校验通过，共 ${result.rowCount} 条数据，可以上传`)
    } else {
      ElMessage.error(`格式校验失败，共 ${result.errors.length} 处错误，请修正后重传`)
    }
  } finally {
    validating.value = false
  }

  return false
}

async function handleImport(): Promise<void> {
  if (!uploadFile.value) {
    ElMessage.warning('请先上传文件')
    return
  }
  if (validationErrors.value.length) {
    ElMessage.error('请先修正格式错误后再上传')
    return
  }

  importing.value = true
  const ext = uploadFile.value.name.split('.').pop()?.toLowerCase()
  const log = await executeImport({
    importType: toDataTemplateType(templateId.value) as 'score' | 'attendance',
    dataSource: ext === 'txt' ? 'txt' : 'excel',
    fileName: uploadFile.value.name,
    totalCount: 0,
    operatorName: userStore.userInfo?.name || '未知',
  })

  importResult.value = log
  dataFlowStore.setLastImportResult(log)
  importHistory.value = await fetchImportLogs()
  importing.value = false
  ElMessage.success('数据上传成功！')
}

function goToManage(): void {
  router.push('/data/manage')
}

const statusMap: Record<number, { label: string; type: 'success' | 'warning' | 'danger' }> = {
  0: { label: '上传中', type: 'warning' },
  1: { label: '成功', type: 'success' },
  2: { label: '失败', type: 'danger' },
}
</script>

<template>
  <div class="page-container">
    <DataFlowNav />

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="上传说明"
      description="请先下载标准模板，按模板格式填写数据后上传。系统仅校验文件结构与字段是否匹配，不匹配将提示错误行号。数据由任课教师上传，仅可操作自己授课课程的数据。"
      style="margin-bottom: 16px"
    />

    <el-row :gutter="16">
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">1. 下载标准模板</div>
          <el-form label-width="90px">
            <el-form-item label="数据类型">
              <el-radio-group v-model="templateId">
                <el-radio v-for="t in templateList" :key="t.templateId" :value="t.templateId">
                  {{ t.name }}
                </el-radio>
              </el-radio-group>
              <p v-if="selectedTemplate" class="type-desc">{{ selectedTemplate.description }}</p>
            </el-form-item>
            <el-form-item label="所属课程">
              <el-select v-model="courseId" placeholder="选择您授课的课程" style="width: 100%">
                <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="下载模板">
              <div class="download-btns">
                <el-button :icon="Download" :disabled="!templateId" @click="handleDownloadExcel">
                  下载 Excel 模板 (.xlsx)
                </el-button>
                <el-button :icon="Download" :disabled="!templateId" @click="handleDownloadTxt">
                  下载 Txt 模板 (.txt)
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">2. 上传填写好的文件</div>
          <el-upload
            drag
            :before-upload="beforeUpload"
            accept=".xlsx,.txt"
            :limit="1"
            :disabled="validating"
          >
            <el-icon class="el-icon--upload" :size="48"><Upload /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">
                仅支持 .xlsx（Excel）和 .txt（UTF-8 英文逗号分隔）格式
              </div>
              <div class="el-upload__tip" style="margin-top:4px;color:#e6a23c">
                上传前请在左侧确认已选中与文件对应的模板类型，系统将自动识别并校验。
              </div>
            </template>
          </el-upload>

          <div v-if="uploadFile" class="upload-info">
            <el-icon><Document /></el-icon>
            <span>{{ uploadFile.name }}</span>
            <el-tag v-if="!validationErrors.length && !validating" type="success" size="small">校验通过</el-tag>
            <el-tag v-else-if="validationErrors.length" type="danger" size="small">校验失败</el-tag>
          </div>

          <div v-if="validationErrors.length" class="error-list">
            <div class="error-title">
              <el-icon><Warning /></el-icon>
              格式错误（请修正后重新上传）：
            </div>
            <el-table :data="validationErrors.slice(0, 20)" stripe border size="small">
              <el-table-column prop="sheet" label="Sheet" width="100" align="center" />
              <el-table-column prop="row" label="行号" width="70" align="center" />
              <el-table-column prop="column" label="字段" width="120" />
              <el-table-column prop="message" label="错误说明" />
            </el-table>
            <p v-if="validationErrors.length > 20" class="error-more">... 还有 {{ validationErrors.length - 20 }} 处错误</p>
          </div>

          <div class="action-bar">
            <el-button
              type="primary"
              :loading="importing"
              :disabled="!uploadFile || validationErrors.length > 0"
              @click="handleImport"
            >
              确认上传
            </el-button>
            <el-button v-if="importResult" type="success" @click="goToManage">
              下一步：数据管理 <el-icon><Right /></el-icon>
            </el-button>
          </div>

          <el-result v-if="importResult" icon="success" title="上传完成" style="margin-top: 16px">
            <template #sub-title>
              文件 <strong>{{ importResult.fileName }}</strong> 已成功导入
            </template>
          </el-result>
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__title">上传历史</div>
      <el-table :data="importHistory" stripe border>
        <el-table-column prop="fileName" label="文件名" min-width="200">
          <template #default="{ row }">
            <el-icon style="vertical-align: -2px"><Document /></el-icon>
            {{ row.fileName }}
          </template>
        </el-table-column>
        <el-table-column prop="dataSource" label="格式" width="80">
          <template #default="{ row }">{{ row.dataSource === 'excel' ? 'Excel' : 'Txt' }}</template>
        </el-table-column>
        <el-table-column prop="successCount" label="成功条数" width="100" align="center" />
        <el-table-column prop="operatorName" label="操作人" width="100" />
        <el-table-column prop="importTime" label="上传时间" width="170" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.type-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.download-btns {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.upload-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 14px;
}

.error-list {
  margin-top: 16px;

  .error-title {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #ef4444;
    font-size: 14px;
    margin-bottom: 8px;
  }

  .error-more {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 8px;
  }
}

.action-bar {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
</style>
