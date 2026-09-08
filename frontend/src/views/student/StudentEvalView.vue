<!--
  学生个人学习评价页
  对接 evaluations.py：/evaluations/results、/evaluations
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { useUserStore } from '@/stores/user'
import { fetchMyCourses } from '@/api/dict'
import {
  evalGradeTagType,
  fetchEvaluationResults,
  fetchEvaluations,
  type AcademicPartScore,
  type AttitudeDetail,
} from '@/api/evaluations'

const userStore = useUserStore()
const loading = ref(true)
const courseId = ref<number>()
const courseOptions = ref<{ label: string; value: number }[]>([])

const evalData = ref<{
  targetName: string
  courseName: string
  totalScore: number | null
  grade: string
  dimensions: { name: string; score: number; weight: number }[]
  academicParts: AcademicPartScore[]
  attitudeDetail: AttitudeDetail | null
}>({
  targetName: userStore.userInfo?.name || '同学',
  courseName: '',
  totalScore: null,
  grade: '—',
  dimensions: [] as { name: string; score: number; weight: number }[],
  academicParts: [] as AcademicPartScore[],
  attitudeDetail: null,
})

const gradeTagType = computed(() => evalGradeTagType(evalData.value.grade))
const academicDimension = computed(() => evalData.value.dimensions.find(
  (dimension) => dimension.name.includes('学业') || dimension.name === '成绩',
))
const attitudeDimension = computed(() => evalData.value.dimensions.find(
  (dimension) => dimension.name.includes('态度'),
))
const hasAcademicData = computed(() => evalData.value.academicParts.some(
  (part) => part.score != null,
))
const hasAttitudeData = computed(() => {
  const detail = evalData.value.attitudeDetail
  return Boolean(
    detail?.attendanceAvailable
    || detail?.interactionAvailable
    || detail?.homeworkAvailable,
  )
})
const academicSourceScore = computed<number | null>(() => {
  const scored = evalData.value.academicParts.filter(
    (part): part is AcademicPartScore & { score: number } => part.score != null,
  )
  const totalWeight = scored.reduce((total, part) => total + part.weight, 0)
  if (!totalWeight) return null
  const total = scored.reduce((sum, part) => sum + part.score * part.weight, 0)
  return Number((total / totalWeight).toFixed(1))
})
const academicDimensionWeight = computed(() => academicDimension.value?.weight ?? 60)
const attitudeDimensionWeight = computed(() => attitudeDimension.value?.weight ?? 40)

const academicPartNames: Record<AcademicPartScore['part'], string> = {
  discussion: '课堂讨论',
  midterm: '期中考试',
  final: '期末考试',
  attendance: '课程考勤',
  homework: '平时作业',
  other: '其他过程性考核',
}
const barOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 100, right: 20, top: 10, bottom: 30 },
  xAxis: {
    type: 'value', max: 100,
    axisLabel: { color: '#64748b', formatter: '{value}分' },
  },
  yAxis: {
    type: 'category',
    data: evalData.value.dimensions.map((d) => d.name),
    axisLabel: { color: '#64748b' },
  },
  series: [{
    type: 'bar',
    data: evalData.value.dimensions.map((d) => ({
      value: d.score,
      itemStyle: {
        color: d.score >= 85 ? '#10b981' : d.score >= 75 ? '#2563eb' : d.score >= 60 ? '#f59e0b' : '#ef4444',
        borderRadius: [0, 6, 6, 0],
      },
    })),
    barWidth: 20,
  }],
}))

async function loadCourses(): Promise<void> {
  const studentId = userStore.userInfo?.studentId
  if (!studentId) {
    courseOptions.value = []
    return
  }

  const courses = await fetchMyCourses()
  courseOptions.value = courses.map((course) => ({
    value: course.id,
    label: course.courseName,
  }))

  if (!courseId.value && courseOptions.value.length) {
    courseId.value = courseOptions.value[0]!.value
  }
  if (courseId.value && !courseOptions.value.some((c) => c.value === courseId.value)) {
    courseId.value = courseOptions.value[0]?.value
  }
}

