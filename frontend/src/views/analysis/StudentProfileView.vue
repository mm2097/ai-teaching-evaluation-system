<!--
  学情画像分析页面
  支持班级整体 / 学生个人双视角，单课程维度雷达图、标签与知识点优劣势
-->
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import {
  MagicStick, School, User, Warning, Trophy,
} from '@element-plus/icons-vue'
import BaseChart from '@/components/charts/BaseChart.vue'
import StatCard from '@/components/common/StatCard.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { studentProfileRadar } from '@/mock'
import { fetchClassProfile, fetchStudentProfile } from '@/api/analysis'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import { useUserStore } from '@/stores/user'
import type { ClassProfileData, StudentProfileData } from '@/types'

type ViewMode = 'class' | 'student'

const router = useRouter()
const userStore = useUserStore()
const canViewClass = computed(() => userStore.userInfo?.role !== 'student')

const viewMode = ref<ViewMode>(userStore.userInfo?.role === 'student' ? 'student' : 'class')
const loading = ref(false)

const scope = useAnalysisScope('class')
const {
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
  queryParams,
} = scope

const studentProfile = ref<StudentProfileData | null>(null)
const classProfile = ref<ClassProfileData | null>(null)

const radarIndicators = studentProfileRadar.indicators

function scoreColor(score: number): string {
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#2563eb'
  return '#ef4444'
}

async function loadProfile(): Promise<void> {
  if (!queryParams.value.courseId) return
  if (viewMode.value === 'student' && !queryParams.value.targetId) {
    studentProfile.value = null
    return
  }
  if (viewMode.value === 'class' && !queryParams.value.classId) return

  loading.value = true
  try {
    if (viewMode.value === 'class') {
      classProfile.value = await fetchClassProfile({
        ...queryParams.value,
        analysisType: '学情画像',
        targetType: 'class',
        targetId: classId.value,
      })
      studentProfile.value = null
    } else {
      studentProfile.value = await fetchStudentProfile({
        ...queryParams.value,
        analysisType: '学情画像',
        targetType: 'student',
      })
      classProfile.value = null
    }
  } finally {
    loading.value = false
  }
}

watch(viewMode, (mode) => {
  targetType.value = mode === 'class' ? 'class' : 'student'
}, { immediate: true })

function handleViewModeChange(mode: ViewMode): void {
  viewMode.value = mode
}

function goStudentProfile(studentId: number): void {
  viewMode.value = 'student'
  targetType.value = 'student'
  targetId.value = studentId
  loadProfile()
}

// ── 学生视角 ──
const studentName = computed(() => studentProfile.value?.studentName || '—')
const studentInfo = computed(() =>
  studentProfile.value
    ? `学号 ${studentProfile.value.studentNo} · ${studentProfile.value.className} · ${studentProfile.value.courseName}`
    : '',
)
const studentTags = computed(() => studentProfile.value?.tags || [])
const studentDimensions = computed(() => studentProfile.value?.dimensionScores || [])

const studentRadarOption = computed<EChartsOption>(() => ({
  tooltip: {},
  radar: {
    indicator: radarIndicators,
    shape: 'polygon',
    radius: '68%',
    splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
    axisName: { color: '#64748b', fontSize: 12 },
  },
  series: [{
    type: 'radar',
    data: [{
      value: studentProfile.value?.radarValues || studentProfileRadar.values,
      name: studentName.value,
      areaStyle: { color: 'rgba(37, 99, 235, 0.22)' },
      lineStyle: { color: '#2563eb', width: 2 },
      itemStyle: { color: '#2563eb' },
    }],
  }],
}))

