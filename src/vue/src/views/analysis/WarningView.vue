<!--
  异常学情预警页面
  展示预警名单、等级与原因，支持筛选
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { fetchWarnings } from '@/api/analysis'
import { semesterOptions, departmentOptions, courses } from '@/mock'
import { useDictCascade } from '@/composables/useDictCascade'
import { useUserStore } from '@/stores/user'
import { warningLevelType } from '@/utils/auth'
import type { WarningRecord } from '@/types'

const userStore = useUserStore()
const { deptId, classId, classOptions } = useDictCascade({
  deptId: userStore.userInfo?.deptId,
})

const levelFilter = ref('')
const typeFilter = ref('')
const semesterId = ref(1)
const courseId = ref<number | undefined>()
const statusFilter = ref<number | ''>('')

const warningList = ref<WarningRecord[]>([])

async function loadWarnings(): Promise<void> {
  warningList.value = await fetchWarnings({
    deptId: deptId.value,
    classId: classId.value,
    semesterId: semesterId.value,
    courseId: courseId.value,
    level: levelFilter.value || undefined,
    type: typeFilter.value || undefined,
    status: statusFilter.value === '' ? undefined : statusFilter.value,
  })
}

watch([deptId, classId, semesterId, courseId, levelFilter, typeFilter, statusFilter], loadWarnings)

onMounted(loadWarnings)

const filteredWarnings = computed(() => warningList.value)

const levelStats = computed(() => ({
  高: filteredWarnings.value.filter((w) => w.level === '高').length,
  中: filteredWarnings.value.filter((w) => w.level === '中').length,
  低: filteredWarnings.value.filter((w) => w.level === '低').length,
}))

const drawerVisible = ref(false)
const currentWarning = ref<WarningRecord | undefined>()

function viewDetail(row: WarningRecord): void {
  currentWarning.value = row
  drawerVisible.value = true
}

const statusOptions = [
  { label: '待处理', value: 0 },
  { label: '处理中', value: 1 },
  { label: '已处理', value: 2 },
  { label: '已忽略', value: 3 },
]

const showDeptFilter = computed(() => ['admin', 'manager'].includes(userStore.userInfo?.role || ''))
</script>

<template>
  <div class="page-container">
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
      <div class="filter-bar">
        <el-select v-model="semesterId" placeholder="学期" style="width: 200px">
          <el-option v-for="s in semesterOptions" :key="s.id" :label="s.label" :value="s.id!" />
        </el-select>
        <el-select v-if="showDeptFilter" v-model="deptId" placeholder="院系" clearable style="width: 150px">
          <el-option v-for="d in departmentOptions.filter(d => d.id)" :key="d.id" :label="d.label" :value="d.id!" />
        </el-select>
        <el-select v-model="classId" placeholder="班级" clearable style="width: 140px">
          <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="courseId" placeholder="课程" clearable style="width: 150px">
          <el-option v-for="c in courses" :key="c.id" :label="c.courseName" :value="c.id" />
        </el-select>
        <el-select v-model="levelFilter" placeholder="预警等级" clearable style="width: 120px">
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
        <el-select v-model="statusFilter" placeholder="处理状态" clearable style="width: 120px">
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </div>

      <el-table :data="filteredWarnings" stripe border>
        <el-table-column prop="studentId" label="学号" width="130" />
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="className" label="班级" width="120" />
        <el-table-column prop="courseName" label="课程" width="120">
          <template #default="{ row }">{{ row.courseName || '-' }}</template>
        </el-table-column>
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
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 2 ? 'success' : row.status === 0 ? 'danger' : 'warning'">
              {{ statusOptions.find(s => s.value === row.status)?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="drawerVisible" title="预警详情" size="400px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="学号">{{ currentWarning?.studentId }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ currentWarning?.studentName }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ currentWarning?.className }}</el-descriptions-item>
        <el-descriptions-item label="课程">{{ currentWarning?.courseName || '-' }}</el-descriptions-item>
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
