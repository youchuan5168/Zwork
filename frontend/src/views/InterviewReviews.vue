<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { careerApi } from '@/api/resources'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const store = useDataStore()
const loading = ref(false)
const busy = ref(false)
const reviews = ref([])
const editingId = ref(null)

function today() {
  const value = new Date()
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}
function emptyForm() {
  return { application_id: null, schedule_id: null, occurred_on: today(), questions: [] }
}
const form = ref(emptyForm())

function report(error) { ElMessage.error(formatApiError(error)) }
async function load() {
  loading.value = true
  try {
    if (!store.loaded) await store.fetchAll()
    reviews.value = await careerApi.reviews()
  } catch (error) { report(error) }
  finally { loading.value = false }
}
function reset() {
  editingId.value = null
  form.value = emptyForm()
}
function edit(item) {
  editingId.value = item.id
  const keys = ['application_id', 'schedule_id', 'occurred_on']
  const base = Object.fromEntries(keys.map(key => [key, item[key]]))
  form.value = { ...base, questions: (item.questions || []).map(q => ({ question: q.question, answer: q.answer, notes: q.notes })) }
  document.querySelector('.content')?.scrollTo({ top: 0, behavior: 'smooth' })
}
function addQuestion() {
  if (form.value.questions.length >= 50) return ElMessage.warning('每条复盘最多 50 道题')
  form.value.questions.push({ question: '', answer: '', notes: '' })
}
function removeQuestion(index) { form.value.questions.splice(index, 1) }
async function save() {
  const questions = form.value.questions
    .map(q => ({ question: q.question.trim(), answer: (q.answer || '').trim(), notes: (q.notes || '').trim() }))
    .filter(q => q.question || q.answer || q.notes)
  if (questions.some(q => !q.question)) return ElMessage.warning('请填写每道题的题干，或删除空行')
  busy.value = true
  try {
    const payload = { ...form.value, questions }
    if (editingId.value) await careerApi.updateReview(editingId.value, payload)
    else await careerApi.createReview(payload)
    reset()
    await load()
    ElMessage.success('复盘已保存')
  } catch (error) { report(error) }
  finally { busy.value = false }
}
async function remove(item) {
  try {
    await ElMessageBox.confirm('删除这条复盘？', '删除复盘', { type: 'warning' })
    await careerApi.deleteReview(item.id)
    if (editingId.value === item.id) reset()
    await load()
  } catch (error) { if (error !== 'cancel' && error !== 'close') report(error) }
}

const questionSets = computed(() => {
  const groups = new Map()
  for (const review of reviews.value) {
    for (const question of review.questions || []) {
      const key = review.application_id ?? 0
      if (!groups.has(key)) {
        const application = review.application_id ? store.applications.find(item => item.id === review.application_id) : null
        groups.set(key, {
          application_id: review.application_id || null,
          label: application ? `${application.company_name} · ${application.position}` : (review.source_label || '独立题目'),
          items: [],
        })
      }
      groups.get(key).items.push({ ...question, occurred_on: review.occurred_on })
    }
  }
  return [...groups.values()].sort((a, b) => b.items.length - a.items.length || (b.application_id || 0) - (a.application_id || 0))
})
const questionTotal = computed(() => questionSets.value.reduce((sum, set) => sum + set.items.length, 0))

onMounted(load)
</script>

