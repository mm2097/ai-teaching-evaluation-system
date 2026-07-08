<!--
  学生学情画像分析页面
  单课程维度学情雷达图、标签与知识点优劣势
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
  classId,
  courseId,
  targetId,
  studentList,
  studentLoading,
  semesterOptions,
  classOptions,
  courseOptions,
  showClassFilter,
  showCourseFilter,
  showTargetTypeFilter,
  showStudentPicker,
  queryParams,
} = scope

const profileData = ref<StudentProfileData | null>(null)

async function loadProfile(): Promise<void> {
  if (!queryParams.value.courseId) return
  if (queryParams.value.targetType === 'student' && !queryParams.value.targetId) return
  profileData.value = await fetchStudentProfile({
    ...queryParams.value,
    analysisType: '学情画像',
  })
}

const studentName = computed(() => profileData.value?.studentName || '加载中...')
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

onMounted(async () => {
  await scope.loadOptions()
  await loadProfile()
})
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
        :show-student-picker="showStudentPicker"
        :student-list="studentList"
        :student-loading="studentLoading"
        :class-options="classOptions"
        :course-options="courseOptions"
        :show-query-button="true"
        @query="loadProfile"
      />
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="content-card profile-card">
          <div class="profile-header">
            <el-avatar :size="72" class="profile-avatar">{{ studentName.charAt(0) }}</el-avatar>
            <div>
              <h3>{{ studentName }}</h3>
              <p class="profile-meta">{{ studentInfo }}</p>
            </div>
          </div>
          <div class="tag-list">
            <el-tag v-for="tag in studentTags" :key="tag" type="primary" effect="plain" size="small">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :lg="16">
        <div class="content-card">
          <div class="content-card__title">学情雷达图</div>
          <BaseChart :option="radarOption" height="360px" />
        </div>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__title">维度得分详情</div>
      <el-table :data="dimensionScores" stripe border>
        <el-table-column prop="name" label="维度" width="140" />
        <el-table-column prop="score" label="得分" width="100" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.score"
              :stroke-width="8"
              :color="row.score >= 80 ? '#10b981' : row.score >= 60 ? '#2563eb' : '#ef4444'"
            />
          </template>
        </el-table-column>
        <el-table-column prop="desc" label="说明" />
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.profile-card {
  height: 100%;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;

  h3 {
    font-size: 20px;
    color: #1e293b;
    margin-bottom: 4px;
  }
}

.profile-meta {
  font-size: 13px;
  color: #64748b;
}

.profile-avatar {
  background: linear-gradient(135deg, #2563eb, #6366f1);
  color: #fff;
  font-size: 28px;
  font-weight: 600;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
