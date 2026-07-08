<!--
  教师教学质量评价页面
  展示教师综合评价得分、维度详情与排名
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { evalGradeType } from '@/utils/auth'
import request from '@/utils/request'

const teacherEvalList = ref<any[]>([])
const selectedTeacher = ref<any>(null)

onMounted(async () => {
  try {
    const res = await request.get('/v1/evaluations')
    teacherEvalList.value = res.data.filter((e: any) => e.targetType === 'student') // 暂复用学生评价数据
    if (teacherEvalList.value.length) selectedTeacher.value = teacherEvalList.value[0]
  } catch { teacherEvalList.value = [] }
})

/** 维度雷达图 */
const radarOption = computed<EChartsOption>(() => {
  const dims = selectedTeacher.value?.dimensions || []
  return {
    tooltip: {},
    radar: {
      indicator: dims.map((d) => ({ name: d.name, max: 100 })),
      shape: 'polygon',
    },
    series: [{
      type: 'radar',
      data: [{
        value: dims.map((d) => d.score),
        name: selectedTeacher.value?.targetName,
        areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
        lineStyle: { color: '#2563eb' },
      }],
    }],
  }
})

/**
 * 选择教师查看详情
 */
function selectTeacher(row: (typeof teacherEvalList)[0]): void {
  selectedTeacher.value = row
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">教师评价排名</div>
          <el-table :data="teacherEvalList" stripe border highlight-current-row @row-click="selectTeacher">
            <el-table-column prop="rank" label="排名" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.rank <= 3" :type="row.rank === 1 ? 'danger' : row.rank === 2 ? 'warning' : 'primary'" effect="dark" round>
                  {{ row.rank }}
                </el-tag>
                <span v-else>{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="targetName" label="教师姓名" width="120" />
            <el-table-column prop="totalScore" label="综合得分" width="100" align="center">
              <template #default="{ row }">
                <span style="font-weight: 600; color: #2563eb">{{ row.totalScore }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="评价等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="evalGradeType(row.grade)" size="small">{{ row.grade }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="维度得分">
              <template #default="{ row }">
                <span v-for="d in row.dimensions" :key="d.name" class="dim-tag">{{ d.name }}: {{ d.score }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">{{ selectedTeacher?.targetName }} - 维度分析</div>
          <BaseChart :option="radarOption" height="300px" />
          <el-divider />
          <div v-for="dim in selectedTeacher?.dimensions" :key="dim.name" class="dim-detail">
            <div class="dim-info">
              <span>{{ dim.name }}</span>
              <span>权重 {{ dim.weight }}%</span>
            </div>
            <el-progress :percentage="dim.score" :stroke-width="8" />
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.dim-tag {
  display: inline-block;
  font-size: 12px;
  color: #64748b;
  margin-right: 12px;
}

.dim-detail {
  margin-bottom: 12px;

  .dim-info {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    margin-bottom: 4px;
    color: #64748b;
  }
}
</style>
