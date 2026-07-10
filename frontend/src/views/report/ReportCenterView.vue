<!--
  报告生成与导出中心
  统计指标由后端计算，分析结论与建议由 LLM 生成
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, View } from '@element-plus/icons-vue'
import { generateReport as generateReportApi, type ReportResponse } from '@/api/ai'
import { fetchSemesters, fetchCourses, fetchClasses, fetchStudents } from '@/api/dict'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'

const userStore = useUserStore()

const semesterOptions = ref<{ label: string; value: string }[]>([])
const courses = ref<any[]>([])
const classes = ref<any[]>([])
const students = ref<any[]>([])

onMounted(async () => {
  try {
    const [semRes, courseRes, classRes] = await Promise.all([
      fetchSemesters(),
      fetchCourses({ deptId: 1 }),
      fetchClasses({ deptId: 1 }),
    ])
    semesterOptions.value = semRes.map((s: any) => ({ label: s.semesterName, value: s.semesterCode }))
    courses.value = courseRes
    classes.value = classRes
  } catch { /* empty */ }
})

const reportTypes = [
  { id: 1, name: '班级学情分析报告', desc: '包含班级整体学情、成绩分布、预警名单', roles: ['admin', 'teacher'] },
  { id: 2, name: '学生个人学情报告', desc: '包含学生雷达图、知识点掌握、学习建议' },
  { id: 3, name: '课程知识点分析报告', desc: '包含知识点热力图、薄弱项分析、改进建议' },
  { id: 4, name: '学生学习质量报告', desc: '包含学习质量评价得分、维度分析' },
]

const visibleReportTypes = computed(() =>
  reportTypes.filter((t) => !t.roles || t.roles.includes(userStore.userRole!))
)

const genParams = ref({
  reportType: 1,
  semester: '2025-2026-1',
  courseId: 1,
  classId: 1,
  studentId: undefined as number | undefined,
  format: 'pdf',
})

const generating = ref(false)
const previewVisible = ref(false)
const reportData = ref<ReportResponse | null>(null)
const dashboardStats = ref<Record<string, any>>({})

const csCourses = computed(() => courses.value)
const csClasses = computed(() => classes.value)

const reportSourceLabel = computed(() => {
  if (!reportData.value) return ''
  return reportData.value.source === 'llm' ? 'AI 增强' : '模板生成'
})
const reportSourceTag = computed(() => {
  if (!reportData.value) return ''
  return reportData.value.source === 'llm' ? 'warning' : 'info' as const
})

const previewTitle = computed(() => {
  return reportData.value?.report_type_name
    || reportTypes.find((t) => t.id === genParams.value.reportType)?.name
    || '学情分析报告'
})

const historyReports = ref([
  { id: 1, name: '计科2401班 - 数据结构 班级学情报告', type: '班级学情', time: '2026-03-15 10:30', format: 'PDF' },
  { id: 2, name: '陈同学 - 数据结构 学生个报告', type: '个人学情', time: '2026-03-14 16:00', format: 'PDF' },
  { id: 3, name: '数据结构 知识点分析报告', type: '知识点', time: '2026-03-12 09:00', format: 'PDF' },
])

// 确保默认选中的报告类型对当前角色可见
watch(
  visibleReportTypes,
  (types) => {
    if (types.length > 0 && !types.find((t) => t.id === genParams.value.reportType)) {
      genParams.value.reportType = types[0]!.id
    }
  },
  { immediate: true },
)

// 切换报告类型或班级时加载学生列表
watch(
  [() => genParams.value.reportType, () => genParams.value.classId],
  async ([type, classId]) => {
    if (type === 2 && classId) {
      try {
        students.value = await fetchStudents({ classId: classId as number })
      } catch { students.value = [] }
    }
  },
)

async function loadDashboardStats() {
  try {
    const { data } = await request.get('/v1/dashboard/stats', {
      params: { course_id: genParams.value.courseId },
    })
    dashboardStats.value = data
  } catch { dashboardStats.value = {} }
}

async function generateReport(): Promise<void> {
  generating.value = true
  try {
    await loadDashboardStats()

    // 学生个人报告需要验证 studentId
    if (genParams.value.reportType === 2 && !genParams.value.studentId) {
      ElMessage.warning('请先选择学生')
      generating.value = false
      return
    }

    reportData.value = await generateReportApi({
      courseId: genParams.value.courseId,
      reportType: genParams.value.reportType as 1 | 2 | 3 | 4,
      classId: genParams.value.classId ?? undefined,
      studentId: genParams.value.reportType === 2 ? genParams.value.studentId : undefined,
    })

    const typeName = reportTypes.find((t) => t.id === genParams.value.reportType)?.name || '报告'
    const courseName = courses.value.find((c: any) => c.id === genParams.value.courseId)?.courseName || ''
    const className = classes.value.find((c: any) => c.id === genParams.value.classId)?.className || ''
    historyReports.value.unshift({
      id: Date.now(),
      name: `${className}${courseName ? ' - ' + courseName : ''} ${typeName.slice(0, 4)}报告`,
      type: typeName.slice(0, 4),
      time: new Date().toLocaleString('zh-CN'),
      format: genParams.value.format === 'pdf' ? 'PDF' : 'Excel',
    })
    ElMessage.success('报告生成成功！')
  } catch {
    ElMessage.error('报告生成失败，请确认已选择课程和班级')
  } finally {
    generating.value = false
  }
}

