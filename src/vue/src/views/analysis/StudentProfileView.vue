<!--
  学生学情画像分析页面
  展示多维度学情雷达图、标签与优劣势分析
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { studentProfileRadar } from '@/mock'
import { fetchStudentProfile } from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import type { StudentProfileData } from '@/types'

const scope = useAnalysisScope('student')
const {
  allowedTargetTypes,
  targetType,
  semesterId,
  deptId,
  classId,
  courseId,
  targetId,
  semesterOptions,
  classOptions,
  courseOptions,
  targetOptions,
  showDeptFilter,
  showClassFilter,
  showCourseFilter,
  showTargetTypeFilter,
  showStudentPicker,
  queryParams,
} = scope

const profileData = ref<StudentProfileData | null>(null)

async function loadProfile(): Promise<void> {
  profileData.value = await fetchStudentProfile({
    ...queryParams.value,
    analysisType: '学情画像',
  })
}

watch(() => queryParams.value, loadProfile, { deep: true, immediate: true })

const studentName = computed(() => profileData.value?.studentName || '加载中...')
const studentInfo = computed(() =>
  profileData.value
    ? `学号：${profileData.value.studentNo} · ${profileData.value.className}`
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
  series: [
    {
      type: 'radar',
      data: [
        {
          value: profileData.value?.radarValues || studentProfileRadar.values,
          name: studentName.value,
          areaStyle: { color: 'rgba(37, 99, 235, 0.2)' },
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
        },
      ],
    },
  ],
}))

const dimensionScores = computed(() => profileData.value?.dimensionScores || [])
const studentTags = computed(() => profileData.value?.tags || [])
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
        :allowed-target-types="allowedTargetTypes"
        :semester-options="semesterOptions"
        :show-dept-filter="showDeptFilter"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="showTargetTypeFilter"
        :show-student-picker="showStudentPicker"
        :class-options="classOptions"
        :course-options="courseOptions"
        :target-options="targetOptions"
      />
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="content-card profile-card">
          <div class="profile-header">
            <el-avatar :size="72" class="profile-avatar">{{ studentName.charAt(0) }}</el-avatar>
            <div>
              <h3>{{ studentName }}</h3>
              <p>{{ studentInfo }}</p>
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
              <p>{{ profileData?.strengths || '-' }}</p>
            </div>
            <div class="sw-item danger">
              <h4>薄弱科目</h4>
              <p>{{ profileData?.weaknesses || '-' }}</p>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="8">
        <div class="content-card">
          <div class="content-card__title">多维度学情雷达图</div>
          <BaseChart :option="radarOption" height="340px" />
        </div>
      </el-col>

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
