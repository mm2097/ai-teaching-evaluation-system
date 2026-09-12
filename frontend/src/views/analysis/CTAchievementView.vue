<!--
  课程目标达成度分析页面（重写版）
  参照《计算机网络技术》教学大纲 CT1-CT8，展示班级/学生课程目标达成度画像
  - 班级视角：CT 概览卡 + 均值/达成率双轴柱 + 短板归因面板 + 学生明细表
  - 学生视角：个人 vs 班级对比雷达 + CT 维度卡片（含归因证据链）+ 优势/薄弱总结
-->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ArrowRight, WarningFilled } from '@element-plus/icons-vue'
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
// 学生视角下也拉班级数据，用于对比雷达的"班级均值"线
const classAvgForCompare = ref<Record<string, number>>({})
const loading = ref(false)
// CT 说明默认折叠，避免首屏被文字标签占据
const legendCollapsed = ref(true)
// 学生明细弹窗
const detailVisible = ref(false)

const isClassView = computed(() => targetType.value === 'class')

// CT 达成度仅计网有教学大纲，课程下拉只保留计算机网络，避免切到无大纲课程
const ctCourseOptions = computed(() =>
  courseOptions.value.filter((c) => /计算机网络/.test(c.label)),
)
// 当前课程名（用于判断是否计网）
const currentCourseName = computed(() =>
  courseOptions.value.find((c) => c.value === courseId.value)?.label ?? '',
)
const isSupportedCourse = computed(() => /计算机网络/.test(currentCourseName.value))

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
      // 并行拉班级均值做对比
      const cd = await fetchClassCT(queryParams.value.courseId, queryParams.value.classId)
      classAvgForCompare.value = cd?.ct_avg ?? {}
    }
  } finally {
    loading.value = false
  }
}

watch(
  () => [targetType.value, queryParams.value.courseId, queryParams.value.classId, targetId.value],
  () => loadData(),
)

// 课程选项加载后，若当前 courseId 不在计网选项内则自动选中计网
watch(ctCourseOptions, (opts) => {
  if (opts.length && !opts.some((o) => o.value === courseId.value)) {
    courseId.value = opts[0].value
  }
})

// ============ 等级颜色 ============
function levelColor(level: string | null | undefined): string {
  if (!level) return '#94a3b8'
  if (level === '优秀') return '#22c55e'
  if (level === '良好') return '#3b82f6'
  if (level === '合格') return '#f59e0b'
  if (level === '不足') return '#f97316'
  return '#ef4444' // 严重不足
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return '#94a3b8'
  if (score >= 85) return '#22c55e'
  if (score >= 60) return '#1e293b'
  return '#ef4444'
}

function confidenceText(c: string | null | undefined): string {
  if (c === 'high') return '精确归因'
  if (c === 'medium') return '间接归因'
  if (c === 'low') return '推断'
  return '-'
}

// ============ 班级视角：CT 概览卡数据 ============
const ctOverview = computed(() => {
  if (!classData.value) return []
  const d = classData.value
  return CT_CODES.map((ct) => ({
    ct,
    avg: d.ct_avg[ct] ?? 0,
    passRate: Math.round((d.ct_pass_rate[ct] ?? 0) * 1000) / 10,
    std: d.ct_std[ct] ?? 0,
    category: ctDefinitions.value[ct]?.category ?? '',
    desc: ctDefinitions.value[ct]?.desc ?? '',
    isWeak: (d.weak_cts_class ?? []).includes(ct),
  }))
})

// ============ 班级视角：8 维达成度雷达 ============
const classRadarOption = computed<EChartsOption>(() => {
  const values = CT_CODES.map((ct) => classData.value?.ct_avg?.[ct] ?? 0)
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: CT_CODES.map((ct) => ({ name: ct, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#64748b', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: { areaStyle: { color: ['#f8fafc', '#ffffff'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '班级达成度均值',
        areaStyle: { color: 'rgba(37, 99, 235, 0.15)' },
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
      }],
    }],
  }
})

