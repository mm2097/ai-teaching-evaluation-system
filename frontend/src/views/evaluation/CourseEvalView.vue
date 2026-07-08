<!--
  课程建设质量评价页面
  展示课程综合评价与同类对比排名
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { evalGradeType } from '@/utils/auth'
import request from '@/utils/request'

const courseEvalList = ref<any[]>([])
const selectedCourse = ref<any>(null)

onMounted(async () => {
  try {
    const res = await request.get('/v1/evaluations')
    courseEvalList.value = res.data
    if (courseEvalList.value.length) selectedCourse.value = courseEvalList.value[0]
  } catch { courseEvalList.value = [] }
})

/** 课程维度对比柱状图 */
const barOption = computed<EChartsOption>(() => {
  const courses = courseEvalList
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: courses.map((c) => c.targetName), top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: ['考核质量', '学生参与', '成绩合理', '教学效果'] },
    yAxis: { type: 'value', max: 100 },
    series: courses.map((c, idx) => ({
      name: c.targetName,
      type: 'bar',
      data: c.dimensions.map((d) => d.score),
      barWidth: 24,
      itemStyle: { borderRadius: [4, 4, 0, 0], color: ['#2563eb', '#10b981'][idx] },
    })),
  }
})

function selectCourse(row: (typeof courseEvalList)[0]): void {
  selectedCourse.value = row
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">课程评价排名</div>
          <el-table :data="courseEvalList" stripe border highlight-current-row @row-click="selectCourse">
            <el-table-column prop="rank" label="排名" width="70" align="center" />
            <el-table-column prop="targetName" label="课程名称" />
            <el-table-column prop="totalScore" label="综合得分" width="100" align="center">
              <template #default="{ row }">
                <span style="font-weight: 600; color: #2563eb">{{ row.totalScore }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="等级" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="evalGradeType(row.grade)" size="small">{{ row.grade }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">{{ selectedCourse?.targetName }} 评价报告</div>
          <div class="course-score-card">
            <div class="big-score">{{ selectedCourse?.totalScore }}</div>
            <el-tag :type="evalGradeType(selectedCourse?.grade || '')" effect="dark" size="large">
              {{ selectedCourse?.grade }}
            </el-tag>
          </div>
          <div v-for="dim in selectedCourse?.dimensions" :key="dim.name" style="margin-top: 12px">
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px">
              <span>{{ dim.name }} (权重{{ dim.weight }}%)</span>
              <span style="color: #2563eb; font-weight: 600">{{ dim.score }}分</span>
            </div>
            <el-progress :percentage="dim.score" :stroke-width="8" />
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__title">课程维度对比</div>
      <BaseChart :option="barOption" height="320px" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.course-score-card {
  text-align: center;
  padding: 20px;
  background: linear-gradient(135deg, #eff6ff, #f0fdf4);
  border-radius: 12px;

  .big-score {
    font-size: 48px;
    font-weight: 700;
    color: #2563eb;
    line-height: 1;
    margin-bottom: 8px;
  }
}
</style>
