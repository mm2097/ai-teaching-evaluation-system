<!--
  基础数据概览
  管理员核对系统公共目录，不在此配置教学预警或评价规则
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchDepartments, fetchSemesters } from '@/api/dict'

const loading = ref(false)
const semesters = ref<{ label: string; value: string; current: boolean }[]>([])
const departments = ref<{ label: string; value: number }[]>([])

onMounted(async () => {
  loading.value = true
  try {
    const [semesterRows, departmentRows] = await Promise.all([
      fetchSemesters(),
      fetchDepartments(),
    ])
    semesters.value = semesterRows.map((item) => ({
      label: item.semesterName,
      value: item.semesterCode,
      current: item.isCurrent,
    }))
    departments.value = departmentRows.map((item) => ({
      label: item.deptName,
      value: item.id,
    }))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="page-container base-data-page">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <div class="content-card directory-card">
          <div class="content-card__title">学期目录</div>
          <div class="directory-summary">
            <span>系统学期数量</span>
            <strong>{{ semesters.length }}</strong>
          </div>
          <el-table :data="semesters" stripe border>
            <el-table-column prop="label" label="学期名称" min-width="150" />
            <el-table-column prop="value" label="编码" min-width="130" />
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.current" type="success" size="small">当前</el-tag>
                <span v-else class="muted">历史</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="content-card directory-card">
          <div class="content-card__title">院系目录</div>
          <div class="directory-summary">
            <span>系统院系数量</span>
            <strong>{{ departments.length }}</strong>
          </div>
          <el-table :data="departments" stripe border>
            <el-table-column prop="label" label="院系名称" min-width="180" />
            <el-table-column prop="value" label="目录序号" width="110" align="center" />
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.base-data-page {
  .el-col {
    margin-bottom: 16px;
  }
}

.directory-card {
  min-height: 420px;
}

.directory-summary {
  margin-bottom: 16px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #64748b;
  border-radius: 8px;
  background: #f8fafc;

  strong {
    color: #2563eb;
    font-size: 24px;
  }
}

.muted {
  color: #94a3b8;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .directory-card {
    min-height: auto;
  }
}
</style>
