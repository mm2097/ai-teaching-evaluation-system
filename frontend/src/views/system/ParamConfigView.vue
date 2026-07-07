<!--
  基础参数配置页面
  维护学期、院系、预警阈值等业务参数
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { departmentOptions, semesterOptions } from '@/mock'

/** 当前配置 Tab */
const activeTab = ref('basic')

/** 基础数据 */
const basicData = ref({
  semesters: [...semesterOptions],
  departments: departmentOptions.filter((d) => d.value),
})

/** 预警阈值配置 */
const warningConfig = ref({
  scoreDropThreshold: 15,
  scoreDropCount: 3,
  absenceRateThreshold: 20,
  homeworkMissCount: 4,
})

/** 评价参数 */
const evalConfig = ref({
  excellentScore: 90,
  goodScore: 80,
  passScore: 60,
  autoEvalEnabled: true,
  evalCycle: 'semester',
})

/** 新增院系对话框 */
const deptDialogVisible = ref(false)
const newDeptName = ref('')

/**
 * 保存预警配置
 */
function saveWarningConfig(): void {
  ElMessage.success('预警阈值配置已保存')
}

/**
 * 保存评价配置
 */
function saveEvalConfig(): void {
  ElMessage.success('评价参数配置已保存')
}

/**
 * 新增院系
 */
function addDepartment(): void {
  if (!newDeptName.value) {
    ElMessage.warning('请输入院系名称')
    return
  }
  basicData.value.departments.push({
    label: newDeptName.value,
    value: newDeptName.value.slice(0, 2).toLowerCase(),
  })
  deptDialogVisible.value = false
  newDeptName.value = ''
  ElMessage.success('院系添加成功')
}
</script>

<template>
  <div class="page-container">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 基础数据维护 -->
      <el-tab-pane label="基础数据" name="basic">
        <el-row :gutter="24">
          <el-col :span="12">
            <h4 class="section-title">学期管理</h4>
            <el-table :data="basicData.semesters" stripe border size="small">
              <el-table-column prop="label" label="学期名称" />
              <el-table-column prop="value" label="编码" width="100" />
            </el-table>
          </el-col>
          <el-col :span="12">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <h4 class="section-title">院系管理</h4>
              <el-button type="primary" size="small" @click="deptDialogVisible = true">新增院系</el-button>
            </div>
            <el-table :data="basicData.departments" stripe border size="small">
              <el-table-column prop="label" label="院系名称" />
              <el-table-column prop="value" label="编码" width="100" />
            </el-table>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 预警阈值 -->
      <el-tab-pane label="预警阈值" name="warning">
        <el-form :model="warningConfig" label-width="200px" style="max-width: 600px">
          <el-form-item label="成绩连续下滑阈值 (分)">
            <el-input-number v-model="warningConfig.scoreDropThreshold" :min="5" :max="30" />
          </el-form-item>
          <el-form-item label="连续下滑次数">
            <el-input-number v-model="warningConfig.scoreDropCount" :min="2" :max="5" />
          </el-form-item>
          <el-form-item label="缺勤率预警阈值 (%)">
            <el-input-number v-model="warningConfig.absenceRateThreshold" :min="10" :max="50" />
          </el-form-item>
          <el-form-item label="连续未交作业次数">
            <el-input-number v-model="warningConfig.homeworkMissCount" :min="2" :max="10" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveWarningConfig">保存配置</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 评价参数 -->
      <el-tab-pane label="评价参数" name="eval">
        <el-form :model="evalConfig" label-width="160px" style="max-width: 600px">
          <el-form-item label="优秀分数线">
            <el-input-number v-model="evalConfig.excellentScore" :min="80" :max="100" />
          </el-form-item>
          <el-form-item label="良好分数线">
            <el-input-number v-model="evalConfig.goodScore" :min="70" :max="90" />
          </el-form-item>
          <el-form-item label="合格分数线">
            <el-input-number v-model="evalConfig.passScore" :min="50" :max="70" />
          </el-form-item>
          <el-form-item label="自动评价">
            <el-switch v-model="evalConfig.autoEvalEnabled" />
          </el-form-item>
          <el-form-item label="评价周期">
            <el-radio-group v-model="evalConfig.evalCycle">
              <el-radio value="monthly">每月</el-radio>
              <el-radio value="semester">每学期</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveEvalConfig">保存配置</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="deptDialogVisible" title="新增院系" width="400px">
      <el-input v-model="newDeptName" placeholder="请输入院系名称" />
      <template #footer>
        <el-button @click="deptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addDepartment">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #1e293b;
}
</style>
