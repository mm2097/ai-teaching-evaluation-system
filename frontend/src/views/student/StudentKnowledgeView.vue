<!--
  学生个人知识点热力图页
  展示个人掌握度热力图、薄弱项清单
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { fetchKnowledgeHeatmap } from '@/api/analysis'
import { fetchCourses } from '@/api/dict'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(true)
const dataReady = ref(false)
const courseId = ref<number>(1)

const heatmapData = ref({
  knowledgePoints: [] as string[],
  students: [] as string[],
  data: [] as number[][],
})

async function loadHeatmap(): Promise<void> {
  loading.value = true
  try {
    heatmapData.value = await fetchKnowledgeHeatmap({
      targetType: 'student',
      targetId: userStore.userInfo?.studentId || 1,
      courseId: courseId.value,
      classId: userStore.userInfo?.classId,
      analysisType: '知识点掌握度',
    })
    dataReady.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 获取学生所在班级的课程
  try {
    const studentClassId = userStore.userInfo?.classId
    const courses = studentClassId
      ? await fetchCourses({ deptId: 1, classId: studentClassId })
      : []
    if (courses.length) courseId.value = courses[0]!.id
  } catch { /* empty */ }
  await loadHeatmap()
})

const heatmapOption = computed<EChartsOption>(() => ({
  tooltip: {
    position: 'top',
    formatter: (params: unknown) => {
      const p = params as { value: number[] }
      return `${heatmapData.value.knowledgePoints[p.value[0]!]}<br/>掌握度: ${p.value[2]!}%`
    },
  },
  grid: { left: 20, right: 40, top: 10, bottom: 60 },
  xAxis: {
    type: 'category',
    data: heatmapData.value.knowledgePoints,
    axisLabel: { rotate: 30, fontSize: 11 },
  },
  yAxis: { type: 'category', data: [''], show: false },
  visualMap: {
    min: 0, max: 100,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    inRange: { color: ['#fef2f2', '#fca5a5', '#f59e0b', '#86efac', '#10b981'] },
  },
  series: [{
    type: 'heatmap',
    data: heatmapData.value.data,
    label: { show: false },
  }],
}))

const weakPoints = computed(() => {
  if (!heatmapData.value.data.length) return []
  return heatmapData.value.data
    .map(([x, , val]) => ({
      name: heatmapData.value.knowledgePoints[x!]!,
      rate: val!,
      level: val! < 60 ? ('严重' as const) : val! < 75 ? ('中等' as const) : ('轻微' as const),
    }))
    .filter((p) => p.rate < 75)
    .sort((a, b) => a.rate - b.rate)
})

const overviewStats = computed(() => {
  if (!heatmapData.value.data.length) return { avg: '—', maxItem: '—', minItem: '—' }
  const values = heatmapData.value.data.map((d) => d[2]!)
  const maxIdx = values.indexOf(Math.max(...values))
  const minIdx = values.indexOf(Math.min(...values))
  return {
    avg: (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) + '%',
    maxItem: heatmapData.value.knowledgePoints[maxIdx]!,
    minItem: heatmapData.value.knowledgePoints[minIdx]!,
  }
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card">
      <div class="content-card__title">个人知识点掌握度热力图</div>
      <el-descriptions :column="3" border style="margin-bottom: 16px">
        <el-descriptions-item label="平均掌握度">{{ overviewStats.avg }}</el-descriptions-item>
        <el-descriptions-item label="最佳知识点">{{ overviewStats.maxItem }}</el-descriptions-item>
        <el-descriptions-item label="最弱知识点">{{ overviewStats.minItem }}</el-descriptions-item>
      </el-descriptions>
      <el-skeleton v-if="!dataReady" :rows="3" animated style="padding: 20px" />
      <BaseChart v-else :option="heatmapOption" height="220px" />
    </div>

    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">需要加强的知识点</div>
      <el-empty v-if="!weakPoints.length" description="所有知识点掌握良好！" />
      <el-table v-else :data="weakPoints" stripe border>
        <el-table-column type="index" label="#" width="60" align="center" />
        <el-table-column prop="name" label="知识点" />
        <el-table-column prop="rate" label="掌握率" width="120" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.rate < 60 ? '#ef4444' : '#f59e0b', fontWeight: 600 }">
              {{ row.rate }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.level === '严重' ? 'danger' : row.level === '中等' ? 'warning' : 'info'" size="small">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议" min-width="180">
          <template #default="{ row }">
            <span v-if="row.level === '严重'" class="suggest-text">建议优先通过AI练习强化该知识点</span>
            <span v-else-if="row.level === '中等'" class="suggest-text">建议针对性复习相关章节</span>
            <span v-else class="suggest-text">保持练习即可巩固</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.suggest-text {
  font-size: 13px;
  color: #64748b;
}
</style>
