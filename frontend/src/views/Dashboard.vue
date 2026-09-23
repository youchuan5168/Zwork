<script setup>
import { ArrowRight, Bell, Calendar, DataLine, Plus, SuccessFilled, Tickets } from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ApplicationForm from '@/components/ApplicationForm.vue'
import StageBadge from '@/components/StageBadge.vue'
import { STAGES, TYPE_COLORS } from '@/constants/stages'
import { useDataStore } from '@/stores/data'

const store = useDataStore()
const route = useRoute()
const router = useRouter()
const formOpen = ref(false)

function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = dateKey(new Date())
const sevenDays = dateKey(new Date(Date.now() + 7 * 86400e3))

onMounted(() => { if (!store.loaded) store.fetchAll() })
watch(() => route.query.new, (value) => {
  if (value === '1') {
    formOpen.value = true
    router.replace({ path: '/dashboard' })
  }
}, { immediate: true })

const stats = computed(() => {
  const apps = store.applications
  return {
    total: apps.length,
    inProgress: apps.filter((a) => !['offer', 'rejected', 'withdrawn'].includes(a.current_stage)).length,
    offers: apps.filter((a) => a.current_stage === 'offer').length,
    upcoming: store.schedules.filter((s) => !s.done && s.sched_date >= today && s.sched_date <= sevenDays).length,
  }
})

const statCards = computed(() => [
  { label: '投递总数', value: stats.value.total, note: '累计投递记录', icon: Tickets, tone: 'green' },
  { label: '进行中的流程', value: stats.value.inProgress, note: '仍在推进', icon: DataLine, tone: 'mint' },
  { label: '收到的 Offer', value: stats.value.offers, note: '阶段为 Offer', icon: SuccessFilled, tone: 'lavender' },
  { label: '未来 7 天安排', value: stats.value.upcoming, note: '待完成事项', icon: Bell, tone: 'sage' },
])

const stageCounts = computed(() => {
  const counts = {}
  store.applications.forEach((app) => { counts[app.current_stage] = (counts[app.current_stage] || 0) + 1 })
  return counts
})

const visibleStages = computed(() => STAGES.filter((stage) => stageCounts.value[stage.key]))
const maxStageCount = computed(() => Math.max(1, ...visibleStages.value.map((stage) => stageCounts.value[stage.key])))

const weeklyTrend = computed(() => {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7) - 7 * 7)
  return Array.from({ length: 8 }, (_, index) => {
    const from = new Date(start)
    from.setDate(start.getDate() + index * 7)
    const to = new Date(from)
    to.setDate(from.getDate() + 7)
    const fromKey = dateKey(from)
    const toKey = dateKey(to)
    return {
      label: `${from.getMonth() + 1}/${from.getDate()}`,
      count: store.applications.filter((app) => app.apply_date >= fromKey && app.apply_date < toKey).length,
    }
  })
})

const chartMax = computed(() => Math.max(1, ...weeklyTrend.value.map((item) => item.count)))
const chartPoints = computed(() => weeklyTrend.value.map((item, index) => ({
  x: 25 + index * 77,
  y: 145 - (item.count / chartMax.value) * 112,
  ...item,
})))
const chartLine = computed(() => chartPoints.value.map((p) => `${p.x},${p.y}`).join(' '))
const chartArea = computed(() => `25,145 ${chartLine.value} 564,145`)

const recentApps = computed(() => [...store.applications]
  .sort((a, b) => (b.apply_date || '').localeCompare(a.apply_date || ''))
  .slice(0, 6))

const upcomingSchedules = computed(() => [...store.schedules]
  .filter((schedule) => !schedule.done && schedule.sched_date >= today)
  .sort((a, b) => `${a.sched_date} ${a.sched_time || ''}`.localeCompare(`${b.sched_date} ${b.sched_time || ''}`))
  .slice(0, 5))

function nextSchedule(appId) {
  return store.schedules
    .filter((schedule) => schedule.application_id === appId && !schedule.done && schedule.sched_date >= today)
    .sort((a, b) => `${a.sched_date} ${a.sched_time || ''}`.localeCompare(`${b.sched_date} ${b.sched_time || ''}`))[0]
}

