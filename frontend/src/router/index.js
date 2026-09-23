import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/components/AppLayout.vue'
import { useDataStore } from '@/stores/data'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/agent' },
      {
        path: 'agent', name: 'agent',
        component: () => import('@/views/Agent.vue'),
        meta: { title: 'Zwork 助手' },
      },
      { path: 'profile', redirect: '/resume' },
      {
        path: 'interview-reviews', name: 'interview-reviews',
        component: () => import('@/views/InterviewReviews.vue'),
        meta: { title: '面试复盘' },
      },
      { path: 'career', redirect: '/interview-reviews' },
      {
        path: 'resume', name: 'resume',
        component: () => import('@/views/ResumeCenter.vue'),
        meta: { title: '简历中心' },
      },
      {
        path: 'platform-recruitment', name: 'platform-recruitment',
        component: () => import('@/views/PlatformRecruitment.vue'),
        meta: { title: '平台招聘' },
      },
      { path: 'scheduled-tasks', redirect: '/platform-recruitment' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '总览' },
      },
      {
        path: 'applications',
        name: 'applications',
        component: () => import('@/views/Applications.vue'),
        meta: { title: '投递记录' },
      },
      {
        path: 'schedules',
        name: 'schedules',
        component: () => import('@/views/Schedules.vue'),
        meta: { title: '未来安排' },
      },
      {
        path: 'statistics',
        name: 'statistics',
        component: () => import('@/views/Statistics.vue'),
        meta: { title: '统计分析' },
      },
      {
        path: 'companies',
        name: 'companies',
        component: () => import('@/views/Companies.vue'),
        meta: { title: '公司管理' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '设置' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/agent' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const store = useDataStore()
  await store.restoreSession()
  document.title = `${to.meta.title || '工作台'} · Zwork`
  if (!to.meta.public && !store.authenticated) {
    return { name: 'login' }
  }
  if (to.name === 'login' && store.authenticated) {
    return { name: 'agent' }
  }
})

export default router
