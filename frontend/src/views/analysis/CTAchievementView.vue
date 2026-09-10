<!--
  课程目标达成度分析页面
  参照《计算机网络技术》教学大纲 CT1-CT8，展示班级/学生课程目标达成度画像
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import AnalysisFilterBar from '@/components/common/AnalysisFilterBar.vue'
import { useAnalysisScope } from '@/composables/useAnalysisScope'
import {
  fetchCTDefinitions,
  fetchStudentCT,
  fetchClassCT,
} from '@/api/analysis'
import type {
  CTStudentAchievement,
  CTClassAchievement,
  CTScoreItem,
} from '@/api/analysis'

const scope = useAnalysisScope('class')
const {
  allowedTargetTypes, targetType, semesterId, classId, courseId, targetId,
  studentList, studentLoading,
  semesterOptions, classOptions, courseOptions,
  showClassFilter, showCourseFilter, showTargetTypeFilter, showStudentPicker,
  queryParams,
} = scope

// CT 定义
const ctDefinitions = ref<Record<string, { category: string; desc: string }>>({})
const categories = ref<{ key: string; cts: string[] }[]>([])
void fetchCTDefinitions().then((d) => {
  ctDefinitions.value = d.ct_definitions ?? {}
  categories.value = d.categories ?? []
})

const CT_CODES = ['CT1', 'CT2', 'CT3', 'CT4', 'CT5', 'CT6', 'CT7', 'CT8']

// 数据
const classData = ref<CTClassAchievement | null>(null)
const studentData = ref<CTStudentAchievement | null>(null)
const loading = ref(false)

const isClassView = computed(() => targetType.value === 'class')

async function loadData() {
  if (!queryParams.value.courseId) return
  loading.value = true
  try {
    if (isClassView.value) {
      classData.value = await fetchClassCT(
        queryParams.value.courseId,
        queryParams.value.classId,
      )
    } else {
      if (targetId.value) {
        studentData.value = await fetchStudentCT(
          targetId.value,
          queryParams.value.courseId,
        )
      }
    }
  } finally {
    loading.value = false
  }
}

watch(
  () => [targetType.value, queryParams.value.courseId, queryParams.value.classId, targetId.value],
  () => loadData(),
)

// ============ 雷达图 ============
const radarOption = computed<EChartsOption>(() => {
  const values = isClassView.value
    ? CT_CODES.map((ct) => classData.value?.ct_avg?.[ct] ?? 0)
    : CT_CODES.map((ct) => studentData.value?.radar?.[ct] ?? 0)
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: CT_CODES.map((ct) => ({
        name: ct,
        max: 100,
      })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#64748b', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: { areaStyle: { color: ['#f8fafc', '#ffffff'] } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: isClassView.value ? '班级达成度均值' : '个人达成度',
            areaStyle: { color: 'rgba(37, 99, 235, 0.15)' },
            lineStyle: { color: '#2563eb', width: 2 },
            itemStyle: { color: '#2563eb' },
          },
        ],
      },
    ],
  }
})

// ============ 班级达成率柱状图 ============
const passRateOption = computed<EChartsOption>(() => {
  const rates = CT_CODES.map((ct) =>
    Math.round((classData.value?.ct_pass_rate?.[ct] ?? 0) * 100),
  )
  return {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: CT_CODES, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' } },
    series: [
      {
        type: 'bar',
        data: rates.map((r) => ({
          value: r,
          itemStyle: { color: r >= 80 ? '#22c55e' : r >= 60 ? '#f59e0b' : '#ef4444' },
        })),
        barWidth: '50%',
        label: { show: true, position: 'top', formatter: '{c}%', color: '#64748b' },
      },
    ],
  }
})

// ============ 等级颜色 ============
function levelColor(level: string | null): string {
  if (!level) return '#94a3b8'
  if (level === '优秀') return '#22c55e'
  if (level === '良好') return '#3b82f6'
  if (level === '合格') return '#f59e0b'
  if (level === '不足') return '#f97316'
  return '#ef4444' // 严重不足
}

function confidenceText(c: string | null): string {
  if (c === 'high') return '精确归因'
  if (c === 'medium') return '间接归因'
  if (c === 'low') return '推断'
  return '-'
}

// 表格行
const tableRows = computed(() => {
  if (!classData.value) return []
  return classData.value.students.map((s) => ({
    name: s.name,
    ...Object.fromEntries(CT_CODES.map((ct) => [ct, s.ct_scores[ct]])),
    overall: s.overall,
    level: s.overall_level,
    weak: s.weak_cts,
  }))
})
</script>