function shortDate(value) { return value ? value.slice(5).replace('-', '/') : '—' }
function typeColor(type) { return TYPE_COLORS[type] || '#6f8274' }
</script>

<template>
  <div class="content-wrapper dashboard">
    <div class="page-head">
      <div><span class="eyebrow">YOUR WORKSPACE</span><h1 class="qz-page-title">总览</h1><p>集中查看投递进展与接下来的安排。</p></div>
      <el-button type="primary" :icon="Plus" @click="formOpen = true">添加投递</el-button>
    </div>

    <div class="stat-grid">
      <div v-for="card in statCards" :key="card.label" class="qz-card stat-card">
        <div class="stat-icon" :class="card.tone"><el-icon :size="21"><component :is="card.icon" /></el-icon></div>
        <div class="stat-text"><div class="stat-label">{{ card.label }}</div><div class="stat-value">{{ card.value }}</div><div class="stat-note">{{ card.note }}</div></div>
      </div>
    </div>

    <div class="dashboard-columns">
      <div class="primary-column">
        <div class="visual-grid">
          <section class="qz-card trend-card">
            <div class="section-head"><div><h2>投递趋势</h2><p>近 8 周 · 按投递日期统计</p></div><span class="soft-pill">{{ stats.total }} 条记录</span></div>
            <div class="trend-plot" role="img" :aria-label="`近八周投递数量：${weeklyTrend.map((week) => week.count).join('、')}`">
              <div class="y-labels"><span>{{ chartMax }}</span><span>{{ Math.round(chartMax / 2) }}</span><span>0</span></div>
              <svg viewBox="0 0 590 170" preserveAspectRatio="none" aria-hidden="true">
                <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#55bea9" stop-opacity=".22"/><stop offset="1" stop-color="#55bea9" stop-opacity="0"/></linearGradient></defs>
                <path d="M 25 33 H 564 M 25 89 H 564 M 25 145 H 564" stroke="#e5f0ec" stroke-dasharray="3 4" fill="none" />
                <polygon :points="chartArea" fill="url(#trendFill)" />
                <polyline :points="chartLine" fill="none" stroke="#28847c" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
                <circle v-for="point in chartPoints" :key="point.x" :cx="point.x" :cy="point.y" r="4" fill="#28847c" stroke="white" stroke-width="2" />
              </svg>
              <div class="x-labels"><span v-for="week in weeklyTrend" :key="week.label">{{ week.label }}</span></div>
            </div>
          </section>

          <section class="qz-card stage-card">
            <div class="section-head"><div><h2>阶段分布</h2><p>当前所有投递</p></div><router-link to="/statistics" class="text-link">查看分析 <ArrowRight class="inline-arrow" /></router-link></div>
            <div v-if="visibleStages.length" class="stage-bars">
              <div v-for="stage in visibleStages" :key="stage.key" class="stage-row">
                <div class="stage-meta"><span>{{ stage.label }}</span><strong>{{ stageCounts[stage.key] }}</strong></div>
                <div class="bar-track"><div class="bar-fill" :style="{ width: `${(stageCounts[stage.key] / maxStageCount) * 100}%`, background: stage.color }" /></div>
              </div>
            </div>
            <div v-else class="empty-panel">添加投递后，这里会显示阶段分布。</div>
          </section>
        </div>

        <section class="qz-card records-card">
          <div class="section-head"><div><h2>最近投递</h2><p>最新的求职进展</p></div><router-link to="/applications" class="text-link">查看全部 <ArrowRight class="inline-arrow" /></router-link></div>
          <div v-if="recentApps.length" class="table-scroll">
            <table class="records-table"><thead><tr><th>公司 / 岗位</th><th>投递日期</th><th>当前阶段</th><th>下一步安排</th></tr></thead>
              <tbody><tr v-for="app in recentApps" :key="app.id"><td><strong>{{ app.company_name }}</strong><small>{{ app.position }}</small></td><td>{{ shortDate(app.apply_date) }}</td><td><StageBadge :stage-key="app.current_stage" /></td><td><span v-if="nextSchedule(app.id)">{{ shortDate(nextSchedule(app.id).sched_date) }} · {{ nextSchedule(app.id).type }}</span><span v-else class="muted">暂无安排</span></td></tr></tbody>
            </table>
          </div>
          <div v-else class="empty-panel">还没有投递记录。点击右上角「添加投递」开始。</div>
        </section>
      </div>

      <aside class="secondary-column">
        <section class="qz-card activity-card">
          <div class="section-head"><div><h2>近期安排</h2><p>即将到来的待办事项</p></div><Calendar class="section-icon" /></div>
          <div v-if="upcomingSchedules.length" class="activity-list">
            <div v-for="schedule in upcomingSchedules" :key="schedule.id" class="activity-item">
              <span class="activity-dot" :style="{ background: typeColor(schedule.type) }" />
              <div><strong>{{ schedule.title }}</strong><p>{{ shortDate(schedule.sched_date) }} · {{ schedule.sched_time || '全天' }}</p><span class="activity-type" :style="{ color: typeColor(schedule.type) }">{{ schedule.type }}</span></div>
            </div>
          </div>
          <div v-else class="empty-panel">近期暂无待办安排。</div>
          <router-link to="/schedules" class="activity-more">查看所有安排 <ArrowRight class="inline-arrow" /></router-link>
        </section>

        <section class="insight-card"><div class="insight-head"><DataLine /><span>进展一览</span></div><strong>{{ stats.inProgress }} 个流程正在推进</strong><p>保持跟进，把下一次安排放进日程。</p><router-link to="/applications">管理投递 <ArrowRight class="inline-arrow" /></router-link></section>
      </aside>
    </div>

    <ApplicationForm v-model="formOpen" @saved="store.fetchAll()" />
  </div>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 18px; }
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-bottom: 1px; }
.eyebrow { color: #75a79e; font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.page-head h1 { margin: 3px 0 2px; }
.page-head p, .section-head p { margin: 0; color: #667085; font-size: 12px; }
.page-head .el-button { height: 37px; padding: 0 15px; }
.stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 13px; }
.stat-card { min-height: 118px; display: flex; align-items: flex-start; gap: 14px; padding: 20px 17px; }
.stat-icon { width: 42px; height: 42px; flex: none; display: grid; place-items: center; border-radius: 50%; }
.stat-icon.green { background: var(--button-gradient); color: #214a4d; }
.stat-icon.mint { background: #e2f8f4; color: #287b75; }
.stat-icon.lavender { background: #eceafa; color: #6054a1; }
.stat-icon.sage { background: #edf8e2; color: #587b4c; }
.stat-text { min-width: 0; }
.stat-label { color: #51616b; font-size: 12px; font-weight: 600; }
.stat-value { margin-top: 2px; color: #111827; font-size: 29px; line-height: 1.2; font-weight: 750; letter-spacing: -.04em; }
.stat-note { margin-top: 5px; color: #97a5aa; font-size: 11px; }
.dashboard-columns { display: grid; grid-template-columns: minmax(0, 2.3fr) minmax(245px, .85fr); align-items: start; gap: 14px; }
.primary-column, .secondary-column { min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.visual-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 14px; }
.trend-card, .stage-card { min-height: 260px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 19px; }
.section-head h2 { margin: 0 0 3px; color: #172033; font-size: 14px; font-weight: 750; }
.soft-pill { padding: 5px 8px; border-radius: 20px; color: #277b75; background: #e9f9f2; white-space: nowrap; font-size: 10px; font-weight: 700; }
.text-link { display: inline-flex; align-items: center; gap: 4px; color: #277b75; text-decoration: none; white-space: nowrap; font-size: 11px; font-weight: 700; }
.text-link:hover, .activity-more:hover, .insight-card a:hover { text-decoration: underline; }
.inline-arrow { width: 12px; height: 12px; }
.trend-plot { position: relative; height: 174px; padding: 0 0 22px 17px; }
.trend-plot svg { width: 100%; height: 150px; overflow: visible; }
.y-labels { position: absolute; top: 0; bottom: 27px; left: 0; display: flex; flex-direction: column; justify-content: space-between; color: #9aa69e; font-size: 9px; }
.x-labels { display: flex; justify-content: space-between; margin: 0 4px 0 6px; color: #9aa69e; font-size: 9px; }
.stage-bars { display: flex; flex-direction: column; gap: 13px; }
.stage-meta { display: flex; justify-content: space-between; margin-bottom: 5px; color: #586975; font-size: 11px; }
.stage-meta strong { color: #344054; }
.bar-track { height: 7px; overflow: hidden; background: #ecf3f0; border-radius: 10px; }
.bar-fill { height: 100%; border-radius: inherit; min-width: 5px; }
.records-card { padding-bottom: 7px; }
.records-card .section-head { margin-bottom: 15px; }
.table-scroll { overflow-x: auto; }
.records-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 11px; }
.records-table th { padding: 10px 8px; background: #f7fcfa; color: #86939c; font-size: 10px; font-weight: 700; white-space: nowrap; }
.records-table td { padding: 10px 8px; border-bottom: 1px solid #eaf2ef; color: #51616b; white-space: nowrap; }
.records-table tr:last-child td { border-bottom: 0; }
.records-table td strong { display: block; max-width: 220px; overflow: hidden; text-overflow: ellipsis; color: #273346; font-weight: 700; }
.records-table td small { display: block; max-width: 220px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; color: #89978e; }
.muted { color: #a3aea6; }
.section-icon { width: 17px; color: #758e7b; }
.activity-card { padding-bottom: 12px; }
.activity-list { border-top: 1px solid #eaf2ef; }
.activity-item { display: flex; gap: 10px; padding: 15px 0; border-bottom: 1px solid #eaf2ef; }
.activity-dot { width: 7px; height: 7px; flex: none; margin-top: 5px; border-radius: 50%; }
.activity-item strong { display: block; color: #273346; font-size: 11px; line-height: 1.5; font-weight: 650; }
.activity-item p { margin: 5px 0 3px; color: #96a39a; font-size: 10px; }
.activity-type { font-size: 10px; font-weight: 700; }
.activity-more { display: flex; align-items: center; justify-content: center; gap: 7px; margin-top: 12px; padding: 9px 10px; border: 1px solid #dcece7; border-radius: 8px; color: #277b75; text-decoration: none; font-size: 11px; font-weight: 700; }
.insight-card { padding: 17px; border: 1px solid #d9efe7; border-radius: 13px; background: linear-gradient(115deg, #e1faf5, #f8fef0 90%); }
.insight-head { display: flex; align-items: center; gap: 7px; margin-bottom: 14px; color: #287b75; font-size: 11px; font-weight: 750; }
.insight-head svg { width: 15px; }
.insight-card strong { display: block; color: #1b3440; font-size: 14px; }
.insight-card p { margin: 7px 0 17px; color: #667b80; font-size: 11px; line-height: 1.5; }
.insight-card a { display: flex; align-items: center; gap: 5px; color: #277b75; font-size: 11px; font-weight: 700; text-decoration: none; }
.empty-panel { display: grid; place-items: center; min-height: 120px; color: #9aa79d; text-align: center; font-size: 12px; }

@media (max-width: 1150px) { .dashboard-columns { grid-template-columns: minmax(0, 1fr); } .secondary-column { display: grid; grid-template-columns: 1.4fr 1fr; } }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .visual-grid { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .page-head { align-items: center; } .page-head p { max-width: 220px; line-height: 1.45; } .stat-grid { gap: 9px; } .stat-card { min-height: 107px; gap: 9px; padding: 14px 11px; } .stat-icon { width: 34px; height: 34px; } .stat-value { font-size: 25px; } .stat-note { font-size: 10px; } .secondary-column { display: flex; } .records-table { min-width: 550px; } }
</style>
