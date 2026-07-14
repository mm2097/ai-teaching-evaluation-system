<!--
  题库批量导入对话框
  支持：标准模板下载 + 文件上传 / 内置参考模板一键导入
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Upload, Document } from '@element-plus/icons-vue'
import {
  fetchBuiltinTemplates,
  importQuestionsFromFile,
  importQuestionsFromBuiltin,
} from '@/api/questionBank'
import { downloadQuestionExcelTemplate, downloadQuestionTxtTemplate } from '@/utils/questionTemplateDownload'
import { validateQuestionUploadFile } from '@/utils/questionTemplateValidator'
import type { QuestionBuiltinTemplate, ValidationError } from '@/types'

const props = defineProps<{
  modelValue: boolean
  courseId?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  imported: []
}>()

const importMode = ref<'file' | 'builtin'>('file')
const uploadFile = ref<File | null>(null)
const parsedRows = ref<import('@/utils/questionTemplateValidator').ParsedQuestionRow[]>([])
const validating = ref(false)
const importing = ref(false)
const validationErrors = ref<ValidationError[]>([])
const validatedRowCount = ref(0)

const builtinTemplates = ref<QuestionBuiltinTemplate[]>([])
const selectedTemplateId = ref('')

const filteredBuiltin = computed(() => {
  if (!props.courseId) return builtinTemplates.value
  return builtinTemplates.value.filter((t) => t.courseId === props.courseId)
})

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    uploadFile.value = null
    parsedRows.value = []
    validationErrors.value = []
    validatedRowCount.value = 0
    selectedTemplateId.value = ''
    builtinTemplates.value = await fetchBuiltinTemplates(props.courseId)
    if (filteredBuiltin.value.length) {
      selectedTemplateId.value = filteredBuiltin.value[0]!.id
    }
  },
)

function close(): void {
  emit('update:modelValue', false)
}

function handleDownloadExcel(): void {
  downloadQuestionExcelTemplate()
  ElMessage.success('Excel 模板已下载，请按格式填写后上传')
}

function handleDownloadTxt(): void {
  downloadQuestionTxtTemplate()
  ElMessage.success('Txt 模板已下载，请按格式填写后上传')
}

async function handleFileChange(file: { raw?: File }): Promise<void> {
  const raw = file.raw
  if (!raw) return
  const ext = raw.name.split('.').pop()?.toLowerCase()
  if (ext !== 'xlsx' && ext !== 'txt') {
    ElMessage.error('仅支持 .xlsx 或 .txt 格式')
    return
  }
  if (!props.courseId) {
    ElMessage.warning('请先选择课程')
    return
  }

  validating.value = true
  validationErrors.value = []
  uploadFile.value = raw
  parsedRows.value = []

  try {
    const result = await validateQuestionUploadFile(raw)
    validationErrors.value = result.errors
    validatedRowCount.value = result.rowCount
    parsedRows.value = result.rows
    if (result.valid) {
      ElMessage.success(`格式校验通过，共 ${result.rowCount} 道题目`)
    } else {
      ElMessage.error(`校验失败，共 ${result.errors.length} 处错误`)
    }
  } finally {
    validating.value = false
  }
}

async function handleFileImport(): Promise<void> {
  if (!props.courseId || !uploadFile.value) {
    ElMessage.warning('请先选择课程并上传文件')
    return
  }
  if (validationErrors.value.length) {
    ElMessage.error('请先修正格式错误')
    return
  }

  importing.value = true
  try {
    const importResult = await importQuestionsFromFile(props.courseId, parsedRows.value)
    ElMessage.success(
      `导入完成：新增 ${importResult.imported} 道${importResult.skipped ? `，跳过重复 ${importResult.skipped} 道` : ''}`,
    )
    emit('imported')
    close()
  } catch {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    importing.value = false
  }
}

