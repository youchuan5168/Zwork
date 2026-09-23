<script setup>
import { Download, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import api from '@/api'
import { applicationApi, authApi, scheduleApi, settingsApi } from '@/api/resources'
import { computed, onMounted, ref } from 'vue'
import { formatApiError } from '@/utils/errors'
import { useDataStore } from '@/stores/data'

const store = useDataStore()
const router = useRouter()
const password = ref({ current_password: '', new_password: '' })
const changingPassword = ref(false)

const llm = ref({ protocol: 'openai_responses', api_url: '', model: '', api_key: '' })
const llmSaved = ref({ configured: false, protocol: 'openai_responses', api_url: '', model: '', key_masked: '', updated_at: '' })
const llmBusy = ref(false)
const llmUrlPlaceholder = computed(() => llm.value.protocol === 'deepseek_chat'
  ? 'https://api.deepseek.com/v1/chat/completions'
  : 'https://api.openai.com/v1/responses')

async function loadLlm() {
  try {
    const saved = await settingsApi.llm()
    llmSaved.value = saved
    if (saved.configured) llm.value = { protocol: saved.protocol, api_url: saved.api_url, model: saved.model, api_key: '' }
  } catch (e) { ElMessage.error(formatApiError(e)) }
}

async function saveLlm() {
  if (!llm.value.api_url.trim() || !llm.value.model.trim()) { ElMessage.warning('请填写接口地址和模型名称'); return }
  llmBusy.value = true
  try {
    llmSaved.value = await settingsApi.saveLlm({
      protocol: llm.value.protocol,
      api_url: llm.value.api_url.trim(),
      model: llm.value.model.trim(),
      api_key: llm.value.api_key.trim() || null,
    })
    llm.value.api_key = ''
    ElMessage.success('大模型 API 配置已保存')
  } catch (e) { ElMessage.error(formatApiError(e)) }
  finally { llmBusy.value = false }
}

async function clearLlm() {
  try {
    await ElMessageBox.confirm('清除后 Agent 将回退到服务器默认配置，若服务器未配置则不可用。确定清除？', '清除大模型配置', { type: 'warning' })
  } catch { return }
  llmBusy.value = true
  try {
    await settingsApi.deleteLlm()
    llmSaved.value = { configured: false, protocol: 'openai_responses', api_url: '', model: '', key_masked: '', updated_at: '' }
    llm.value = { protocol: 'openai_responses', api_url: '', model: '', api_key: '' }
    ElMessage.success('配置已清除')
  } catch (e) { ElMessage.error(formatApiError(e)) }
  finally { llmBusy.value = false }
}

function llmTime(iso) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

onMounted(() => {
  loadLlm()
})
async function changePassword() {
  changingPassword.value = true
  try {
    await authApi.changePassword(password.value)
    password.value = { current_password: '', new_password: '' }
    store.clearAuth()
    store.notifyAuthChange()
    ElMessage.success('密码已修改，所有设备需要重新登录')
    router.push({ name: 'login' })
  } catch (e) { ElMessage.error(formatApiError(e)) }
  finally { changingPassword.value = false }
}

function exportData() {
  const blob = new Blob([JSON.stringify(
    {
      exported_at: new Date().toISOString(),
      applications: store.applications,
      schedules: store.schedules,
      companies: store.companies,
    },
    null,
    2,
  )], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `qiuzhao-backup-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('备份文件已导出')
}

function importData() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'application/json'
  input.onchange = async () => {
    const file = input.files[0]
    if (!file) return
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed.applications)) throw new Error('格式不正确')
      await ElMessageBox.confirm(
        `将导入 ${parsed.applications.length} 条投递记录、${parsed.schedules?.length || 0} 条安排，` +
        '会与现有数据合并（重复记录以服务端为准）。确定继续？',
        '导入数据',
        { type: 'warning', confirmButtonText: '继续导入', cancelButtonText: '取消' },
      )
      // 逐条恢复（个人数据量小）
      for (const app of parsed.applications) {
        try {
          await applicationApi.create({
            company_id: null,
            company_name: app.company_name,
            position: app.position,
            channel: app.channel || '',
            apply_date: app.apply_date,
            current_stage: app.current_stage || 'not_started',
            notes: app.notes || '',
          })
        } catch {
          /* 跳过导入失败的单条 */
        }
      }
      for (const sched of parsed.schedules || []) {
        try {
          await scheduleApi.create({
            application_id: null,
            title: sched.title,
            type: sched.type || '其他',
            sched_date: sched.sched_date,
            sched_time: sched.sched_time || '',
            link: sched.link || '',
            location: sched.location || '',
            done: !!sched.done,
          })
        } catch {
          /* 跳过 */
        }
      }
      await store.fetchAll()
      ElMessage.success('导入完成')
    } catch (e) {
      if (e !== 'cancel') ElMessage.error(e.message || '导入失败')
    }
  }
  input.click()
}

async function logout() {
  try {
    await store.logout()
    router.push({ name: 'login' })
  } catch (e) { ElMessage.error(formatApiError(e)) }
}
</script>

<template>
  <div class="content-wrapper settings">
    <h2 class="qz-page-title" style="margin-bottom: 12px">设置</h2>

    <div class="qz-card section">
      <div class="section-title">数据备份</div>
      <p class="desc">导出投递记录、安排和公司为 JSON 文件。简历版本、求职档案和材料库请使用完整数据库备份。</p>
      <div class="btn-row">
        <el-button :icon="Download" @click="exportData">导出备份</el-button>
        <el-button :icon="Upload" @click="importData">导入数据</el-button>
      </div>
      <p class="small">当前：投递 {{ store.applications.length }} 条 · 安排 {{ store.schedules.length }} 条 · 公司 {{ store.companies.length }} 家</p>
    </div>

    <div class="qz-card section">
      <div class="section-title">大模型 API 配置</div>
      <p class="desc">Zwork 助手按此配置调用你自己的大模型，未填写时沿用服务器默认。接口地址须为 HTTPS 完整端点；密钥加密保存，仅显示掩码。</p>
      <el-form label-position="top" class="llm-form">
        <el-form-item label="接口协议">
          <el-select v-model="llm.protocol">
            <el-option label="OpenAI Responses（/v1/responses）" value="openai_responses" />
            <el-option label="Chat Completions 兼容（DeepSeek 等）" value="deepseek_chat" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口地址 URL">
          <el-input v-model="llm.api_url" :placeholder="llmUrlPlaceholder" clearable />
        </el-form-item>
        <el-form-item label="模型名称 Model">
          <el-input v-model="llm.model" placeholder="如 gpt-5-mini、deepseek-chat" clearable />
        </el-form-item>
        <el-form-item label="API 密钥 Key">
          <el-input v-model="llm.api_key" type="password" show-password autocomplete="off"
                    :placeholder="llmSaved.configured ? `留空表示保持不变（当前 ${llmSaved.key_masked}）` : 'sk-…'" />
        </el-form-item>
      </el-form>
      <div class="btn-row">
        <el-button type="primary" :loading="llmBusy" @click="saveLlm">保存配置</el-button>
        <el-button v-if="llmSaved.configured" type="danger" plain :loading="llmBusy" @click="clearLlm">清除配置</el-button>
      </div>
      <p v-if="llmSaved.configured" class="small">已保存：{{ llmSaved.model }} @ {{ llmSaved.api_url }} · 密钥 {{ llmSaved.key_masked }} · 更新于 {{ llmTime(llmSaved.updated_at) }}</p>
    </div>

    <div class="qz-card section">
      <div class="section-title">账号</div>
      <p class="desc">当前登录：<b>{{ store.username }}</b>。退出登录将使所有设备的会话失效。</p>
      <el-button type="danger" plain @click="logout">退出登录</el-button>
      <el-form style="margin-top: 16px" @submit.prevent="changePassword">
        <el-form-item label="当前密码"><el-input v-model="password.current_password" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="password.new_password" type="password" show-password autocomplete="new-password" placeholder="至少 15 位，UTF-8 最多 72 字节" /></el-form-item>
        <el-button :loading="changingPassword" @click="changePassword">修改密码并退出所有设备</el-button>
      </el-form>
    </div>

    <div class="qz-card section">
      <div class="section-title">关于</div>
      <p class="desc">
        Zwork：找工作，更有章法。
        数据保存在本地 MySQL（{{ api.defaults.baseURL }} 接口），后续接入 AI 智能体辅助识别岗位、总结进展。
      </p>
    </div>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 720px;
}

.section-title {
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 8px;
}

.desc {
  color: #6b7280;
  font-size: 13px;
  margin: 0 0 12px;
  line-height: 1.7;
}

.small {
  color: #9ca3af;
  font-size: 12px;
  margin: 12px 0 0;
}

.btn-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.llm-form { max-width: 480px; }
.llm-form :deep(.el-select) { width: 100%; }
</style>
