<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowUp, Refresh, Document, Calendar, EditPen, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { agentApi } from '@/api/resources'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'
import { STAGE_MAP } from '@/constants/stages'

const store = useDataStore()
const route = useRoute()
const router = useRouter()
const capabilities = ref(null)
const message = ref('')
const run = ref(null)
const recent = ref([])
const events = ref([])
const executing = ref(false)
const submitting = ref(false)
const requestKey = ref(null)
const thread = ref([])
const transcript = ref(null)
const composer = ref(null)
const selecting = ref(false)
const busy = computed(() => submitting.value || executing.value || selecting.value)
const canSend = computed(() => capabilities.value?.enabled && message.value.trim() && !active.value && !busy.value)
const suggestions = [
  { icon: Document, title: '查找投递进展', text: '查询腾讯的投递记录和当前阶段' },
  { icon: Calendar, title: '梳理面试安排', text: '查看本周的笔试和面试安排' },
  { icon: EditPen, title: '更新投递阶段', text: '将投递 #1 的阶段更新为面试' },
  { icon: DataAnalysis, title: '规划下一步', text: '结合我的每日简报和本周回顾，帮我规划下一步行动' },
]
const conversation = computed(() => thread.value.map(row => row.id === run.value?.id ? run.value : row))
function formatReply(text) {
  return String(text || '').split('\n').map((line) => {
    const segments = []
    const pattern = /\*\*(.+?)\*\*/g
    let start = 0
    let match
    while ((match = pattern.exec(line)) !== null) {
      if (match.index > start) segments.push({ text: line.slice(start, match.index), bold: false })
      segments.push({ text: match[1], bold: true })
      start = pattern.lastIndex
    }
    if (start < line.length) segments.push({ text: line.slice(start), bold: false })
    return segments.length ? segments : [{ text: '\u00a0', bold: false }]
  })
}
function newChat() {
  if (busy.value || active.value) return
  stopStream(); run.value = null; thread.value = []; events.value = []; message.value = ''
  if (route.query.run) router.replace({ name: 'agent' })
  nextTick(() => composer.value?.focus())
}
function useSuggestion(text) { message.value = text; nextTick(() => composer.value?.focus()) }
function onComposerKey(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (canSend.value) start() }
}
async function copyReply(text) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('回复已复制') }
  catch { ElMessage.warning('无法访问剪贴板，请手动复制') }
}
watch(() => [run.value?.status, run.value?.output, events.value.length, thread.value.length], async () => {
  await nextTick()
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight
})
let source = null
let alive = true
const terminal = new Set(['completed', 'failed', 'cancelled', 'budget_exhausted', 'expired'])
const active = computed(() => run.value && !terminal.has(run.value.status))
const statusNames = {
  queued: '等待执行', running: '执行中', waiting_approval: '等待审批',
  completed: '已完成', failed: '失败', cancelled: '已取消',
  budget_exhausted: '预算耗尽', expired: '已过期',
}
const eventNames = {
  run_created: '创建运行', run_started: '开始执行', model_started: '请求模型',
  model_completed: '模型返回', tool_requested: '请求工具', tool_completed: '查询完成',
  approval_required: '等待用户审批', approval_decided: '记录审批决策', tool_executed: '执行批准动作',
  run_completed: '任务完成', run_failed: '任务失败', run_cancelled: '取消运行', run_expired: '运行过期',
}
function current(generation) { return alive && store.authenticated && generation === store.authGeneration }
function stopStream() { source?.close(); source = null }
function stream(id) {
  stopStream()
  const generation = store.authGeneration
  const cursor = events.value.at(-1)?.sequence ?? -1
  const connection = agentApi.events(id, cursor)
  source = connection
  for (const kind of Object.keys(eventNames)) {
    connection.addEventListener(kind, (event) => {
      if (!current(generation) || run.value?.id !== id) return
      const sequence = Number(event.lastEventId)
      if (events.value.some((item) => item.sequence === sequence)) return
      events.value.push({ sequence, kind, payload: JSON.parse(event.data) })
    })
  }
  connection.addEventListener('auth_expired', () => {
    connection.close()
    if (!current(generation)) return
    window.dispatchEvent(new Event('auth-expired'))
  })
  connection.onerror = () => connection.close() // 断流不重放动作；可重新查看运行状态。
}
async function refreshRecent() {
  const generation = store.authGeneration
  const rows = await agentApi.list()
  if (current(generation)) {
    recent.value = rows
    window.dispatchEvent(new Event('agent-history-changed'))
  }
}
async function select(id, preserveThread = false) {
  if (busy.value) return
  const generation = store.authGeneration
  selecting.value = true
  try {
    const row = await agentApi.get(id)
    if (!current(generation)) return
    stopStream()
    run.value = row
    if (!preserveThread) thread.value = [row]
    events.value = []
    stream(id)
  } catch (error) { if (current(generation)) ElMessage.error(formatApiError(error)) }
  finally { if (current(generation)) selecting.value = false }
}
async function execute(id) {
  const generation = store.authGeneration
  executing.value = true
  stream(id)
  try {
    const row = await agentApi.execute(id)
    if (!current(generation)) return
    if (run.value?.id === id) run.value = row
    await refreshRecent()
    if (row.status === 'completed') await store.fetchAll()
  } catch (error) {
    if (!current(generation)) return
    ElMessage.error(formatApiError(error))
    // 网络失败不自动重试工具；先读取已持久化状态。
    try { const row = await agentApi.get(id); if (current(generation) && run.value?.id === id) run.value = row } catch { /* 已提示 */ }
  } finally {
    if (current(generation)) {
      executing.value = false
      if (run.value?.id === id) stopStream()
    }
  }
}
async function start() {
  if (!canSend.value) return
  const generation = store.authGeneration
  submitting.value = true
  requestKey.value ||= Array.from(crypto.getRandomValues(new Uint8Array(16)), (item) => item.toString(16).padStart(2, '0')).join('')
  try {
    const row = await agentApi.create({ request_key: requestKey.value, message: message.value, timezone: 'Asia/Shanghai' })
    if (!current(generation)) return
    requestKey.value = null
    if (run.value) thread.value = conversation.value.map(item => ({ ...item }))
    run.value = row
    thread.value.push(row)
    router.replace({ name: 'agent', query: { run: row.id } })
    message.value = ''
    events.value = []
    if (row.status === 'queued') await execute(row.id)
    else await refreshRecent()
  } catch (error) { if (current(generation)) ElMessage.error(formatApiError(error)) }
  finally { if (current(generation)) submitting.value = false }
}
async function decide(decision) {
  const generation = store.authGeneration
  const id = run.value.id
  submitting.value = true
  try {
    const row = await agentApi.decide(id, { approval_id: run.value.approval.approval_id, decision })
    if (!current(generation)) return
    run.value = row
    await execute(id)
  } catch (error) { if (current(generation)) ElMessage.error(formatApiError(error)) }
  finally { if (current(generation)) submitting.value = false }
}
async function cancel() {
  const generation = store.authGeneration
  const id = run.value.id
  try {
    const row = await agentApi.cancel(id)
    if (current(generation) && run.value?.id === id) run.value = row
    stopStream()
    await refreshRecent()
  } catch (error) { if (current(generation)) ElMessage.error(formatApiError(error)) }
}
watch(message, () => { requestKey.value = null })
watch(() => route.query.run, async (id) => {
  if (!id) {
    if (run.value && !active.value) newChat()
    return
  }
  if (id !== run.value?.id) await select(String(id))
})
watch(() => store.authGeneration, () => {
  stopStream(); run.value = null; recent.value = []; events.value = []; message.value = ''; thread.value = []; selecting.value = false
  requestKey.value = null; executing.value = false; submitting.value = false
})
onMounted(async () => {
  const generation = store.authGeneration
  try {
    const data = await agentApi.capabilities()
    if (!current(generation)) return
    capabilities.value = data
    if (data.enabled) {
      await refreshRecent()
      const requested = route.query.run
      const pending = recent.value.find((row) => !terminal.has(row.status))
      if (requested) await select(String(requested))
      else if (pending) {
        await select(pending.id)
        router.replace({ name: 'agent', query: { run: pending.id } })
      }
    }
  } catch (error) { if (current(generation)) ElMessage.error(formatApiError(error)) }
})
onBeforeUnmount(() => { alive = false; stopStream() })
</script>

