import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './styles/global.css'
import { useDataStore } from './stores/data'

const savedTheme = localStorage.getItem('zwork-theme')
document.documentElement.dataset.theme = savedTheme === 'dark' ? 'dark' : 'light'

const pinia = createPinia()
function clearSession() {
  const store = useDataStore(pinia)
  const wasAuthenticated = store.authenticated
  store.clearAuth()
  if (wasAuthenticated) router.replace({ name: 'login' })
}
window.addEventListener('auth-expired', clearSession)
window.addEventListener('storage', (event) => {
  if (event.key === 'qz-auth-event') clearSession()
})
localStorage.removeItem('token')
localStorage.removeItem('username')
createApp(App)
  .use(pinia)
  .use(router)
  .use(ElementPlus, { locale: zhCn })
  .mount('#app')
