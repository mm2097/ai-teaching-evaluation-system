/**
 * 应用入口文件
 * 初始化 Vue 实例，注册 Element Plus、Pinia、Router 等插件
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'

/** 全局样式 */
import './styles/global.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn, size: 'default' })

/** 应用启动时恢复登录态 */
const userStore = useUserStore()
userStore.restoreSession()

app.mount('#app')
