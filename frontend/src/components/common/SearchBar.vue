<!--
  通用搜索筛选栏组件
  通过 fields 配置数组动态渲染搜索条件，支持 input / select / date 类型
-->
<script setup lang="ts">
import { Search, RefreshRight } from '@element-plus/icons-vue'

export interface SearchField {
  key: string
  label: string
  type: 'input' | 'select' | 'date'
  placeholder?: string
  width?: string | number
  clearable?: boolean
  options?: { label: string; value: string | number }[]
  /** select 是否多选 */
  multiple?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, string | number | undefined | (string | number)[]>
    fields: SearchField[]
    showReset?: boolean
    inline?: boolean
  }>(),
  {
    showReset: true,
    inline: true,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, any>): void
  (e: 'search'): void
  (e: 'reset'): void
}>()

function handleInput(key: string, value: unknown): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function handleSearch(): void {
  emit('search')
}

function handleReset(): void {
  const resetObj: Record<string, string | number | undefined> = {}
  for (const f of props.fields) {
    resetObj[f.key] = f.type === 'input' ? '' : undefined
  }
  emit('update:modelValue', resetObj)
  emit('reset')
}
</script>

<template>
  <div class="search-bar" :class="{ 'search-bar--block': !inline }">
    <div class="search-fields" :class="{ 'search-fields--block': !inline }">
      <template v-for="field in fields" :key="field.key">
        <!-- 输入框 -->
        <el-input
          v-if="field.type === 'input'"
          :model-value="modelValue[field.key]"
          :placeholder="field.placeholder || `请输入${field.label}`"
          :clearable="field.clearable !== false"
          :style="{ width: typeof field.width === 'number' ? field.width + 'px' : field.width || '200px' }"
          :prefix-icon="Search"
          @input="handleInput(field.key, $event)"
          @keyup.enter="handleSearch"
        />

        <!-- 下拉选择 -->
        <el-select
          v-else-if="field.type === 'select'"
          :model-value="modelValue[field.key]"
          :placeholder="field.placeholder || `请选择${field.label}`"
          :clearable="field.clearable !== false"
          :multiple="field.multiple"
          :style="{ width: typeof field.width === 'number' ? field.width + 'px' : field.width || '160px' }"
          @change="handleInput(field.key, $event)"
        >
          <el-option
            v-for="opt in field.options"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>

        <!-- 日期 -->
        <el-date-picker
          v-else-if="field.type === 'date'"
          :model-value="modelValue[field.key]"
          type="date"
          :placeholder="field.placeholder || `请选择${field.label}`"
          :clearable="field.clearable !== false"
          :style="{ width: typeof field.width === 'number' ? field.width + 'px' : field.width || '160px' }"
          @update:model-value="handleInput(field.key, $event)"
        />
      </template>
    </div>

    <div class="search-actions">
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button v-if="showReset" :icon="RefreshRight" @click="handleReset">重置</el-button>
      <slot name="extra" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.search-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;

  .search-fields {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;

    &--block {
      flex-direction: column;
      align-items: stretch;
    }
  }

  .search-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
}
</style>