async function handleBuiltinImport(): Promise<void> {
  if (!props.courseId || !selectedTemplateId.value) {
    ElMessage.warning('请选择课程和参考模板')
    return
  }
  importing.value = true
  try {
    const result = await importQuestionsFromBuiltin(props.courseId, selectedTemplateId.value)
    const tpl = builtinTemplates.value.find((t) => t.id === selectedTemplateId.value)
    if (result.imported > 0) {
      ElMessage.success(
        `已从「${tpl?.name}」导入 ${result.imported} 道题目${result.skipped ? `，跳过重复 ${result.skipped} 道` : ''}`,
      )
    } else {
      ElMessage.info('该模板题目已在题库中，无需重复导入')
    }
    emit('imported')
    close()
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="批量导入题库"
    width="720px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-tabs v-model="importMode">
      <el-tab-pane label="模板文件导入" name="file">
        <div class="import-section">
          <p class="section-desc">下载标准模板，按格式填写题目后上传。支持单选、多选、判断、填空、简答五种题型。</p>
          <div class="download-btns">
            <el-button :icon="Download" @click="handleDownloadExcel">下载 Excel 模板</el-button>
            <el-button :icon="Download" @click="handleDownloadTxt">下载 Txt 模板</el-button>
          </div>

          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="true"
            accept=".xlsx,.txt"
            :limit="1"
            :on-change="handleFileChange"
          >
            <el-icon :size="40"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="upload-tip">仅支持 .xlsx 或 .txt（UTF-8 英文逗号分隔），单次建议不超过 200 题</div>
            </template>
          </el-upload>

          <div v-if="validatedRowCount && !validationErrors.length" class="validate-ok">
            校验通过，共 {{ validatedRowCount }} 道题目待导入
          </div>

          <div v-if="validationErrors.length" class="error-list">
            <p class="error-title">格式错误（{{ validationErrors.length }} 处）：</p>
            <div v-for="(err, idx) in validationErrors.slice(0, 8)" :key="idx" class="error-item">
              {{ err.message }}
            </div>
            <p v-if="validationErrors.length > 8" class="error-more">… 还有 {{ validationErrors.length - 8 }} 处错误</p>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="内置参考模板" name="builtin">
        <div class="import-section">
          <p class="section-desc">从系统内置参考题库一键导入，适用于快速初始化课程题库。</p>
          <el-radio-group v-model="selectedTemplateId" class="template-list">
            <el-radio
              v-for="tpl in filteredBuiltin"
              :key="tpl.id"
              :value="tpl.id"
              class="template-item"
            >
              <div class="template-info">
                <span class="template-name">
                  <el-icon><Document /></el-icon>
                  {{ tpl.name }}
                </span>
                <span class="template-meta">{{ tpl.courseName }} · 约 {{ tpl.questionCount }} 题</span>
                <span class="template-desc">{{ tpl.description }}</span>
              </div>
            </el-radio>
          </el-radio-group>
          <el-empty v-if="!filteredBuiltin.length" description="当前课程暂无内置参考模板" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        v-if="importMode === 'file'"
        type="primary"
        :loading="importing || validating"
        :disabled="!uploadFile || !!validationErrors.length"
        @click="handleFileImport"
      >
        确认导入
      </el-button>
      <el-button
        v-else
        type="primary"
        :loading="importing"
        :disabled="!selectedTemplateId"
        @click="handleBuiltinImport"
      >
        从参考模板导入
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.import-section {
  padding: 4px 0;
}

.section-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
}

.download-btns {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.upload-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

.validate-ok {
  margin-top: 12px;
  padding: 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 13px;
  color: #16a34a;
}

.error-list {
  margin-top: 12px;
  padding: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  max-height: 160px;
  overflow-y: auto;

  .error-title {
    font-size: 13px;
    font-weight: 600;
    color: #dc2626;
    margin-bottom: 6px;
  }

  .error-item {
    font-size: 12px;
    color: #991b1b;
    padding: 2px 0;
  }

  .error-more {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
  }
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.template-item {
  width: 100%;
  height: auto;
  margin-right: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;

  :deep(.el-radio__label) {
    width: 100%;
  }
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 4px;

  .template-name {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    font-size: 14px;
    color: #1e293b;
  }

  .template-meta {
    font-size: 12px;
    color: #64748b;
  }

  .template-desc {
    font-size: 12px;
    color: #94a3b8;
  }
}
</style>
