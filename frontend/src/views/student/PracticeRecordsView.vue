<!--
  练习记录页面
  展示教师布置与自主练习的全部已提交记录
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import { fetchStudentPracticeRecords } from '@/api/quiz'
import { isSelfPracticeTask } from '@/utils/errorBookStorage'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment } from '@/types'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)
const records = ref<QuizAssignment[]>([])
const filterTab = ref<'all' | 'assigned' | 'self'>('all')

const filteredRecords = computed(() => {
  if (filterTab.value === 'assigned') {
    return records.value.filter((r) => !isSelfPracticeTask(r.title))
  }
  if (filterTab.value === 'self') {
    return records.value.filter((r) => isSelfPracticeTask(r.title))
  }
  return records.value
})

onMounted(async () => {
  loading.value = true
  try {
    const studentId = userStore.userInfo?.studentId
    if (!studentId) {
      ElMessage.warning('未获取到学生信息，请重新登录')
      return
    }
    records.value = await fetchStudentPracticeRecords(studentId)
  } finally {
    loading.value = false
  }
})

function viewDetail(record: QuizAssignment): void {
  if (record.allowReview === false && !isSelfPracticeTask(record.title)) {
    ElMessage.info('教师已关闭本次练习的题目详情查看')
    return
  }
  if (record.mySubmissionId) {
    router.push(`/student/quiz-result?id=${record.mySubmissionId}`)
  } else {
    ElMessage.warning('暂无答题记录详情')
  }
}
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card">
      <div class="content-card__title">练习记录</div>
      <p class="page-desc">查看教师布置练习与自主练习的全部作答记录，数据来自服务端持久化存储。</p>

      <el-tabs v-model="filterTab">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="教师布置" name="assigned" />
        <el-tab-pane label="自主练习" name="self" />
      </el-tabs>

      <el-empty v-if="!filteredRecords.length" description="暂无练习记录">
        <el-button type="primary" @click="router.push('/quiz/answer')">去答题</el-button>
      </el-empty>

      <div
        v-for="record in filteredRecords"
        :key="record.id"
        class="record-card"
      >
        <div class="record-info">
          <h3>
            {{ record.title }}
            <el-tag v-if="isSelfPracticeTask(record.title)" size="small" type="warning" effect="plain">自主练习</el-tag>
            <el-tag v-else size="small" type="success" effect="plain">教师布置</el-tag>
          </h3>
          <p>{{ record.courseName }} · {{ record.questionCount }} 题 · 满分 {{ record.totalScore }} 分</p>
          <p class="record-score">
            得分：<span>{{ record.myScore ?? 0 }} / {{ record.totalScore }}</span>
          </p>
          <div class="record-tags">
            <el-tag v-for="kp in record.knowledgePoints" :key="kp" size="small" effect="plain">{{ kp }}</el-tag>
          </div>
        </div>
        <el-button
          v-if="record.mySubmissionId"
          :type="record.allowReview === false && !isSelfPracticeTask(record.title) ? 'info' : 'primary'"
          :icon="View"
          plain
          :disabled="record.allowReview === false && !isSelfPracticeTask(record.title)"
          @click="viewDetail(record)"
        >
          {{ record.allowReview === false && !isSelfPracticeTask(record.title) ? '详情不可查看' : '查看详情' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-desc {
  margin: -8px 0 16px;
  font-size: 13px;
  color: #64748b;
}

.record-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 12px;
  background: #f8fafc;

  h3 {
    font-size: 16px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  p {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 8px;
  }

  .record-score span {
    font-weight: 700;
    color: #2563eb;
  }

  .record-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
}
</style>
