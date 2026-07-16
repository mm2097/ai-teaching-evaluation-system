<!--
  练习列表面板（从 QuizManageView 拆出）
  详情 / 关闭 / 重新开启 / 延期 / 查看权限开关 / 截止时间
-->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, CircleClose, RefreshRight } from '@element-plus/icons-vue'
import {
  fetchQuizAssignments,
  closeQuizAssignment,
  reopenQuizAssignment,
  updateReviewPolicy,
  type QuizAssignmentRecord,
} from '@/api/quiz'

const props = defineProps<{
  refreshTrigger?: number  // 外部变更时递增以触发刷新
}>()

// 后端返回的数据实际含 QuizAssignment 所有字段，用宽松类型避免 vue-tsc 报错
type AssignmentItem = QuizAssignmentRecord & Record<string, any>

const assignmentList = ref<AssignmentItem[]>([])
const detailVisible = ref(false)
const detailAssignment = ref<AssignmentItem | null>(null)

// 重开 / 延期对话框
const reopenVisible = ref(false)
const reopenTarget = ref<AssignmentItem | null>(null)
const reopenDeadline = ref('')
const reopening = ref(false)

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

/** 判断任务是否已过截止时间 */
function isAssignmentExpired(row: AssignmentItem): boolean {
  if (!row.deadline) return false
  return new Date(String(row.deadline).replace(' ', 'T')) < new Date()
}

function openReopenDialog(row: AssignmentItem) {
  reopenTarget.value = row
  // 默认新截止时间为7天后
  const d = new Date()
  d.setDate(d.getDate() + 7)
  reopenDeadline.value = d.toISOString().replace('T', ' ').substring(0, 16)
  reopenVisible.value = true
}

async function handleReopen() {
  if (!reopenTarget.value) return
  reopening.value = true
  try {
    const result = await reopenQuizAssignment(reopenTarget.value.id, reopenDeadline.value || undefined)
    ElMessage.success(result.message || '已重新开启')
    reopenVisible.value = false
    await loadAssignments()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    reopening.value = false
  }
}

async function handleToggleReview(row: AssignmentItem) {
  const newVal = !row.allowReview
  try {
    await updateReviewPolicy(row.id, newVal)
    row.allowReview = newVal
    ElMessage.success(newVal ? '已允许学生查看详情' : '已禁止学生查看详情')
  } catch {
    ElMessage.error('操作失败')
  }
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
      <el-table-column prop="deadline" label="截止时间" width="170">
        <template #default="{ row }">
          <span :class="{ 'deadline--expired': row.status === 'published' && isAssignmentExpired(row) }">
            {{ row.deadline || '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" :icon="View" @click="viewAssignment(row)">详情</el-button>
          <!-- 查看权限开关（所有非草稿状态均可修改） -->
          <el-popconfirm
            v-if="row.status !== 'draft'"
            :title="row.allowReview ? '确定禁止学生查看答题详情？' : '确定允许学生查看答题详情？'"
            @confirm="handleToggleReview(row)"
          >
            <template #reference>
              <el-button link size="small" :type="row.allowReview ? 'success' : 'info'">
                {{ row.allowReview ? '可查看' : '禁查看' }}
              </el-button>
            </template>
          </el-popconfirm>
          <!-- 已关闭：可重新开启 -->
          <el-button
            v-if="row.status === 'closed'"
            type="success"
            link
            size="small"
            :icon="RefreshRight"
            @click="openReopenDialog(row)"
          >
            重新开启
          </el-button>
          <!-- 已发布但已截止：可延长期限 -->
          <el-button
            v-else-if="row.status === 'published' && isAssignmentExpired(row)"
            type="warning"
            link
            size="small"
            :icon="RefreshRight"
            @click="openReopenDialog(row)"
          >
            延期
          </el-button>
          <!-- 已发布未截止：可关闭 -->
          <el-button
            v-else-if="row.status === 'published'"
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

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" :title="detailAssignment?.title" width="700px">
      <template v-if="detailAssignment">
        <p class="detail-meta">
          {{ detailAssignment.courseName }} · {{ detailAssignment.className }} ·
          {{ detailAssignment.questionCount }} 题 · 满分 {{ detailAssignment.totalScore }} 分
        </p>
        <p v-if="detailAssignment.deadline" class="detail-meta">
          截止时间：{{ detailAssignment.deadline }}
        </p>
        <div v-for="(q, idx) in detailAssignment.questions" :key="idx" class="question-card compact">
          <p><strong>{{ Number(idx) + 1 }}.</strong> {{ q.stem }}（{{ q.score }}分）</p>
        </div>
      </template>
    </el-dialog>

    <!-- 重新开启 / 延长期限对话框 -->
    <el-dialog
      v-model="reopenVisible"
      :title="reopenTarget?.status === 'closed' ? '重新开启答题' : '延长期限'"
      width="480px"
    >
      <el-form v-if="reopenTarget" label-width="100px">
        <el-form-item label="练习标题">
          <span>{{ reopenTarget.title }}</span>
        </el-form-item>
        <el-form-item label="课程班级">
          <span>{{ reopenTarget.courseName }} · {{ reopenTarget.className }}</span>
        </el-form-item>
        <el-form-item label="原截止时间">
          <span>{{ reopenTarget.deadline || '—' }}</span>
        </el-form-item>
        <el-form-item label="新截止时间" required>
          <el-date-picker
            v-model="reopenDeadline"
            type="datetime"
            placeholder="选择新的截止时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reopenVisible = false">取消</el-button>
        <el-button type="primary" :loading="reopening" @click="handleReopen">
          确认{{ reopenTarget?.status === 'closed' ? '重新开启' : '延期' }}
        </el-button>
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

.deadline--expired {
  color: #ef4444;
  font-weight: 600;
}
</style>
