/// <reference types="vite/client" />

/** 扩展 vue-router 路由 meta 类型 */
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    public?: boolean
    roles?: string[]
  }
}

export {}
