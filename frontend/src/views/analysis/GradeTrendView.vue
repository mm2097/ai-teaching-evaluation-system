<!--
  成绩趋势与预测分析页面
  展示班级成绩趋势、分布与个人预测结果
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { gradeTrendData } from '@/mock'

/** 班级成绩趋势折线图 */
const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['平均分', '最高分', '最低分', '及格率'], top: 0 },
  grid: { left: 50, right: 50, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: gradeTrendData.months },
  yAxis: [
    { type: 'value', name: '分数', max: 100 },
    { type: 'value', name: '及格率', max: 100, axisLabel: { formatter: '{value}%' } },
  ],
  series: [
    { name: '平均分', type: 'line', smooth: true, data: gradeTrendData.avgScore, itemStyle: { color: '#2563eb' } },
    { name: '最高分', type: 'line', smooth: true, data: gradeTrendData.maxScore, itemStyle: { color: '#10b981' } },
    { name: '最低分', type: 'line', smooth: true, data: gradeTrendData.minScore, itemStyle: { color: '#ef4444' } },
    { name: '及格率', type: 'line', smooth: true, yAxisIndex: 1, data: gradeTrendData.passRate, itemStyle: { color: '#f59e0b' }, lineStyle: { type: 'dashed' } },
  ],
}))

/** 成绩分布直方图 */
const histOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 30, bottom: 30 },
  xAxis: { type: 'category', data: ['0-59', '60-69', '70-79', '80-89', '90-100'] },
  yAxis: { type: 'value', name: '人数' },
  series: [{
    type: 'bar',
    data: [15, 38, 52, 48, 27],
    barWidth: 40,
    itemStyle: {
      borderRadius: [6, 6, 0, 0],
      color: (params: { dataIndex: number }) => {
        const colors = ['#ef4444', '#f59e0b', '#2563eb', '#10b981', '#6366f1']
        return colors[params.dataIndex] || '#2563eb'
      },
    },
  }],
}))

/** 个人成绩预测列表 */
const predictions = [
  { name: '陈同学', current: 85, predicted: '82-88', trend: '稳定', confidence: 92 },
  { name: '刘同学', current: 72, predicted: '68-74', trend: '下滑', confidence: 85 },
  { name: '赵同学', current: 90, predicted: '88-93', trend: '上升', confidence: 88 },
  { name: '孙同学', current: 65, predicted: '60-68', trend: '下滑', confidence: 78 },
  { name: '周同学', current: 95, predicted: '93-98', trend: '稳定', confidence: 94 },
]

/** 班级特征分析结论 */
const classFeatures = [
  { title: '整体水平', content: '班级平均分 78.6，高于年级均值 3.2 分，整体表现良好' },
  { title: '分化程度', content: '标准差 12.8，存在一定程度的两极分化，需关注低分群体' },
  { title: '偏科现象', content: '操作系统科目平均分偏低 (65.3)，为该班主要薄弱项' },
]
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">班级成绩趋势</div>
          <BaseChart :option="trendOption" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">成绩分布</div>
          <BaseChart :option="histOption" height="360px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">个人成绩预测（线性回归算法）</div>
          <el-table :data="predictions" stripe border>
            <el-table-column prop="name" label="学生" width="100" />
            <el-table-column prop="current" label="当前成绩" width="100" align="center" />
            <el-table-column prop="predicted" label="预测区间" width="120" align="center">
              <template #default="{ row }">
                <el-tag type="primary" effect="plain">{{ row.predicted }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="trend" label="趋势" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.trend === '上升' ? 'success' : row.trend === '下滑' ? 'danger' : 'info'" size="small">
                  {{ row.trend }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" align="center">
              <template #default="{ row }">
                <el-progress :percentage="row.confidence" :stroke-width="6" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">班级成绩特征分析</div>
          <div v-for="item in classFeatures" :key="item.title" class="feature-item">
            <h4>{{ item.title }}</h4>
            <p>{{ item.content }}</p>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.feature-item {
  padding: 14px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;
  border-left: 3px solid #2563eb;

  h4 {
    font-size: 14px;
    color: #1e293b;
    margin-bottom: 6px;
  }

  p {
    font-size: 13px;
    color: #64748b;
    line-height: 1.6;
  }
}
</style>
