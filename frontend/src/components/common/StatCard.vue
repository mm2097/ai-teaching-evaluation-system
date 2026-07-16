<!--
  统计指标卡片组件
  用于看板页展示核心数据指标，支持趋势指示
-->
<script setup lang="ts">
import { computed } from 'vue'
import * as Icons from '@element-plus/icons-vue'

/** 卡片数据属性 */
const props = defineProps<{
  title: string
  value: number | string
  unit?: string
  icon: string
  color: string
  trend?: number
  /** 'number' 大数字展示（默认），'text' 文本展示（小字、可换行） */
  variant?: 'number' | 'text'
}>()

/** 动态解析 Element Plus 图标组件 */
const IconComponent = computed(() => {
  return (Icons as Record<string, unknown>)[props.icon] || Icons.DataLine
})
</script>

<template>
  <div class="stat-card" :class="{ 'stat-card--text': variant === 'text' }">
    <div class="stat-card__icon" :style="{ background: `${color}15`, color }">
      <el-icon :size="28"><component :is="IconComponent" /></el-icon>
    </div>
    <div class="stat-card__content">
      <div class="stat-card__title">{{ title }}</div>
      <div class="stat-card__value">
        <span class="num">{{ value }}</span>
        <span v-if="unit" class="unit">{{ unit }}</span>
      </div>
      <div v-if="trend !== undefined" class="stat-card__trend" :class="trend >= 0 ? 'up' : 'down'">
        <el-icon><component :is="trend >= 0 ? Icons.Top : Icons.Bottom" /></el-icon>
        {{ Math.abs(trend) }}% 较上期
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.12);
  }

  &__icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__content {
    overflow: hidden;
    min-width: 0;
  }

  &__title {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__value {
    .num {
      font-size: 28px;
      font-weight: 700;
      color: #1e293b;
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
      display: inline-block;
    }

    .unit {
      font-size: 14px;
      color: #94a3b8;
      margin-left: 4px;
    }
  }

  // 文本型卡片：小字、允许换行，便于展示完整课程/班级名称
  &--text {
    .stat-card__value .num {
      font-size: 17px;
      font-weight: 600;
      line-height: 1.35;
      white-space: normal;
      word-break: break-all;
      overflow: visible;
      text-overflow: unset;
      display: block;
    }
  }

  &__trend {
    font-size: 12px;
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 2px;

    &.up {
      color: #10b981;
    }

    &.down {
      color: #ef4444;
    }
  }
}
</style>
