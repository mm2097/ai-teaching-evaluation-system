/**
 * Axios 实例
 * 统一 baseURL、超时、错误处理、认证头
 *
 * USE_MOCK = true 时启用前端全量 Mock，无需后端即可独立运行。
 * 改为 false 即恢复真实后端联调。
 */
import axios from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, clearAuth } from '@/utils/auth'
import router from '@/router'
import { handleRequest } from '@/mock/handler'

/** 一键开关：true=全量 Mock，false=真实后端 */
export const USE_MOCK = false

const request = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

/* ============================================================
 * Mock adapter —— 在 axios 层统一拦截，不改动任何 View / API 文件
 * ============================================================ */
if (USE_MOCK) {
  request.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    // 模拟 200-500ms 网络延迟
    await new Promise((resolve) => setTimeout(resolve, 200 + Math.random() * 300))

    const method = (config.method || 'GET').toUpperCase()
    const url = config.url || ''
    const params = config.params
    const data = config.data

    const result = handleRequest({ method, url, params, data })

    if (result.status >= 400) {
      // 构造错误让拦截器处理
      const error: any = {
        response: {
          status: result.status,
          data: result.data,
        },
        config,
        message: `Request failed with status code ${result.status}`,
      }
      throw error
    }

    return {
      data: result.data,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    } as AxiosResponse
  }
}

request.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestUrl = error.config?.url || ''
    const isLoginRequest = requestUrl === '/login' || requestUrl.endsWith('/login')
    const isOnLoginPage = router.currentRoute.value.path === '/login'

    if (error.response?.status === 401 && !isLoginRequest) {
      clearAuth()
      if (!isOnLoginPage) {
        ElMessage.error('登录已过期，请重新登录')
        router.push('/login')
      }
    } else if (error.response?.status === 403) {
      // 权限不足时静默失败，避免反复弹出「当前角色无权…」干扰使用
    } else if (!error.config?.silentError && !isLoginRequest) {
      const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout')
      const isNetwork = error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')
      const detail = error.response?.data?.detail
      let msg = typeof detail === 'string' ? detail : error.message || '请求失败'
      if (!USE_MOCK && (isTimeout || isNetwork)) {
        msg = '无法连接后端服务（请确认 backend 已在 8000 端口启动：uvicorn app.main:app --reload）'
      }
      if (!USE_MOCK) {
        ElMessage.error(msg)
      }
    }
    return Promise.reject(error)
  },
)

export default request
