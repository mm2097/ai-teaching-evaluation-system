<!--
  教学效果关联分析页面
  分析教学行为指标与学习效果的关联度
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { useAnalysisScope } from '@/composables/useAnalysisScope'

const scope = useAnalysisScope('teacher')
const {
  allowedTargetTypes, targetType, semesterId, deptId, classId, courseId, targetId,
  semesterOptions, classOptions, courseOptions, targetOptions,
  showDeptFilter, showTargetTypeFilter,
} = scope

const correlationTargetTypes = computed(() =>
  allowedTargetTypes.value.filter((t) => t === 'teacher' || t === 'course'),
)

const indicators = [
  { name: '作业布置量', correlation: 0.72, impact: '显著正相关', suggestion: '适度增加课后练习有助于巩固知识' },
  { name: '作业批改反馈', correlation: 0.85, impact: '强正相关', suggestion: '及时详细的批改反馈对成绩提升效果最明显' },
  { name: '课堂互动频次', correlation: 0.68, impact: '显著正相关', suggestion: '增加课堂提问与讨论环节' },
  { name: '答疑响应速度', correlation: 0.61, impact: '中等正相关', suggestion: '缩短答疑响应时间，提升学生满意度' },
  { name: '课件更新频率', correlation: 0.45, impact: '弱正相关', suggestion: '定期更新课件内容，保持与时俱进' },
  { name: '考试难度系数', correlation: -0.32, impact: '负相关', suggestion: '考试难度过高可能导致及格率下降' },
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
  xAxis: { name: '批改反馈次数', nameLocation: 'center', nameGap: 25 },
  yAxis: { name: '平均成绩', nameTextStyle: { padding: [0, 0, 0, 20] } },
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
        v-model:dept-id="deptId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="correlationTargetTypes"
        :semester-options="semesterOptions"
        :show-dept-filter="showDeptFilter"
        :show-class-filter="false"
        :show-course-filter="targetType === 'course'"
        :show-target-type-filter="showTargetTypeFilter"
        :show-student-picker="false"
        :class-options="classOptions"
        :course-options="courseOptions"
        :target-options="targetOptions"
      />
    </div>

    <el-row :gutter="16">
      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">教学行为关联度分析</div>
          <BaseChart :option="barOption" height="380px" />
        </div>
      </el-col>
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">批改反馈 vs 成绩散点图</div>
          <BaseChart :option="scatterOption" height="380px" />
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__title">教学优化建议</div>
      <el-table :data="indicators" stripe border>
        <el-table-column prop="name" label="教学行为指标" width="140" />
        <el-table-column prop="correlation" label="关联度" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.correlation >= 0 ? '#2563eb' : '#ef4444', fontWeight: 600 }">
              {{ row.correlation > 0 ? '+' : '' }}{{ row.correlation }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="impact" label="影响程度" width="130">
          <template #default="{ row }">
            <el-tag :type="row.correlation >= 0.7 ? 'success' : row.correlation >= 0.5 ? 'primary' : 'info'" size="small">
              {{ row.impact }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="suggestion" label="优化建议" />
      </el-table>
    </div>
  </div>
</template>