// ── 班级视角 ──
const classStatCards = computed(() => {
  const p = classProfile.value
  if (!p) return []
  return [
    { title: '班级人数', value: p.studentCount, icon: 'User', color: '#2563eb' },
    { title: '综合得分', value: p.totalProfileScore, unit: '分', icon: 'TrendCharts', color: '#6366f1' },
    { title: '及格率', value: p.passRate, unit: '%', icon: 'CircleCheck', color: '#10b981' },
    { title: '优秀率', value: p.excellentRate, unit: '%', icon: 'Star', color: '#f59e0b' },
    { title: '预警学生', value: p.warningCount, icon: 'Bell', color: '#ef4444' },
  ]
})

const classRadarOption = computed<EChartsOption>(() => ({
  tooltip: {},
  radar: {
    indicator: radarIndicators,
    shape: 'polygon',
    radius: '68%',
    splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'] } },
    axisName: { color: '#64748b', fontSize: 12 },
  },
  series: [{
    type: 'radar',
    data: [{
      value: classProfile.value?.radarValues || [0, 0, 0, 0, 0],
      name: classProfile.value?.className || '班级均值',
      areaStyle: { color: 'rgba(99, 102, 241, 0.22)' },
      lineStyle: { color: '#6366f1', width: 2 },
      itemStyle: { color: '#6366f1' },
    }],
  }],
}))

const levelPieOption = computed<EChartsOption>(() => {
  const dist = classProfile.value?.levelDistribution || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
    color: dist.map((d) => d.color),
    series: [{
      type: 'pie',
      radius: ['44%', '70%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: dist.map((d) => ({ name: d.label, value: d.count })),
    }],
  }
})

const classDimensions = computed(() => classProfile.value?.dimensionScores || [])
const classTags = computed(() => classProfile.value?.tags || [])

onMounted(async () => {
  await scope.loadOptions()
  await loadProfile()
})
</script>