function previewReport(): void {
  if (!reportData.value) {
    ElMessage.info('请先生成报告')
    return
  }
  previewVisible.value = true
}

function exportReport(): void {
  if (!reportData.value) {
    ElMessage.info('请先生成报告')
    return
  }
  ElMessage.success(`报告已导出为 ${genParams.value.format.toUpperCase()} 格式`)
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="10">
        <div class="content-card">
          <div class="content-card__title">报告生成</div>

          <div class="report-type-grid">
            <div
              v-for="item in visibleReportTypes"
              :key="item.id"
              class="report-type-card"
              :class="{ active: genParams.reportType === item.id }"
              @click="genParams.reportType = item.id"
            >
              <el-icon :size="24"><Document /></el-icon>
              <h4>{{ item.name }}</h4>
              <p>{{ item.desc }}</p>
            </div>
          </div>

          <el-divider />

          <el-form label-width="80px">
            <el-form-item label="学期">
              <el-select v-model="genParams.semester" style="width: 100%">
                <el-option v-for="s in semesterOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="课程">
              <el-select v-model="genParams.courseId" style="width: 100%">
                <el-option v-for="c in csCourses" :key="c.id" :label="c.courseName" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="班级">
              <el-select v-model="genParams.classId" style="width: 100%">
                <el-option v-for="c in csClasses" :key="c.id" :label="c.className" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="genParams.reportType === 2" label="学生">
              <el-select
                v-model="genParams.studentId"
                style="width: 100%"
                placeholder="请先选择班级"
                :disabled="!genParams.classId"
              >
                <el-option
                  v-for="s in students"
                  :key="s.id"
                  :label="`${s.studentName}（${s.studentNo}）`"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="导出格式">
              <el-radio-group v-model="genParams.format">
                <el-radio value="pdf">PDF</el-radio>
                <el-radio value="excel">Excel</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <div style="display: flex; gap: 12px">
            <el-button type="primary" :loading="generating" :icon="Document" @click="generateReport">
              生成报告
            </el-button>
            <el-button :icon="View" @click="previewReport">在线预览</el-button>
            <el-button :icon="Download" @click="exportReport">导出</el-button>
          </div>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="content-card">
          <div class="content-card__title">历史报告</div>
          <el-table :data="historyReports" stripe border>
            <el-table-column prop="name" label="报告名称" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="format" label="格式" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.format === 'PDF' ? 'danger' : 'success'">{{ row.format }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="time" label="生成时间" width="170" />
            <el-table-column label="操作" width="140" align="center">
              <template #default>
                <el-button type="primary" link size="small">预览</el-button>
                <el-button type="success" link size="small">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="previewVisible" title="报告预览" width="720px" top="5vh">
      <div v-if="reportData" class="report-preview">
        <h2 style="text-align: center; margin-bottom: 20px">{{ previewTitle }}</h2>

        <h3>一、核心指标概览</h3>
        <el-descriptions :column="2" border style="margin: 16px 0">
          <el-descriptions-item label="学生总数">{{ dashboardStats.studentCount ?? '-' }} 人</el-descriptions-item>
          <el-descriptions-item label="课程数量">{{ dashboardStats.courseCount ?? '-' }} 门</el-descriptions-item>
          <el-descriptions-item label="及格率">{{ dashboardStats.passRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="优秀率">{{ dashboardStats.excellentRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="平均出勤率">{{ dashboardStats.attendanceRate ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="预警学生">{{ dashboardStats.warningCount ?? '-' }} 人</el-descriptions-item>
        </el-descriptions>

        <h3>二、总体概述 <el-tag size="small" :type="reportSourceTag">{{ reportSourceLabel }}</el-tag></h3>
        <p>{{ reportData.summary }}</p>

        <h3>三、关键结论</h3>
        <p>{{ reportData.conclusion }}</p>

        <h3>四、建议措施</h3>
        <p>{{ reportData.suggestion }}</p>

        <el-alert
          v-if="reportData.source === 'llm'"
          title="本报告由 AI 增强生成，结论与建议仅供参考"
          type="info"
          show-icon
          :closable="false"
          style="margin-top: 16px"
        />
      </div>
      <el-empty v-else description="暂无报告数据" />
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.report-type-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.report-type-card {
  padding: 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;

  h4 {
    font-size: 14px;
    margin: 8px 0 4px;
  }

  p {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.4;
  }

  &:hover {
    border-color: #93c5fd;
    background: #f8fafc;
  }

  &.active {
    border-color: #2563eb;
    background: #eff6ff;

    .el-icon {
      color: #2563eb;
    }
  }
}

.report-preview {
  h3 {
    font-size: 15px;
    margin: 16px 0 8px;
    color: #1e293b;
  }

  p, ol {
    font-size: 14px;
    color: #475569;
    line-height: 1.8;
  }

  ol {
    padding-left: 20px;
  }
}
</style>
