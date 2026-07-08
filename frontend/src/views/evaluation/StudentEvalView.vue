<!--
  学生学习质量评价页面
  展示学生综合评价与班级分布
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { evalGradeType } from '@/utils/auth'
import request from '@/utils/request'

const studentEvalList = ref<any[]>([])

onMounted(async () => {
  try {
    const res = await request.get('/v1/evaluations')
    studentEvalList.value = res.data
  } catch { studentEvalList.value = [] }
})

/** 评价等级分布饼图 */
const pieOption = computed<EChartsOption>(() => {
  const gradeCount: Record<string, number> = {}
  for (const item of studentEvalList.value) {
    const g = item.grade || '未知'
    gradeCount[g] = (gradeCount[g] || 0) + 1
  }
  const gradeNames = ['优秀', '良好', '中等', '合格', '不合格']
  const data = gradeNames
    .map((name) => ({ name, value: gradeCount[name] || 0 }))
    .filter((d) => d.value > 0)
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    color: ['#10b981', '#2563eb', '#f59e0b', '#94a3b8', '#ef4444'],
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%' },
      data,
    }],
  }
})
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="16">
        <div class="content-card">
          <div class="content-card__title">学生学习质量评价</div>
          <el-table :data="studentEvalList" stripe border>
            <el-table-column prop="targetName" label="学生姓名" width="120" />
            <el-table-column prop="totalScore" label="综合得分" width="100" align="center">
              <template #default="{ row }">
                <span style="font-weight: 600; color: #2563eb; font-size: 16px">{{ row.totalScore }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="评价等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="evalGradeType(row.grade)" effect="dark" size="small">{{ row.grade }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="各维度得分">
              <template #default="{ row }">
                <div class="dim-scores">
                  <div v-for="d in row.dimensions" :key="d.name" class="dim-score-item">
                    <span class="dim-name">{{ d.name }}</span>
                    <el-progress :percentage="d.score" :stroke-width="6" :show-text="false" style="width: 80px" />
                    <span class="dim-val">{{ d.score }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <div class="content-card__title">班级评价分布</div>
          <BaseChart :option="pieOption" height="340px" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.dim-scores {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.dim-score-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;

  .dim-name {
    color: #64748b;
    width: 56px;
  }

  .dim-val {
    font-weight: 600;
    color: #2563eb;
    width: 24px;
  }
}
</style>