async function loadEvalData(): Promise<void> {
  const studentId = userStore.userInfo?.studentId
  if (!studentId || !courseId.value) {
    evalData.value = {
      targetName: userStore.userInfo?.name || '同学',
      courseName: '',
      totalScore: null,
      grade: '—',
      dimensions: [],
      academicParts: [],
      attitudeDetail: null,
    }
    return
  }

  loading.value = true
  try {
    const [results, list] = await Promise.all([
      fetchEvaluationResults({ studentId, courseId: courseId.value }),
      fetchEvaluations({ studentId, courseId: courseId.value }),
    ])

    const detail = list.find((item) => item.courseId === courseId.value) ?? list[0]
    const latest = results.length ? results[results.length - 1]! : null

    if (detail || latest) {
      const courseName = detail?.courseName || courseOptions.value.find((c) => c.value === courseId.value)?.label || ''
      if (detail?.courseName && courseId.value) {
        const opt = courseOptions.value.find((c) => c.value === courseId.value)
        if (opt) opt.label = detail.courseName
      }
      evalData.value = {
        targetName: detail?.studentName || latest?.studentName || evalData.value.targetName,
        courseName,
        totalScore: detail ? detail.totalScore : (latest?.totalScore ?? null),
        grade: detail?.grade ?? latest?.grade ?? '—',
        dimensions: detail?.dimensions.map((d) => ({
          name: d.name,
          score: d.score,
          weight: d.weight,
        })) ?? [],
        academicParts: detail?.academicParts ?? [],
        attitudeDetail: detail?.attitudeDetail ?? null,
      }
    } else {
      evalData.value = {
        targetName: userStore.userInfo?.name || '同学',
        courseName: courseOptions.value.find((c) => c.value === courseId.value)?.label || '',
        totalScore: null,
        grade: '—',
        dimensions: [],
        academicParts: [],
        attitudeDetail: null,
      }
    }
  } catch {
    evalData.value.dimensions = []
    evalData.value.academicParts = []
    evalData.value.attitudeDetail = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadCourses()
  await loadEvalData()
  inited = true
})