// ============ 班级视角：达成等级分布堆叠柱 ============
const dualBarOption = computed<EChartsOption>(() => {
  const d = classData.value
  const toPct = (v: number) => Math.round(v * 1000) / 10
  const levels = [
    { name: '优秀(≥85)', key: 'excellent', color: '#22c55e' },
    { name: '良好(70-84)', key: 'good', color: '#3b82f6' },
    { name: '合格(60-69)', key: 'pass', color: '#f59e0b' },
    { name: '未达成(<60)', key: 'fail', color: '#ef4444' },
  ] as const
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const ct = params[0]?.name ?? ''
        const avg = d?.ct_avg?.[ct] ?? 0
        const lines = params.map((p: any) => `${p.marker} ${p.seriesName}: ${p.value}%`).join('<br/>')
        return `<b>${ct}</b>（均值 ${avg}）<br/>${lines}`
      },
    },
    legend: { data: levels.map((l) => l.name), top: 0, textStyle: { color: '#64748b', fontSize: 11 } },
    grid: { left: 44, right: 20, top: 36, bottom: 28 },
    xAxis: { type: 'category', data: CT_CODES, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: levels.map((lv) => ({
      name: lv.name,
      type: 'bar',
      stack: 'total',
      barWidth: '52%',
      data: CT_CODES.map((ct) => toPct(d?.ct_level_dist?.[ct]?.[lv.key] ?? 0)),
      itemStyle: { color: lv.color },
      emphasis: { focus: 'series' },
    })),
  }
})

// ============ 班级视角：短板归因面板 ============
const weakDetails = computed(() => {
  const d = classData.value
  if (!d?.weak_cts_class?.length) return []
  return d.weak_cts_class.map((ct) => ({
    ct,
    desc: ctDefinitions.value[ct]?.desc ?? '',
    avg: d.ct_avg[ct] ?? 0,
    passRate: Math.round((d.ct_pass_rate[ct] ?? 0) * 1000) / 10,
    evidence: (d.ct_evidence_summary?.[ct] ?? []).slice(0, 3),
  }))
})

// ============ 班级视角：学生明细表 ============
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

// ============ 学生视角：个人 vs 班级对比雷达 ============
const radarOption = computed<EChartsOption>(() => {
  const personal = CT_CODES.map((ct) => studentData.value?.radar?.[ct] ?? 0)
  const classAvg = CT_CODES.map((ct) => classAvgForCompare.value[ct] ?? 0)
  return {
    tooltip: { trigger: 'item' },
    legend: { data: ['个人', '班级均值'], top: 0, textStyle: { color: '#64748b' } },
    radar: {
      indicator: CT_CODES.map((ct) => ({ name: ct, max: 100 })),
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
            value: classAvg,
            name: '班级均值',
            areaStyle: { color: 'rgba(148, 163, 184, 0.12)' },
            lineStyle: { color: '#94a3b8', width: 1.5, type: 'dashed' },
            itemStyle: { color: '#94a3b8' },
          },
          {
            value: personal,
            name: '个人',
            areaStyle: { color: 'rgba(37, 99, 235, 0.18)' },
            lineStyle: { color: '#2563eb', width: 2 },
            itemStyle: { color: '#2563eb' },
          },
        ],
      },
    ],
  }
})

