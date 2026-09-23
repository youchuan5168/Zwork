<script setup>
import { Calendar, DataAnalysis, DataBoard, House, OfficeBuilding, Setting, Tickets, Plus, ArrowDown, Monitor, Document, Menu as MenuIcon, SwitchButton, ChatDotRound, Delete, Sunny, Moon } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import BrandMark from '@/components/BrandMark.vue'
import { agentApi } from '@/api/resources'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const store = useDataStore()
const conversations = ref([])
const historyLoading = ref(false)
const theme = ref(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

const onlineMenus = [
  { path: '/dashboard', label: '总览', icon: DataBoard },
  { path: '/applications', label: '投递记录', icon: Tickets },
  { path: '/schedules', label: '未来安排', icon: Calendar },
  { path: '/statistics', label: '统计分析', icon: DataAnalysis },
  { path: '/companies', label: '公司管理', icon: OfficeBuilding },
]
const toolMenus = [
  { path: '/resume', label: '简历中心', icon: Document },
  { path: '/interview-reviews', label: '面试复盘', icon: DataAnalysis },
]

const tabMenus = [onlineMenus[0], onlineMenus[1], onlineMenus[2], { path: '/platform-recruitment', label: '平台招聘', icon: Monitor }]
const activePath = computed(() => route.path)
const mobileMenuOpen = ref(false)
watch(() => route.path, () => { mobileMenuOpen.value = false })

function setTheme(value) {
  theme.value = value
  document.documentElement.dataset.theme = value
  localStorage.setItem('zwork-theme', value)
}

const terminal = new Set(['completed', 'failed', 'cancelled', 'budget_exhausted', 'expired'])
const statusNames = {
  queued: '等待执行', running: '执行中', waiting_approval: '等待审批',
  completed: '已完成', failed: '失败', cancelled: '已取消',
  budget_exhausted: '预算耗尽', expired: '已过期',
}
function timeLabel(value) {
  return value ? new Date(value).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : ''
}
async function loadConversations() {
  if (!store.authenticated || historyLoading.value) return
  const generation = store.authGeneration
  historyLoading.value = true
  try {
    const rows = await agentApi.list()
    if (store.authenticated && generation === store.authGeneration) conversations.value = rows
  } catch (error) {
    if (error.response?.status !== 503 && generation === store.authGeneration) {
      ElMessage.error(formatApiError(error))
    }
  } finally { historyLoading.value = false }
}
function openConversation(id) {
  router.push({ name: 'agent', query: { run: id } })
}
function newConversation() {
  router.push({ name: 'agent' })
}
async function deleteConversation(row) {
  if (!terminal.has(row.status)) {
    ElMessage.warning('进行中的对话请先停止或完成')
    return
  }
  try {
    await ElMessageBox.confirm('删除后无法恢复，确定删除这条对话吗？', '删除对话', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await agentApi.remove(row.id)
    conversations.value = conversations.value.filter(item => item.id !== row.id)
    if (route.query.run === row.id) newConversation()
    ElMessage.success('对话已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(formatApiError(error))
  }
}
function historyChanged() { loadConversations() }
onMounted(() => {
  loadConversations()
  window.addEventListener('agent-history-changed', historyChanged)
})
onBeforeUnmount(() => window.removeEventListener('agent-history-changed', historyChanged))
watch(() => store.authGeneration, () => {
  conversations.value = []
  if (store.authenticated) loadConversations()
})

async function logout() {
  try {
    await store.logout()
    router.push({ name: 'login' })
  } catch (e) { ElMessage.error(formatApiError(e)) }
}
</script>

<template>
  <div class="app-canvas">
    <div class="layout">
      <aside class="sidebar">
        <router-link to="/agent" class="brand" aria-label="Zwork 首页">
          <BrandMark />
          <span class="wordmark"><b>Z</b><i>w</i>ork</span>
        </router-link>

        <router-link :to="{ path: '/dashboard', query: { new: '1' } }" class="quick-action">
          <el-icon><Plus /></el-icon><span>快速添加投递</span><kbd>+</kbd>
        </router-link>

        <div class="nav-label">工作台</div>
        <el-menu :default-active="activePath" :default-openeds="['online']" router class="side-menu">
          <el-sub-menu index="online">
            <template #title><el-icon><House /></el-icon><span>网申板块</span></template>
            <el-menu-item v-for="m in onlineMenus" :key="m.path" :index="m.path">
              <el-icon><component :is="m.icon" /></el-icon><span>{{ m.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/platform-recruitment">
            <el-icon><Monitor /></el-icon><span>平台招聘</span>
          </el-menu-item>
        </el-menu>
        <div class="nav-label nav-label-second">工具</div>
        <el-menu :default-active="activePath" router class="side-menu side-menu-secondary">
          <el-menu-item v-for="m in toolMenus" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon><span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>

        <div class="history-section">
          <div class="nav-label history-label"><span>对话历史</span><button type="button" aria-label="新建对话" @click="newConversation"><Plus /></button></div>
          <div class="conversation-list">
            <div v-for="row in conversations" :key="row.id" class="conversation-row" :class="{ active: route.query.run === row.id }">
              <button type="button" class="conversation-open" @click="openConversation(row.id)">
                <ChatDotRound /><span><strong>{{ row.message }}</strong><small>{{ timeLabel(row.created_at) }} · {{ statusNames[row.status] }}</small></span>
              </button>
              <button type="button" class="conversation-delete" aria-label="删除对话" @click.stop="deleteConversation(row)"><Delete /></button>
            </div>
            <p v-if="!conversations.length && !historyLoading" class="empty-conversations">还没有对话记录</p>
          </div>
        </div>

        <div class="sidebar-footer">
          <el-dropdown trigger="click" class="account-dropdown">
            <button class="account-card" type="button">
              <span class="account-avatar">{{ store.username?.slice(0, 1)?.toUpperCase() || 'W' }}</span>
              <span class="account-copy"><strong>{{ store.username }}</strong><small>个人工作台</small></span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="Setting" @click="router.push('/settings')">设置</el-dropdown-item>
                <el-dropdown-item divided :icon="SwitchButton" @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </aside>

      <div class="main">
        <header class="workspace-bar">
          <div class="workspace-location"><span>Zwork</span><span class="slash">/</span><strong>{{ route.meta.title || '总览' }}</strong></div>
          <div class="workspace-actions">
            <div class="theme-switch" role="group" aria-label="主题颜色">
              <button type="button" :class="{ active: theme === 'light' }" aria-label="切换为浅色主题" :aria-pressed="theme === 'light'" @click="setTheme('light')"><Sunny /></button>
              <button type="button" :class="{ active: theme === 'dark' }" aria-label="切换为深色主题" :aria-pressed="theme === 'dark'" @click="setTheme('dark')"><Moon /></button>
            </div>
            <div class="workspace-user"><span class="online-dot" /> {{ store.username }}</div>
          </div>
        </header>

        <header class="mobile-header">
          <router-link to="/agent" class="mobile-brand"><BrandMark /><span class="wordmark"><b>Z</b><i>w</i>ork</span></router-link>
          <div class="mobile-header-actions"><span class="mobile-title">{{ route.meta.title || '总览' }}</span><button type="button" class="mobile-theme" :aria-label="theme === 'light' ? '切换为深色主题' : '切换为浅色主题'" @click="setTheme(theme === 'light' ? 'dark' : 'light')"><Moon v-if="theme === 'light'" /><Sunny v-else /></button></div>
        </header>

        <main class="content" :class="{ 'agent-content': route.name === 'agent' }"><router-view /></main>

        <nav class="tabbar" aria-label="主导航">
          <router-link v-for="m in tabMenus" :key="m.path" :to="m.path" class="tab-item" :class="{ active: activePath === m.path }">
            <el-icon :size="19"><component :is="m.icon" /></el-icon><span>{{ m.label }}</span>
          </router-link>
          <button type="button" class="tab-item tab-button" :class="{ active: !tabMenus.some((m) => m.path === activePath) }" @click="mobileMenuOpen = true">
            <el-icon :size="19"><MenuIcon /></el-icon><span>更多</span>
          </button>
        </nav>
        <el-drawer v-model="mobileMenuOpen" title="全部功能" direction="btt" size="min(78vh, 640px)" class="mobile-nav-drawer">
          <div class="mobile-nav-group"><strong>工作台 · 网申板块</strong>
            <router-link v-for="m in onlineMenus" :key="m.path" :to="m.path"><el-icon><component :is="m.icon" /></el-icon>{{ m.label }}</router-link>
          </div>
          <div class="mobile-nav-group">
            <router-link to="/platform-recruitment"><el-icon><Monitor /></el-icon>平台招聘</router-link>
          </div>
          <div class="mobile-nav-group"><strong>工具</strong>
            <router-link v-for="m in toolMenus" :key="m.path" :to="m.path"><el-icon><component :is="m.icon" /></el-icon>{{ m.label }}</router-link>
          </div>
          <div class="mobile-nav-group"><strong>对话历史</strong>
            <button v-for="row in conversations" :key="row.id" type="button" @click="mobileMenuOpen = false; openConversation(row.id)"><el-icon><ChatDotRound /></el-icon>{{ row.message }}</button>
          </div>
          <div class="mobile-nav-group"><strong>账户</strong>
            <router-link to="/settings"><el-icon><Setting /></el-icon>设置</router-link>
            <button type="button" @click="mobileMenuOpen = false; logout()"><el-icon><SwitchButton /></el-icon>退出登录</button>
          </div>
        </el-drawer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-canvas { height: 100vh; min-height: 0; overflow: hidden; padding: 10px; background: #f5f5f7; }
.layout { display: flex; height: calc(100vh - 20px); min-height: 540px; background: #fff; border: 1px solid #e5e7eb; border-radius: 20px; overflow: hidden; box-shadow: 0 12px 36px rgba(15, 23, 42, .07); }
.sidebar { width: 228px; flex: none; display: flex; flex-direction: column; overflow-y: auto; border-right: 1px solid #e8eaed; background: #fff; }
.brand { min-height: 70px; display: flex; align-items: center; gap: 7px; padding: 16px 20px; color: #111827; text-decoration: none; font-size: 23px; font-weight: 800; letter-spacing: -.06em; }
.brand :deep(.brand-mark) { width: 31px; height: 31px; }
.wordmark { color: #173e3d; letter-spacing: -.055em; }
.wordmark b { color: #269b86; font-weight: 850; }
.wordmark i { color: #d9784e; font-style: normal; }
.quick-action { height: 38px; display: flex; align-items: center; gap: 9px; margin: 0 14px 25px; padding: 0 11px; border: 1px solid #e1e4e8; border-radius: 10px; background: #fff; color: #263238; text-decoration: none; font-size: 12px; font-weight: 600; box-shadow: 0 1px 3px rgba(15,23,42,.04); }
.quick-action:hover { border-color: #aeb7c2; background: #f8f9fa; }
.quick-action kbd { margin-left: auto; color: #7b9691; font-family: inherit; }
.nav-label { padding: 0 23px 7px; color: #8a9c9a; font-size: 10px; font-weight: 700; letter-spacing: .12em; }
.nav-label-second { padding-top: 15px; }
.side-menu { border-right: 0; padding: 0 12px; }
.side-menu .el-menu-item { height: 39px; margin: 2px 0; border-radius: 8px; padding: 0 13px !important; color: #455564; font-size: 13px; }
.side-menu .el-menu-item .el-icon { margin-right: 12px; font-size: 17px; }
.side-menu .el-menu-item:hover { background: #f4f5f6; }
.side-menu .el-menu-item.is-active { background: #eef1f3; color: #1f2937; font-weight: 700; }
.side-menu :deep(.el-sub-menu__title) { height: 39px; margin: 2px 0; border-radius: 8px; padding: 0 13px !important; color: #455564; font-size: 13px; }
.side-menu :deep(.el-sub-menu__title .el-icon) { margin-right: 12px; font-size: 17px; }
.side-menu :deep(.el-sub-menu .el-menu-item) { min-width: 0; padding-left: 30px !important; }
.side-menu :deep(.el-sub-menu__title:hover) { background: #f4f5f6; }
.side-menu-secondary { margin-bottom: 8px; }
.history-section { min-height: 120px; display: flex; flex-direction: column; padding-bottom: 10px; }
.history-label { display: flex; align-items: center; justify-content: space-between; padding-top: 10px; }
.history-label button { width: 24px; height: 24px; display: grid; place-items: center; border: 0; border-radius: 6px; background: transparent; color: #78838f; cursor: pointer; }
.history-label button:hover { background: #f0f2f4; color: #111827; }
.history-label svg { width: 13px; }
.conversation-list { max-height: 218px; overflow-y: auto; padding: 0 8px 3px 12px; }
.conversation-row { position: relative; border-radius: 9px; }
.conversation-row:hover, .conversation-row.active { background: #f0f2f4; }
.conversation-open { width: 100%; display: flex; align-items: flex-start; gap: 8px; padding: 9px 30px 9px 9px; border: 0; background: transparent; color: #475467; text-align: left; cursor: pointer; }
.conversation-open > svg { width: 14px; flex: none; margin-top: 2px; }
.conversation-open > span { min-width: 0; }
.conversation-open strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; font-weight: 550; }
.conversation-open small { display: block; margin-top: 4px; color: #98a2b3; font-size: 9px; }
.conversation-delete { position: absolute; top: 8px; right: 6px; width: 24px; height: 24px; display: none; place-items: center; border: 0; border-radius: 6px; background: #fff; color: #98a2b3; cursor: pointer; }
.conversation-row:hover .conversation-delete, .conversation-row:focus-within .conversation-delete { display: grid; }
.conversation-delete:hover { color: #d92d20; background: #fff1f0; }
.conversation-delete svg { width: 13px; }
.empty-conversations { margin: 12px; color: #98a2b3; font-size: 11px; text-align: center; }
.sidebar-footer { margin-top: auto; padding: 14px; border-top: 1px solid #eaf1ee; }
.account-dropdown { width: 100%; }
.sidebar-footer { position: sticky; bottom: 0; background: #fff; }
.account-card { width: 100%; display: flex; align-items: center; gap: 9px; padding: 7px; border: 1px solid #e2eeea; border-radius: 10px; background: #fff; color: #243449; cursor: pointer; text-align: left; }
.account-card:hover { background: #f6f7f8; }
.account-avatar { width: 30px; height: 30px; display: grid; place-items: center; flex: none; background: #e8f4f1; color: #176b62; border-radius: 7px; font-weight: 700; }
.account-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.account-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.account-copy small { color: #91a097; font-size: 10px; }
.account-card .el-icon { color: #88978d; font-size: 12px; }
.main { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.workspace-bar { height: 56px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 26px; border-bottom: 1px solid #e8eaed; background: rgba(255,255,255,.94); }
.workspace-location { display: flex; align-items: center; gap: 10px; color: #8b9b9e; font-size: 12px; }
.workspace-location strong { color: #344054; font-weight: 650; }
.slash { color: #ccd9d6; }
.workspace-actions { display: flex; align-items: center; gap: 12px; }
.theme-switch { display: flex; align-items: center; gap: 2px; padding: 3px; border: 1px solid #e1e4e8; border-radius: 10px; background: #f4f5f6; }
.theme-switch button { width: 30px; height: 27px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 7px; background: transparent; color: #8993a1; cursor: pointer; }
.theme-switch button:hover { color: #344054; }
.theme-switch button.active { background: #fff; color: #111827; box-shadow: 0 1px 3px rgba(15,23,42,.12); }
.theme-switch svg,.mobile-theme svg { width: 15px; height: 15px; }
.workspace-user { display: flex; align-items: center; gap: 8px; padding: 6px 11px; background: #fff; border: 1px solid #e2e5e9; border-radius: 100px; color: #51606f; font-size: 12px; }
.online-dot { width: 7px; height: 7px; background: #5cbfa8; border-radius: 50%; }
.content { flex: 1; min-width: 0; overflow-y: auto; padding: 24px 26px 34px; background: #f8f9fa; }
.content.agent-content { overflow: hidden; padding: 0; background: #fff; }
.mobile-header, .tabbar { display: none; }
.mobile-header-actions { display: flex; align-items: center; gap: 10px; }
.mobile-theme { width: 32px; height: 32px; display: grid; place-items: center; border: 1px solid var(--line); border-radius: 9px; background: var(--card-bg); color: var(--ink); }
.mobile-nav-group { display: grid; gap: 3px; margin-bottom: 20px; }
.mobile-nav-group strong { padding: 8px 12px; color: #8a9c9a; font-size: 12px; }
.mobile-nav-group a, .mobile-nav-group button { display: flex; align-items: center; gap: 12px; min-height: 42px; padding: 8px 12px; border: 0; border-radius: 8px; background: transparent; color: #344054; text-decoration: none; text-align: left; font-size: 14px; }
.mobile-nav-group a.router-link-active { background: #eaf9f2; color: #246d68; font-weight: 700; }
.mobile-nav-group .el-icon { font-size: 18px; }

@media (max-width: 768px) {
  .app-canvas { padding: 0; }
  .layout { height: 100dvh; min-height: 0; border: 0; border-radius: 0; box-shadow: none; }
  .sidebar, .workspace-bar { display: none; }
  .mobile-header { height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 0 17px; border-bottom: 1px solid #e7f0ed; background: #fff; }
  .mobile-brand { display: flex; align-items: center; gap: 5px; color: #111827; text-decoration: none; font-size: 19px; font-weight: 800; letter-spacing: -.05em; }
  .mobile-brand :deep(.brand-mark) { width: 26px; height: 26px; }
  .mobile-title { font-size: 13px; font-weight: 650; color: #667085; }
  .content { padding: 18px 14px 84px; }
  .content.agent-content { padding: 0 0 calc(59px + env(safe-area-inset-bottom)); }
  .tabbar { position: fixed; z-index: 100; left: 0; right: 0; bottom: 0; height: calc(59px + env(safe-area-inset-bottom)); display: flex; padding-bottom: env(safe-area-inset-bottom); background: #fff; border-top: 1px solid #e7f0ed; box-shadow: 0 -6px 22px rgba(42, 100, 90, .05); }
  .tab-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; color: #8a989b; text-decoration: none; font-size: 10px; }
  .tab-item.active { color: #277b75; font-weight: 700; }
  .tab-button { border: 0; background: transparent; cursor: pointer; }
}
</style>