<template>
  <div class="reviews-page content-wrapper" v-loading="loading">
    <header class="page-head">
      <div><span class="eyebrow">工具 / 面试复盘</span><h1 class="qz-page-title">面试复盘</h1><p>记录真实面试问题、回答和复盘备注，沉淀为可复用的岗位题库。</p></div>
      <el-button @click="load">刷新数据</el-button>
    </header>

    <section class="qz-card form-card">
      <div class="section-head"><div><h2>{{ editingId ? '编辑复盘' : '记录一次面试' }}</h2><p>关联投递或日程后，Zwork 助手可以在后续面试准备中读取这些记录。</p></div></div>
      <el-form label-position="top">
        <div class="form-row">
          <el-form-item label="日期"><el-date-picker v-model="form.occurred_on" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="关联日程"><el-select v-model="form.schedule_id" clearable filterable placeholder="可选" @change="form.application_id = null"><el-option v-for="item in store.schedules" :key="item.id" :value="item.id" :label="`${item.sched_date} · ${item.title} (#${item.id})`" /></el-select></el-form-item>
          <el-form-item label="关联投递"><el-select v-model="form.application_id" clearable filterable placeholder="可选"><el-option v-for="item in store.applications.filter(app => !form.schedule_id || store.schedules.find(schedule => schedule.id === form.schedule_id)?.application_id === app.id)" :key="item.id" :value="item.id" :label="`${item.company_name} · ${item.position} (#${item.id})`" /></el-select></el-form-item>
        </div>
        <el-form-item label="本场面试问题">
          <div class="question-list">
            <p class="muted">逐题记录被问到的问题、你的回答和复盘备注。</p>
            <div v-for="(question, index) in form.questions" :key="index" class="question-row">
              <el-input v-model="question.question" maxlength="500" placeholder="被问到的问题（必填）" />
              <el-input v-model="question.answer" type="textarea" :rows="2" maxlength="2000" placeholder="我的回答（可选）" />
              <el-input v-model="question.notes" maxlength="2000" placeholder="备注 / 反思（可选）" />
              <el-button link type="danger" @click="removeQuestion(index)">删除</el-button>
            </div>
            <el-button size="small" @click="addQuestion">添加问题</el-button>
          </div>
        </el-form-item>
        <el-button type="primary" :loading="busy" @click="save">保存复盘</el-button>
        <el-button v-if="editingId" @click="reset">取消编辑</el-button>
      </el-form>
    </section>

    <section class="qz-card">
      <div class="section-head"><div><h2>复盘记录</h2><p>共 {{ reviews.length }} 条，可随时继续补充。</p></div></div>
      <el-empty v-if="!reviews.length" description="暂无复盘" :image-size="64" />
      <article v-for="item in reviews" :key="item.id" class="record">
        <div class="record-main"><h3>{{ item.occurred_on }} · {{ item.source_label || '独立复盘' }}</h3><small>复盘 #{{ item.id }}<span v-if="item.application_id"> · 投递 #{{ item.application_id }}</span><span v-if="item.schedule_id"> · 日程 #{{ item.schedule_id }}</span></small><ul v-if="item.questions?.length"><li v-for="question in item.questions" :key="question.id"><b>{{ question.question }}</b><span v-if="question.answer">回答：{{ question.answer }}</span><span v-if="question.notes">备注：{{ question.notes }}</span></li></ul><p v-else class="muted">暂未记录面试问题</p></div>
        <div class="record-actions"><el-button link @click="edit(item)">编辑</el-button><el-button link type="danger" @click="remove(item)">删除</el-button></div>
      </article>
    </section>

    <section class="qz-card">
      <div class="section-head"><div><h2>岗位题目集</h2><p>{{ questionTotal }} 题 · {{ questionSets.length }} 组</p></div></div>
      <el-empty v-if="!questionSets.length" description="还没有题目，在复盘中记录面试被问的问题" :image-size="64" />
      <el-collapse v-else><el-collapse-item v-for="set in questionSets" :key="set.application_id ?? 'standalone'" :title="`${set.label} · ${set.items.length} 题`"><div v-for="question in set.items" :key="`${question.review_id}-${question.id}`" class="question-entry"><b>{{ question.question }}</b><small>{{ question.occurred_on }} · 复盘 #{{ question.review_id }}</small><p v-if="question.answer">回答：{{ question.answer }}</p><p v-if="question.notes">备注：{{ question.notes }}</p></div></el-collapse-item></el-collapse>
    </section>
  </div>
</template>

<style scoped>
.reviews-page { max-width: 1180px; }
.page-head,.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-head { margin-bottom: 20px; }
.page-head p,.section-head p,.muted { margin: 6px 0 0; color: #7b8491; font-size: 12px; line-height: 1.65; }
.eyebrow { display: block; margin-bottom: 7px; color: #697586; font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.qz-card { margin-bottom: 16px; }
.section-head { margin-bottom: 18px; }
.section-head h2 { margin: 0; color: #1f2937; font-size: 17px; }
.form-card { max-width: 980px; }
.form-row { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; }
.question-list { width: 100%; display: flex; flex-direction: column; gap: 9px; }
.question-row { display: grid; grid-template-columns: minmax(0,1.3fr) minmax(0,1.3fr) minmax(0,1fr) auto; gap: 8px; align-items: start; padding: 12px; border: 1px solid #e6e8eb; border-radius: 10px; background: #fafbfc; }
.record { display: flex; gap: 16px; padding: 18px 0; border-top: 1px solid #eceef1; }
.record-main { flex: 1; min-width: 0; }
.record h3 { margin: 0; color: #1f2937; font-size: 15px; }
.record small,.question-entry small { display: block; margin-top: 5px; color: #8a94a3; font-size: 11px; }
.record p,.question-entry p { color: #475467; font-size: 13px; line-height: 1.7; }
.record ul { margin: 12px 0 0; padding-left: 20px; }
.record li { margin: 7px 0; color: #344054; font-size: 12px; }
.record li span { display: block; margin-top: 3px; color: #697586; }
.record-actions { flex: none; }
.question-entry { padding: 12px 0; border-top: 1px solid #eceef1; }
@media (max-width: 768px) { .form-row,.question-row { grid-template-columns: 1fr; } .record { flex-wrap: wrap; } }
</style>
