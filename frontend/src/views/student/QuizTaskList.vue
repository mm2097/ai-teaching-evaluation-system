<!--
  答题任务列表页
  按待完成 / 已完成分类展示答题任务
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit, Checked, View } from '@element-plus/icons-vue'
import { fetchStudentQuizzes } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment } from '@/types'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)

const allQuizzes = ref<QuizAssignment[]>([])
const activeTab = ref<'pending' | 'completed'>('pending')

const pendingQuizzes = computed(() =>
  allQuizzes.value.filter((q) => !q.submitted),
)

const completedQuizzes = computed(() =>
  allQuizzes.value.filter((q) => q.submitted),
)

const statusMap: Record<string, { label: string; type: 'success' | 'warning' | 'info' | 'danger' }> = {
  published: { label: '进行中', type: 'warning' },
  closed: { label: '已关闭', type: 'info' },
}

onMounted(async () => {
  loading.value = true
  try {
    const studentId = userStore.userInfo?.studentId || 1
    allQuizzes.value = await fetchStudentQuizzes(studentId)
  } finally {
    loading.value = false
  }
})

/** 判断任务是否已过截止时间 */
function isExpired(quiz: QuizAssignment): boolean {
  if (!quiz.deadline) return false
  return new Date(quiz.deadline.replace(' ', 'T')) < new Date()
}

function startQuiz(quiz: QuizAssignment): void {
  if (isExpired(quiz)) {
    return  // 已截止，按钮已禁用，兜底拦截
  }
  if (quiz.submitted) {
    return  // 已提交，兜底拦截
  }
  router.push(`/quiz/answer?start=${quiz.id}`)
}

function viewResult(quiz: QuizAssignment): void {
  if (quiz.mySubmissionId) {
    router.push(`/student/quiz-result?id=${quiz.mySubmissionId}`)
  } else {
    ElMessage.warning('暂无答题记录，请完成练习后再查看')
  }
}
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待完成" name="pending" />
        <el-tab-pane label="已完成" name="completed" />
      </el-tabs>

      <!-- 待完成 -->
      <div v-if="activeTab === 'pending'">
        <el-empty v-if="!pendingQuizzes.length" description="暂无待完成的练习" />
        <div v-for="quiz in pendingQuizzes" :key="quiz.id" class="quiz-card" :class="{ expired: isExpired(quiz) }">
          <div class="quiz-info">
            <h3>{{ quiz.title }}</h3>
            <p class="quiz-meta">{{ quiz.courseName }} · {{ quiz.questionCount }} 题 · 满分 {{ quiz.totalScore }} 分</p>
            <div class="quiz-tags">
              <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">
                {{ kp }}
              </el-tag>
            </div>
            <p v-if="quiz.deadline" class="deadline" :class="{ 'deadline--expired': isExpired(quiz) }">
              截止：{{ quiz.deadline }}
            </p>
          </div>
          <template v-if="isExpired(quiz)">
            <el-tag type="danger" size="small" effect="plain" style="margin-right: 12px">已截止</el-tag>
            <el-button type="info" :icon="Edit" disabled>已截止</el-button>
          </template>
          <template v-else>
            <el-tag type="warning" size="small" effect="plain" style="margin-right: 12px">待完成</el-tag>
            <el-button type="primary" :icon="Edit" @click="startQuiz(quiz)">开始答题</el-button>
          </template>
        </div>
      </div>

      <!-- 已完成 -->
      <div v-if="activeTab === 'completed'">
        <el-empty v-if="!completedQuizzes.length" description="暂无已完成的练习" />
        <div
          v-for="quiz in completedQuizzes"
          :key="quiz.id"
          class="quiz-card completed"
          :class="{ expired: isExpired(quiz), closed: quiz.status === 'closed' }"
        >
          <div class="quiz-info">
            <h3>
              {{ quiz.title }}
              <el-tag v-if="quiz.status === 'closed'" type="info" size="small" effect="plain">已关闭</el-tag>
              <el-tag v-else-if="isExpired(quiz)" type="danger" size="small" effect="plain">已截止</el-tag>
            </h3>
            <p class="quiz-meta">
              {{ quiz.courseName }} · {{ quiz.questionCount }} 题 ·
              得分：<span class="completed-score">{{ quiz.myScore ?? 0 }} / {{ quiz.totalScore }}</span>
            </p>
            <div class="quiz-tags">
              <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">
                {{ kp }}
              </el-tag>
            </div>
            <p v-if="quiz.deadline" class="deadline" :class="{ 'deadline--expired': isExpired(quiz) || quiz.status === 'closed' }">
              截止：{{ quiz.deadline }}
            </p>
          </div>
          <el-tag type="success" size="small" effect="plain" style="margin-right: 12px">已答题</el-tag>
          <el-button
            type="primary"
            :icon="View"
            plain
            @click="viewResult(quiz)"
          >
            查看结果
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.quiz-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 12px;
  transition: box-shadow 0.2s;

  &:hover { box-shadow: 0 2px 12px rgba(37, 99, 235, 0.08); }

  &.completed {
    background: #f8fafc;
  }

  &.expired {
    background: #fef2f2;
  }

  &.closed {
    background: #f1f5f9;
  }

  h3 { font-size: 16px; margin-bottom: 6px; }

  .quiz-meta {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 4px;
  }

  .quiz-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 4px;
  }

  .deadline {
    font-size: 12px;
    color: #ef4444;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .completed-score {
    font-weight: 700;
    color: #2563eb;
  }
}
</style>
