<!--
  知识点掌握度分析页面
  热力图展示班级与个人知识点掌握情况
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { knowledgeHeatmap } from '@/mock'

/** 知识点掌握度热力图 */
const heatmapOption = computed<EChartsOption>(() => ({
  tooltip: {
    position: 'top',
    formatter: (params: { value: number[] }) => {
      const [x, y, val] = params.value
      return `${knowledgeHeatmap.students[y]} - ${knowledgeHeatmap.knowledgePoints[x]}<br/>掌握度: ${val}%`
    },
  },
  grid: { left: 80, right: 40, top: 10, bottom: 80 },
  xAxis: {
    type: 'category',
    data: knowledgeHeatmap.knowledgePoints,
    splitArea: { show: true },
    axisLabel: { rotate: 30, fontSize: 11 },
  },
  yAxis: {
    type: 'category',
    data: knowledgeHeatmap.students,
    splitArea: { show: true },
  },
  visualMap: {
    min: 0,
    max: 100,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    inRange: { color: ['#fef2f2', '#fca5a5', '#f59e0b', '#86efac', '#10b981'] },
  },
  series: [{
    type: 'heatmap',
    data: knowledgeHeatmap.data,
    label: { show: true, fontSize: 11 },
    emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
  }],
}))

/** 薄弱知识点清单 */
const weakPoints = [
  { name: '面向对象', classRate: 62, weakCount: 18, level: '严重' },
  { name: '异常处理', classRate: 66, weakCount: 15, level: '中等' },
  { name: '文件IO', classRate: 70, weakCount: 12, level: '中等' },
  { name: '控制结构', classRate: 78, weakCount: 8, level: '轻微' },
]

/** 个人 vs 班级对比数据 */
const compareData = [
  { point: '变量与表达式', personal: 92, classAvg: 84 },
  { point: '控制结构', personal: 78, classAvg: 78 },
  { point: '函数定义', personal: 85, classAvg: 80 },
  { point: '面向对象', personal: 65, classAvg: 62 },
  { point: '数据结构', personal: 80, classAvg: 77 },
]
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="content-card__title">知识点掌握度热力图</div>
      <BaseChart :option="heatmapOption" height="400px" />
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">班级薄弱知识点</div>
          <el-table :data="weakPoints" stripe border>
            <el-table-column prop="name" label="知识点" />
            <el-table-column prop="classRate" label="班级掌握率" width="120" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.classRate < 70 ? '#ef4444' : '#f59e0b' }">{{ row.classRate }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="weakCount" label="薄弱人数" width="100" align="center" />
            <el-table-column prop="level" label="严重程度" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.level === '严重' ? 'danger' : row.level === '中等' ? 'warning' : 'info'" size="small">
                  {{ row.level }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">个人与班级掌握度对比</div>
          <div v-for="item in compareData" :key="item.point" class="compare-item">
            <div class="compare-label">{{ item.point }}</div>
            <div class="compare-bars">
              <div class="bar-row">
                <span class="bar-tag personal">个人</span>
                <el-progress :percentage="item.personal" :stroke-width="10" color="#2563eb" />
              </div>
              <div class="bar-row">
                <span class="bar-tag class">班级</span>
                <el-progress :percentage="item.classAvg" :stroke-width="10" color="#94a3b8" />
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.compare-item {
  margin-bottom: 16px;

  .compare-label {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
  }

  .bar-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;

    .bar-tag {
      font-size: 12px;
      width: 32px;
      flex-shrink: 0;

      &.personal { color: #2563eb; }
      &.class { color: #94a3b8; }
    }

    .el-progress {
      flex: 1;
    }
  }
}
</style>
