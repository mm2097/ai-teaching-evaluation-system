<!--
  通用数据表格组件
  封装 el-table + el-pagination，统一处理分页、选择、操作列、加载态、空状态
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

export interface TableColumn {
  type?: 'selection' | 'index'
  prop?: string
  label: string
  width?: string | number
  minWidth?: string | number
  align?: 'left' | 'center' | 'right'
  fixed?: 'left' | 'right'
  showOverflowTooltip?: boolean
  /** 操作列按钮配置 */
  actions?: { label: string; type?: 'primary' | 'danger' | 'warning' | 'success' | 'info'; event: string; icon?: Component }[]
  /** 自定义 slot 名 */
  slot?: string
  /** tag 展示配置 */
  tag?: (row: any) => { text: string; type?: 'success' | 'warning' | 'danger' | 'info' | 'primary' }
}

const props = withDefaults(
  defineProps<{
    data: any[]
    columns: TableColumn[]
    loading?: boolean
    showPagination?: boolean
    currentPage?: number
    pageSize?: number
    total?: number
    pageSizes?: number[]
    showSelection?: boolean
    stripe?: boolean
    border?: boolean
    emptyText?: string
  }>(),
  {
    loading: false,
    showPagination: true,
    currentPage: 1,
    pageSize: 10,
    total: 0,
    pageSizes: () => [10, 20, 50],
    showSelection: false,
    stripe: true,
    border: true,
    emptyText: '暂无数据',
  },
)

const emit = defineEmits<{
  (e: 'page-change', page: number): void
  (e: 'size-change', size: number): void
  (e: 'selection-change', rows: any[]): void
  (e: 'action', event: string, row: any): void
}>()

const computedColumns = computed(() => {
  const cols = [...props.columns]
  if (props.showSelection) {
    cols.unshift({ type: 'selection', label: '', width: '50', align: 'center' })
  }
  return cols
})

function handleSelectionChange(rows: any[]): void {
  emit('selection-change', rows)
}

function handleAction(event: string, row: any): void {
  emit('action', event, row)
}

function handleCurrentChange(page: number): void {
  emit('page-change', page)
}

function handleSizeChange(size: number): void {
  emit('size-change', size)
}
</script>

<template>
  <div class="data-table-wrapper">
    <div v-loading="loading" class="table-body">
      <el-table
        :data="data"
        :stripe="stripe"
        :border="border"
        @selection-change="handleSelectionChange"
      >
        <template v-for="col in computedColumns" :key="col.prop || col.label || col.slot">
          <!-- 选择列 -->
          <el-table-column
            v-if="col.type === 'selection'"
            type="selection"
            width="50"
            align="center"
          />

          <!-- 序号列 -->
          <el-table-column
            v-else-if="col.type === 'index'"
            type="index"
            :label="col.label"
            :width="col.width"
            :align="col.align || 'center'"
          />

          <!-- 操作列 -->
          <el-table-column
            v-else-if="col.actions"
            :label="col.label"
            :width="col.width"
            :fixed="col.fixed || 'right'"
            :align="col.align || 'center'"
          >
            <template #default="{ row }">
              <el-button
                v-for="act in col.actions"
                :key="act.event"
                :type="act.type || 'primary'"
                link
                size="small"
                :icon="act.icon"
                @click="handleAction(act.event, row)"
              >
                {{ act.label }}
              </el-button>
            </template>
          </el-table-column>

          <!-- 自定义 slot 列 -->
          <el-table-column
            v-else-if="col.slot"
            :label="col.label"
            :prop="col.prop"
            :width="col.width"
            :min-width="col.minWidth"
            :fixed="col.fixed"
            :align="col.align"
            :show-overflow-tooltip="col.showOverflowTooltip"
          >
            <template #default="{ row }">
              <slot :name="col.slot" :row="row" />
            </template>
          </el-table-column>

          <!-- tag 列 -->
          <el-table-column
            v-else-if="col.tag"
            :label="col.label"
            :prop="col.prop"
            :width="col.width"
            :min-width="col.minWidth"
            :fixed="col.fixed"
            :align="col.align || 'center'"
            :show-overflow-tooltip="col.showOverflowTooltip"
          >
            <template #default="{ row }">
              <el-tag v-if="col.tag" :type="col.tag(row).type || 'info'" size="small">
                {{ col.tag(row).text }}
              </el-tag>
            </template>
          </el-table-column>

          <!-- 普通列 -->
          <el-table-column
            v-else
            :label="col.label"
            :prop="col.prop"
            :width="col.width"
            :min-width="col.minWidth"
            :fixed="col.fixed"
            :align="col.align"
            :show-overflow-tooltip="col.showOverflowTooltip"
          />
        </template>

        <template #empty>
          <el-empty :description="emptyText" :image-size="80" />
        </template>
      </el-table>
    </div>

    <div v-if="showPagination" class="table-pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-sizes="pageSizes"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="handleCurrentChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.data-table-wrapper {
  .table-body {
    min-height: 200px;
  }

  .table-pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
