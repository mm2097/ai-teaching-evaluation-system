<!--
  向导 - 第1步：需求配置
  居中表单：课程/班级/知识点/题型/难度分布/补充说明
  难度分布：简单/中等/困难各几题，自动汇总题量
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { fetchCourses, fetchClasses } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import { exerciseTypeLabels } from '@/utils/exerciseJudge'
import type { ExerciseType } from '@/types'

const props = defineProps<{
  loading: boolean
}>()

export interface DifficultyDistribution {
  easy: number
  medium: number
  hard: number
}

const emit = defineEmits<{
  generate: [config: {
    courseId: number
    classId: number
    knowledgePoints: string[]
    questionTypes: ExerciseType[]
    questionCount: number
    difficultyDistribution: DifficultyDistribution
    extraRequirements: string
    title: string
  }]
}>()

const userStore = useUserStore()

const courseOptions = ref<{ label: string; value: number }[]>([])
const classOptions = ref<{ label: string; value: number }[]>([])
const knowledgePointOptions = ref<string[]>([])

const form = ref({
  courseId: undefined as number | undefined,
  classId: undefined as number | undefined,
  title: '',
  knowledgePoints: [] as string[],
  questionTypes: ['single_choice', 'multi_choice'] as ExerciseType[],
  difficultyDistribution: { easy: 2, medium: 2, hard: 1 } as DifficultyDistribution,
  extraRequirements: '',
})

const questionTypeOptions = [
  { label: exerciseTypeLabels.single_choice, value: 'single_choice' as ExerciseType },
  { label: exerciseTypeLabels.multi_choice, value: 'multi_choice' as ExerciseType },
  { label: exerciseTypeLabels.judge, value: 'judge' as ExerciseType },
  { label: exerciseTypeLabels.fill_blank, value: 'fill_blank' as ExerciseType },
]

const totalCount = computed(() =>
  form.value.difficultyDistribution.easy +
  form.value.difficultyDistribution.medium +
  form.value.difficultyDistribution.hard
)

const distributionHint = computed(() => {
  const d = form.value.difficultyDistribution
  if (totalCount.value === 0) return '请分配题量'
  const parts: string[] = []
  if (d.easy) parts.push(`简单 ${d.easy}`)
  if (d.medium) parts.push(`中等 ${d.medium}`)
  if (d.hard) parts.push(`困难 ${d.hard}`)
  return `${parts.join(' · ')}（共 ${totalCount.value} 题）`
})

async function loadClassOptions(): Promise<void> {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const classes = await fetchClasses({
    deptId: 1,
    courseId: form.value.courseId,
    teacherId,
  })
  classOptions.value = classes.map((c) => ({ label: c.className, value: c.id }))
  if (!classOptions.value.some((c) => c.value === form.value.classId)) {
    form.value.classId = classOptions.value[0]?.value
  }
}

function handleGenerate(): void {
  if (!form.value.courseId || !form.value.classId) {
    ElMessage.warning('请选择课程和班级')
    return
  }
  if (!form.value.questionTypes.length) {
    ElMessage.warning('请至少选择一种题型')
    return
  }
  if (totalCount.value === 0) {
    ElMessage.warning('请至少分配 1 道题')
    return
  }
  emit('generate', {
    courseId: form.value.courseId,
    classId: form.value.classId,
    knowledgePoints: form.value.knowledgePoints,
    questionTypes: form.value.questionTypes,
    questionCount: totalCount.value,
    difficultyDistribution: { ...form.value.difficultyDistribution },
    extraRequirements: form.value.extraRequirements,
    title: form.value.title,
  })
}

watch(() => form.value.courseId, async () => {
  await loadClassOptions()
})

onMounted(async () => {
  const teacherId = userStore.userInfo?.role === 'teacher' ? userStore.userInfo?.teacherId : undefined
  const courses = await fetchCourses({ teacherId, deptId: 1, semesterId: 1 })
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length) form.value.courseId = courseOptions.value[0]!.value
  await loadClassOptions()
})

defineExpose({
  form,
  courseOptions,
  classOptions,
})
</script>

<template>
  <div class="step1-config">
    <div class="config-form">
      <div class="form-header">
        <h3>配置出题需求</h3>
        <p class="form-desc">填写课程信息与题目要求，AI 将从题库检索参考题并生成新题</p>
      </div>

      <el-form label-width="100px" label-position="right">
        <el-form-item label="练习标题">
          <el-input v-model="form.title" placeholder="如：数据结构专项练习（留空自动生成）" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="课程">
              <el-select v-model="form.courseId" style="width: 100%">
                <el-option v-for="c in courseOptions" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="班级">
              <el-select v-model="form.classId" style="width: 100%">
                <el-option v-for="c in classOptions" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="知识点">
          <el-select
            v-model="form.knowledgePoints"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入或选择知识点（留空则不限）"
            style="width: 100%"
          >
            <el-option v-for="kp in knowledgePointOptions" :key="kp" :label="kp" :value="kp" />
          </el-select>
        </el-form-item>

        <el-form-item label="题型">
          <el-checkbox-group v-model="form.questionTypes">
            <el-checkbox v-for="t in questionTypeOptions" :key="t.value" :value="t.value">
              {{ t.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <!-- 难度分布 -->
        <el-form-item label="难度分布">
          <div class="difficulty-distribution">
            <div class="diff-input">
              <span class="diff-label easy">🟢 简单</span>
              <el-input-number
                v-model="form.difficultyDistribution.easy"
                :min="0"
                :max="20"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="diff-input">
              <span class="diff-label medium">🟡 中等</span>
              <el-input-number
                v-model="form.difficultyDistribution.medium"
                :min="0"
                :max="20"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="diff-input">
              <span class="diff-label hard">🔴 困难</span>
              <el-input-number
                v-model="form.difficultyDistribution.hard"
                :min="0"
                :max="20"
                size="small"
                controls-position="right"
              />
            </div>
            <span class="distribution-hint">{{ distributionHint }}</span>
          </div>
        </el-form-item>

        <el-form-item label="补充说明">
          <el-input
            v-model="form.extraRequirements"
            type="textarea"
            :rows="3"
            placeholder="如：面向初学者，干扰项要合理；侧重二叉树遍历相关知识点"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="props.loading"
            :icon="MagicStick"
            @click="handleGenerate"
          >
            开始 AI 出题（{{ totalCount }} 题）
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped lang="scss">
.step1-config {
  display: flex;
  justify-content: center;
  padding: 24px 0;

  .config-form {
    max-width: 680px;
    width: 100%;

    .form-header {
      text-align: center;
      margin-bottom: 24px;

      h3 { font-size: 18px; color: #1e293b; margin-bottom: 4px; }
      .form-desc { font-size: 13px; color: #64748b; }
    }
  }

  .difficulty-distribution {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;

    .diff-input {
      display: flex;
      align-items: center;
      gap: 6px;

      .diff-label {
        font-size: 13px;
        white-space: nowrap;

        &.easy { color: #67c23a; }
        &.medium { color: #e6a23c; }
        &.hard { color: #f56c6c; }
      }
    }

    .distribution-hint {
      font-size: 13px;
      color: #64748b;
      margin-left: 8px;
    }
  }
}
</style>
