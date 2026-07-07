<!--
  面包屑导航组件
  根据当前路由自动生成层级路径，提升页面定位感
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { routeParentMap, routeTitleMap } from '@/config/menu'

const route = useRoute()

/** 面包屑项列表 */
const breadcrumbs = computed(() => {
  const path = route.path
  const items: { title: string; path?: string }[] = [{ title: '首页', path: '/dashboard' }]

  const parent = routeParentMap[path]
  if (parent) {
    items.push({ title: parent.title })
  }

  const currentTitle = routeTitleMap[path]
  if (currentTitle && path !== '/dashboard') {
    items.push({ title: currentTitle })
  }

  return items
})
</script>

<template>
  <el-breadcrumb separator="/" class="breadcrumb-nav">
    <el-breadcrumb-item
      v-for="(item, index) in breadcrumbs"
      :key="index"
      :to="item.path ? { path: item.path } : undefined"
    >
      {{ item.title }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<style scoped lang="scss">
.breadcrumb-nav {
  :deep(.el-breadcrumb__inner) {
    font-weight: 400;
    color: #64748b;
  }

  :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
    color: #1e293b;
    font-weight: 500;
  }
}
</style>