<template>
  <section class="agent-workbench">
    <div class="workspace">
      <main class="chat-main"><div v-if="capabilities && !capabilities.enabled" class="notice">Zwork 助手尚未启用，请在服务端配置模型连接后使用。</div>
        <div ref="transcript" class="transcript" role="log" aria-label="与 Zwork 助手的对话" aria-live="polite">
          <div v-if="!conversation.length" class="welcome"><span class="hero-logo">✦</span><span class="eyebrow">让求职更有条理</span><h2>Hello，{{ store.username }}，接下来做什么？</h2><p>查进展、看安排、更新阶段。<br />把你的问题交给我，一起理清秋招的下一步。</p><div class="suggestions"><button v-for="item in suggestions" :key="item.title" @click="useSuggestion(item.text)"><el-icon><component :is="item.icon" /></el-icon><strong>{{ item.title }}</strong><span>{{ item.text }}</span><i>↗</i></button></div></div>
          <div v-else class="messages"><article v-for="row in conversation" :key="row.id" class="exchange"><div class="user-message"><div class="user-bubble">{{ row.message }}</div><span class="user-avatar">{{ store.username?.slice(0, 1)?.toUpperCase() || '我' }}</span></div><div class="assistant-message"><span class="assistant-avatar">✦</span><div class="assistant-content"><div class="assistant-heading">Zwork 助手 <span class="status" :class="row.status">{{ statusNames[row.status] }}</span></div><div v-if="row.output" class="reply"><div v-for="(line, lineIndex) in formatReply(row.output)" :key="lineIndex" class="reply-line"><template v-for="(segment, segmentIndex) in line" :key="segmentIndex"><strong v-if="segment.bold">{{ segment.text }}</strong><span v-else>{{ segment.text }}</span></template></div></div><div v-else-if="['queued', 'running'].includes(row.status)" class="thinking"><span class="dots"><i /><i /><i /></span>{{ row.id === run?.id && events.length ? eventNames[events.at(-1).kind] : '正在分析你的请求' }}</div>
            <div v-if="row.status === 'waiting_approval' && row.approval" class="approval"><h3><el-icon><EditPen /></el-icon>确认阶段更新</h3><p>{{ row.approval.target.company_name }} · {{ row.approval.target.position }} · #{{ row.approval.target.application_id }}</p><div class="stage-change"><span>{{ STAGE_MAP[row.approval.target.stage]?.label || row.approval.target.stage }}</span> → <strong>{{ STAGE_MAP[row.approval.arguments.stage]?.label || row.approval.arguments.stage }}</strong></div><p class="muted">确认后将更新投递记录。有效至 {{ new Date(row.approval.expires_at).toLocaleString('zh-CN') }}</p><el-button type="primary" :disabled="busy" @click="decide('approve')">确认更新</el-button><el-button :disabled="busy" @click="decide('reject')">拒绝更新</el-button></div>
            <div v-if="row.error_code" class="notice">本次请求未完成（{{ row.error_code }}）。请检查最新状态后重新提问；不会自动重试写操作。</div><p v-else-if="!row.output && terminal.has(row.status)" class="muted">{{ row.status === 'cancelled' ? '你已停止本次请求。' : '本次运行已结束，未返回回复。' }}</p><div class="reply-actions"><button v-if="row.output" @click="copyReply(row.output)">复制回复</button><button v-if="row.id === run?.id" :disabled="busy" @click="select(row.id, true)"><el-icon><Refresh /></el-icon>刷新状态</button><button v-if="row.id === run?.id && row.status === 'queued'" :disabled="busy" @click="execute(row.id)">继续执行</button></div><details class="run-details"><summary>运行详情 <span>{{ row.tool_calls }} 次工具调用</span></summary><p>模型 {{ row.model }} · 模型步数 {{ row.steps }} · 输入 {{ row.usage?.input_tokens || 0 }} / 输出 {{ row.usage?.output_tokens || 0 }} Token<template v-if="row.estimated_cost_usd != null"> · ${{ row.estimated_cost_usd.toFixed(6) }}</template> · Prompt {{ row.prompt_version }}</p><ol v-if="row.id === run?.id && events.length"><li v-for="event in events" :key="event.sequence">{{ eventNames[event.kind] }}<details><summary>详情</summary><pre>{{ JSON.stringify(event.payload, null, 2) }}</pre></details></li></ol></details></div></div></article></div>
        </div>
        <footer class="composer-area"><div class="composer"><el-input ref="composer" v-model="message" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" maxlength="4000" aria-label="向 Zwork 助手提问" :placeholder="active ? '当前请求完成后，可以继续提问…' : '问问 Zwork 助手，或描述你想完成的操作…'" :disabled="!capabilities?.enabled || busy || !!active" @keydown="onComposerKey" /><div class="composer-bottom"><span class="model-label">✦ {{ capabilities?.model || 'Zwork 助手' }}</span><div class="send-controls"><small>{{ message.length }} / 4000</small><button v-if="active" class="stop-button" @click="cancel">■ 停止</button><button v-else class="send-button" :disabled="!canSend" aria-label="发送消息" @click="start"><el-icon><ArrowUp /></el-icon></button></div></div></div><p class="composer-hint">AI 回复仅供参考，阶段更新需你确认。<span>每次提问独立运行 · Enter 发送，Shift + Enter 换行</span></p></footer>
      </main>
    </div>
  </section>
