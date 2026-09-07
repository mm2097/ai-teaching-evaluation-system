<!--
  学生个人学习评价页
  对接 evaluations.py：/evaluations/results、/evaluations
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { useUserStore } from '@/stores/user'
import {
  evalGradeTagType,
  fetchEvaluationResults,
  fetchEvaluations,
  type AcademicPartScore,
} from '@/api/evaluations'

const userStore = useUserStore()
const loading = ref(true)
const courseId = ref<number>()
const courseOptions = ref<{ label: string; value: number }[]>([])

const evalData = ref({
  targetName: userStore.userInfo?.name || '同学',
  courseName: '',
  totalScore: 0,
  grade: '—',
  dimensions: [] as { name: string; score: number; weight: number }[],
  academicParts: [] as AcademicPartScore[],
})

const gradeTagType = computed(() => evalGradeTagType(evalData.value.grade))

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

  const list = await fetchEvaluations({ studentId })
  const courseMap = new Map<number, string>()
  for (const item of list) {
    courseMap.set(item.courseId, item.courseName)
  }

  if (!courseMap.size) {
    const results = await fetchEvaluationResults({ studentId })
    for (const r of results) {
      if (!courseMap.has(r.courseId)) {
        courseMap.set(r.courseId, `课程 ${r.courseId}`)
      }
    }
  }

  courseOptions.value = [...courseMap.entries()].map(([value, label]) => ({ value, label }))

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
      totalScore: 0,
      grade: '—',
      dimensions: [],
      academicParts: [],
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
        totalScore: detail?.totalScore ?? latest?.totalScore ?? 0,
        grade: detail?.grade ?? latest?.grade ?? '—',
        dimensions: detail?.dimensions.map((d) => ({
          name: d.name,
          score: d.score,
          weight: d.weight,
        })) ?? [],
        academicParts: detail?.academicParts ?? [],
      }
    } else {
      evalData.value = {
        targetName: userStore.userInfo?.name || '同学',
        courseName: courseOptions.value.find((c) => c.value === courseId.value)?.label || '',
        totalScore: 0,
        grade: '—',
        dimensions: [],
        academicParts: [],
      }
    }
  } catch {
    evalData.value.dimensions = []
    evalData.value.academicParts = []
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
          <div class="total-score">{{ evalData.totalScore || '—' }}</div>
          <div class="total-label">综合得分</div>
          <el-tag v-if="evalData.grade !== '—'" :type="gradeTagType" size="large" effect="dark">
            {{ evalData.grade }}
          </el-tag>
          <el-tag v-else type="info" size="large">暂无评价</el-tag>
        </div>
      </div>

      <div class="content-card academic-parts-card">
        <div class="content-card__title">课程成绩类型构成</div>
        <el-empty v-if="!evalData.academicParts.length" description="该课程暂未配置成绩构成" />
        <el-row v-else :gutter="12">
          <el-col
            v-for="part in evalData.academicParts"
            :key="part.part"
            :xs="24"
            :sm="12"
            :lg="8"
          >
            <div class="academic-part-item">
              <div class="part-heading">
                <span>{{ part.name }}</span>
                <el-tag size="small" effect="plain">权重 {{ part.weight }}%</el-tag>
              </div>
              <div class="part-score" :class="{ empty: part.score == null }">
                {{ part.score == null ? '暂无成绩' : `${part.score} 分` }}
              </div>
              <el-progress
                v-if="part.score != null"
                :percentage="part.score"
                :stroke-width="7"
                :show-text="false"
                :color="part.score >= 85 ? '#10b981' : part.score >= 75 ? '#2563eb' : part.score >= 60 ? '#f59e0b' : '#ef4444'"
              />
            </div>
          </el-col>
        </el-row>
      </div>

      <el-row :gutter="16">
        <el-col :span="14">
          <div class="content-card">
            <div class="content-card__title">各维度得分详情</div>
            <el-empty v-if="!evalData.dimensions.length" description="该课程暂无评价数据" />
            <div v-for="dim in evalData.dimensions" :key="dim.name" class="dim-card">
              <div class="dim-top">
                <span class="dim-name">{{ dim.name }}</span>
                <span class="dim-weight">权重 {{ dim.weight }}%</span>
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
            <div class="content-card__title">维度得分可视化</div>
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

.academic-parts-card {
  margin-bottom: 16px;
}

.academic-part-item {
  min-height: 104px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: linear-gradient(145deg, #ffffff, #f8fbff);

  .part-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: #334155;
    font-weight: 600;
  }

  .part-score {
    margin: 12px 0 8px;
    color: #0f172a;
    font-size: 22px;
    font-weight: 700;

    &.empty {
      color: #94a3b8;
      font-size: 15px;
      font-weight: 500;
    }
  }
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
