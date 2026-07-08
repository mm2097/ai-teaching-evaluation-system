<!--
  报告生成与导出中心
  统计指标由后端计算，分析结论与建议由 LLM 生成
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, View } from '@element-plus/icons-vue'
import { generateAiReport } from '@/api/ai'
import { fetchSemesters, fetchCourses, fetchClasses } from '@/api/dict'
import type { AiReportResult } from '@/types'

const semesterOptions = ref<{ label: string; value: string }[]>([])
const courses = ref<any[]>([])
const classes = ref<any[]>([])

onMounted(async () => {
  try {
    const [semRes, courseRes, classRes] = await Promise.all([
      fetchSemesters(),
      fetchCourses({ deptId: 1 }),
      fetchClasses({ deptId: 1 }),
    ])
    semesterOptions.value = semRes.map(s => ({ label: s.semesterName, value: s.semesterCode }))
    courses.value = courseRes
    classes.value = classRes
  } catch { /* empty */ }
})

const reportTypes = [
  { id: 1, name: '班级学情分析报告', desc: '包含班级整体学情、成绩分布、预警名单', icon: 'Reading' },
  { id: 2, name: '学生个人学情报告', desc: '包含学生雷达图、知识点掌握、学习建议', icon: 'User' },
  { id: 3, name: '课程知识点分析报告', desc: '包含知识点热力图、薄弱项分析、改进建议', icon: 'Grid' },
  { id: 4, name: '学生学习质量报告', desc: '包含学习质量评价得分、维度分析', icon: 'Medal' },
]

const genParams = ref({
  reportType: 1,
  semester: '2025-2026-1',
  courseId: 1,
  classId: 1,
  format: 'pdf',
})

const generating = ref(false)
const previewVisible = ref(false)
const reportData = ref<AiReportResult | null>(null)

const csCourses = computed(() => courses.value)
const csClasses = computed(() => classes.value)

const historyReports = ref([
  { id: 1, name: '计科2401班-数据结构学情报告', type: '班级学情', time: '2026-03-15 10:30', format: 'PDF' },
  { id: 2, name: '陈同学-数据结构个人报告', type: '个人学情', time: '2026-03-14 16:00', format: 'PDF' },
  { id: 3, name: '数据结构知识点分析报告', type: '知识点', time: '2026-03-12 09:00', format: 'PDF' },
])

async function generateReport(): Promise<void> {
  generating.value = true
  try {
    reportData.value = await generateAiReport({ courseId: genParams.value.courseId, scope: 'class' })
    const typeName = reportTypes.find((t) => t.id === genParams.value.reportType)?.name || '报告'
    historyReports.value.unshift({
      id: Date.now(),
      name: typeName,
      type: typeName.slice(0, 4),
      time: new Date().toLocaleString('zh-CN'),
      format: genParams.value.format === 'pdf' ? 'PDF' : 'Excel',
    })
    ElMessage.success('报告生成成功！')
  } catch {
    ElMessage.error('报告生成失败，核心指标仍可查看')
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
              v-for="item in reportTypes"
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
        <h2 style="text-align: center; margin-bottom: 20px">计算机学院学情分析报告</h2>

        <h3>一、核心指标概览</h3>
        <p>本报告基于统计数据生成，面向计算机学院单课程/单班级维度。</p>
        <el-descriptions :column="2" border style="margin: 16px 0">
          <el-descriptions-item label="班级人数">{{ reportData.metrics.classSize }} 人</el-descriptions-item>
          <el-descriptions-item label="平均成绩">{{ reportData.metrics.avgScore }}</el-descriptions-item>
          <el-descriptions-item label="及格率">{{ (reportData.metrics.passRate * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="平均出勤率">{{ (reportData.metrics.attendanceRate * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="预警学生">{{ reportData.metrics.warningCount }} 人</el-descriptions-item>
          <el-descriptions-item label="成绩趋势">{{ reportData.trend }}</el-descriptions-item>
        </el-descriptions>

        <h3>二、薄弱知识点</h3>
        <el-table :data="reportData.weakKnowledgePoints" size="small" border style="margin-bottom: 16px">
          <el-table-column prop="name" label="知识点" />
          <el-table-column prop="correctRate" label="正确率" width="120">
            <template #default="{ row }">{{ (row.correctRate * 100).toFixed(0) }}%</template>
          </el-table-column>
        </el-table>

        <h3>三、分析结论 <el-tag size="small" type="warning">AI 生成</el-tag></h3>
        <p>{{ reportData.conclusion }}</p>

        <h3>四、教学优化建议 <el-tag size="small" type="warning">AI 生成</el-tag></h3>
        <ol>
          <li v-for="(item, idx) in reportData.suggestions" :key="idx">{{ item }}</li>
        </ol>
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
