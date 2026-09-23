<script setup>
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { applicationApi } from '@/api/resources'
import ApplicationForm from '@/components/ApplicationForm.vue'
import StageBadge from '@/components/StageBadge.vue'
import { STAGES, TYPE_COLORS } from '@/constants/stages'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const store = useDataStore()

const keyword = ref('')
const stageFilter = ref('')
const companyFilter = ref('')
const page = ref(1)
const pageSize = 10

const formOpen = ref(false)
const editing = ref(null)
const today = new Date().toISOString().slice(0, 10)

const isMobile = window.matchMedia('(max-width: 768px)')

onMounted(() => {
  if (!store.loaded) store.fetchAll()
})

// 筛选 + 分页
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return store.applications.filter((a) => {
    if (stageFilter.value && a.current_stage !== stageFilter.value) return false
    if (companyFilter.value && a.company_name !== companyFilter.value) return false
    if (kw && !(a.company_name.toLowerCase().includes(kw) || a.position.toLowerCase().includes(kw)))
      return false
    return true
  })
})

const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize),
)

// 公司筛选选项：公司库 + 记录中出现过的公司
const companyOptions = computed(() => {
  const names = new Set(store.companies.map((c) => c.name))
  store.applications.forEach((a) => names.add(a.company_name))
  return [...names].sort()
})

function nextSchedule(appId) {
  return store.schedules
    .filter((s) => s.application_id === appId && !s.done && s.sched_date >= today)
    .sort(
      (a, b) =>
        `${a.sched_date} ${a.sched_time}`.localeCompare(`${b.sched_date} ${b.sched_time}`),
    )[0]
}

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(row) {
  editing.value = row
  formOpen.value = true
}

async function changeStage(row, stage) {
  try {
    await applicationApi.changeStage(row.id, stage)
    // 找回最新的值（PATCH 返回的正是行数据）
    await store.fetchAll()
    ElMessage.success('阶段已更新')
  } catch (e) {
    ElMessage.error(formatApiError(e))
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除「${row.company_name} - ${row.position}」的投递记录吗？`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await applicationApi.remove(row.id)
  ElMessage.success('已删除')
  await store.fetchAll()
}
</script>

<template>
  <div class="content-wrapper">
    <div class="header-row">
      <h2 class="qz-page-title">投递记录</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加投递</el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="qz-card filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索公司或岗位"
        :prefix-icon="Search"
        clearable
        class="filter-kw"
        @input="page = 1"
      />
      <el-select v-model="companyFilter" placeholder="全部公司" clearable class="filter-sel" @change="page = 1">
        <el-option v-for="name in companyOptions" :key="name" :label="name" :value="name" />
      </el-select>
      <el-select v-model="stageFilter" placeholder="全部阶段" clearable class="filter-sel" @change="page = 1">
        <el-option v-for="s in STAGES" :key="s.key" :label="s.label" :value="s.key" />
      </el-select>
      <span class="count-hint">共 {{ filtered.length }} 条</span>
    </div>

    <!-- 桌面端表格 -->
    <div v-if="!isMobile.matches" class="qz-card">
      <el-table :data="paged" size="default" style="width: 100%">
        <el-table-column prop="company_name" label="公司" min-width="110" />
        <el-table-column prop="position" label="岗位" min-width="130" />
        <el-table-column prop="apply_date" label="投递日期" width="105" />
        <el-table-column label="当前阶段" width="130">
          <template #default="{ row }">
            <el-select
              :model-value="row.current_stage"
              size="small"
              class="stage-select"
              @change="(v) => changeStage(row, v)"
            >
              <el-option v-for="s in STAGES" :key="s.key" :label="s.label" :value="s.key" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="下一步安排" min-width="150">
          <template #default="{ row }">
            <template v-if="nextSchedule(row.id)">
              {{ nextSchedule(row.id).sched_date }}
              <span
                class="stage-badge"
                :style="{
                  color: TYPE_COLORS[nextSchedule(row.id).type] || '#909399',
                  background: (TYPE_COLORS[nextSchedule(row.id).type] || '#909399') + '1a',
                }"
              >
                {{ nextSchedule(row.id).type }}
              </span>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="filtered.length > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="filtered.length"
        layout="prev, pager, next"
        class="pager"
        background
      />
    </div>

    <!-- 移动端卡片列表 -->
    <div v-else class="card-list">
      <div v-for="row in paged" :key="row.id" class="qz-card app-card">
        <div class="app-card-top">
          <div>
            <div class="app-card-company">{{ row.company_name }}</div>
            <div class="app-card-position">{{ row.position }} · {{ row.apply_date }}</div>
          </div>
          <div class="app-card-stage">
            <el-select
              :model-value="row.current_stage"
              size="small"
              class="stage-select"
              @change="(v) => changeStage(row, v)"
            >
              <el-option v-for="s in STAGES" :key="s.key" :label="s.label" :value="s.key" />
            </el-select>
          </div>
        </div>
        <div class="app-card-actions">
          <span class="muted">{{ row.channel || '未填渠道' }} · {{ row.notes || '无备注' }}</span>
          <div>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
      </div>
      <el-pagination
        v-if="filtered.length > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="filtered.length"
        layout="prev, pager, next"
        class="pager"
        background
      />
      <el-empty v-if="!paged.length" description="没有匹配的记录" :image-size="72" />
    </div>

    <ApplicationForm v-model="formOpen" :record="editing" @saved="store.fetchAll()" />
  </div>
</template>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filter-kw {
  width: 240px;
}

.filter-sel {
  width: 150px;
}

.count-hint {
  font-size: 13px;
  color: #9ca3af;
}

.pager {
  margin-top: 14px;
  justify-content: center;
}

.stage-select {
  width: 108px;
}

.muted {
  color: #c0c4cc;
}

/* 移动端卡片 */
.card-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.app-card-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.app-card-company {
  font-weight: 700;
  color: #1f2937;
}

.app-card-position {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.app-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .filter-kw {
    width: 100%;
  }

  .filter-sel {
    flex: 1;
    min-width: 120px;
  }
}
</style>