<template>
  <div class="page-container profile-page">
    <!-- 筛选栏 -->
    <div class="content-card">
      <div class="view-mode-bar">
        <span class="mode-label">分析视角</span>
        <el-radio-group :model-value="viewMode" size="default" @update:model-value="handleViewModeChange">
          <el-radio-button v-if="canViewClass" value="class">班级学情画像</el-radio-button>
          <el-radio-button value="student">学生个人画像</el-radio-button>
        </el-radio-group>
      </div>

      <AnalysisFilterBar
        v-model:target-type="targetType"
        v-model:semester-id="semesterId"
        v-model:class-id="classId"
        v-model:course-id="courseId"
        v-model:target-id="targetId"
        :allowed-target-types="viewMode === 'class' ? ['class'] : ['student']"
        :semester-options="semesterOptions"
        :show-dept-filter="false"
        :show-class-filter="showClassFilter"
        :show-course-filter="showCourseFilter"
        :show-target-type-filter="false"
        :show-student-picker="viewMode === 'student' && canViewClass"
        :student-list="studentList"
        :student-loading="studentLoading"
        :class-options="classOptions"
        :course-options="courseOptions"
        :show-query-button="true"
        @query="loadProfile"
      />
    </div>

    <!-- ═══ 班级学情画像 ═══ -->
    <template v-if="viewMode === 'class'">
      <div v-loading="loading">
        <template v-if="classProfile">
          <!-- 头部概览 -->
          <div class="class-hero">
            <div class="class-hero__bg" />
            <div class="class-hero__body">
              <div class="class-hero__left">
                <div class="class-hero__icon">
                  <el-icon :size="32"><School /></el-icon>
                </div>
                <div>
                  <h2 class="class-hero__title">{{ classProfile.className }}</h2>
                  <p class="class-hero__meta">
                    {{ classProfile.majorName }} · {{ classProfile.courseName }} · {{ classProfile.studentCount }} 人
                  </p>
                  <div class="tag-list">
                    <el-tag
                      v-for="tag in classTags"
                      :key="tag"
                      effect="dark"
                      size="small"
                      class="hero-tag"
                    >
                      {{ tag }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <div class="class-hero__score">
                <div class="score-ring">
                  <svg viewBox="0 0 120 120" class="score-ring__svg">
                    <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="8" />
                    <circle
                      cx="60" cy="60" r="52" fill="none"
                      stroke="#fff" stroke-width="8" stroke-linecap="round"
                      :stroke-dasharray="`${classProfile.totalProfileScore * 3.27} 327`"
                      transform="rotate(-90 60 60)"
                    />
                  </svg>
                  <div class="score-ring__text">
                    <span class="score-ring__num">{{ classProfile.totalProfileScore }}</span>
                    <span class="score-ring__label">综合得分</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 统计卡片 -->
          <div class="stat-grid">
            <StatCard v-for="item in classStatCards" :key="item.title" v-bind="item" />
          </div>

          <!-- 雷达 + 等级分布 -->
          <el-row :gutter="16">
            <el-col :xs="24" :lg="14">
              <div class="content-card">
                <div class="content-card__title">班级五维学情雷达</div>
                <BaseChart :option="classRadarOption" height="340px" />
              </div>
            </el-col>
            <el-col :xs="24" :lg="10">
              <div class="content-card">
                <div class="content-card__title">学业水平等级分布</div>
                <BaseChart :option="levelPieOption" height="340px" />
              </div>
            </el-col>
          </el-row>

          <!-- 维度得分 -->
          <div class="content-card">
            <div class="content-card__title">维度得分详情</div>
            <div class="dimension-grid">
              <div v-for="dim in classDimensions" :key="dim.name" class="dimension-card">
                <div class="dimension-card__head">
                  <span class="dimension-card__name">{{ dim.name }}</span>
                  <span class="dimension-card__score" :style="{ color: scoreColor(dim.score) }">
                    {{ dim.score }}
                  </span>
                </div>
                <el-progress
                  :percentage="dim.score"
                  :stroke-width="10"
                  :color="scoreColor(dim.score)"
                  :show-text="false"
                />
                <p class="dimension-card__desc">{{ dim.desc }}</p>
              </div>
            </div>
          </div>

          <!-- 优劣势 + 学生名单 -->
          <el-row :gutter="16">
            <el-col :xs="24" :lg="12">
              <div class="content-card insight-card insight-card--strong">
                <div class="content-card__title">班级优势知识点</div>
                <p class="insight-text">{{ classProfile.strongPoints }}</p>
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <div class="content-card insight-card insight-card--weak">
                <div class="content-card__title">班级薄弱知识点</div>
                <p class="insight-text">{{ classProfile.weakPoints }}</p>
              </div>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :xs="24" :lg="12">
              <div class="content-card">
                <div class="content-card__title">
                  <el-icon><Trophy /></el-icon>
                  优秀学生
                </div>
                <div class="student-rank-list">
                  <div
                    v-for="(s, idx) in classProfile.topStudents"
                    :key="s.studentId"
                    class="student-rank-item"
                    @click="goStudentProfile(s.studentId)"
                  >
                    <span class="rank-badge" :class="`rank-${idx + 1}`">{{ idx + 1 }}</span>
                    <span class="rank-name">{{ s.studentName }}</span>
                    <span class="rank-score">{{ s.score }} 分</span>
                  </div>
                  <p v-if="!classProfile.topStudents.length" class="empty-hint">暂无数据</p>
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <div class="content-card">
                <div class="content-card__title">
                  <el-icon><Warning /></el-icon>
                  需关注学生
                </div>
                <div class="student-rank-list">
                  <div
                    v-for="s in classProfile.attentionStudents"
                    :key="s.studentId"
                    class="student-rank-item student-rank-item--warn"
                    @click="goStudentProfile(s.studentId)"
                  >
                    <span class="rank-name">{{ s.studentName }}</span>
                    <span class="rank-score warn">{{ s.score }} 分</span>
                    <span class="rank-reason">{{ s.reason }}</span>
                  </div>
                  <p v-if="!classProfile.attentionStudents.length" class="empty-hint">暂无需重点关注学生</p>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- AI 分析 -->
          <div class="content-card ai-panel">
            <div class="ai-panel__header">
              <div class="ai-panel__icon">
                <el-icon :size="22"><MagicStick /></el-icon>
              </div>
              <div>
                <h3>AI 智能分析结论</h3>
                <p class="ai-panel__sub">基于班级多维度学情数据自动生成</p>
              </div>
            </div>
            <p class="ai-panel__summary">{{ classProfile.aiSummary }}</p>
            <div class="ai-panel__suggestions">
              <div class="suggestion-label">教学优化建议</div>
              <ul>
                <li v-for="(item, idx) in classProfile.teachingSuggestions" :key="idx">{{ item }}</li>
              </ul>
            </div>
            <div class="ai-panel__actions">
              <el-button type="primary" plain @click="router.push('/analysis/warning')">
                查看预警详情
              </el-button>
              <el-button plain @click="router.push('/report/center')">导出班级报告</el-button>
            </div>
          </div>
        </template>

        <div v-else-if="!loading" class="empty-state">
          <el-icon :size="48" color="#cbd5e1"><School /></el-icon>
          <p>请选择课程与班级后点击「查询」，查看班级学情画像</p>
        </div>
      </div>
    </template>

    <!-- ═══ 学生个人画像 ═══ -->
    <template v-else>
      <div v-loading="loading">
        <template v-if="studentProfile">
          <el-row :gutter="16">
            <el-col :xs="24" :lg="8">
              <div class="content-card student-card">
                <div class="student-card__header">
                  <el-avatar :size="76" class="student-avatar">{{ studentName.charAt(0) }}</el-avatar>
                  <div>
                    <h3>{{ studentName }}</h3>
                    <p class="student-meta">{{ studentInfo }}</p>
                  </div>
                </div>
                <div class="tag-list">
                  <el-tag v-for="tag in studentTags" :key="tag" type="primary" effect="plain" size="small">
                    {{ tag }}
                  </el-tag>
                </div>
                <div class="student-kp-section">
                  <div class="kp-block kp-block--strong">
                    <span class="kp-label">优势</span>
                    <p>{{ studentProfile.strongPoints }}</p>
                  </div>
                  <div class="kp-block kp-block--weak">
                    <span class="kp-label">薄弱</span>
                    <p>{{ studentProfile.weakPoints }}</p>
                  </div>
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :lg="16">
              <div class="content-card">
                <div class="content-card__title">个人五维学情雷达</div>
                <BaseChart :option="studentRadarOption" height="380px" />
              </div>
            </el-col>
          </el-row>

          <div class="content-card">
            <div class="content-card__title">维度得分详情</div>
            <div class="dimension-grid">
              <div v-for="dim in studentDimensions" :key="dim.name" class="dimension-card">
                <div class="dimension-card__head">
                  <span class="dimension-card__name">{{ dim.name }}</span>
                  <span class="dimension-card__score" :style="{ color: scoreColor(dim.score) }">
                    {{ dim.score }}
                  </span>
                </div>
                <el-progress
                  :percentage="dim.score"
                  :stroke-width="10"
                  :color="scoreColor(dim.score)"
                  :show-text="false"
                />
                <p class="dimension-card__desc">{{ dim.desc }}</p>
              </div>
            </div>
          </div>
        </template>

        <div v-else-if="!loading" class="empty-state">
          <el-icon :size="48" color="#cbd5e1"><User /></el-icon>
          <p>{{ canViewClass ? '请选择学生后点击「查询」，查看个人学情画像' : '暂无学情画像数据' }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.profile-page {
  .view-mode-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid #f1f5f9;
  }

  .mode-label {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
    flex-shrink: 0;
  }
}

// ── 班级头部 Hero ──
.class-hero {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(37, 99, 235, 0.18);

  &__bg {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, #1e40af 0%, #4338ca 50%, #6366f1 100%);
  }

  &__body {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 32px 36px;
    gap: 24px;
    flex-wrap: wrap;
  }

  &__left {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  &__icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    flex-shrink: 0;
  }

  &__title {
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 6px;
  }

  &__meta {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.75);
    margin-bottom: 12px;
  }

  .hero-tag {
    background: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.3);
    color: #fff;
  }
}

