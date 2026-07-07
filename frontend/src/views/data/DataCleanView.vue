<!--
  数据清洗与标准化页面
  展示清洗流程与数据质量报告
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { delay } from '@/utils/auth'

/** 清洗任务执行状态 */
const cleaning = ref(false)
const cleaned = ref(false)

/** 清洗步骤进度 */
const steps = ref([
  { title: '重复数据检测', desc: '基于学号、课程号去重', status: 'wait', count: 0 },
  { title: '缺失值处理', desc: '标记并填充关键字段缺失', status: 'wait', count: 0 },
  { title: '格式统一', desc: '日期、数值、文本标准化', status: 'wait', count: 0 },
  { title: '异常值识别', desc: '识别超范围成绩与异常考勤', status: 'wait', count: 0 },
])

/** 异常数据清单 */
const anomalyList = ref([
  { id: 1, type: '成绩异常', field: '分数', value: '105', reason: '分数超出合理范围 (0-100)', studentId: '2024001012' },
  { id: 2, type: '缺失值', field: '学号', value: '空', reason: '关键字段缺失', studentId: '-' },
  { id: 3, type: '重复记录', field: '学号+课程号', value: '2024001001+CS101', reason: '存在重复导入记录', studentId: '2024001001' },
  { id: 4, type: '格式错误', field: '考试时间', value: '2025/13/32', reason: '日期格式无效', studentId: '2024001023' },
])

/** 数据质量报告 */
const qualityReport = ref({
  totalRecords: 9868,
  duplicateRemoved: 45,
  missingMarked: 23,
  formatFixed: 156,
  anomalyDetected: 18,
  qualityScore: 96.8,
})

/**
 * 执行数据清洗流程
 */
async function startCleaning(): Promise<void> {
  cleaning.value = true
  cleaned.value = false

  const results = [45, 23, 156, 18]
  for (let i = 0; i < steps.value.length; i++) {
    steps.value[i]!.status = 'process'
    await delay(800)
    steps.value[i]!.status = 'finish'
    steps.value[i]!.count = results[i]!
  }

  cleaning.value = false
  cleaned.value = true
  ElMessage.success('数据清洗完成！')
}
</script>

<template>
  <div class="page-container">
    <!-- 清洗操作区 -->
    <div class="content-card">
      <div class="content-card__title">数据清洗流程</div>
      <el-steps :active="cleaned ? 4 : (cleaning ? -1 : 0)" finish-status="success" align-center>
        <el-step
          v-for="step in steps"
          :key="step.title"
          :title="step.title"
          :description="step.desc"
          :status="step.status as 'wait' | 'process' | 'finish'"
        />
      </el-steps>
      <div style="text-align: center; margin-top: 24px">
        <el-button type="primary" size="large" :loading="cleaning" @click="startCleaning">
          {{ cleaning ? '清洗中...' : '开始清洗' }}
        </el-button>
      </div>
    </div>

    <!-- 数据质量报告 -->
    <div v-if="cleaned" class="content-card">
      <div class="content-card__title">数据质量报告</div>
      <el-row :gutter="16">
        <el-col :span="4" v-for="(val, key) in {
          '总记录数': qualityReport.totalRecords,
          '去重记录': qualityReport.duplicateRemoved,
          '缺失标记': qualityReport.missingMarked,
          '格式修正': qualityReport.formatFixed,
          '异常识别': qualityReport.anomalyDetected,
        }" :key="key">
          <div class="quality-item">
            <div class="quality-value">{{ val }}</div>
            <div class="quality-label">{{ key }}</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="quality-item highlight">
            <div class="quality-value">{{ qualityReport.qualityScore }}%</div>
            <div class="quality-label">数据质量得分</div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 异常数据清单 -->
    <div class="content-card">
      <div class="content-card__title">异常数据清单</div>
      <el-table :data="anomalyList" stripe border>
        <el-table-column prop="type" label="异常类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.type === '成绩异常' ? 'danger' : 'warning'">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="studentId" label="学号" width="140" />
        <el-table-column prop="field" label="异常字段" width="120" />
        <el-table-column prop="value" label="异常值" width="160" />
        <el-table-column prop="reason" label="异常原因" />
        <el-table-column label="操作" width="120" align="center">
          <template #default>
            <el-button type="primary" link size="small">修正</el-button>
            <el-button type="danger" link size="small">忽略</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.quality-item {
  text-align: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;

  .quality-value {
    font-size: 24px;
    font-weight: 700;
    color: #1e293b;
  }

  .quality-label {
    font-size: 13px;
    color: #64748b;
    margin-top: 4px;
  }

  &.highlight {
    background: linear-gradient(135deg, #eff6ff, #dbeafe);

    .quality-value {
      color: #2563eb;
    }
  }
}
</style>
