<!--
  个人成绩档案页
  展示历次成绩趋势与历史记录
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { useUserStore } from '@/stores/user'
import { delay } from '@/utils/auth'

const userStore = useUserStore()
const loading = ref(true)

/** 历史成绩记录 */
const records = ref([
  { id: 1, courseName: '数据结构', semester: '2025-2026-1', type: '期中考', score: 82, total: 100, classAvg: 76, rank: 15, date: '2025-11-15' },
  { id: 2, courseName: '数据结构', semester: '2025-2026-1', type: '期末考', score: 88, total: 100, classAvg: 74, rank: 8, date: '2026-01-20' },
  { id: 3, courseName: '数据结构', semester: '2025-2026-2', type: '第一次测验', score: 85, total: 100, classAvg: 72, rank: 10, date: '2026-03-10' },
  { id: 4, courseName: '数据结构', semester: '2025-2026-2', type: '第二次测验', score: 90, total: 100, classAvg: 73, rank: 6, date: '2026-04-15' },
  { id: 5, courseName: '操作系统', semester: '2025-2026-1', type: '期末考', score: 82, total: 100, classAvg: 74, rank: 12, date: '2026-01-22' },
  { id: 6, courseName: '计算机网络', semester: '2025-2026-1', type: '期末考', score: 78, total: 100, classAvg: 72, rank: 18, date: '2026-01-25' },
])

const courseFilter = ref('')
const courseOptions = computed(() =>
  [...new Set(records.value.map((r) => r.courseName))],
)

const filteredRecords = computed(() => {
  if (!courseFilter.value) return records.value
  return records.value.filter((r) => r.courseName === courseFilter.value)
})

/** 成绩趋势折线图 */
const trendOption = computed<EChartsOption>(() => {
  const data = [...filteredRecords.value].reverse()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['我的成绩', '班级均分'], top: 0, textStyle: { color: '#64748b' } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.type + '\n' + r.date),
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
      {
        name: '班级均分',
        type: 'line',
        smooth: true,
        data: data.map((r) => r.classAvg),
        itemStyle: { color: '#94a3b8' },
        lineStyle: { type: 'dashed' },
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
  await delay(300)
  loading.value = false
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
          <BaseChart :option="trendOption" height="340px" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">课程筛选</div>
          <el-radio-group v-model="courseFilter" style="display:flex;flex-direction:column;gap:10px">
            <el-radio value="">全部课程</el-radio>
            <el-radio v-for="c in courseOptions" :key="c" :value="c">{{ c }}</el-radio>
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
        <el-table-column prop="type" label="考试类型" width="110" />
        <el-table-column label="成绩" width="120" align="center">
          <template #default="{ row }">
            <span :style="{ fontWeight: 600, color: row.score >= 90 ? '#10b981' : row.score >= 80 ? '#2563eb' : row.score >= 60 ? '#f59e0b' : '#ef4444' }">
              {{ row.score }}
            </span>
            <span style="color:#94a3b8"> / {{ row.total }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="classAvg" label="班级均分" width="90" align="center" />
        <el-table-column label="班级排名" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.rank <= 5" type="success" size="small">第 {{ row.rank }} 名</el-tag>
            <el-tag v-else-if="row.rank <= 15" type="warning" size="small">第 {{ row.rank }} 名</el-tag>
            <span v-else>第 {{ row.rank }} 名</span>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="120" />
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
