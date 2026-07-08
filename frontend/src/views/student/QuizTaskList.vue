<!--
  答题任务列表页
  按待完成 / 已完成分类展示答题任务
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Edit, Checked, View } from '@element-plus/icons-vue'
import { fetchStudentQuizzes } from '@/api/quiz'
import { useUserStore } from '@/stores/user'
import type { QuizAssignment } from '@/types'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)

const allQuizzes = ref<QuizAssignment[]>([])
const submissions = ref<{ assignmentId: number; score: number; totalScore: number; submitTime: string }[]>([])
const activeTab = ref<'pending' | 'completed'>('pending')

const pendingQuizzes = computed(() =>
  allQuizzes.value.filter((q) => !submissions.value.some((s) => s.assignmentId === q.id)),
)

const completedQuizzes = computed(() =>
  allQuizzes.value.filter((q) => submissions.value.some((s) => s.assignmentId === q.id)).map((q) => {
    const sub = submissions.value.find((s) => s.assignmentId === q.id)!
    return { ...q, score: sub.score, submitTime: sub.submitTime }
  }),
)

const statusMap: Record<string, { label: string; type: 'success' | 'warning' }> = {
  published: { label: '待完成', type: 'warning' },
  closed: { label: '已关闭', type: 'success' },
}

onMounted(async () => {
  loading.value = true
  try {
    const studentId = userStore.userInfo?.studentId || 1
    allQuizzes.value = await fetchStudentQuizzes(studentId)
    // 模拟部分已完成
    submissions.value = [
      { assignmentId: allQuizzes.value[0]?.id || 1, score: 85, totalScore: 100, submitTime: '2026-03-15 10:30' },
      { assignmentId: allQuizzes.value[1]?.id || 2, score: 72, totalScore: 100, submitTime: '2026-03-14 16:00' },
    ]
  } finally {
    loading.value = false
  }
})

function startQuiz(quiz: QuizAssignment): void {
  router.push(`/quiz/answer?start=${quiz.id}`)
}

function viewResult(submissionId: number): void {
  router.push(`/student/quiz-result?id=${submissionId}`)
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
        <div v-for="quiz in pendingQuizzes" :key="quiz.id" class="quiz-card">
          <div class="quiz-info">
            <h3>{{ quiz.title }}</h3>
            <p class="quiz-meta">{{ quiz.courseName }} · {{ quiz.questionCount }} 题 · 满分 {{ quiz.totalScore }} 分</p>
            <div class="quiz-tags">
              <el-tag v-for="kp in quiz.knowledgePoints" :key="kp" size="small" effect="plain">
                {{ kp }}
              </el-tag>
            </div>
            <p v-if="quiz.deadline" class="deadline">
              <el-icon><Clock /></el-icon> 截止：{{ quiz.deadline }}
            </p>
          </div>
          <el-button type="primary" :icon="Edit" @click="startQuiz(quiz)">开始答题</el-button>
        </div>
      </div>

      <!-- 已完成 -->
      <div v-if="activeTab === 'completed'">
        <el-empty v-if="!completedQuizzes.length" description="暂无已完成的练习" />
        <div v-for="quiz in completedQuizzes" :key="quiz.id" class="quiz-card completed">
          <div class="quiz-info">
            <h3>{{ quiz.title }}</h3>
            <p class="quiz-meta">
              {{ quiz.courseName }} · {{ quiz.questionCount }} 题 ·
              得分：<span class="completed-score">{{ quiz.score }} / {{ quiz.totalScore }}</span>
            </p>
            <p class="quiz-meta">提交时间：{{ quiz.submitTime }}</p>
          </div>
          <el-button type="primary" :icon="View" plain @click="viewResult(quiz.id)">查看结果</el-button>
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
