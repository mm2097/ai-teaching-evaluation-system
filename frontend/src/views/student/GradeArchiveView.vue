<!--
  个人成绩档案页
  展示历次成绩趋势与历史记录
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { fetchStudentScoreArchive, type ScoreArchiveRecord } from '@/api/studentDashboard'
import { fetchMyCourses } from '@/api/dict'

const loading = ref(true)

/** 历史成绩记录（来自后端真实接口） */
const records = ref<ScoreArchiveRecord[]>([])

const courseFilter = ref<number | ''>('')
const courseOptions = ref<{ id: number; name: string }[]>([])

const filteredRecords = computed(() => {
  if (!courseFilter.value) return records.value
  return records.value.filter((r) => r.courseId === courseFilter.value)
})
const selectedCourseName = computed(() =>
  courseOptions.value.find((course) => course.id === courseFilter.value)?.name,
)

const trendOption = computed<EChartsOption>(() => {
  const data = filteredRecords.value
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['我的成绩'], top: 0, textStyle: { color: '#64748b' } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.batchName || r.type),
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    yAxis: { type: 'value', max: 100, name: '分数', axisLabel: { color: '#64748b' } },
    series: [
      {
        name: '我的成绩',
        type: 'line',
        smooth: true,
        data: data.map((r) => r.score),
        itemStyle: { color: '#2563eb' },
        areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
        markLine: {
          silent: true,
          data: [{ type: 'average', name: '平均' }],
          lineStyle: { color: '#f59e0b', type: 'dashed' },
        },
      },
    ],
  }
})

const stats = computed(() => {
  const scores = filteredRecords.value.map((r) => r.score)
  if (!scores.length) return { avg: '—', max: '—', min: '—', trend: '—' }
  return {
    avg: (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1),
    max: Math.max(...scores).toString(),
    min: Math.min(...scores).toString(),
    trend: scores.length >= 2
      ? (scores[scores.length - 1]! >= scores[scores.length - 2]! ? '上升' : '下降')
      : '—',
  }
})

onMounted(async () => {
  try {
    const [archiveRecords, courses] = await Promise.all([
      fetchStudentScoreArchive(),
      fetchMyCourses(),
    ])
    records.value = archiveRecords
    courseOptions.value = courses.map((course) => ({ id: course.id, name: course.courseName }))
  } catch {
    records.value = []
    courseOptions.value = []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="平均分">{{ stats.avg }} 分</el-descriptions-item>
        <el-descriptions-item label="最高分">{{ stats.max }} 分</el-descriptions-item>
        <el-descriptions-item label="最低分">{{ stats.min }} 分</el-descriptions-item>
        <el-descriptions-item label="成绩趋势">
          <el-tag :type="stats.trend === '上升' ? 'success' : stats.trend === '下降' ? 'danger' : 'info'" size="small">
            {{ stats.trend }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">成绩变化趋势</div>
          <BaseChart v-if="filteredRecords.length" :option="trendOption" height="340px" />
          <el-empty v-else :description="selectedCourseName ? `${selectedCourseName} 暂无成绩记录` : '暂无成绩记录'" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">课程筛选</div>
          <el-radio-group v-model="courseFilter" style="display:flex;flex-direction:column;gap:10px">
            <el-radio value="">全部课程</el-radio>
            <el-radio v-for="c in courseOptions" :key="c.id" :value="c.id">{{ c.name }}</el-radio>
          </el-radio-group>
        </div>
      </el-col>
    </el-row>

    <div class="content-card" style="margin-top: 16px">
      <div class="content-card__title">
        成绩记录
        <el-tag size="small" class="count-tag">{{ filteredRecords.length }} 条</el-tag>
      </div>
      <el-table :data="filteredRecords" stripe border>
        <el-table-column prop="courseName" label="课程" width="130" />
        <el-table-column prop="semester" label="学期" width="140" />
        <el-table-column prop="type" label="成绩类型" width="150" />
        <el-table-column prop="batchName" label="考核批次" width="140">
          <template #default="{ row }">{{ row.batchName || '—' }}</template>
        </el-table-column>
        <el-table-column label="成绩" width="120" align="center">
          <template #default="{ row }">
            <span :style="{ fontWeight: 600, color: row.score >= 90 ? '#10b981' : row.score >= 80 ? '#2563eb' : row.score >= 60 ? '#f59e0b' : '#ef4444' }">
              {{ row.score }}
            </span>
            <span style="color:#94a3b8"> / {{ row.total }}</span>
          </template>
        </el-table-column>
        <el-table-column label="班级均分" width="90" align="center"><template #default="{ row }">{{ row.classAvg ?? '—' }}</template></el-table-column>
        <el-table-column label="班级排名" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.rank && row.rank <= 5" type="success" size="small">第 {{ row.rank }} 名</el-tag>
            <el-tag v-else-if="row.rank && row.rank <= 15" type="warning" size="small">第 {{ row.rank }} 名</el-tag>
            <span v-else>{{ row.rank ? `第 ${row.rank} 名` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="日期" width="120">
          <template #default="{ row }">{{ row.date || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.count-tag {
  margin-left: 8px;
  font-weight: normal;
}
</style>
