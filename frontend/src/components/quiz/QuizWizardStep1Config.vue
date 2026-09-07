<!--
  向导 - 第1步：需求配置
  居中表单：课程/班级/知识点/题型/难度分布/补充说明
  难度分布：简单/中等/困难各几题，自动汇总题量
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Collection } from '@element-plus/icons-vue'
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

export type GenerateConfig = {
  courseId: number
  classId: number
  knowledgePoints: string[]
  questionTypes: ExerciseType[]
  questionCount: number
  difficultyDistribution: DifficultyDistribution
  extraRequirements: string
  title: string
  totalScore: number
  typeRatios: Record<ExerciseType, number>
  typeCounts: Record<ExerciseType, number>
}

const emit = defineEmits<{
  generate: [config: GenerateConfig, options?: { append?: boolean }]
  pickFromBank: []
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
  questionTypes: ['single_choice', 'multi_choice', 'judge', 'fill_blank', 'short_answer'] as ExerciseType[],
  difficultyDistribution: { easy: 2, medium: 2, hard: 1 } as DifficultyDistribution,
  extraRequirements: '',
  totalScore: 100,
  typeRatios: {
    single_choice: 0,
    multi_choice: 0,
    judge: 0,
    fill_blank: 0,
    short_answer: 0,
  } as Record<ExerciseType, number>,
  typeCounts: {
    single_choice: 3,
    multi_choice: 2,
    judge: 2,
    fill_blank: 2,
    short_answer: 2,
  } as Record<ExerciseType, number>,
})

const questionTypeOptions = [
  { label: exerciseTypeLabels.single_choice, value: 'single_choice' as ExerciseType },
  { label: exerciseTypeLabels.multi_choice, value: 'multi_choice' as ExerciseType },
  { label: exerciseTypeLabels.judge, value: 'judge' as ExerciseType },
  { label: exerciseTypeLabels.fill_blank, value: 'fill_blank' as ExerciseType },
  { label: exerciseTypeLabels.short_answer, value: 'short_answer' as ExerciseType },
]

/** 总题量 = 已选题型的题目数量之和 */
const totalCount = computed(() =>
  form.value.questionTypes.reduce((sum, t) => sum + (form.value.typeCounts[t] || 0), 0)
)

/** 难度占比提示（难度仅用于把每种题型按比例拆分到简单/中等/困难） */
const difficultyRatioHint = computed(() => {
  const d = form.value.difficultyDistribution
  const parts: string[] = []
  if (d.easy) parts.push(`简单 : ${d.easy}`)
  if (d.medium) parts.push(`中等 : ${d.medium}`)
  if (d.hard) parts.push(`困难 : ${d.hard}`)
  return `难度占比（${parts.join('  ')}）：将每种题型的题数按该比例分配到各难度`
})

/** 已选题型的数量（用于均分占比兜底） */
const selectedTypeCount = computed(() => form.value.questionTypes.length)

/** 已选题型的占比合计(%) */
const totalRatio = computed(() => {
  if (!form.value.questionTypes.length) return 0
  return form.value.questionTypes.reduce(
    (sum, t) => sum + (form.value.typeRatios[t] || 0),
    0,
  )
})

/** 将当前占比按比例归一化到 100%（避免四舍五入误差累积） */
function normalizeRatios(): void {
  const types = form.value.questionTypes
  if (!types.length) return
  const sum = types.reduce((s, t) => s + (form.value.typeRatios[t] || 0), 0)
  if (sum === 0) {
    // 全部为 0：均分
    let rest = 100
    types.forEach((t, i) => {
      const v = i === types.length - 1 ? rest : Math.round(rest / types.length)
      form.value.typeRatios[t] = v
      rest -= v
    })
    return
  }
  let rest = 100
  types.forEach((t, i) => {
    if (i === types.length - 1) {
      form.value.typeRatios[t] = rest
      return
    }
    const v = Math.round((form.value.typeRatios[t] / sum) * 100)
    form.value.typeRatios[t] = Math.max(0, v)
    rest -= v
  })
  // 负值防呆
  types.forEach((t) => {
    form.value.typeRatios[t] = Math.max(0, form.value.typeRatios[t])
  })
}

function handleTypeChange(): void {
  // 保证每个已选题型占比与题数为正（至少 1），避免后端按 0 占比/0 题数算漏分
  form.value.questionTypes.forEach((t) => {
    if ((form.value.typeRatios[t] || 0) <= 0) form.value.typeRatios[t] = 1
    if ((form.value.typeCounts[t] || 0) <= 0) form.value.typeCounts[t] = 1
  })
}

/** 智能分配：按当前已选数量均分占比 */
function autoBalanceRatios(): void {
  if (!form.value.questionTypes.length) return
  const types = form.value.questionTypes
  const per = Math.floor(100 / types.length)
  let rest = 100
  types.forEach((t, i) => {
    const v = i === types.length - 1 ? rest : per
    form.value.typeRatios[t] = v
    rest -= v
  })
}

/** 均分每种题型的题数（按已选题型均分总题数） */
function autoBalanceCounts(): void {
  if (!form.value.questionTypes.length) return
  const types = form.value.questionTypes
  const per = Math.floor(30 / types.length) || 1
  types.forEach((t) => {
    form.value.typeCounts[t] = per
  })
}

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

