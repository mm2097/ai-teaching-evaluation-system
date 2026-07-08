<!--
  学习行为关联分析页面（单课程维度）
  分析学习行为指标与成绩效果的关联度
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { useAnalysisScope } from '@/composables/useAnalysisScope'

const scope = useAnalysisScope('class')
const {
  allowedTargetTypes, targetType, semesterId, classId, courseId, targetId,
  semesterOptions, classOptions, courseOptions,
  showClassFilter, showCourseFilter, showTargetTypeFilter,
} = scope

const indicators = [
  { name: '作业提交率', correlation: 0.72, impact: '显著正相关', suggestion: '督促未交作业学生及时补交' },
  { name: '课堂问答参与', correlation: 0.85, impact: '强正相关', suggestion: '鼓励更多学生参与课堂互动' },
  { name: '考勤出勤率', correlation: 0.68, impact: '显著正相关', suggestion: '关注频繁缺勤学生' },
  { name: 'AI 练习完成率', correlation: 0.61, impact: '中等正相关', suggestion: '通过 AI 练习巩固薄弱知识点' },
  { name: '作业得分', correlation: 0.78, impact: '强正相关', suggestion: '加强作业反馈与错题讲解' },
  { name: '缺勤频次', correlation: -0.45, impact: '负相关', suggestion: '缺勤与成绩下滑高度相关，需及时干预' },
]

const barOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis', formatter: '{b}<br/>关联度: {c}' },
  grid: { left: 120, right: 40, top: 20, bottom: 30 },
  xAxis: { type: 'value', min: -1, max: 1, splitLine: { lineStyle: { type: 'dashed' } } },
  yAxis: {
    type: 'category',
    data: indicators.map((i) => i.name),
    axisLabel: { fontSize: 12 },
  },
  series: [{
    type: 'bar',
    data: indicators.map((i) => ({
      value: i.correlation,
      itemStyle: {
        color: i.correlation >= 0 ? '#2563eb' : '#ef4444',
        borderRadius: i.correlation >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
      },
    })),
    barWidth: 20,
    label: { show: true, position: 'right', formatter: '{c}' },
  }],
}))

const scatterOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item' },
  grid: { left: 60, right: 30, top: 30, bottom: 40 },
  xAxis: { name: 'AI 练习得分', nameLocation: 'center', nameGap: 25 },
  yAxis: { name: '课程成绩', nameTextStyle: { padding: [0, 0, 0, 20] } },
  series: [{
    type: 'scatter',
    symbolSize: 14,
    data: [
      [5, 62], [8, 68], [12, 72], [15, 76], [18, 80],
      [22, 83], [25, 86], [28, 88], [30, 90], [35, 93],
    ],
    itemStyle: { color: '#2563eb', opacity: 0.7 },
  }],
}))
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <AnalysisFilterBar
        v-model:target-type="targetType"
        v-model:semester-id="semesterId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="allowedTargetTypes"
        :semester-options="semesterOptions"
        :show-dept-filter="false"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="showTargetTypeFilter"
        :show-student-picker="false"
        :class-options="classOptions"
        :course-options="courseOptions"
      />
    </div>

    <el-row :gutter="16">
      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">学习行为关联度分析</div>
          <BaseChart :option="barOption" height="380px" />
        </div>
      </el-col>
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">AI 练习得分 vs 课程成绩</div>
          <BaseChart :option="scatterOption" height="380px" />
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__title">关联分析详情</div>
      <el-table :data="indicators" stripe border>
        <el-table-column prop="name" label="行为指标" width="140" />
        <el-table-column prop="correlation" label="关联度" width="100" align="center" />
        <el-table-column prop="impact" label="影响程度" width="120" />
        <el-table-column prop="suggestion" label="改进建议" />
      </el-table>
    </div>
  </div>
</template>
