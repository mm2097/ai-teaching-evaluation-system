<!--
  三步向导 - 第2步：AI 生成进度
  Timeline 展示：检索参考题 → 构建RAG → DeepSeek生成 → 去重
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  stage: 'searching' | 'embedding' | 'generating' | 'deduping' | 'done' | 'error'
  ragReferenceCount: number
  error?: string
}>()

const stages = computed(() => [
  {
    key: 'searching',
    title: '检索参考题',
    desc: props.ragReferenceCount > 0
      ? `已找到 ${props.ragReferenceCount} 道参考题`
      : '从题库检索相关知识点的题目',
  },
  {
    key: 'embedding',
    title: '构建 RAG',
    desc: '将参考题注入向量上下文',
  },
  {
    key: 'generating',
    title: 'AI 生成',
    desc: 'DeepSeek 根据参考题生成新题（耗时最长，约 10-30 秒）',
  },
  {
    key: 'deduping',
    title: '去重',
    desc: '检查生成题与已有题的重复度',
  },
])

const stageOrder = ['searching', 'embedding', 'generating', 'deduping', 'done']
const currentIndex = computed(() => stageOrder.indexOf(props.stage))
</script>

<template>
  <div class="step2-progress">
    <div class="progress-content">
      <div class="progress-icon">
        <el-icon v-if="stage === 'error'" :size="48" color="#f56c6c">
          <WarningFilled />
        </el-icon>
        <el-icon v-else-if="stage === 'done'" :size="48" color="#67c23a">
          <CircleCheckFilled />
        </el-icon>
        <span v-else class="loading-spinner" />
      </div>

      <h3 v-if="stage === 'error'" class="progress-title error">生成失败</h3>
      <h3 v-else-if="stage === 'done'" class="progress-title success">生成完成</h3>
      <h3 v-else class="progress-title">AI 正在出题...</h3>

      <p v-if="stage === 'error'" class="error-msg">{{ error || 'AI 服务暂不可用，请稍后重试' }}</p>

      <div v-if="stage !== 'error'" class="timeline">
        <div
          v-for="(s, idx) in stages"
          :key="s.key"
          class="timeline-item"
          :class="{
            completed: currentIndex > idx || stage === 'done',
            active: currentIndex === idx,
            pending: currentIndex < idx,
          }"
        >
          <div class="timeline-dot">
            <el-icon v-if="currentIndex > idx || stage === 'done'">
              <Check />
            </el-icon>
            <span v-else-if="currentIndex === idx" class="dot-pulse" />
            <span v-else class="dot-empty" />
          </div>
          <div class="timeline-content">
            <div class="timeline-title">{{ s.title }}</div>
            <div class="timeline-desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Check, WarningFilled, CircleCheckFilled } from '@element-plus/icons-vue'
export default { components: { Check, WarningFilled, CircleCheckFilled } }
</script>

<style scoped lang="scss">
.step2-progress {
  display: flex;
  justify-content: center;
  padding: 40px 0;

  .progress-content {
    max-width: 480px;
    width: 100%;
    text-align: center;

    .progress-icon {
      margin-bottom: 16px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 48px;
    }

    .loading-spinner {
      display: inline-block;
      width: 40px;
      height: 40px;
      border: 4px solid #e2e8f0;
      border-top-color: #409eff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    .progress-title {
      font-size: 18px;
      color: #1e293b;
      margin-bottom: 8px;
      &.error { color: #f56c6c; }
      &.success { color: #67c23a; }
    }

    .error-msg {
      font-size: 13px;
      color: #f56c6c;
      margin-bottom: 16px;
    }

    .timeline {
      text-align: left;
      margin-top: 32px;
      padding-left: 20px;

      .timeline-item {
        display: flex;
        gap: 16px;
        padding-bottom: 24px;
        position: relative;

        &:not(:last-child)::before {
          content: '';
          position: absolute;
          left: 11px;
          top: 24px;
          bottom: 0;
          width: 2px;
          background: #e2e8f0;
        }

        &.completed::before { background: #67c23a; }

        .timeline-dot {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          font-size: 14px;
          z-index: 1;
          background: white;
        }

        &.completed .timeline-dot { color: #67c23a; }
        &.active .timeline-dot {
          .dot-pulse {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #409eff;
            animation: pulse 1s infinite;
          }
        }
        &.pending .timeline-dot .dot-empty {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: 2px solid #e2e8f0;
        }

        .timeline-content {
          .timeline-title {
            font-size: 14px;
            font-weight: 600;
            color: #1e293b;
          }
          .timeline-desc {
            font-size: 12px;
            color: #64748b;
            margin-top: 2px;
          }
        }

        &.pending .timeline-title { color: #94a3b8; }
      }
    }
  }
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
