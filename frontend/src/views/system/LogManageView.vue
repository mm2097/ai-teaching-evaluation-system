<!--
  系统日志管理页面
  记录并查询用户操作日志
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { systemLogList } from '@/mock'

/** 筛选条件 */
const filters = ref({
  username: '',
  type: '',
  dateRange: [] as string[],
})

/** 日志类型选项 */
const logTypes = ['登录', '数据操作', '查询', '导出', '配置修改']

/** 筛选后的日志 */
const filteredLogs = computed(() => {
  return systemLogList.filter((log) => {
    if (filters.value.username && !log.username.includes(filters.value.username)) return false
    if (filters.value.type && log.type !== filters.value.type) return false
    return true
  })
})

/** 日志类型 Tag 颜色映射 */
function logTypeTag(type: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'primary' | 'warning' | 'info' | 'danger'> = {
    登录: 'success',
    数据操作: 'primary',
    查询: 'info',
    导出: 'warning',
    配置修改: 'danger',
  }
  return map[type] || 'info'
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="filter-bar">
        <el-input v-model="filters.username" placeholder="用户名" clearable style="width: 160px" />
        <el-select v-model="filters.type" placeholder="操作类型" clearable style="width: 140px">
          <el-option v-for="t in logTypes" :key="t" :label="t" :value="t" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 260px"
        />
      </div>

      <el-table :data="filteredLogs" stripe border>
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="username" label="操作用户" width="120" />
        <el-table-column prop="operation" label="操作内容" />
        <el-table-column prop="type" label="操作类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="logTypeTag(row.type)" size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP 地址" width="140" />
        <el-table-column prop="time" label="操作时间" width="170" />
      </el-table>
    </div>
  </div>
</template>