<template>
  <div class="page-container">
    <!-- 筛选栏 -->
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
        @query="loadData"
      />
    </div>

    <!-- 课程目标说明 -->
    <div class="content-card ct-legend">
      <div v-for="cat in categories" :key="cat.key" class="ct-group">
        <span class="ct-cat-label">{{ cat.key }}</span>
        <el-tag
          v-for="ct in cat.cts"
          :key="ct"
          type="info"
          effect="plain"
          size="small"
          class="ct-tag"
        >
          <strong>{{ ct }}</strong> {{ ctDefinitions[ct]?.desc }}
        </el-tag>
      </div>
    </div>

    <!-- ============ 班级视角 ============ -->
    <template v-if="isClassView">
      <div v-loading="loading" class="charts-row">
        <div class="content-card chart-card">
          <div class="card-title">班级 8 维达成度雷达</div>
          <BaseChart :option="radarOption" height="340px" />
        </div>
        <div class="content-card chart-card">
          <div class="card-title">各课程目标达成率</div>
          <BaseChart :option="passRateOption" height="340px" />
        </div>
      </div>

      <!-- 班级短板提示 -->
      <div v-if="classData?.weak_cts_class?.length" class="content-card weak-notice">
        <span class="weak-icon">⚠</span>
        <span class="weak-text">
          班级突出短板：{{ classData.weak_cts_class.join('、') }}（达成度均值 &lt; 60 或达成率 &lt; 60%），建议针对性强化。
        </span>
      </div>

      <!-- 学生达成度列表 -->
      <div class="content-card">
        <div class="card-title">学生课程目标达成度明细</div>
        <el-table :data="tableRows" stripe size="small" style="width: 100%">
          <el-table-column prop="name" label="姓名" width="90" fixed />
          <el-table-column
            v-for="ct in CT_CODES"
            :key="ct"
            :label="ct"
            width="70"
            align="center"
          >
            <template #default="{ row }">
              <span :style="{ color: row[ct] < 60 ? '#ef4444' : row[ct] >= 85 ? '#22c55e' : '#1e293b' }">
                {{ row[ct] != null ? row[ct] : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="overall" label="总体" width="70" align="center">
            <template #default="{ row }">
              <strong>{{ row.overall }}</strong>
            </template>
          </el-table-column>
          <el-table-column prop="level" label="等级" width="80" align="center">
            <template #default="{ row }">
              <el-tag :color="levelColor(row.level)" effect="dark" size="small" round>
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- ============ 学生视角 ============ -->
    <template v-else>
      <div v-loading="loading" class="charts-row">
        <div class="content-card chart-card">
          <div class="card-title">
            {{ studentData?.name ?? '学生' }} 课程目标达成度雷达
          </div>
          <BaseChart :option="radarOption" height="360px" />
        </div>
      </div>

      <!-- CT 维度卡片 -->
      <div class="ct-cards-grid">
        <div
          v-for="ct in CT_CODES"
          :key="ct"
          class="content-card ct-card"
          :class="{ 'ct-weak': (studentData?.ct_scores[ct]?.score ?? 999) < 60 }"
        >
          <div class="ct-card-header">
            <span class="ct-code">{{ ct }}</span>
            <el-tag
              :color="levelColor(studentData?.ct_scores[ct]?.level ?? null)"
              effect="dark"
              size="small"
              round
            >
              {{ studentData?.ct_scores[ct]?.level ?? '无数据' }}
            </el-tag>
          </div>
          <div class="ct-card-score">
            {{ studentData?.ct_scores[ct]?.score != null
              ? studentData.ct_scores[ct].score : '—' }}
            <span class="ct-card-conf">（{{ confidenceText(studentData?.ct_scores[ct]?.confidence ?? null) }}）</span>
          </div>
          <div class="ct-card-desc">{{ ctDefinitions[ct]?.desc }}</div>
          <div class="ct-card-cat">{{ ctDefinitions[ct]?.category }}类</div>
        </div>
      </div>

      <!-- 优势/薄弱总结 -->
      <div class="content-card summary-card">
        <div class="summary-block">
          <span class="summary-label">总体达成度</span>
          <span class="summary-value">
            {{ studentData?.overall?.score ?? '—' }}
            <el-tag
              :color="levelColor(studentData?.overall?.level ?? null)"
              effect="dark"
              size="small"
              round
            >
              {{ studentData?.overall?.level ?? '—' }}
            </el-tag>
          </span>
        </div>
        <div class="summary-block">
          <span class="summary-label">优势目标</span>
          <div>
            <el-tag
              v-for="ct in (studentData?.strong_cts ?? [])"
              :key="ct"
              type="success"
              size="small"
              class="ct-tag"
            >{{ ct }}</el-tag>
            <span v-if="!studentData?.strong_cts?.length" class="empty-hint">暂无</span>
          </div>
        </div>
        <div class="summary-block">
          <span class="summary-label">薄弱目标</span>
          <div>
            <el-tag
              v-for="ct in (studentData?.weak_cts ?? [])"
              :key="ct"
              type="danger"
              size="small"
              class="ct-tag"
            >{{ ct }}</el-tag>
            <span v-if="!studentData?.weak_cts?.length" class="empty-hint">暂无</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page-container {
  padding: 16px;
  background: #f1f5f9;
  min-height: 100%;
}
.content-card {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.chart-card {
  flex: 1;
}
.ct-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ct-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.ct-cat-label {
  min-width: 40px;
  font-weight: 600;
  color: #475569;
  padding-top: 2px;
}
.ct-tag {
  margin-right: 4px;
}
.weak-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fef2f2;
  border-left: 3px solid #ef4444;
}
.weak-icon {
  font-size: 18px;
}
.weak-text {
  color: #991b1b;
  font-size: 14px;
}
.ct-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.ct-card {
  padding: 14px;
  margin-bottom: 0;
}
.ct-card.ct-weak {
  border: 1px solid #fecaca;
  background: #fef9f9;
}
.ct-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.ct-code {
  font-size: 16px;
  font-weight: 700;
  color: #2563eb;
}
.ct-card-score {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 6px;
}
.ct-card-conf {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
}
.ct-card-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 4px;
}
.ct-card-cat {
  font-size: 11px;
  color: #94a3b8;
}
.summary-card {
  display: flex;
  gap: 32px;
  align-items: center;
}
.summary-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.summary-label {
  font-size: 12px;
  color: #64748b;
}
.summary-value {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}
.empty-hint {
  font-size: 13px;
  color: #94a3b8;
}
</style>
