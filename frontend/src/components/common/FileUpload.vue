<!--
  通用文件上传组件
  封装 el-upload，支持拖拽上传、文件类型限制、大小校验、上传进度
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles, UploadRawFile } from 'element-plus'

const props = withDefaults(
  defineProps<{
    accept?: string
    maxSize?: number
    disabled?: boolean
    loading?: boolean
    tip?: string
    buttonText?: string
  }>(),
  {
    accept: '.xlsx,.xls,.txt,.csv',
    maxSize: 10,
    disabled: false,
    loading: false,
    tip: '',
    buttonText: '点击上传',
  },
)

const emit = defineEmits<{
  (e: 'file-change', file: File): void
  (e: 'upload', file: File): void
}>()

const fileList = ref<UploadFile[]>([])
const dragOver = ref(false)

function handleChange(uploadFile: UploadFile, _uploadFiles: UploadFiles): void {
  const raw = uploadFile.raw
  if (!raw) return
  fileList.value = [uploadFile]
  emit('file-change', raw)
}

function beforeUpload(rawFile: UploadRawFile): boolean {
  const ext = rawFile.name.split('.').pop()?.toLowerCase()
  const allowed = props.accept.split(',').map((s) => s.trim().replace('.', ''))
  if (!allowed.includes(ext || '')) {
    ElMessage.error(`仅支持 ${props.accept} 格式`)
    return false
  }
  const sizeMB = rawFile.size / 1024 / 1024
  if (sizeMB > props.maxSize) {
    ElMessage.error(`文件大小不能超过 ${props.maxSize}MB`)
    return false
  }
  return false
}

function removeFile(): void {
  fileList.value = []
}

function handleUpload(): void {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  const raw = fileList.value[0]?.raw
  if (raw) {
    emit('upload', raw)
  }
}

function handleDragOver(): void {
  dragOver.value = true
}

function handleDragLeave(): void {
  dragOver.value = false
}
</script>

<template>
  <div class="file-upload">
    <el-upload
      v-model:file-list="fileList"
      drag
      :auto-upload="false"
      :accept="accept"
      :disabled="disabled"
      :limit="1"
      :show-file-list="true"
      :before-upload="beforeUpload"
      :on-change="handleChange"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <div class="upload-trigger">
        <el-icon :size="40" class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <p class="upload-label">{{ buttonText }}</p>
          <p class="upload-hint">或将文件拖拽到此区域</p>
        </div>
        <p v-if="accept" class="upload-accept">支持 {{ accept }} 格式</p>
        <p v-if="maxSize" class="upload-size">单个文件不超过 {{ maxSize }}MB</p>
      </div>
    </el-upload>

    <p v-if="tip" class="file-tip">{{ tip }}</p>

    <div v-if="fileList.length > 0" class="upload-actions">
      <el-button type="primary" :loading="loading" @click="handleUpload">开始上传</el-button>
      <el-button @click="removeFile">重新选择</el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.file-upload {
  .upload-trigger {
    padding: 20px;
    color: #64748b;

    .upload-icon {
      color: #94a3b8;
      margin-bottom: 8px;
    }

    .upload-text {
      .upload-label {
        font-size: 15px;
        color: #334155;
        font-weight: 500;
        margin-bottom: 4px;
      }

      .upload-hint {
        font-size: 13px;
        color: #94a3b8;
      }
    }

    .upload-accept,
    .upload-size {
      font-size: 12px;
      color: #94a3b8;
      margin-top: 4px;
    }
  }

  .file-tip {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 8px;
  }

  .upload-actions {
    margin-top: 12px;
    display: flex;
    gap: 8px;
  }

  :deep(.el-upload-dragger) {
    border: 2px dashed #cbd5e1;
    border-radius: 10px;
    transition: border-color 0.2s;

    &:hover {
      border-color: #2563eb;
    }
  }
}
</style>
