<!--
  学生学情画像分析页面
  展示多维度学情雷达图、标签与优劣势分析
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { studentProfileRadar, studentTags } from '@/mock'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

/** 展示的学生姓名（学生角色显示自己） */
const studentName = computed(() =>
  userStore.userInfo?.role === 'student' ? userStore.userInfo.name : '陈同学',
)

/** 学情雷达图配置 */
const radarOption = computed<EChartsOption>(() => ({
  tooltip: {},
  radar: {
    indicator: studentProfileRadar.indicators,
    shape: 'polygon',
    splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
    axisName: { color: '#64748b' },
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: studentProfileRadar.values,
          name: studentName.value,
          areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
        },
      ],
    },
  ],
}))

/** 各维度得分明细 */
const dimensionScores = [
  { name: '学业水平', score: 85, desc: '各科目加权平均分处于班级前 20%' },
  { name: '学习态度', score: 72, desc: '出勤率 88%，作业提交率 92%' },
  { name: '学习进步', score: 88, desc: '近三次考试平均分提升 12 分' },
  { name: '知识掌握', score: 76, desc: '核心知识点平均掌握度 76%' },
  { name: '课堂参与', score: 80, desc: '课堂互动频次高于班级均值' },
]
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <!-- 学情画像卡片 -->
      <el-col :xs="24" :lg="8">
        <div class="content-card profile-card">
          <div class="profile-header">
            <el-avatar :size="72" class="profile-avatar">{{ studentName.charAt(0) }}</el-avatar>
            <div>
              <h3>{{ studentName }}</h3>
              <p>学号：2024001001 · 计科2401班</p>
            </div>
          </div>
          <div class="profile-tags">
            <el-tag v-for="tag in studentTags" :key="tag" type="primary" effect="plain" round>
              {{ tag }}
            </el-tag>
          </div>
          <el-divider />
          <div class="strength-weakness">
            <div class="sw-item success">
              <h4>优势科目</h4>
              <p>数据结构 (92分)、计算机网络 (88分)</p>
            </div>
            <div class="sw-item danger">
              <h4>薄弱科目</h4>
              <p>操作系统 (68分)、编译原理 (72分)</p>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 雷达图 -->
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">多维度学情雷达图</div>
          <BaseChart :option="radarOption" height="340px" />
        </div>
      </el-col>

      <!-- 维度得分明细 -->
      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">维度得分详情</div>
          <div v-for="dim in dimensionScores" :key="dim.name" class="dim-item">
            <div class="dim-header">
              <span>{{ dim.name }}</span>
              <span class="dim-score">{{ dim.score }}分</span>
            </div>
            <el-progress :percentage="dim.score" :stroke-width="8" :color="dim.score >= 80 ? '#10b981' : dim.score >= 60 ? '#2563eb' : '#f59e0b'" />
            <p class="dim-desc">{{ dim.desc }}</p>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.profile-card {
  .profile-header {
    display: flex;
    align-items: center;
    gap: 16px;

    .profile-avatar {
      background: linear-gradient(135deg, #2563eb, #6366f1);
      font-size: 28px;
      color: #fff;
    }

    h3 {
      font-size: 20px;
      margin-bottom: 4px;
    }

    p {
      color: #64748b;
      font-size: 13px;
    }
  }

  .profile-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
  }

  .strength-weakness {
    .sw-item {
      padding: 12px;
      border-radius: 8px;
      margin-bottom: 8px;

      h4 {
        font-size: 14px;
        margin-bottom: 4px;
      }

      p {
        font-size: 13px;
        color: #64748b;
      }

      &.success {
        background: #ecfdf5;
        h4 { color: #10b981; }
      }

      &.danger {
        background: #fef2f2;
        h4 { color: #ef4444; }
      }
    }
  }
}

.dim-item {
  margin-bottom: 16px;

  .dim-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 14px;

    .dim-score {
      font-weight: 600;
      color: #2563eb;
    }
  }

  .dim-desc {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
  }
}
</style>
