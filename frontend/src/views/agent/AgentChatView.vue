<!--
  Agent 对话页面
  学情问答 Agent (P0) + 自适应组卷 Agent (P1) + 学生助学 Agent (P2)
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AgentChat from '@/components/agent/AgentChat.vue'
import { fetchCourses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import type { AgentType } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const isStudent = computed(() => userStore.userInfo?.role === 'student')
const activeAgent = ref<AgentType>(isStudent.value ? 'tutor' : 'qa')
const courseId = ref<number>()
const courseOptions = ref<{ label: string; value: number }[]>([])

const courseName = computed(
  () => courseOptions.value.find((c) => c.value === courseId.value)?.label || '',
)

onMounted(async () => {
  const role = userStore.userInfo?.role
  const teacherId = role === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const classId = role === 'student' ? userStore.userInfo?.classId : undefined
  const courses = await fetchCourses({ teacherId, classId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) {
    courseId.value = courseOptions.value[0]!.value
  }
})

function goToQuizManage(): void {
  router.push('/quiz/manage')
}

function goToQuestionBank(): void {
  router.push('/quiz/bank')
}
</script>

<template>
  <div class="page-container agent-page">
    <div class="agent-header content-card">
      <div class="agent-header__left">
        <h2>AI 智能助手</h2>
        <p v-if="isStudent">知识点讲解、错题辅导，只给提示不直接给答案</p>
        <p v-else>自然语言查询学情、智能组卷，工具调用过程全程可见</p>
      </div>
      <div class="agent-header__right">
        <span class="label">当前课程</span>
        <el-select v-model="courseId" style="width: 220px" placeholder="选择课程">
          <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeAgent" class="agent-tabs">
      <template v-if="isStudent">
        <el-tab-pane label="助学助手" name="tutor">
          <AgentChat
            v-if="courseId"
            :key="`tutor-${courseId}`"
            agent-type="tutor"
            :course-id="courseId"
            :course-name="courseName"
          />
        </el-tab-pane>
      </template>

      <template v-else>
        <el-tab-pane label="学情问答" name="qa">
          <AgentChat
            v-if="courseId"
            :key="`qa-${courseId}`"
            agent-type="qa"
            :course-id="courseId"
            :course-name="courseName"
          />
        </el-tab-pane>
        <el-tab-pane label="智能组卷" name="exam">
          <div v-if="courseId" class="exam-pane">
            <div class="exam-tip">
              <span>组卷方案生成后，请前往「AI 出题」审核发布，或在「题库管理」查看已有题目。</span>
              <div class="exam-tip__actions">
                <el-button type="primary" link @click="goToQuestionBank">题库管理 →</el-button>
                <el-button type="primary" link @click="goToQuizManage">AI 出题 →</el-button>
              </div>
            </div>
            <AgentChat
              :key="`exam-${courseId}`"
              agent-type="exam"
              :course-id="courseId"
              :course-name="courseName"
            />
          </div>
        </el-tab-pane>
      </template>
    </el-tabs>
  </div>
</template>

<style scoped lang="scss">
.agent-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  min-height: 0;
  overflow: hidden;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  margin-bottom: 16px;
  padding: 16px 20px;

  h2 {
    font-size: 18px;
    margin-bottom: 4px;
  }

  p {
    font-size: 13px;
    color: #64748b;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 10px;

    .label {
      font-size: 14px;
      color: #475569;
    }
  }
}

.agent-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;

  :deep(.el-tabs__header) {
    flex-shrink: 0;
  }

  :deep(.el-tabs__content) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  :deep(.el-tab-pane) {
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
}

.exam-pane {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.exam-tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 10px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;

  span {
    min-width: 0;
  }

  &__actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}
</style>
