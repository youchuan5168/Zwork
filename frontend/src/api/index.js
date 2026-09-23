import axios from 'axios'

const api = axios.create({ baseURL: '/api', withCredentials: true, timeout: 15000 })

// 统一携带 JWT
api.interceptors.request.use((config) => {
  const csrf = document.cookie.split('; ').find((item) => item.startsWith('qz_csrf='))
  if (csrf) config.headers['X-CSRF-Token'] = decodeURIComponent(csrf.slice(8))
  return config
})

// 401 统一跳登录；其余错误透传给调用方
api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    if (err.response?.status === 401) {
      window.dispatchEvent(new Event('auth-expired'))
    }
    return Promise.reject(err)
  },
)

export default api
