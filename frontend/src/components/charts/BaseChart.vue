<!--
  ECharts 图表封装组件
  统一处理图表初始化、resize 自适应与销毁，避免内存泄漏
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

/** 组件属性：图表配置项与高度 */
const props = withDefaults(
  defineProps<{
    option: EChartsOption
    height?: string
  }>(),
  {
    height: '360px',
  },
)

/** 图表 DOM 容器引用 */
const chartRef = ref<HTMLDivElement>()
/** ECharts 实例（浅响应式，避免深度代理影响性能） */
const chartInstance = shallowRef<echarts.ECharts>()

/**
 * 初始化或更新图表
 */
function renderChart(): void {
  if (!chartRef.value) return
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
  chartInstance.value.setOption(props.option, true)
}

/**
 * 窗口尺寸变化时重绘图表
 */
function handleResize(): void {
  chartInstance.value?.resize()
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})

/** 监听配置变化，动态更新图表（浅监听，option 来自 computed 每次会返回新引用） */
watch(
  () => props.option,
  () => renderChart(),
)
</script>

<template>
  <div ref="chartRef" class="base-chart" :style="{ height }" />
</template>

<style scoped lang="scss">
.base-chart {
  width: 100%;
}
</style>
