<!--
  异常学情预警页面
  展示预警名单、等级与原因，支持筛选
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { warningRecords } from '@/mock'
import { warningLevelType } from '@/utils/auth'

/** 筛选条件 */
const levelFilter = ref('')
const typeFilter = ref('')

/** 筛选后的预警列表 */
const filteredWarnings = computed(() => {
  return warningRecords.filter((item) => {
    if (levelFilter.value && item.level !== levelFilter.value) return false
    if (typeFilter.value && item.type !== typeFilter.value) return false
    return true
  })
})

/** 各级别预警统计 */
const levelStats = computed(() => ({
  高: warningRecords.filter((w) => w.level === '高').length,
  中: warningRecords.filter((w) => w.level === '中').length,
  低: warningRecords.filter((w) => w.level === '低').length,
}))

/** 详情抽屉 */
const drawerVisible = ref(false)
const currentWarning = ref(warningRecords[0])

/**
 * 查看预警详情
 * @param row 预警记录
 */
function viewDetail(row: (typeof warningRecords)[0]): void {
  currentWarning.value = row
  drawerVisible.value = true
}
</script>

<template>
  <div class="page-container">
    <!-- 预警统计卡片 -->
    <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr)">
      <div class="warning-stat high">
        <div class="stat-num">{{ levelStats.高 }}</div>
        <div class="stat-label">高级预警</div>
      </div>
      <div class="warning-stat medium">
        <div class="stat-num">{{ levelStats.中 }}</div>
        <div class="stat-label">中级预警</div>
      </div>
      <div class="warning-stat low">
        <div class="stat-num">{{ levelStats.低 }}</div>
        <div class="stat-label">低级预警</div>
      </div>
    </div>

    <div class="content-card">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-select v-model="levelFilter" placeholder="预警等级" clearable style="width: 140px">
          <el-option label="高" value="高" />
          <el-option label="中" value="中" />
          <el-option label="低" value="低" />
        </el-select>
        <el-select v-model="typeFilter" placeholder="预警类型" clearable style="width: 140px">
          <el-option label="成绩下滑" value="成绩下滑" />
          <el-option label="缺勤异常" value="缺勤异常" />
          <el-option label="作业未交" value="作业未交" />
          <el-option label="综合异常" value="综合异常" />
        </el-select>
      </div>

      <!-- 预警列表 -->
      <el-table :data="filteredWarnings" stripe border>
        <el-table-column prop="studentId" label="学号" width="130" />
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="className" label="班级" width="120" />
        <el-table-column prop="type" label="预警类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="预警等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="warningLevelType(row.level)" size="small" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="预警原因" show-overflow-tooltip />
        <el-table-column prop="warningTime" label="预警时间" width="120" />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="预警详情" size="400px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="学号">{{ currentWarning?.studentId }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ currentWarning?.studentName }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ currentWarning?.className }}</el-descriptions-item>
        <el-descriptions-item label="预警类型">{{ currentWarning?.type }}</el-descriptions-item>
        <el-descriptions-item label="预警等级">
          <el-tag :type="warningLevelType(currentWarning?.level || '')" size="small">
            {{ currentWarning?.level }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预警原因">{{ currentWarning?.reason }}</el-descriptions-item>
        <el-descriptions-item label="预警时间">{{ currentWarning?.warningTime }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 20px">
        <el-button type="primary">标记已处理</el-button>
        <el-button>发送通知</el-button>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.warning-stat {
  text-align: center;
  padding: 24px;
  border-radius: 12px;
  color: #fff;

  .stat-num {
    font-size: 36px;
    font-weight: 700;
  }

  .stat-label {
    font-size: 14px;
    margin-top: 4px;
    opacity: 0.9;
  }

  &.high { background: linear-gradient(135deg, #ef4444, #dc2626); }
  &.medium { background: linear-gradient(135deg, #f59e0b, #d97706); }
  &.low { background: linear-gradient(135deg, #6366f1, #4f46e5); }
}
</style>