// ============ 学生视角：CT 卡片（按类别分组） ============
const studentCtByCategory = computed(() => {
  if (!studentData.value) return []
  return categories.value.map((cat) => ({
    key: cat.key,
    cts: cat.cts.map((ct) => ({
      ct,
      item: studentData.value!.ct_scores[ct],
      desc: ctDefinitions.value[ct]?.desc ?? '',
    })),
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
        :course-options="ctCourseOptions"
        :show-query-button="true"
        @query="loadData"
      />
    </div>

    <!-- 非计网课程：CT 达成度仅计算机网络有教学大纲支持 -->
    <div v-if="!isSupportedCourse" class="content-card unsupported-card">
      <el-icon class="unsupported-icon"><WarningFilled /></el-icon>
      <div class="unsupported-text">
        <div class="unsupported-title">当前课程暂不支持课程目标达成度分析</div>
        <div class="unsupported-desc">
          课程目标达成度需依据教学大纲的 CT1-CT8 映射，目前仅「计算机网络」课程配置了大纲。
          请在课程下拉中切换到「计算机网络」查看。
        </div>
      </div>
    </div>

    <div v-if="isSupportedCourse">
    <!-- 课程目标说明（可折叠，默认收起） -->
    <div class="content-card ct-legend">
      <div class="ct-legend-head" @click="legendCollapsed = !legendCollapsed">
        <span class="card-title" style="margin-bottom: 0">课程目标说明（CT1-CT8）</span>
        <el-icon class="ct-legend-arrow" :class="{ 'is-open': !legendCollapsed }"><ArrowRight /></el-icon>
      </div>
      <div v-show="!legendCollapsed" class="ct-legend-body">
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
    </div>

    <!-- ============ 班级视角 ============ -->
    <template v-if="isClassView">
      <div v-loading="loading">
        <!-- 首屏：雷达 + 双轴柱 并排，一眼看整体达成形态 -->
        <div class="charts-row">
          <div class="content-card chart-card">
            <div class="card-title">班级 8 维达成度雷达</div>
            <BaseChart :option="classRadarOption" height="280px" />
          </div>
          <div class="content-card chart-card">
            <div class="card-title">达成等级分布</div>
            <BaseChart :option="dualBarOption" height="280px" />
          </div>
        </div>

        <!-- 班级短板归因（紧跟图表，优先露出短板） -->
        <div v-if="weakDetails.length" class="content-card weak-panel">
          <div class="card-title">⚠ 班级突出短板归因</div>
          <div v-for="w in weakDetails" :key="w.ct" class="weak-item">
            <div class="weak-item-head">
              <span class="weak-item-ct">{{ w.ct }}</span>
              <span class="weak-item-desc">{{ w.desc }}</span>
              <span class="weak-item-stat">均值 {{ w.avg }} · 未达成 {{ Math.round((classData?.ct_level_dist?.[w.ct]?.fail ?? 0) * 1000) / 10 }}%</span>
            </div>
            <div class="weak-evidence-list">
              <span
                v-for="(ev, i) in w.evidence"
                :key="i"
                class="weak-evidence-tag"
              >
                {{ ev.source }}：均分 {{ ev.avg_score }}（权重 {{ ev.avg_weight }}）
              </span>
              <span v-if="!w.evidence.length" class="empty-hint">暂无归因证据</span>
            </div>
          </div>
        </div>

        <!-- CT 概览卡：每类一行，该类 CT 卡水平等分占满 -->
        <div v-for="cat in categories" :key="cat.key" class="cat-section">
          <div class="cat-title">{{ cat.key }}类（{{ cat.cts.length }}）</div>
          <div
            class="ct-overview-grid"
            :style="{ gridTemplateColumns: `repeat(${cat.cts.length}, 1fr)` }"
          >
            <div
              v-for="ct in cat.cts"
              :key="ct"
              class="ct-overview-card"
              :class="{ 'is-weak': (classData?.weak_cts_class ?? []).includes(ct) }"
            >
              <div class="ct-ov-header">
                <span class="ct-ov-code">{{ ct }}</span>
                <el-tag
                  v-if="(classData?.weak_cts_class ?? []).includes(ct)"
                  type="danger"
                  size="small"
                  effect="plain"
                >短板</el-tag>
              </div>
              <div class="ct-ov-score">
                {{ classData?.ct_avg?.[ct] ?? '-' }}
                <span class="ct-ov-unit">/100</span>
              </div>
              <div class="ct-ov-bar">
                <div
                  class="ct-ov-bar-fill"
                  :style="{
                    width: (classData?.ct_avg?.[ct] ?? 0) + '%',
                    background: (classData?.ct_avg?.[ct] ?? 0) >= 85 ? '#22c55e' : (classData?.ct_avg?.[ct] ?? 0) >= 60 ? '#3b82f6' : '#ef4444',
                  }"
                />
              </div>
              <div class="ct-ov-meta">
                优秀 <strong>{{ Math.round((classData?.ct_level_dist?.[ct]?.excellent ?? 0) * 1000) / 10 }}%</strong>
                · 未达成 <strong :style="{ color: ((classData?.ct_level_dist?.[ct]?.fail ?? 0) > 0.05) ? '#ef4444' : '#1e293b' }">{{ Math.round((classData?.ct_level_dist?.[ct]?.fail ?? 0) * 1000) / 10 }}%</strong>
                · σ {{ classData?.ct_std?.[ct] ?? 0 }}
              </div>
            </div>
          </div>
        </div>

        <!-- 学生达成度明细：入口按钮，弹窗展示 -->
        <div class="content-card detail-entry">
          <div class="detail-entry-info">
            <span class="card-title" style="margin-bottom: 0">学生课程目标达成度明细</span>
            <span class="detail-entry-hint">共 {{ tableRows.length }} 名学生 · 按 CT 维度查看每人达成度与等级</span>
          </div>
          <el-button type="primary" plain @click="detailVisible = true">
            查看明细
          </el-button>
        </div>
      </div>
    </template>

    <!-- ============ 学生视角 ============ -->
    <template v-else>
      <div v-loading="loading">
        <!-- 对比雷达 -->
        <div class="content-card">
          <div class="card-title">
            {{ studentData?.name ?? '学生' }} · 个人与班级达成度对比
          </div>
          <BaseChart :option="radarOption" height="360px" />
        </div>

        <!-- CT 维度卡片（按类别分组，含归因证据链） -->
        <div v-for="cat in studentCtByCategory" :key="cat.key" class="cat-section">
          <div class="cat-title">{{ cat.key }}类课程目标</div>
          <div class="ct-cards-grid" :class="`cols-${cat.cts.length}`">
            <div
              v-for="entry in cat.cts"
              :key="entry.ct"
              class="content-card ct-card"
              :class="{ 'ct-weak': (entry.item?.score ?? 999) < 60 }"
            >
              <div class="ct-card-header">
                <span class="ct-code">{{ entry.ct }}</span>
                <el-tag
                  :color="levelColor(entry.item?.level ?? null)"
                  effect="dark"
                  size="small"
                  round
                >
                  {{ entry.item?.level ?? '无数据' }}
                </el-tag>
              </div>
              <div class="ct-card-score">
                {{ entry.item?.score != null ? entry.item.score : '—' }}
                <span class="ct-card-conf">（{{ confidenceText(entry.item?.confidence ?? null) }}）</span>
              </div>
              <div class="ct-card-desc">{{ entry.desc }}</div>
              <!-- 归因证据链 -->
              <div v-if="entry.item?.evidence?.length" class="ct-evidence">
                <div class="ct-evidence-title">归因证据</div>
                <div
                  v-for="(ev, i) in entry.item.evidence.slice(0, 3)"
                  :key="i"
                  class="ct-evidence-row"
                >
                  <span class="ev-source">{{ ev.source }}</span>
                  <span class="ev-meta">得分率 {{ ev.score }} · 权重 {{ ev.weight }}</span>
                </div>
              </div>
              <div v-else class="ct-evidence-empty">无归因证据</div>
            </div>
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
      </div>
    </template>

    <!-- 学生明细弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="学生课程目标达成度明细"
      width="min(900px, 94vw)"
      top="6vh"
      append-to-body
      destroy-on-close
      class="ct-detail-dialog"
    >
      <el-table :data="tableRows" stripe size="small" class="detail-table" style="width: 100%" max-height="68vh">
        <el-table-column prop="name" label="姓名" width="90" fixed />
        <el-table-column
          v-for="ct in CT_CODES"
          :key="ct"
          :label="ct"
          min-width="64"
          align="center"
          sortable
        >
          <template #default="{ row }">
            <span :style="{ color: scoreColor(row[ct]), fontWeight: row[ct] < 60 ? 600 : 400 }">
              {{ row[ct] != null ? row[ct] : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="overall" label="总体" min-width="70" align="center" sortable>
          <template #default="{ row }">
            <strong>{{ row.overall }}</strong>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="等级" min-width="80" align="center">
          <template #default="{ row }">
            <el-tag :color="levelColor(row.level)" effect="dark" size="small" round>
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
    </div>
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
/* 图表卡：标题与图表留足间距，避免标题被 canvas 顶部遮盖 */
.chart-card .card-title {
  margin-bottom: 18px;
}
.chart-card :deep(.base-chart) {
  margin-top: 4px;
}
.ct-legend {
  padding: 10px 20px;
}
.ct-legend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}
.ct-legend-arrow {
  transition: transform 0.2s;
  color: #94a3b8;
}
.ct-legend-arrow.is-open {
  transform: rotate(90deg);
}
.ct-legend-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
/* 首屏图表两列并排 */
.charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.chart-card {
  flex: 1;
  min-width: 0;
}
@media (max-width: 720px) {
  .charts-row {
    flex-direction: column;
  }
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

/* 分类区块 */
.cat-section {
  margin-bottom: 16px;
}
.cat-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #2563eb;
}

/* CT 概览卡：每类一行，等分该类 CT 数 */
.ct-overview-grid {
  display: grid;
  gap: 12px;
}
/* 窄屏单卡过窄时退回两列换行，避免文字挤压 */
@media (max-width: 720px) {
  .ct-overview-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}
.ct-overview-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
}
.ct-overview-card.is-weak {
  border-color: #fecaca;
  background: #fef9f9;
}
.ct-ov-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.ct-ov-code {
  font-size: 16px;
  font-weight: 700;
  color: #2563eb;
}
.ct-ov-score {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.1;
}
.ct-ov-unit {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
}
.ct-ov-bar {
  height: 6px;
  background: #f1f5f9;
  border-radius: 3px;
  margin: 8px 0;
  overflow: hidden;
}
.ct-ov-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}
.ct-ov-meta {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}
.ct-ov-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

/* 短板归因面板 */
.weak-panel {
  background: #fef2f2;
  border-left: 3px solid #ef4444;
}
.weak-item {
  padding: 10px 0;
  border-bottom: 1px dashed #fecaca;
}
.weak-item:last-child {
  border-bottom: none;
}
.weak-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.weak-item-ct {
  font-weight: 700;
  color: #dc2626;
}
.weak-item-desc {
  font-size: 13px;
  color: #475569;
  flex: 1;
}
.weak-item-stat {
  font-size: 12px;
  color: #991b1b;
}
.weak-evidence-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.weak-evidence-tag {
  font-size: 12px;
  color: #475569;
  background: #fff;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 3px 8px;
}

/* 学生视角 CT 卡片 */
.ct-cards-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}
.ct-cards-grid.cols-3 {
  grid-template-columns: repeat(3, 1fr);
}
.ct-cards-grid.cols-2 {
  grid-template-columns: repeat(2, 1fr);
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
  margin-bottom: 8px;
}
.ct-evidence {
  border-top: 1px dashed #e2e8f0;
  padding-top: 8px;
}
.ct-evidence-title {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.ct-evidence-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-bottom: 3px;
}
.ev-source {
  color: #1e293b;
  font-weight: 500;
}
.ev-meta {
  color: #64748b;
  font-size: 11px;
}
.ct-evidence-empty {
  font-size: 11px;
  color: #cbd5e1;
  border-top: 1px dashed #e2e8f0;
  padding-top: 8px;
}

/* 总结卡 */
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

/* 非支持课程提示 */
.unsupported-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 32px 24px;
}
.unsupported-icon {
  font-size: 40px;
  color: #f59e0b;
  flex-shrink: 0;
}
.unsupported-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}
.unsupported-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}

/* 明细入口卡 */
.detail-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.detail-entry-info {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.detail-entry-hint {
  font-size: 12px;
  color: #94a3b8;
}

/* 明细弹窗：表格撑满弹窗宽度，列自适应分配 */
</style>