let inited = false
watch(courseId, async () => {
  if (!inited) return
  await loadEvalData()
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card filter-row">
      <span class="filter-label">选择课程</span>
      <el-select
        v-model="courseId"
        placeholder="请选择课程"
        style="width: 260px"
        :disabled="!courseOptions.length"
      >
        <el-option v-for="opt in courseOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <el-empty v-if="!courseOptions.length" description="暂无选修课程" />

    <template v-else>
      <div class="content-card score-hero">
        <div class="hero-left">
          <h2>学习质量综合评价</h2>
          <p class="hero-sub">
            <template v-if="evalData.courseName">《{{ evalData.courseName }}》</template>
            基于多维度数据的综合学习质量评价
          </p>
        </div>
        <div class="hero-right">
          <div class="total-score">{{ evalData.totalScore ?? '—' }}</div>
          <div class="total-label">综合得分</div>
          <el-tag v-if="evalData.grade !== '—'" :type="gradeTagType" size="large" effect="dark">
            {{ evalData.grade }}
          </el-tag>
          <el-tag v-else type="info" size="large">暂无评价</el-tag>
        </div>
      </div>

      <div class="content-card source-section source-section--academic">
        <div class="source-section__header">
          <div class="source-section__identity">
            <span class="source-section__index">综合评价维度一</span>
            <h3>学业水平</h3>
            <p>由各类课程考核成绩按构成占比汇总，反映本课程的学业表现。</p>
          </div>
          <div class="source-section__summary">
            <el-tag effect="plain">综合评价权重 {{ academicDimensionWeight }}%</el-tag>
            <span>维度得分</span>
            <strong v-if="hasAcademicData">{{ academicSourceScore }} 分</strong>
            <strong v-else class="empty">暂无数据</strong>
          </div>
        </div>
        <div class="source-section__divider" />
        <el-empty v-if="!evalData.academicParts.length" description="该课程暂未配置学业水平构成" />
        <div v-else class="source-grid">
          <div v-for="part in evalData.academicParts" :key="part.part" class="source-item">
            <div class="source-item__heading">
              <span>{{ academicPartNames[part.part] }}</span>
              <el-tag size="small" effect="plain">构成占比 {{ part.weight }}%</el-tag>
            </div>
            <div class="source-item__score" :class="{ empty: part.score == null }">
              {{ part.score == null ? '暂无成绩数据' : `${part.score} 分` }}
            </div>
            <el-progress
              v-if="part.score != null"
              :percentage="part.score"
              :stroke-width="7"
              :show-text="false"
              :color="part.score >= 85 ? '#10b981' : part.score >= 75 ? '#2563eb' : part.score >= 60 ? '#f59e0b' : '#ef4444'"
            />
          </div>
        </div>
      </div>

      <div v-if="evalData.attitudeDetail" class="content-card source-section source-section--attitude">
        <div class="source-section__header">
          <div class="source-section__identity">
            <span class="source-section__index">综合评价维度二</span>
            <h3>学习态度</h3>
            <p>由课程考勤、课堂参与和作业提交记录按构成占比汇总，不等同于课程考核成绩。</p>
          </div>
          <div class="source-section__summary">
            <el-tag effect="plain" type="success">综合评价权重 {{ attitudeDimensionWeight }}%</el-tag>
            <span>维度得分</span>
            <strong v-if="hasAttitudeData">{{ evalData.attitudeDetail.score }} 分</strong>
            <strong v-else class="empty">暂无数据</strong>
          </div>
        </div>
        <div class="source-section__divider" />
        <div class="source-grid">
          <div class="source-item">
            <div class="source-item__heading">
              <span>课程考勤</span>
              <el-tag size="small" effect="plain">构成占比 {{ evalData.attitudeDetail.weights.attendance * 100 }}%</el-tag>
            </div>
            <div v-if="evalData.attitudeDetail.attendanceAvailable" class="source-item__score">
              {{ evalData.attitudeDetail.attendanceScore }} 分
            </div>
            <div v-else class="source-item__score empty">暂无考勤数据</div>
          </div>
          <div class="source-item">
            <div class="source-item__heading">
              <span>课堂参与</span>
              <el-tag size="small" effect="plain">构成占比 {{ evalData.attitudeDetail.weights.interaction * 100 }}%</el-tag>
            </div>
            <div v-if="evalData.attitudeDetail.interactionAvailable" class="source-item__score">
              {{ evalData.attitudeDetail.interactionScore }} 分
            </div>
            <div v-else class="source-item__score empty">暂无参与数据</div>
          </div>
          <div class="source-item">
            <div class="source-item__heading">
              <span>作业提交</span>
              <el-tag size="small" effect="plain">构成占比 {{ evalData.attitudeDetail.weights.homework * 100 }}%</el-tag>
            </div>
            <div v-if="evalData.attitudeDetail.homeworkAvailable" class="source-item__score">
              {{ evalData.attitudeDetail.homeworkScore }} 分
              <small>已提交 {{ evalData.attitudeDetail.homeworkSubmittedCount }}/{{ evalData.attitudeDetail.homeworkAssignedCount }}</small>
            </div>
            <div v-else class="source-item__score empty">暂无已发布作业</div>
          </div>
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :span="14">
          <div class="content-card">
            <div class="content-card__title">综合评价维度得分</div>
            <p class="dimension-note">由上方“学业水平”和“学习态度”数据来源分别汇总后，用于计算综合得分。</p>
            <el-empty v-if="!evalData.dimensions.length" description="该课程暂无评价数据" />
            <div v-for="dim in evalData.dimensions" :key="dim.name" class="dim-card">
              <div class="dim-top">
                <span class="dim-name">{{ dim.name }}</span>
                <span class="dim-weight">综合评价权重 {{ dim.weight }}%</span>
              </div>
              <div class="dim-progress">
                <el-progress
                  :percentage="dim.score"
                  :stroke-width="10"
                  :color="dim.score >= 85 ? '#10b981' : dim.score >= 75 ? '#2563eb' : dim.score >= 60 ? '#f59e0b' : '#ef4444'"
                />
                <span class="dim-score">{{ dim.score }}分</span>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="10">
          <div v-if="evalData.dimensions.length" class="content-card">
            <div class="content-card__title">综合评价维度图</div>
            <BaseChart :option="barOption" height="280px" />
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped lang="scss">
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;

  .filter-label {
    font-size: 14px;
    color: #64748b;
  }
}

.score-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .hero-left {
    h2 { font-size: 20px; margin-bottom: 6px; }
    .hero-sub { font-size: 14px; color: #64748b; }
  }

  .hero-right {
    text-align: center;

    .total-score { font-size: 48px; font-weight: 700; color: #2563eb; line-height: 1; }
    .total-label { font-size: 14px; color: #64748b; margin: 6px 0 10px; }
  }
}

.source-section {
  margin-bottom: 16px;
  border-top: 3px solid #2563eb;

  &--attitude { border-top-color: #10b981; }
}

.source-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.source-section__identity {
  min-width: 0;

  h3 {
    margin: 3px 0 5px;
    color: #0f172a;
    font-size: 19px;
  }

  p { margin: 0; color: #64748b; font-size: 13px; }
}

.source-section__index {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.source-section--attitude .source-section__index { color: #059669; }

.source-section__summary {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  justify-items: end;
  gap: 4px 14px;
  flex: 0 0 auto;

  .el-tag { grid-row: 1 / 3; }
  > span { color: #94a3b8; font-size: 12px; }
  > strong { color: #2563eb; font-size: 20px; }
  > strong.empty { color: #94a3b8; font-size: 14px; font-weight: 500; }
}

.source-section--attitude .source-section__summary > strong { color: #059669; }
.source-section--attitude .source-section__summary > strong.empty { color: #94a3b8; }

.source-section__divider {
  height: 1px;
  margin: 16px 0;
  background: #e2e8f0;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.source-item {
  min-height: 92px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  background: #f8fafc;
}

.source-item__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #334155;
  font-weight: 600;
}

.source-item__score {
  margin: 12px 0 8px;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;

  small { margin-left: 8px; color: #64748b; font-size: 12px; font-weight: 400; }
  &.empty { color: #94a3b8; font-size: 14px; font-weight: 500; }
}

.dimension-note {
  margin: -3px 0 14px;
  color: #64748b;
  font-size: 13px;
}

@media (max-width: 900px) {
  .source-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .source-section__header { align-items: flex-start; flex-direction: column; }
  .source-section__summary { justify-items: start; }
  .source-grid { grid-template-columns: 1fr; }
}

.dim-card {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;

  .dim-top {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;

    .dim-name { font-weight: 600; font-size: 14px; }
    .dim-weight { font-size: 12px; color: #94a3b8; }
  }

  .dim-progress {
    display: flex;
    align-items: center;
    gap: 12px;

    .el-progress { flex: 1; }
    .dim-score { font-weight: 700; color: #2563eb; font-size: 16px; }
  }
}
</style>
