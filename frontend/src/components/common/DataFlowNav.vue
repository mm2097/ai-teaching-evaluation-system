<!--
  数据采集流程导航条
  在「模板上传 → 数据管理」页面间提供跳转
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Document } from '@element-plus/icons-vue'
import { useDataFlowStore } from '@/stores/dataFlow'

const route = useRoute()
const router = useRouter()
const dataFlowStore = useDataFlowStore()

const steps = [
  { path: '/data/import', title: '模板上传', step: 1 },
  { path: '/data/manage', title: '数据管理', step: 2 },
]

const currentStep = computed(() => {
  const idx = steps.findIndex((s) => s.path === route.path)
  return idx >= 0 ? idx + 1 : 0
})

const currentLog = computed(() => dataFlowStore.currentImportLog)

function goTo(path: string): void {
  router.push(path)
}
</script>

<template>
  <div class="data-flow-nav content-card">
    <div class="flow-steps">
      <template v-for="(step, index) in steps" :key="step.path">
        <div
          class="flow-step"
          :class="{ active: route.path === step.path, done: currentStep > step.step }"
          @click="goTo(step.path)"
        >
          <span class="step-num">{{ step.step }}</span>
          <span class="step-title">{{ step.title }}</span>
        </div>
        <el-icon v-if="index < steps.length - 1" class="flow-arrow"><ArrowRight /></el-icon>
      </template>
    </div>

    <div v-if="currentLog" class="flow-context">
      <el-icon><Document /></el-icon>
      <span class="context-label">当前数据文件：</span>
      <el-tag type="primary" effect="plain">{{ currentLog.fileName }}</el-tag>
      <span class="context-stat">成功 {{ currentLog.successCount }} 条</span>
    </div>
    <div v-else class="flow-context empty">
      <span>尚未上传数据，请先在「模板上传」下载模板并上传文件</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.data-flow-nav {
  padding: 16px 24px;
}

.flow-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #f8fafc;
  border: 1px solid #e2e8f0;

  &:hover {
    border-color: #2563eb;
    background: #eff6ff;
  }

  &.active {
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;

    .step-num {
      background: rgba(255, 255, 255, 0.25);
      color: #fff;
    }
  }

  &.done:not(.active) {
    border-color: #10b981;
    background: #ecfdf5;
  }

  .step-num {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
  }

  .step-title {
    font-size: 14px;
    font-weight: 500;
  }
}

.flow-arrow {
  color: #94a3b8;
}

.flow-context {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
  color: #64748b;

  &.empty {
    color: #94a3b8;
    font-style: italic;
  }

  .context-label {
    font-weight: 500;
    color: #475569;
  }

  .context-stat {
    margin-left: auto;
    color: #64748b;
  }
}
</style>
