<!--
  学生个人学情画像页
  展示个人雷达图、学习标签、知识模块优劣势
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import { fetchStudentProfile } from '@/api/analysis'
import { useUserStore } from '@/stores/user'
import { studentProfileRadar } from '@/mock'
import { delay } from '@/utils/auth'
import type { StudentProfileData } from '@/types'

const userStore = useUserStore()
const loading = ref(true)
const profileData = ref<StudentProfileData | null>(null)

async function loadProfile(): Promise<void> {
  loading.value = true
  try {
    profileData.value = await fetchStudentProfile({
      targetType: 'student',
      targetId: userStore.userInfo?.studentId || 1,
      analysisType: '学情画像',
    })
  } finally {
    loading.value = false
  }
}

const studentName = computed(() => profileData.value?.studentName || userStore.userInfo?.name || '同学')
const studentInfo = computed(() =>
  profileData.value
    ? `学号：${profileData.value.studentNo} · ${profileData.value.className} · ${profileData.value.courseName}`
    : '',
)

const radarOption = computed<EChartsOption>(() => ({
  tooltip: {},
  radar: {
    indicator: studentProfileRadar.indicators,
    shape: 'polygon',
    splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
    axisName: { color: '#64748b' },
  },
  series: [{
    type: 'radar',
    data: [{
      value: profileData.value?.radarValues || studentProfileRadar.values,
      name: studentName.value,
      areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
      lineStyle: { color: '#2563eb', width: 2 },
      itemStyle: { color: '#2563eb' },
    }],
  }],
}))

const dimensionScores = computed(() => profileData.value?.dimensionScores || [])
const studentTags = computed(() => profileData.value?.tags || [])

onMounted(loadProfile)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="content-card profile-card">
      <div class="profile-header">
        <el-avatar :size="72" class="profile-avatar">{{ studentName.charAt(0) }}</el-avatar>
        <div>
          <h3>{{ studentName }}</h3>
          <p>{{ studentInfo }}</p>
        </div>
      </div>
      <div class="profile-tags">
        <el-tag v-for="tag in studentTags" :key="tag" type="primary" effect="plain" round>{{ tag }}</el-tag>
      </div>
      <el-divider />
      <div class="strength-weakness">
        <div class="sw-item success">
          <h4>优势知识点</h4>
          <p>{{ profileData?.strongPoints || '-' }}</p>
        </div>
        <div class="sw-item danger">
          <h4>薄弱知识点</h4>
          <p>{{ profileData?.weakPoints || '-' }}</p>
        </div>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">学情雷达图</div>
          <BaseChart :option="radarOption" height="340px" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="content-card">
          <div class="content-card__title">维度得分详情</div>
          <div v-for="dim in dimensionScores" :key="dim.name" class="dim-item">
            <div class="dim-header">
              <span>{{ dim.name }}</span>
              <span class="dim-score">{{ dim.score }}分</span>
            </div>
            <el-progress
              :percentage="dim.score"
              :stroke-width="8"
              :color="dim.score >= 80 ? '#10b981' : dim.score >= 60 ? '#2563eb' : '#f59e0b'"
            />
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

    h3 { font-size: 20px; margin-bottom: 4px; }
    p { color: #64748b; font-size: 13px; }
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

      h4 { font-size: 14px; margin-bottom: 4px; }
      p { font-size: 13px; color: #64748b; }

      &.success { background: #ecfdf5; h4 { color: #10b981; } }
      &.danger { background: #fef2f2; h4 { color: #ef4444; } }
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

    .dim-score { font-weight: 600; color: #2563eb; }
  }

  .dim-desc { font-size: 12px; color: #94a3b8; margin-top: 4px; }
}
</style>
