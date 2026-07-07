<!--
  报告生成与导出中心
  支持多种报告类型的一键生成与导出
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, View } from '@element-plus/icons-vue'
import { delay } from '@/utils/auth'
import { departmentOptions, semesterOptions } from '@/mock'

/** 报告类型列表 */
const reportTypes = [
  { id: 1, name: '班级学情分析报告', desc: '包含班级整体学情、成绩分布、预警名单', icon: 'Reading' },
  { id: 2, name: '教师教学评价报告', desc: '包含教学各维度得分、排名对比、优化建议', icon: 'Avatar' },
  { id: 3, name: '课程质量报告', desc: '包含课程建设各维度评价、同类课程对比', icon: 'Notebook' },
  { id: 4, name: '院系教学质量总报告', desc: '包含院系整体指标、趋势分析、决策建议', icon: 'OfficeBuilding' },
]

/** 生成参数 */
const genParams = ref({
  reportType: 1,
  semester: '2025-1',
  department: '',
  format: 'pdf',
})

/** 生成状态 */
const generating = ref(false)
const previewVisible = ref(false)

/** 历史报告 */
const historyReports = ref([
  { id: 1, name: '计科2401班学情分析报告', type: '班级学情', time: '2026-03-15 10:30', format: 'PDF' },
  { id: 2, name: '2025春季教师评价报告', type: '教师评价', time: '2026-03-14 16:00', format: 'Excel' },
  { id: 3, name: '计算机学院质量总报告', type: '院系总报告', time: '2026-03-12 09:00', format: 'PDF' },
])

/**
 * 生成报告
 */
async function generateReport(): Promise<void> {
  generating.value = true
  await delay(2000)
  generating.value = false
  const typeName = reportTypes.find((t) => t.id === genParams.value.reportType)?.name || '报告'
  historyReports.value.unshift({
    id: Date.now(),
    name: typeName,
    type: typeName.slice(0, 4),
    time: new Date().toLocaleString('zh-CN'),
    format: genParams.value.format === 'pdf' ? 'PDF' : 'Excel',
  })
  ElMessage.success('报告生成成功！')
}

/**
 * 预览报告
 */
function previewReport(): void {
  previewVisible.value = true
}

/**
 * 导出报告
 */
function exportReport(): void {
  ElMessage.success(`报告已导出为 ${genParams.value.format.toUpperCase()} 格式`)
}
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <!-- 报告生成区 -->
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
            <el-form-item label="院系">
              <el-select v-model="genParams.department" style="width: 100%">
                <el-option v-for="d in departmentOptions" :key="d.value" :label="d.label" :value="d.value" />
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

      <!-- 历史报告 -->
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

    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" title="报告预览" width="700px" top="5vh">
      <div class="report-preview">
        <h2 style="text-align: center; margin-bottom: 20px">教学分析报告</h2>
        <h3>一、核心指标概览</h3>
        <p>本报告基于 2025-2026 学年第一学期教学数据生成，涵盖学生 2846 人、课程 186 门。</p>
        <el-descriptions :column="2" border style="margin: 16px 0">
          <el-descriptions-item label="整体及格率">87.6%</el-descriptions-item>
          <el-descriptions-item label="优秀率">23.4%</el-descriptions-item>
          <el-descriptions-item label="平均出勤率">92.3%</el-descriptions-item>
          <el-descriptions-item label="预警学生">47 人</el-descriptions-item>
        </el-descriptions>
        <h3>二、分析结论</h3>
        <p>整体教学质量良好，计算机学院表现突出。需重点关注操作系统课程的教改。</p>
        <h3>三、优化建议</h3>
        <ol>
          <li>加强薄弱知识点（面向对象、异常处理）的针对性辅导</li>
          <li>对 47 名预警学生实施一对一学业帮扶</li>
          <li>推广作业批改反馈优秀的教学经验</li>
        </ol>
      </div>
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
