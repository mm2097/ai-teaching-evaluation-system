<!--
  学生个人学习评价页
  展示个人综合得分、各维度评价详情
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { useUserStore } from '@/stores/user'
import { evalGradeType } from '@/utils/auth'

/** 评价指标体系配置 */
const evalIndicatorConfig = [
  { id: 'academic', name: '学业成绩', weight: 40, rule: '基于各次作业、测验、考试的加权平均分' },
  { id: 'attitude', name: '学习态度', weight: 25, rule: '综合出勤率、作业提交率、课堂参与度' },
  { id: 'progress', name: '学习进步', weight: 20, rule: '对比近三次测验成绩的变化趋势' },
  { id: 'mastery', name: '知识掌握', weight: 15, rule: '基于知识点测评的掌握率统计' },
]

const userStore = useUserStore()
const loading = ref(true)

const evalData = ref({
  targetName: userStore.userInfo?.name || '同学',
  totalScore: 88.5,
  grade: '优秀' as const,
  dimensions: [
    { name: '学业成绩', score: 90, weight: 40 },
    { name: '学习态度', score: 85, weight: 25 },
    { name: '学习进步', score: 92, weight: 20 },
    { name: '知识掌握', score: 86, weight: 15 },
  ],
})

const gradeTagType = computed(() => evalGradeType(evalData.value.grade))

/** 各维度得分柱状图 */
const barOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 100, right: 20, top: 10, bottom: 30 },
  xAxis: {
    type: 'value', max: 100,
    axisLabel: { color: '#64748b', formatter: '{value}分' },
  },
  yAxis: {
    type: 'category',
    data: evalData.value.dimensions.map((d) => d.name),
    axisLabel: { color: '#64748b' },
  },
  series: [{
    type: 'bar',
    data: evalData.value.dimensions.map((d) => ({
      value: d.score,
      itemStyle: {
        color: d.score >= 90 ? '#10b981' : d.score >= 80 ? '#2563eb' : d.score >= 70 ? '#f59e0b' : '#ef4444',
        borderRadius: [0, 6, 6, 0],
      },
    })),
    barWidth: 20,
  }],
}))

onMounted(() => {
  loading.value = false
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 总评 -->
    <div class="content-card score-hero">
      <div class="hero-left">
        <h2>学习质量综合评价</h2>
        <p class="hero-sub">基于学业成绩、学习态度、进步趋势、知识掌握四维评估</p>
      </div>
      <div class="hero-right">
        <div class="total-score">{{ evalData.totalScore }}</div>
        <div class="total-label">综合得分</div>
        <el-tag :type="gradeTagType" size="large" effect="dark">{{ evalData.grade }}</el-tag>
      </div>
    </div>

    <!-- 维度详情 -->
    <el-row :gutter="16">
      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">各维度得分详情</div>
          <div v-for="dim in evalData.dimensions" :key="dim.name" class="dim-card">
            <div class="dim-top">
              <span class="dim-name">{{ dim.name }}</span>
              <span class="dim-weight">权重 {{ dim.weight }}%</span>
            </div>
            <div class="dim-progress">
              <el-progress
                :percentage="dim.score"
                :stroke-width="10"
                :color="dim.score >= 90 ? '#10b981' : dim.score >= 80 ? '#2563eb' : dim.score >= 70 ? '#f59e0b' : '#ef4444'"
              />
              <span class="dim-score">{{ dim.score }}分</span>
            </div>
            <p class="dim-desc">
              <template v-if="dim.name === '学业成绩'">本课程加权平均分排名班级前列</template>
              <template v-else-if="dim.name === '学习态度'">考勤率高、作业按时提交、课堂参与积极</template>
              <template v-else-if="dim.name === '学习进步'">近三次测验成绩持续提升，进步趋势明显</template>
              <template v-else>核心知识点掌握度较高，薄弱项需加强</template>
            </p>
          </div>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">评价体系说明</div>
          <div v-for="indicator in evalIndicatorConfig" :key="indicator.id" class="indicator-item">
            <div class="ind-header">
              <span class="ind-name">{{ indicator.name }}</span>
              <el-tag size="small" type="info">{{ indicator.weight }}%</el-tag>
            </div>
            <p class="ind-rule">{{ indicator.rule }}</p>
          </div>
        </div>
        <div class="content-card" style="margin-top: 16px">
          <div class="content-card__title">维度得分可视化</div>
          <BaseChart :option="barOption" height="280px" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.score-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .hero-left {
    h2 { font-size: 20px; margin-bottom: 6px; }
    .hero-sub { font-size: 14px; color: #64748b; }
  }

  .hero-right {
    text-align: center;

    .total-score { font-size: 48px; font-weight: 700; color: #2563eb; line-height: 1; }
    .total-label { font-size: 14px; color: #64748b; margin: 6px 0 10px; }
  }
}

.dim-card {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;

  .dim-top {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;

    .dim-name { font-weight: 600; font-size: 14px; }
    .dim-weight { font-size: 12px; color: #94a3b8; }
  }

  .dim-progress {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;

    .el-progress { flex: 1; }

    .dim-score { font-weight: 700; color: #2563eb; font-size: 16px; }
  }

  .dim-desc { font-size: 13px; color: #64748b; line-height: 1.5; }
}

.indicator-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 8px;

  .ind-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;

    .ind-name { font-size: 14px; font-weight: 500; }
  }

  .ind-rule { font-size: 12px; color: #94a3b8; line-height: 1.5; }
}
</style>