</template>
<style scoped>
.agent-workbench { --accent: #147d73; width: 100%; height: 100%; min-height: 0; margin: 0; display: flex; flex-direction: column; background: #fff; border: 0; border-radius: 0; overflow: hidden; color: #1f2937; box-shadow: none; }
button { font: inherit; cursor: pointer; transition: background .18s; } button:disabled { opacity: .45; cursor: not-allowed; } button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.chat-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 17px 24px; border-bottom: 1px solid #e8eaed; background: rgba(255,255,255,.96); } .assistant-brand, .header-actions { display: flex; align-items: center; gap: 12px; } .logo { display: grid; place-items: center; width: 36px; height: 36px; background: #edf7f5; color: var(--accent); border-radius: 11px; font-size: 27px; } h1 { font-size: 16px; margin: 0; color: #111827; } .assistant-brand p { font-size: 10px; color: #8a94a3; margin: 5px 0 0; } .header-actions button { display: flex; gap: 6px; align-items: center; background: #111827; border: 1px solid #111827; padding: 8px 12px; border-radius: 9px; color: #fff; font-size: 12px; } .connection { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #98a2b3; } .connection i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; } .connection.online { color: #15967d; }
.workspace { display: flex; flex: 1; min-height: 0; position: relative; } .history { width: 218px; flex-shrink: 0; padding: 22px 14px 16px; border-right: 1px solid #e9ede5; background: #f8faf5; display: flex; flex-direction: column; } .history-title { display: flex; align-items: center; justify-content: space-between; font-size: 12px; font-weight: 600; margin: 0 6px 16px; } .history-title small { color: #9ca594; font-weight: 400; } .history :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px #e4e9de inset; border-radius: 7px; } .history :deep(input) { font-size: 11px; } .history-list { overflow-y: auto; flex: 1; padding-top: 14px; } .history-item { display: flex; gap: 9px; width: 100%; background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 12px 9px; text-align: left; color: #76866a; margin-bottom: 4px; } .history-item.selected { background: #eaf1e4; border-color: #dee8d5; } .history-item:hover { background: #edf2e8; } .history-item > .el-icon { margin-top: 3px; } .history-item > span { min-width: 0; } .history-item strong { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 12px; font-weight: 500; } .history-item small { display: block; font-size: 10px; color: #9aa48f; margin-top: 7px; } .empty-history { text-align: center; font-size: 12px; color: #9aa58e; margin-top: 30px; } .history-note { display: flex; gap: 8px; font-size: 10px; line-height: 1.8; color: #8c9a7e; border-top: 1px solid #e6ecdf; padding-top: 16px; } .history-note .el-icon { margin-top: 4px; }
.chat-main { display: flex; flex: 1; min-width: 0; flex-direction: column; background: #fff; } .transcript { overflow-y: auto; flex: 1; min-height: 0; scroll-behavior: smooth; } .welcome { min-height: 100%; max-width: 920px; margin: auto; padding: 38px 36px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; } .hero-logo { font-size: 58px; color: var(--accent); line-height: 1; margin-bottom: 22px; } .eyebrow { color: #8993a1; font-size: 11px; letter-spacing: 3px; } .welcome h2 { font-size: clamp(26px, 2.5vw, 38px); font-weight: 650; letter-spacing: -1.2px; margin: 17px 0 13px; color: #111827; } .welcome p { font-size: 13px; line-height: 1.9; color: #7b8491; margin: 0; } .suggestions { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; width: 100%; margin-top: 38px; } .suggestions button { position: relative; background: #fff; border: 1px solid #e1e4e8; border-radius: 14px; padding: 19px 17px; text-align: left; color: #303b49; box-shadow: 0 1px 2px rgba(15,23,42,.025); } .suggestions button:hover { background: #f7f8fa; border-color: #b9c0c8; transform: translateY(-1px); } .suggestions .el-icon { color: var(--accent); font-size: 19px; margin-bottom: 14px; } .suggestions strong { display: block; font-size: 12px; font-weight: 600; } .suggestions button > span { display: block; font-size: 10px; line-height: 1.8; color: #8a94a3; margin-top: 8px; } .suggestions i { position: absolute; right: 16px; top: 16px; color: #a6aeb8; font-style: normal; }
.messages { max-width: 860px; padding: 30px 34px; margin: auto; } .exchange + .exchange { margin-top: 32px; } .user-message { display: flex; align-items: flex-start; justify-content: flex-end; gap: 10px; margin-bottom: 28px; } .user-bubble { max-width: 82%; padding: 12px 18px; border-radius: 16px 4px 16px 16px; background: #f0f2f4; color: #273346; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.8; } .user-avatar, .assistant-avatar { display: grid; place-items: center; width: 30px; height: 30px; flex-shrink: 0; background: #eef1f3; color: #56616d; border-radius: 50%; font-size: 12px; } .assistant-avatar { border-radius: 9px; color: var(--accent); font-size: 24px; background: #edf7f5; } .assistant-message { display: flex; gap: 12px; } .assistant-content { min-width: 0; flex: 1; } .assistant-heading { display: flex; gap: 10px; align-items: center; min-height: 30px; font-size: 12px; font-weight: 600; margin-bottom: 9px; } .status { font-size: 10px; font-weight: 400; color: #8993a1; } .status.waiting_approval { color: #a46f16; } .status.failed { color: #c24132; } .reply { overflow-wrap: anywhere; font-size: 14px; line-height: 1.9; color: #344054; } .reply-line { min-height: 1.9em; white-space: pre-wrap; } .reply-line strong { color: #111827; font-weight: 700; } .thinking { display: flex; gap: 10px; align-items: center; padding: 10px 0; font-size: 12px; color: #7b8491; } .dots { display: flex; gap: 4px; } .dots i { width: 5px; height: 5px; background: var(--accent); border-radius: 50%; animation: pulse 1.3s infinite; } .dots i:nth-child(2) { animation-delay: .2s; } .dots i:nth-child(3) { animation-delay: .4s; } @keyframes pulse { 50% { opacity: .25; transform: translateY(-2px); } }
.reply-actions { display: flex; gap: 16px; margin-top: 15px; } .reply-actions button { border: 0; background: transparent; display: flex; align-items: center; gap: 4px; color: #92a185; font-size: 11px; padding: 0; } .reply-actions button:hover { color: var(--accent); } .run-details { font-size: 11px; color: #92a084; margin-top: 16px; line-height: 1.8; overflow-wrap: anywhere; } summary { cursor: pointer; } .run-details > summary span { color: #a5b097; margin-left: 12px; font-size: 10px; } .run-details pre { white-space: pre-wrap; overflow-wrap: anywhere; } .run-details li { margin: 8px 0; } .approval { border: 1px solid #dce8d2; background: #f7fbf3; padding: 18px; border-radius: 12px; margin-top: 12px; } .approval h3 { font-size: 14px; display: flex; gap: 8px; align-items: center; margin: 0; } .approval p { font-size: 13px; line-height: 1.8; } .stage-change { font-size: 13px; } .stage-change strong { background: #e6f0de; color: var(--accent); padding: 5px 12px; border-radius: 6px; margin-left: 8px; } .approval :deep(.el-button--primary) { --el-button-bg-color: #277b75; --el-button-border-color: #277b75; --el-button-hover-bg-color: #1d625e; --el-button-hover-border-color: #1d625e; } .muted, .approval .muted { font-size: 11px; color: #93a182; } .notice { background: #fbf6eb; color: #a17944; padding: 12px 16px; font-size: 12px; border-radius: 8px; margin-top: 12px; } .chat-main > .notice { margin: 12px 22px 0; }
.composer-area { width: 100%; max-width: 860px; align-self: center; padding: 16px 34px 18px; } .composer { background: #fff; border: 1px solid #d9dde2; border-radius: 16px; padding: 14px 16px 11px; box-shadow: 0 8px 26px rgba(15,23,42,.06); } .composer:focus-within { border-color: #8b96a3; box-shadow: 0 0 0 3px rgba(17,24,39,.06); } .composer :deep(.el-textarea__inner) { box-shadow: none; resize: none; padding: 0; background: transparent; font-size: 13px; line-height: 1.8; color: #273346; } .composer :deep(.el-textarea__inner::placeholder) { color: #9aa3ad; } .composer-bottom { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 10px; } .model-label { font-size: 10px; color: #7d8792; overflow-wrap: anywhere; } .send-controls { display: flex; align-items: center; gap: 12px; flex-shrink: 0; } .send-controls small { color: #a3abb4; font-size: 10px; } .send-button { width: 32px; height: 32px; border: 0; border-radius: 9px; display: grid; place-items: center; color: #fff; background: #111827; font-size: 19px; } .send-button:disabled { background: #eceff2; color: #a3abb4; opacity: 1; } .stop-button { border: 1px solid #d9dde2; background: #fff; color: #596575; border-radius: 8px; padding: 7px 10px; font-size: 11px; } .composer-hint { text-align: center; color: #9aa3ad; font-size: 9px; margin: 10px 0 0; line-height: 1.8; } .composer-hint span { margin-left: 8px; }
.logo, .assistant-avatar { background: #edf7f5; color: var(--accent); }
.header-actions button:last-child, .send-button { background: #111827; border-color: #111827; color: #fff; }
.header-actions button:last-child:hover, .send-button:hover:not(:disabled) { background: #2f3947; }
.send-button:disabled { background: #eceff2; border-color: #eceff2; color: #9ba4ae; }
@media (max-width: 1100px) { .welcome { padding: 30px 24px; } .suggestions { gap: 8px; } .suggestions button { padding: 14px 11px; } .messages, .composer-area { padding-left: 24px; padding-right: 24px; } }
@media (max-width: 768px) { .agent-workbench { height: 100%; min-height: 0; } .chat-header { padding: 13px 14px; } h1 { font-size: 13px; } .assistant-brand { gap: 8px; } .logo { width: 30px; height: 30px; font-size: 23px; } .header-actions { gap: 5px; } .connection { display: none; } .header-actions button { font-size: 11px; padding: 7px 8px; } .welcome { padding: 24px 18px; } .hero-logo { font-size: 38px; margin-bottom: 15px; } .welcome h2 { font-size: 24px; } .welcome p { font-size: 12px; } .suggestions { margin-top: 22px; grid-template-columns: 1fr; gap: 8px; } .suggestions button { display: flex; align-items: center; gap: 10px; padding: 12px 15px; } .suggestions .el-icon { margin: 0; } .suggestions button > span { display: none; } .suggestions i { top: 10px; } .messages { padding: 22px 14px; } .composer-area { padding: 10px 12px 12px; } .composer { padding: 12px; border-radius: 12px; } .composer-hint span { display: none; } .assistant-message { gap: 8px; } .reply, .user-bubble { font-size: 13px; } }
@media (prefers-reduced-motion: reduce) { .transcript { scroll-behavior: auto; } .dots i { animation: none; } }
</style>
