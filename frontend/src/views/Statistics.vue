<script setup>
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { STAGES } from '@/constants/stages'
import { useDataStore } from '@/stores/data'

const store = useDataStore()
const trendRef = ref()
const stageRef = ref()
const companyRef = ref()

let charts = []
const companyColors = [
  '#2f8f83', '#6d5ce7', '#e27b56', '#4d83c4', '#d6a43b',
  '#4fa66f', '#b45f91', '#68778f', '#26a6a1', '#9a6ac8',
]

onMounted(async () => {
  if (!store.loaded) await store.fetchAll()
  await new Promise((r) => setTimeout(r, 50)) // 等待 DOM 渲染
  renderCharts()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  charts.forEach((c) => c.dispose())
})

function resizeCharts() {
  charts.forEach((c) => c.resize())
}

function fmtMonth(d) {
  return d.slice(0, 7) // YYYY-MM
}

const trendData = computed(() => {
  const map = {}
  store.applications.forEach((a) => {
    const m = fmtMonth(a.apply_date)
    map[m] = (map[m] || 0) + 1
  })
  return Object.entries(map).sort(([a], [b]) => a.localeCompare(b))
})

const stageData = computed(() => {
  const map = {}
  store.applications.forEach((a) => {
    map[a.current_stage] = (map[a.current_stage] || 0) + 1
  })
  return STAGES.filter((s) => map[s.key]).map((s) => ({
    name: s.label,
    value: map[s.key],
    itemStyle: { color: s.color },
  }))
})

const companyData = computed(() => {
  const map = {}
  store.applications.forEach((a) => {
    map[a.company_name] = (map[a.company_name] || 0) + 1
  })
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
})

function renderCharts() {
  // 1. 投递趋势折线图
  const trend = echarts.init(trendRef.value)
  trend.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: trendData.value.map(([m]) => m) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '投递数量',
        type: 'line',
        smooth: true,
        data: trendData.value.map(([, c]) => c),
        areaStyle: { color: 'rgba(85,190,169,0.18)' },
        lineStyle: { width: 3, color: '#28847c' },
        itemStyle: { color: '#28847c' },
      },
    ],
  })

  // 2. 阶段分布饼图
  const stage = echarts.init(stageRef.value)
  stage.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        center: ['50%', '44%'],
        data: stageData.value,
        label: { formatter: '{b}: {c}' },
        labelLine: { length: 12 },
      },
    ],
  })

  // 3. 公司投递数柱状图
  const company = echarts.init(companyRef.value)
  company.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: companyData.value.map(([name]) => name),
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: companyData.value.map(([, count], index) => ({
          value: count,
          itemStyle: { color: companyColors[index], borderRadius: [6, 6, 0, 0] },
        })),
        barMaxWidth: 34,
      },
    ],
  })

  charts = [trend, stage, company]
}
</script>

<template>
  <div class="content-wrapper">
    <h2 class="qz-page-title" style="margin-bottom: 12px">统计分析</h2>

    <div class="chart-grid">
      <div class="qz-card chart-card wide">
        <div class="chart-title">投递趋势</div>
        <div ref="trendRef" class="chart-box"></div>
      </div>
      <div class="qz-card chart-card">
        <div class="chart-title">阶段分布</div>
        <div ref="stageRef" class="chart-box"></div>
      </div>
      <div class="qz-card chart-card wide">
        <div class="chart-title">公司投递 TOP 10</div>
        <div ref="companyRef" class="chart-box"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 14px;
}

.chart-card {
  min-width: 0;
}

.chart-title {
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 8px;
}

.chart-box {
  height: 320px;
}

@media (max-width: 768px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }

  .chart-box {
    height: 260px;
  }
}
</style>
