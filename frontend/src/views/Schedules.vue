<script setup>
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { scheduleApi } from '@/api/resources'
import { SCHEDULE_TYPES, TYPE_COLORS } from '@/constants/stages'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const store = useDataStore()

const formOpen = ref(false)
const editing = ref(null)
const formRef = ref()
const today = new Date().toISOString().slice(0, 10)

const form = reactive({
  application_id: null,
  title: '',
  type: '笔试',
  sched_date: '',
  sched_time: '',
  link: '',
  location: '',
  done: false,
})

const rules = {
  title: [{ required: true, message: '请输入安排标题', trigger: 'blur' }],
  sched_date: [{ required: true, message: '选择日期', trigger: 'change' }],
}

onMounted(() => {
  if (!store.loaded) store.fetchAll()
})

const sorted = computed(() =>
  [...store.schedules].sort(
    (a, b) => `${a.sched_date} ${a.sched_time}`.localeCompare(`${b.sched_date} ${b.sched_time}`),
  ),
)

// 关联投递选项
const appOptions = computed(() =>
  store.applications.map((a) => ({
    label: `${a.company_name} - ${a.position}`,
    value: a.id,
  })),
)

function openCreate() {
  editing.value = null
  Object.assign(form, {
    application_id: null,
    title: '',
    type: '笔试',
    sched_date: today,
    sched_time: '',
    link: '',
    location: '',
    done: false,
  })
  formOpen.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    application_id: row.application_id,
    title: row.title,
    type: row.type,
    sched_date: row.sched_date,
    sched_time: row.sched_time,
    link: row.link,
    location: row.location,
    done: row.done,
  })
  formOpen.value = true
}

async function submit() {
  await formRef.value.validate()
  if (editing.value) {
    await scheduleApi.update(editing.value.id, { ...form })
    ElMessage.success('已保存')
  } else {
    await scheduleApi.create( { ...form })
    ElMessage.success('已添加安排')
  }
  formOpen.value = false
  await store.fetchAll()
}

async function toggleDone(row) {
  await scheduleApi.update(row.id, {
    ...row,
    done: !row.done,
    application_id: row.application_id,
  })
  await store.fetchAll()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除「${row.title}」吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await scheduleApi.remove(row.id)
  ElMessage.success('已删除')
  await store.fetchAll()
}

function dateLabel(d) {
  if (d === today) return '今天'
  const diff = Math.round((new Date(`${d}T00:00:00`) - new Date(`${today}T00:00:00`)) / 86400e3)
  if (diff === 1) return '明天'
  const date = new Date(`${d}T00:00:00`)
  return `${d.slice(5)} 周${'日一二三四五六'[date.getDay()]}`
}

function typeColor(type) {
  return TYPE_COLORS[type] || '#909399'
}

function appName(id) {
  const app = store.applications.find((a) => a.id === id)
  return app ? `${app.company_name} · ${app.position}` : ''
}
</script>

<template>
  <div class="content-wrapper">
    <div class="header-row">
      <h2 class="qz-page-title">未来安排</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加安排</el-button>
    </div>

    <div class="qz-card">
      <div v-if="sorted.length" class="sched-list">
        <div
          v-for="row in sorted"
          :key="row.id"
          class="sched-item"
          :class="{ done: row.done, today: row.sched_date === today }"
        >
          <el-checkbox :model-value="row.done" @change="toggleDone(row)" />
          <div class="sched-date">
            <div class="sd-date">{{ dateLabel(row.sched_date) }}</div>
            <div class="sd-time">{{ row.sched_time || '全天' }}</div>
          </div>
          <div class="sched-body">
            <div class="sched-title">
              {{ row.title }}
              <span
                class="stage-badge sched-type"
                :style="{ color: typeColor(row.type), background: typeColor(row.type) + '1a' }"
              >
                {{ row.type }}
              </span>
            </div>
            <div v-if="row.location || row.link || appName(row.application_id)" class="sched-detail">
              {{ appName(row.application_id) }}
              <template v-if="row.location"> · {{ row.location }}</template>
              <a v-if="row.link" :href="row.link" target="_blank" class="sched-link">🔗 链接</a>
            </div>
          </div>
          <div class="sched-ops">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="还没有安排。添加笔试、面试时间规划，不错过任何一场。" :image-size="80" />
    </div>

    <el-dialog
      v-model="formOpen"
      :title="editing ? '编辑安排' : '添加安排'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="如：腾讯 - 产品经理 一面" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option v-for="t in SCHEDULE_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期/时间">
          <div class="dt-row">
            <el-date-picker v-model="form.sched_date" type="date" value-format="YYYY-MM-DD" style="flex: 1" />
            <el-input v-model="form.sched_time" placeholder="14:00" style="width: 110px" />
          </div>
        </el-form-item>
        <el-form-item label="关联投递">
          <el-select v-model="form.application_id" clearable filterable placeholder="关联某条投递（可空）" style="width: 100%">
            <el-option v-for="o in appOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="选填" />
        </el-form-item>
        <el-form-item label="链接">
          <el-input v-model="form.link" placeholder="会议链接 / 笔试链接，选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formOpen = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sched-list {
  display: flex;
  flex-direction: column;
}

.sched-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 4px;
  border-bottom: 1px solid #f3f4f6;
}

.sched-item.today .sd-date {
  color: #277b75;
}

.sched-item.done .sched-title {
  text-decoration: line-through;
  color: #b0b7c3;
}

.sched-date {
  min-width: 88px;
  text-align: center;
}

.sd-date {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.sd-time {
  font-size: 12px;
  color: #9ca3af;
}

.sched-body {
  flex: 1;
}

.sched-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sched-type {
  font-weight: 400;
}

.sched-detail {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  gap: 8px;
  align-items: center;
}

.sched-link {
  text-decoration: none;
}

.sched-ops {
  white-space: nowrap;
}

.dt-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>
