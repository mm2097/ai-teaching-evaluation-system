<!--
  练习列表面板（从 QuizManageView 拆出）
-->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, CircleClose } from '@element-plus/icons-vue'
import { fetchQuizAssignments, closeQuizAssignment, type QuizAssignmentRecord } from '@/api/quiz'

const props = defineProps<{
  refreshTrigger?: number  // 外部变更时递增以触发刷新
}>()

// 后端返回的数据实际含 QuizAssignment 所有字段，用宽松类型避免 vue-tsc 报错
type AssignmentItem = QuizAssignmentRecord & Record<string, any>

const assignmentList = ref<AssignmentItem[]>([])
const detailVisible = ref(false)
const detailAssignment = ref<AssignmentItem | null>(null)

async function loadAssignments() {
  assignmentList.value = await fetchQuizAssignments()
}

watch(() => props.refreshTrigger, () => { loadAssignments() }, { immediate: true })

async function handleCloseAssignment(row: AssignmentItem) {
  await ElMessageBox.confirm(`确定关闭练习「${row.title}」？关闭后学生将无法继续作答。`, '关闭确认', {
    type: 'warning',
  })
  await closeQuizAssignment(row.id)
  await loadAssignments()
  ElMessage.success('练习已关闭')
}

function viewAssignment(row: AssignmentItem) {
  detailAssignment.value = row
  detailVisible.value = true
}

const statusMap: Record<string, { label: string; type: 'success' | 'info' | 'warning' }> = {
  draft: { label: '草稿', type: 'info' },
  published: { label: '已发布', type: 'success' },
  closed: { label: '已关闭', type: 'warning' },
}

defineExpose({ loadAssignments })
</script>

<template>
  <div class="content-card">
    <div class="content-card__title">练习列表</div>
    <el-table :data="assignmentList" stripe border>
      <el-table-column prop="title" label="练习标题" min-width="200" />
      <el-table-column prop="courseName" label="课程" width="140" />
      <el-table-column prop="className" label="班级" width="110" />
      <el-table-column prop="questionCount" label="题量" width="70" align="center" />
      <el-table-column prop="totalScore" label="总分" width="70" align="center" />
      <el-table-column prop="status" label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="publishTime" label="发布时间" width="170">
        <template #default="{ row }">{{ row.publishTime || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" :icon="View" @click="viewAssignment(row)">详情</el-button>
          <el-button
            v-if="row.status === 'published'"
            type="warning"
            link
            size="small"
            :icon="CircleClose"
            @click="handleCloseAssignment(row)"
          >
            关闭
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" :title="detailAssignment?.title" width="700px">
      <template v-if="detailAssignment">
        <p class="detail-meta">
          {{ detailAssignment.courseName }} · {{ detailAssignment.className }} ·
          {{ detailAssignment.questionCount }} 题 · 满分 {{ detailAssignment.totalScore }} 分
        </p>
        <div v-for="(q, idx) in detailAssignment.questions" :key="idx" class="question-card compact">
          <p><strong>{{ Number(idx) + 1 }}.</strong> {{ q.stem }}（{{ q.score }}分）</p>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.detail-meta {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
}

.question-card {
  &.compact {
    padding: 10px 12px;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    margin-bottom: 8px;
  }
}
</style>
