import { defineStore } from 'pinia'

import { applicationApi, authApi, companyApi, scheduleApi } from '@/api/resources'

/**
 * 全局数据仓库：
 * - 登录后一次拉全量数据（个人数据量小），页面统计全部本地计算
 * - 任何增删改成功后重新拉取，保证多端打开时数据一致
 */
export const useDataStore = defineStore('data', {
  state: () => ({
    username: '',
    authenticated: false,
    sessionChecked: false,
    authGeneration: 0,
    applications: [],
    schedules: [],
    companies: [],
    loaded: false,
  }),

  actions: {
    async fetchAll() {
      const generation = this.authGeneration
      const [apps, scheds, comps] = await Promise.all([
        applicationApi.list(),
        scheduleApi.list(),
        companyApi.list(),
      ])
      if (!this.authenticated || generation !== this.authGeneration) return
      this.applications = apps
      this.schedules = scheds
      this.companies = comps
      this.loaded = true
    },

    async login(username, password) {
      const data = await authApi.login(username, password)
      this._applyAuth(data)
    },

    async register(username, password) {
      const data = await authApi.register(username, password)
      this._applyAuth(data)
    },

    _applyAuth(data) {
      this.clearAuth()
      this.username = data.username
      this.authenticated = true
      this.sessionChecked = true
      this.notifyAuthChange()
    },

    async restoreSession() {
      if (this.sessionChecked) return this.authenticated
      const generation = this.authGeneration
      try {
        const user = await authApi.me()
        if (generation !== this.authGeneration) return this.authenticated
        this.username = user.username
        this.authenticated = true
        this.sessionChecked = true
        return true
      } catch (error) {
        if (error.response?.status !== 401) throw error
        this.clearAuth()
        return false
      }
    },

    notifyAuthChange() {
      localStorage.setItem('qz-auth-event', `${Date.now()}-${Math.random()}`)
    },

    async logout() {
      try { await authApi.logout() } catch (error) {
        if (error.response?.status !== 401) throw error
      }
      this.clearAuth()
      this.notifyAuthChange()
    },

    clearAuth() {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      this.username = ''
      this.authenticated = false
      this.sessionChecked = true
      this.authGeneration += 1
      this.applications = []
      this.schedules = []
      this.companies = []
      this.loaded = false
    },
  },
})