function validateAndGetConfig(): GenerateConfig | null {
  if (!form.value.courseId || !form.value.classId) {
    ElMessage.warning('请选择课程和班级')
    return null
  }
  if (!form.value.questionTypes.length) {
    ElMessage.warning('请至少选择一种题型')
    return null
  }
  if (totalCount.value === 0) {
    ElMessage.warning('请至少分配 1 道题')
    return null
  }
  if (!form.value.totalScore || form.value.totalScore <= 0) {
    ElMessage.warning('请输入有效的总分')
    return null
  }
  // 汇总占比前先归一化到 100%
  normalizeRatios()
  if (totalRatio.value !== 100) {
    ElMessage.warning('题型分数占比须合计为 100%')
    return null
  }
  return {
    courseId: form.value.courseId,
    classId: form.value.classId,
    knowledgePoints: form.value.knowledgePoints,
    questionTypes: form.value.questionTypes,
    questionCount: totalCount.value,
    difficultyDistribution: { ...form.value.difficultyDistribution },
    extraRequirements: form.value.extraRequirements,
    title: form.value.title,
    totalScore: form.value.totalScore,
    typeRatios: { ...form.value.typeRatios },
    typeCounts: { ...form.value.typeCounts },
  }
}

function handleGenerate(append = false): void {
  const config = validateAndGetConfig()
  if (!config) return
  emit('generate', config, { append })
}

function handlePickFromBank(): void {
  if (!form.value.courseId) {
    ElMessage.warning('请先选择课程')
    return
  }
  emit('pickFromBank')
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
  validateAndGetConfig,
})
</script>

<template>
  <div class="step1-config">
    <div class="config-form">
      <div class="form-header">
        <h3>组卷配置</h3>
        <p class="form-desc">支持混合组卷：可先选题再 AI 补题，或先生成再选题</p>
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
          <el-checkbox-group v-model="form.questionTypes" @change="handleTypeChange">
            <el-checkbox v-for="t in questionTypeOptions" :key="t.value" :value="t.value">
              {{ t.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <!-- 每题型数量（题型数量优先，总题量=各题型之和） -->
        <el-form-item label="每题型数量">
          <div class="ratio-box">
            <div v-if="selectedTypeCount" class="ratio-rows">
              <div v-for="t in questionTypeOptions" :key="t.value" v-show="form.questionTypes.includes(t.value)" class="ratio-row">
                <span class="ratio-label">{{ t.label }}</span>
                <el-input-number
                  :model-value="form.typeCounts[t.value]"
                  :min="0"
                  :max="30"
                  size="small"
                  controls-position="right"
                  @update:model-value="(v: number | undefined) => { form.typeCounts[t.value] = v ?? 0 }"
                />
              </div>
              <div class="ratio-actions">
                <span class="count-sum">共 {{ totalCount }} 题</span>
                <el-link type="primary" :underline="false" @click="autoBalanceCounts">均分</el-link>
              </div>
            </div>
            <span v-else class="ratio-empty">请先选择题型</span>
          </div>
        </el-form-item>

        <!-- 试卷总分与题型分数占比 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="试卷总分">
              <el-input-number
                v-model="form.totalScore"
                :min="1"
                :max="1000"
                :step="10"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="题型分数占比">
              <div class="ratio-box">
                <div v-if="selectedTypeCount" class="ratio-rows">
                  <div v-for="t in questionTypeOptions" :key="t.value" v-show="form.questionTypes.includes(t.value)" class="ratio-row">
                    <span class="ratio-label">{{ t.label }}</span>
                    <el-input-number
                      :model-value="form.typeRatios[t.value]"
                      :min="0"
                      :max="100"
                      :step="5"
                      size="small"
                      controls-position="right"
                      @update:model-value="(v: number | undefined) => { form.typeRatios[t.value] = v ?? 0 }"
                    />
                  </div>
                  <div class="ratio-actions">
                    <span :class="['ratio-sum', { 'ok': totalRatio === 100 }]">
                      合计 {{ totalRatio }}%
                    </span>
                    <el-link type="primary" :underline="false" @click="autoBalanceRatios">均分</el-link>
                  </div>
                </div>
                <span v-else class="ratio-empty">请先选择题型</span>
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 难度占比（仅用于把每种题型按比例拆分到各难度） -->
        <el-form-item label="难度占比">
          <div class="difficulty-distribution">
            <div class="diff-input">
              <span class="diff-label easy">🟢 简单</span>
              <el-input-number
                v-model="form.difficultyDistribution.easy"
                :min="0"
                :max="100"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="diff-input">
              <span class="diff-label medium">🟡 中等</span>
              <el-input-number
                v-model="form.difficultyDistribution.medium"
                :min="0"
                :max="100"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="diff-input">
              <span class="diff-label hard">🔴 困难</span>
              <el-input-number
                v-model="form.difficultyDistribution.hard"
                :min="0"
                :max="100"
                size="small"
                controls-position="right"
              />
            </div>
            <span class="distribution-hint">{{ difficultyRatioHint }}</span>
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

        <el-form-item label=" ">
          <div class="compose-actions">
            <el-button
              type="primary"
              size="large"
              :loading="props.loading"
              :icon="MagicStick"
              @click="handleGenerate(false)"
            >
              AI 生成题目（{{ totalCount }} 题）
            </el-button>
            <el-button size="large" :icon="Collection" :disabled="props.loading" @click="handlePickFromBank">
              从题库选题
            </el-button>
          </div>
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

  .ratio-box {
    width: 100%;
    .ratio-rows {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .ratio-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      .ratio-label { font-size: 13px; color: #475569; }
    }
    .ratio-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 4px;
      .ratio-sum {
        font-size: 13px;
        color: #f56c6c;
        &.ok { color: #67c23a; }
      }
      .count-sum {
        font-size: 13px;
        color: #475569;
      }
    }
    .ratio-empty { font-size: 13px; color: #94a3b8; }
  }

  .compose-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
}
</style>

