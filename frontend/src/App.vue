<!--
  根组件
  作为整个应用的入口容器，仅负责渲染路由视图
-->
<script setup lang="ts">
// 根组件无需额外逻辑，路由视图由 router-view 渲染
</script>

<template>
  <router-view />
</template>

<style>
/* 根组件无额外样式，全局样式在 global.scss 中定义 */
</style>
