import axios from 'axios'

const instance = axios.create({
  baseURL: '',
  timeout: 10000
})

/** 从后端统一响应 / FastAPI 422 里取出可读中文 */
export function getErrorMessage(error, fallback = '请求失败') {
  const data = error?.response?.data
  if (!data) return error?.message || fallback

  if (typeof data.message === 'string' && data.message) {
    return data.message
  }
  // 未自定义处理器时的原始 422：detail 是数组
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : ''
        const msg = item.msg || ''
        return field ? `${field}: ${msg}` : msg
      })
      .filter(Boolean)
      .join('；')
  }
  if (typeof data.detail === 'string') return data.detail
  return fallback
}

instance.interceptors.request.use(
  function (config) {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  function (error) {
    return Promise.reject(error)
  }
)

instance.interceptors.response.use(
  function (response) {
    return response
  },
  function (error) {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      if (!location.pathname.includes('/login')) {
        location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default instance
