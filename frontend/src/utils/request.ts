/**
 * Axios 实例
 * 统一 baseURL、超时、错误处理
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 响应拦截:统一错误提示(FastAPI 错误格式为 { detail: "..." })
request.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export default request