.score-ring {
  position: relative;
  width: 120px;
  height: 120px;

  &__svg {
    width: 100%;
    height: 100%;
  }

  &__text {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  &__num {
    font-size: 32px;
    font-weight: 800;
    color: #fff;
    line-height: 1;
  }

  &__label {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
  }
}

// ── 维度卡片网格 ──
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.dimension-card {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px 18px;
  border: 1px solid #e2e8f0;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
  }

  &__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  &__name {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
  }

  &__score {
    font-size: 22px;
    font-weight: 700;
  }

  &__desc {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 10px;
    line-height: 1.5;
  }
}

// ── 优劣势 ──
.insight-card {
  &--strong {
    border-left: 4px solid #10b981;
  }

  &--weak {
    border-left: 4px solid #ef4444;
  }
}

.insight-text {
  font-size: 14px;
  color: #475569;
  line-height: 1.7;
}

// ── 学生排名 ──
.student-rank-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.student-rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;

  &:hover {
    background: #eff6ff;
    transform: translateX(4px);
  }

  &--warn {
    flex-wrap: wrap;
    border-left: 3px solid #f59e0b;
  }
}

.rank-badge {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;

  &.rank-1 { background: linear-gradient(135deg, #f59e0b, #d97706); }
  &.rank-2 { background: linear-gradient(135deg, #94a3b8, #64748b); }
  &.rank-3 { background: linear-gradient(135deg, #cd7f32, #a0522d); }
}

.rank-name {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  flex: 1;
}

.rank-score {
  font-size: 14px;
  font-weight: 600;
  color: #2563eb;

  &.warn { color: #ef4444; }
}

.rank-reason {
  width: 100%;
  font-size: 12px;
  color: #94a3b8;
  padding-left: 38px;
}

// ── AI 面板 ──
.ai-panel {
  background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
  border: 1px solid rgba(37, 99, 235, 0.12);

  &__header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: #1e293b;
    }
  }

  &__icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #2563eb, #6366f1);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 2px;
  }

  &__summary {
    font-size: 14px;
    color: #334155;
    line-height: 1.8;
    margin-bottom: 16px;
    padding: 14px 16px;
    background: rgba(255, 255, 255, 0.7);
    border-radius: 10px;
  }

  &__suggestions {
    margin-bottom: 20px;

    .suggestion-label {
      font-size: 13px;
      font-weight: 600;
      color: #475569;
      margin-bottom: 8px;
    }

    ul {
      padding-left: 20px;

      li {
        font-size: 13px;
        color: #64748b;
        line-height: 1.8;
        margin-bottom: 4px;
      }
    }
  }

  &__actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
}

// ── 学生个人卡片 ──
.student-card {
  height: 100%;

  &__header {
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
}

.student-avatar {
  background: linear-gradient(135deg, #2563eb, #6366f1);
  color: #fff;
  font-size: 28px;
  font-weight: 600;
}

.student-meta {
  font-size: 13px;
  color: #64748b;
}

.student-kp-section {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kp-block {
  padding: 12px 14px;
  border-radius: 10px;

  &--strong {
    background: #f0fdf4;
    border-left: 3px solid #10b981;
  }

  &--weak {
    background: #fef2f2;
    border-left: 3px solid #ef4444;
  }

  .kp-label {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    display: block;
    margin-bottom: 4px;
  }

  p {
    font-size: 13px;
    color: #475569;
    line-height: 1.6;
  }
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;

  p {
    margin-top: 16px;
    font-size: 14px;
  }
}

.empty-hint {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  padding: 12px 0;
}
</style>
