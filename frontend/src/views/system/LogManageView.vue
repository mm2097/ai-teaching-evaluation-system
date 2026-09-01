<!--
  系统日志管理页面
  记录并查询用户操作日志
  筛选/分页/导出均为服务端实现
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import request from '@/utils/request'

const filters = ref({
  username: '',
  module: '',
  dateRange: [] as [Date, Date] | [],
})

/** 操作模块选项(从后端去重接口获取,保证与真实数据一致) */
const moduleOptions = ref<string[]>([])
const logs = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

function formatDate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function buildParams(includePage = true): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (includePage) {
    params.page = page.value
    params.page_size = pageSize.value
  }
  const username = filters.value.username.trim()
  if (username) params.username = username
  if (filters.value.module) params.module = filters.value.module
  if (filters.value.dateRange && filters.value.dateRange.length === 2) {
    params.start_date = formatDate(filters.value.dateRange[0])
    params.end_date = formatDate(filters.value.dateRange[1])
  }
  return params
}

async function loadLogs(): Promise<void> {
  loading.value = true
  try {
    const res = await request.get('/v1/logs', { params: buildParams() })
    logs.value = res.data.list ?? []
    total.value = res.data.total ?? 0
  } catch {
    logs.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  loadLogs()
}

function handleReset(): void {
  filters.value = { username: '', module: '', dateRange: [] }
  page.value = 1
  loadLogs()
}

function handleSizeChange(size: number): void {
  pageSize.value = size
  page.value = 1
  loadLogs()
}

async function handleExport(): Promise<void> {
  try {
    const res = await request.get('/v1/logs/export', {
      params: buildParams(false),
      responseType: 'blob',
    })
    const blob = res.data as Blob
    // 从 Content-Disposition 解析文件名(优先 RFC 5987 中文名)
    const disposition = (res.headers as Record<string, string>)['content-disposition'] ?? ''
    const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/)
    let filename = '操作日志导出.xlsx'
    if (rfc5987) {
      filename = decodeURIComponent(rfc5987[1]!)
    } else {
      const ascii = disposition.match(/filename="?([^";\s]+)"?/)
      if (ascii) filename = ascii[1]!
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('操作日志导出成功，文件已保存至下载目录')
  } catch {
    ElMessage.error('操作日志导出失败')
  }
}

function logTypeTag(type: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'primary' | 'warning' | 'info' | 'danger'> = {
    用户管理: 'danger',
    数据管理: 'primary',
    课程管理: 'success',
    题库管理: 'warning',
    考试管理: 'info',
  }
  return map[type] || 'info'
}

onMounted(async () => {
  try {
    const res = await request.get('/v1/logs/modules')
    moduleOptions.value = res.data.list ?? []
  } catch {
    moduleOptions.value = [] // 下拉为空不影响查询
  }
  await loadLogs()
})
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="filter-bar">
        <el-input
          v-model="filters.username"
          placeholder="用户名"
          clearable
          style="width: 160px"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="filters.module" placeholder="操作模块" clearable style="width: 150px">
          <el-option v-for="m in moduleOptions" :key="m" :label="m" :value="m" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 260px"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        <el-button
          type="success"
          :icon="Download"
          style="margin-left: auto"
          @click="handleExport"
        >
          导出 Excel
        </el-button>
      </div>

      <el-table v-loading="loading" :data="logs" stripe border>
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="username" label="操作用户" width="120" />
        <el-table-column prop="operation" label="操作内容" />
        <el-table-column prop="type" label="操作模块" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="logTypeTag(row.type)" size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP 地址" width="140" />
        <el-table-column prop="time" label="操作时间" width="170" />
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadLogs"
          @size-change="handleSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
