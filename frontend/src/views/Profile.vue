<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, profileApi } from '@/api/resources'
import { formatApiError } from '@/utils/errors'
import { useDataStore } from '@/stores/data'

const store = useDataStore()
const route = useRoute()
const router = useRouter()
const tab = ref('resumes')
const loading = ref(false)
const documents = ref([])
const memories = ref([])
const documentDialog = ref(false)
const documentSaving = ref(false)
const editingDocument = ref(null)
const documentForm = ref({ kind: 'resume', title: '', content: '' })
const selectedFile = ref(null)
const detail = ref(null)
const detailOpen = ref(false)
const versions = ref([])
const selectedVersion = ref(null)
const memoryDialog = ref(false)
const memorySaving = ref(false)
const editingMemory = ref(null)
const memoryForm = ref({ category: 'goal', content: '', source_version_id: null, valid_until: null })
const resumeId = ref(null)
const jdId = ref(null)
const matchResult = ref(null)
const matching = ref(false)
const agentEnabled = ref(false)
const aiRun = ref(null)
const aiLoading = ref(false)
const compareOpen = ref(false)
const compareTitle = ref('')
const compareLeft = ref(null)
const compareRight = ref(null)
const suggestionOpen = ref(false)
const suggestions = ref([])
const selectedSuggestions = ref([])
const suggestionLoading = ref(false)
const suggestionSaving = ref(false)
const tailoring = ref(false)

const kinds = { resume: '简历', jd: '岗位说明', project: '项目材料' }
const categories = { goal: '求职方向', skill: '核心技能', preference: '工作偏好', experience: '经历亮点' }
const resumes = computed(() => documents.value.filter((item) => item.kind === 'resume'))
const jds = computed(() => documents.value.filter((item) => item.kind === 'jd'))
const projects = computed(() => documents.value.filter((item) => item.kind === 'project'))
const activeMemories = computed(() => memories.value.filter((item) => item.active).length)
const compareRows = computed(() => {
  const left = (compareLeft.value?.content || '').split('\n')
  const right = (compareRight.value?.content || '').split('\n')
  const leftSet = new Set(left)
  const rightSet = new Set(right)
  return {
    left: left.map((text) => ({ text, changed: !rightSet.has(text) })),
    right: right.map((text) => ({ text, changed: !leftSet.has(text) })),
  }
})
const generation = () => store.authGeneration

async function refresh() {
  const current = generation()
  loading.value = true
  try {
    const [docs, facts] = await Promise.all([profileApi.documents(), profileApi.memories()])
    if (current !== generation()) return
    documents.value = docs
    memories.value = facts
    if (!resumeId.value && resumes.value.length) resumeId.value = resumes.value[0].id
    if (!jdId.value && jds.value.length) jdId.value = jds.value[0].id
  } catch (error) { if (current === generation()) ElMessage.error(formatApiError(error)) }
  finally { if (current === generation()) loading.value = false }
}

function newDocument(kind = 'resume') {
  editingDocument.value = null
  documentForm.value = { kind, title: '', content: '' }
  selectedFile.value = null
  documentDialog.value = true
}

async function editDocument(row) {
  try {
    const result = await profileApi.document(row.id)
    editingDocument.value = row.id
    documentForm.value = { kind: row.kind, title: row.title, content: result.version.content }
    selectedFile.value = null
    documentDialog.value = true
  } catch (error) { ElMessage.error(formatApiError(error)) }
}

function pickFile(event) { selectedFile.value = event.target.files?.[0] || null }

async function saveDocument() {
  if (!documentForm.value.title.trim() || (!selectedFile.value && !documentForm.value.content.trim())) {
    ElMessage.warning('请填写标题和内容，或选择文件')
    return
  }
  documentSaving.value = true
  try {
    const id = editingDocument.value
    if (selectedFile.value) {
      const form = new FormData()
      form.append('kind', documentForm.value.kind)
      form.append('title', documentForm.value.title.trim())
      form.append('file', selectedFile.value)
      await profileApi.importDocument(form, id)
    } else {
      const body = { ...documentForm.value, title: documentForm.value.title.trim(), source_name: '网页粘贴' }
      if (id == null) await profileApi.createDocument(body)
      else await profileApi.reviseDocument(id, body)
    }
    documentDialog.value = false
    ElMessage.success(id == null ? '资料已添加' : '新版本已保存')
    await refresh()
    if (detail.value?.document?.id === id) await showDocument({ id })
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { documentSaving.value = false }
}

async function showDocument(row) {
  try {
    const [result, history] = await Promise.all([profileApi.document(row.id), profileApi.versions(row.id)])
    detail.value = result
    detailOpen.value = true
    versions.value = history
    selectedVersion.value = result.version
  } catch (error) { ElMessage.error(formatApiError(error)) }
}

async function showVersion(number) {
  try { selectedVersion.value = await profileApi.version(detail.value.document.id, number) }
  catch (error) { ElMessage.error(formatApiError(error)) }
}

async function removeDocument(row) {
  try {
    await ElMessageBox.confirm(
      `删除“${row.title}”及其全部历史版本？与它关联的求职档案信息也会删除。`, '删除资料',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await profileApi.deleteDocument(row.id)
    if (detail.value?.document?.id === row.id) detail.value = null
    if (detail.value == null) detailOpen.value = false
    matchResult.value = null
    await refresh()
    ElMessage.success('资料已删除')
  } catch (error) { if (error !== 'cancel') ElMessage.error(formatApiError(error)) }
}

async function setDefault(row) {
  try {
    await profileApi.setDefault(row.id)
    await refresh()
    ElMessage.success(`已将“${row.title}”设为默认简历`)
  } catch (error) { ElMessage.error(formatApiError(error)) }
}

async function compareVersions(row) {
  try {
    const history = await profileApi.versions(row.id)
    if (history.length < 2) return ElMessage.info('这份简历还没有可比较的历史版本')
    const [right, left] = await Promise.all([
      profileApi.version(row.id, history[0].version),
      profileApi.version(row.id, history[1].version),
    ])
    compareTitle.value = row.title
    compareLeft.value = left
    compareRight.value = right
    compareOpen.value = true
  } catch (error) { ElMessage.error(formatApiError(error)) }
}

async function extractProfile(row) {
  suggestionLoading.value = true
  try {
    const result = await profileApi.profileSuggestions(row.id)
    suggestions.value = result.suggestions
    selectedSuggestions.value = result.suggestions.map((_, index) => index)
    suggestionOpen.value = true
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { suggestionLoading.value = false }
}

async function saveSuggestions() {
  if (!selectedSuggestions.value.length) return ElMessage.warning('请至少选择一条信息')
  suggestionSaving.value = true
  try {
    for (const index of selectedSuggestions.value) {
      const row = suggestions.value[index]
      await profileApi.createMemory({ ...row, valid_until: null })
    }
    suggestionOpen.value = false
    await refresh()
    tab.value = 'profile'
    ElMessage.success(`已保存 ${selectedSuggestions.value.length} 条求职档案信息`)
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { suggestionSaving.value = false }
}

function newMemory() {
  editingMemory.value = null
  memoryForm.value = { category: 'goal', content: '', source_version_id: null, valid_until: null }
  memoryDialog.value = true
}

function newMemoryFromVersion() {
  newMemory()
  memoryForm.value.source_version_id = selectedVersion.value.id
  detailOpen.value = false
}

function editMemory(row) {
  editingMemory.value = row.id
  memoryForm.value = {
    category: row.category, content: row.content,
    source_version_id: row.source_version_id, valid_until: row.valid_until,
  }
  memoryDialog.value = true
}

async function saveMemory() {
  if (!memoryForm.value.content.trim()) return ElMessage.warning('请填写档案内容')
  memorySaving.value = true
  try {
    const body = { ...memoryForm.value, content: memoryForm.value.content.trim() }
    if (editingMemory.value == null) await profileApi.createMemory(body)
    else await profileApi.updateMemory(editingMemory.value, body)
    memoryDialog.value = false
    await refresh()
    ElMessage.success('求职档案已保存')
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { memorySaving.value = false }
}

async function removeMemory(row) {
  try {
    await ElMessageBox.confirm('删除这条求职档案信息？', '删除信息', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await profileApi.deleteMemory(row.id)
    await refresh()
  } catch (error) { if (error !== 'cancel') ElMessage.error(formatApiError(error)) }
}

async function runMatch() {
  if (!resumeId.value || !jdId.value) return ElMessage.warning('请先选择简历和岗位说明')
  matching.value = true
  matchResult.value = null
  aiRun.value = null
  try { matchResult.value = await profileApi.match(resumeId.value, jdId.value) }
  catch (error) { ElMessage.error(formatApiError(error)) }
  finally { matching.value = false }
}

async function explainWithAi() {
  if (!resumeId.value || !jdId.value) return ElMessage.warning('请先选择简历和岗位说明')
  aiLoading.value = true
  aiRun.value = null
  try {
    const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('')
    const created = await agentApi.create({
      request_key: key, skill: 'job_match', timezone: 'Asia/Shanghai',
      message: `请对比简历文档 #${resumeId.value} 与 JD 文档 #${jdId.value}，引用版本和片段，并说明需要核实的要求。`,
    })
    aiRun.value = created.status === 'queued' ? await agentApi.execute(created.id) : created
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { aiLoading.value = false }
}

async function createTailoredResume() {
  const resume = resumes.value.find((row) => row.id === resumeId.value)
  const jd = jds.value.find((row) => row.id === jdId.value)
  if (!resume || !jd) return
  try {
    const { value } = await ElMessageBox.prompt('先复制当前简历，再根据分析结果逐项修改。原简历不会改变。', '创建岗位定制版', {
      inputValue: `${resume.title} · ${jd.title}`,
      inputPattern: /\S+/,
      inputErrorMessage: '请输入定制版名称',
      confirmButtonText: '创建副本', cancelButtonText: '取消',
    })
    tailoring.value = true
    await profileApi.duplicateResume(resume.id, { title: value.trim() })
    await refresh()
    tab.value = 'resumes'
    ElMessage.success('岗位定制版已创建，可以开始修改')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(formatApiError(error))
  } finally { tailoring.value = false }
}

onMounted(async () => {
  await refresh()
  if (route.query.tab === 'match') tab.value = 'match'
  const requestedJd = Number(route.query.jd)
  if (requestedJd && jds.value.some((row) => row.id === requestedJd)) jdId.value = requestedJd
  if (route.query.tab || route.query.jd) router.replace({ path: '/resume' })
  try { agentEnabled.value = (await agentApi.capabilities()).enabled }
  catch { agentEnabled.value = false }
})
</script>

<template>
  <div class="content-wrapper profile-page">
    <header class="page-head">
      <div>
        <span class="eyebrow">工具 / 简历中心</span>
        <h1 class="qz-page-title">简历与求职档案</h1>
        <p class="intro">集中管理简历、岗位要求和求职偏好，让岗位分析、面试准备和平台招聘使用同一份资料。</p>
      </div>
      <el-button type="primary" @click="newDocument('resume')">添加简历</el-button>
    </header>

    <div class="summary-grid">
      <button type="button" class="qz-card summary-card" @click="tab = 'resumes'">
        <strong>{{ resumes.length }}</strong><span>份简历</span><small>管理当前版本和历史版本</small>
      </button>
      <button type="button" class="qz-card summary-card" @click="tab = 'match'">
        <strong>{{ jds.length }}</strong><span>个岗位说明</span><small>用于岗位优化与证据对照</small>
      </button>
      <button type="button" class="qz-card summary-card" @click="tab = 'profile'">
        <strong>{{ activeMemories }}</strong><span>条有效档案</span><small>供助手和面试准备参考</small>
      </button>
    </div>

    <el-tabs v-model="tab" class="workspace-tabs">
      <el-tab-pane label="我的简历" name="resumes">
        <div v-loading="loading" class="document-list">
          <el-empty v-if="!resumes.length" description="还没有简历。导入 TXT、Markdown、PDF、Word，或直接粘贴内容。">
            <el-button type="primary" @click="newDocument('resume')">添加第一份简历</el-button>
          </el-empty>
          <div v-for="row in resumes" :key="row.id" class="qz-card document-row featured-row">
            <div class="document-main">
              <div class="document-title"><el-tag size="small" type="success">简历</el-tag><el-tag v-if="row.is_default" size="small">默认</el-tag><b>{{ row.title }}</b></div>
              <div class="muted">当前为第 {{ row.current_version }} 版 · 更新于 {{ row.updated_at?.slice(0, 10) }}</div>
            </div>
            <div class="actions">
              <el-button v-if="!row.is_default" size="small" text @click="setDefault(row)">设为默认</el-button>
              <el-button size="small" @click="showDocument(row)">查看与历史版本</el-button>
              <el-button size="small" @click="compareVersions(row)">版本对比</el-button>
              <el-button size="small" :loading="suggestionLoading" @click="extractProfile(row)">提取求职档案</el-button>
              <el-button size="small" type="primary" plain @click="editDocument(row)">更新简历</el-button>
              <el-button size="small" type="danger" text @click="removeDocument(row)">删除</el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="岗位优化" name="match">
        <div class="qz-card match-card">
          <div class="section-heading">
            <div><h2>用岗位要求检查简历</h2><p>查看简历中已有的对应证据和仍需补充的要求。分析结果不是录用概率。</p></div>
            <el-button @click="newDocument('jd')">添加岗位说明</el-button>
          </div>
          <div v-if="!resumes.length || !jds.length" class="setup-hint">
            <p>开始分析前，需要至少一份简历和一个岗位说明。</p>
            <el-button v-if="!resumes.length" @click="newDocument('resume')">添加简历</el-button>
            <el-button v-if="!jds.length" @click="newDocument('jd')">添加岗位说明</el-button>
          </div>
          <div v-else class="match-controls">
            <label><span>使用简历</span><el-select v-model="resumeId"><el-option v-for="row in resumes" :key="row.id" :label="`${row.title} · 第 ${row.current_version} 版`" :value="row.id" /></el-select></label>
            <label><span>目标岗位</span><el-select v-model="jdId"><el-option v-for="row in jds" :key="row.id" :label="row.title" :value="row.id" /></el-select></label>
            <el-button type="primary" :loading="matching" @click="runMatch">开始分析</el-button>
            <el-button v-if="agentEnabled" :loading="aiLoading" @click="explainWithAi">获取 AI 建议</el-button>
          </div>
          <div v-if="aiRun" class="ai-result">
            <h3>AI 优化建议</h3>
            <p v-if="aiRun.status === 'completed'" class="ai-text">{{ aiRun.output }}</p>
            <p v-else class="muted">分析未完成：{{ aiRun.error_code || aiRun.status }}</p>
          </div>
          <template v-if="matchResult">
            <div class="result-summary">
              <strong>{{ matchResult.matched.length }}</strong><span>项已有简历证据</span>
              <strong>{{ matchResult.gaps.length }}</strong><span>项需要核实或补充</span>
            </div>
            <section class="result-section">
              <h3>简历中已有的对应内容</h3>
              <div v-for="(item, index) in matchResult.matched" :key="`m-${index}`" class="match-item success-item">
                <b>{{ item.requirement }}</b><p>{{ item.evidence }}</p><span class="muted">来自简历第 {{ item.resume_version }} 版</span>
              </div>
            </section>
            <section class="result-section">
              <h3>尚未找到足够证据</h3>
              <p class="muted">请确认自己是否具备这些经历；不要为了匹配岗位而添加不真实的内容。</p>
              <div v-for="(item, index) in matchResult.gaps" :key="`g-${index}`" class="match-item gap-item">{{ item.requirement }}</div>
            </section>
            <div class="tailor-action"><div><b>准备开始修改？</b><p>复制当前简历创建岗位定制版，原简历和历史版本不会改变。</p></div><el-button type="primary" :loading="tailoring" @click="createTailoredResume">创建岗位定制版</el-button></div>
          </template>
        </div>
      </el-tab-pane>

      <el-tab-pane label="求职档案" name="profile">
        <div class="section-heading">
          <div><h2>让助手了解你的求职方向</h2><p>这些信息会用于岗位分析、面试准备和行动建议；只有你确认保存的内容才会生效。</p></div>
          <el-button type="primary" @click="newMemory">添加信息</el-button>
        </div>
        <el-empty v-if="!memories.length" description="还没有求职档案信息。可以先添加目标岗位、核心技能或工作偏好。">
          <el-button type="primary" @click="newMemory">添加第一条信息</el-button>
        </el-empty>
        <div class="profile-grid">
          <div v-for="row in memories" :key="row.id" class="qz-card memory-card" :class="{ stale: !row.active }">
            <div class="memory-top"><el-tag size="small" type="info">{{ categories[row.category] }}</el-tag><span v-if="!row.active" class="review-badge">需要确认</span></div>
            <p>{{ row.content }}</p>
            <div class="muted">{{ row.source_version_id ? '来自已关联的资料版本' : '由你直接添加' }}<span v-if="row.valid_until"> · {{ row.valid_until }} 后提醒确认</span></div>
            <div class="actions"><el-button size="small" text @click="editMemory(row)">编辑</el-button><el-button size="small" type="danger" text @click="removeMemory(row)">删除</el-button></div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="材料库" name="library">
        <div class="library-section">
          <div class="section-heading"><div><h2>岗位说明</h2><p>保存关注岗位的要求，用于简历优化和后续面试准备。</p></div><el-button @click="newDocument('jd')">添加岗位说明</el-button></div>
          <el-empty v-if="!jds.length" description="还没有保存岗位说明" :image-size="64" />
          <div v-for="row in jds" :key="row.id" class="qz-card document-row">
            <div class="document-main"><b>{{ row.title }}</b><div class="muted">第 {{ row.current_version }} 版 · {{ row.updated_at?.slice(0, 10) }}</div></div>
            <div class="actions"><el-button size="small" @click="showDocument(row)">查看</el-button><el-button size="small" @click="editDocument(row)">更新</el-button><el-button size="small" type="danger" text @click="removeDocument(row)">删除</el-button></div>
          </div>
        </div>
        <div class="library-section">
          <div class="section-heading"><div><h2>项目与经历材料</h2><p>保存项目说明、作品集文字和经历素材，供助手检索引用。</p></div><el-button @click="newDocument('project')">添加项目材料</el-button></div>
          <el-empty v-if="!projects.length" description="还没有项目材料" :image-size="64" />
          <div v-for="row in projects" :key="row.id" class="qz-card document-row">
            <div class="document-main"><b>{{ row.title }}</b><div class="muted">第 {{ row.current_version }} 版 · {{ row.updated_at?.slice(0, 10) }}</div></div>
            <div class="actions"><el-button size="small" @click="showDocument(row)">查看</el-button><el-button size="small" @click="editDocument(row)">更新</el-button><el-button size="small" type="danger" text @click="removeDocument(row)">删除</el-button></div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="documentDialog" :title="editingDocument ? `更新${kinds[documentForm.kind]}` : `添加${kinds[documentForm.kind]}`" width="min(720px, 95vw)">
      <el-form label-position="top">
        <el-form-item v-if="!editingDocument" label="资料类型"><el-segmented v-model="documentForm.kind" :options="Object.entries(kinds).map(([value, label]) => ({ value, label }))" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="documentForm.title" maxlength="128" show-word-limit :placeholder="documentForm.kind === 'resume' ? '例如：产品经理通用简历' : '例如：公司名 · 岗位名'" /></el-form-item>
        <el-form-item label="导入文件"><input type="file" accept=".txt,.md,.pdf,.docx" @change="pickFile" /><span class="form-help">支持 TXT、Markdown、可提取文字的 PDF 和 Word</span></el-form-item>
        <el-form-item label="或直接粘贴内容"><el-input v-model="documentForm.content" type="textarea" :rows="12" placeholder="粘贴完整内容；更新已有资料时会自动保留历史版本" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="documentDialog = false">取消</el-button><el-button type="primary" :loading="documentSaving" @click="saveDocument">{{ editingDocument ? '保存为新版本' : '添加' }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailOpen" title="资料内容与历史版本" size="min(680px, 95vw)">
      <template v-if="detail">
        <h2>{{ detail.document.title }}</h2>
        <div class="version-toolbar"><el-select :model-value="selectedVersion?.version" @update:model-value="showVersion"><el-option v-for="row in versions" :key="row.version" :label="`第 ${row.version} 版`" :value="row.version" /></el-select><el-button @click="newMemoryFromVersion">将信息加入求职档案</el-button></div>
        <p class="muted">来源：{{ selectedVersion?.source_name || '直接粘贴' }} · 保存于 {{ selectedVersion?.created_at?.slice(0, 10) }}</p>
        <pre class="document-content">{{ selectedVersion?.content }}</pre>
      </template>
    </el-drawer>

    <el-dialog v-model="memoryDialog" :title="editingMemory ? '编辑求职档案' : '添加求职档案'" width="min(560px, 95vw)">
      <el-form label-position="top">
        <el-form-item label="信息类型"><el-select v-model="memoryForm.category"><el-option v-for="(label, key) in categories" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        <el-form-item label="内容"><el-input v-model="memoryForm.content" type="textarea" :rows="4" maxlength="1000" show-word-limit :placeholder="memoryForm.category === 'goal' ? '例如：优先寻找上海或杭州的 B 端产品经理岗位' : '写下希望助手长期参考的信息'" /></el-form-item>
        <el-alert v-if="memoryForm.source_version_id" title="这条信息来自你刚才查看的资料；资料更新后会提醒你重新确认。" type="info" :closable="false" />
        <el-form-item label="提醒重新确认（可选）" class="date-field"><el-date-picker v-model="memoryForm.valid_until" type="date" value-format="YYYY-MM-DD" placeholder="长期有效" clearable /></el-form-item>
      </el-form>
      <template #footer><el-button @click="memoryDialog = false">取消</el-button><el-button type="primary" :loading="memorySaving" @click="saveMemory">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="compareOpen" :title="`${compareTitle} · 版本对比`" width="min(1040px, 96vw)">
      <div class="compare-grid">
        <section><h3>第 {{ compareLeft?.version }} 版</h3><div class="compare-content"><p v-for="(line, index) in compareRows.left" :key="`l-${index}`" :class="{ changed: line.changed }">{{ line.text || ' ' }}</p></div></section>
        <section><h3>第 {{ compareRight?.version }} 版（当前）</h3><div class="compare-content"><p v-for="(line, index) in compareRows.right" :key="`r-${index}`" :class="{ changed: line.changed }">{{ line.text || ' ' }}</p></div></section>
      </div>
      <p class="muted compare-help">高亮表示只出现在这一版本中的段落。本次先比较最近两个版本。</p>
    </el-dialog>

    <el-dialog v-model="suggestionOpen" title="确认求职档案信息" width="min(680px, 95vw)">
      <p class="dialog-intro">系统根据简历文字整理出以下候选信息。请只保存准确、希望助手长期参考的内容。</p>
      <el-empty v-if="!suggestions.length" description="没有识别到适合加入求职档案的信息" />
      <el-checkbox-group v-else v-model="selectedSuggestions" class="suggestion-list">
        <el-checkbox v-for="(row, index) in suggestions" :key="index" :value="index" class="suggestion-item">
          <span><b>{{ categories[row.category] }}</b>{{ row.content }}</span>
        </el-checkbox>
      </el-checkbox-group>
      <template #footer><el-button @click="suggestionOpen = false">取消</el-button><el-button type="primary" :loading="suggestionSaving" :disabled="!suggestions.length" @click="saveSuggestions">保存所选信息</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.profile-page { max-width: 1080px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.eyebrow { display: block; margin-bottom: 7px; color: #6c9991; font-size: 11px; font-weight: 700; letter-spacing: .1em; }
.intro, .muted { color: #667085; font-size: 13px; line-height: 1.65; }
.intro { max-width: 720px; margin: 8px 0 0; }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0 18px; }
.summary-card { display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 0 9px; width: 100%; border: 1px solid #e7ecea; color: inherit; text-align: left; cursor: pointer; }
.summary-card:hover { border-color: #9fcac0; transform: translateY(-1px); }
.summary-card strong { color: #176b62; font-size: 27px; line-height: 1; }
.summary-card span { font-size: 14px; font-weight: 700; }
.summary-card small { grid-column: 1 / -1; margin-top: 8px; color: #8a949f; font-size: 12px; }
.workspace-tabs { margin-top: 4px; }
.document-list, .profile-grid { display: grid; gap: 10px; }
.profile-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.document-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 8px 0; }
.featured-row { border-left: 3px solid #62a99b; }
.document-main { min-width: 0; }
.document-title { display: flex; align-items: center; gap: 9px; margin-bottom: 6px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin: 4px 0 16px; }
.section-heading h2 { margin: 0 0 5px; font-size: 17px; }
.section-heading p { margin: 0; color: #667085; font-size: 13px; line-height: 1.6; }
.match-card { padding: 20px; }
.match-controls { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto auto; gap: 10px; align-items: end; }
.match-controls label { display: grid; gap: 6px; color: #475467; font-size: 12px; font-weight: 650; }
.setup-hint { padding: 24px; border-radius: 10px; background: #f6f8f7; text-align: center; }
.result-summary { display: grid; grid-template-columns: auto 1fr auto 1fr; align-items: baseline; gap: 4px 8px; margin-top: 22px; padding: 15px; border-radius: 10px; background: #f5faf8; }
.result-summary strong { color: #176b62; font-size: 23px; }
.result-summary span { color: #667085; font-size: 13px; }
.result-section { margin-top: 22px; }
.result-section h3, .ai-result h3 { margin: 0 0 8px; font-size: 15px; }
.match-item { margin-top: 9px; padding: 13px 14px; border: 1px solid #e8eceb; border-radius: 9px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.match-item p { margin: 7px 0; color: #475467; }
.success-item { border-left: 3px solid #65a694; }
.gap-item { border-left: 3px solid #d6a15e; background: #fffaf3; }
.ai-result { margin-top: 20px; padding: 16px; border-radius: 10px; background: #f7f7fb; }
.ai-text { margin-bottom: 0; white-space: pre-wrap; line-height: 1.75; }
.tailor-action { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 22px; padding: 16px; border: 1px solid #b9dcd3; border-radius: 10px; background: #f3faf7; }
.tailor-action p { margin: 5px 0 0; color: #667085; font-size: 13px; }
.memory-card { display: flex; flex-direction: column; min-height: 150px; }
.memory-card.stale { border-color: #e4c994; background: #fffcf5; }
.memory-card p { margin: 13px 0 8px; line-height: 1.7; }
.memory-card .actions { margin-top: auto; justify-content: flex-end; }
.memory-top { display: flex; align-items: center; justify-content: space-between; }
.review-badge { color: #9a6700; font-size: 12px; }
.library-section + .library-section { margin-top: 32px; padding-top: 25px; border-top: 1px solid #edf0ef; }
.form-help { display: block; width: 100%; margin-top: 6px; color: #98a2b3; font-size: 12px; }
.version-toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0 8px; }
.version-toolbar .el-select { width: 160px; }
.document-content { margin-top: 16px; padding: 16px; border-radius: 10px; background: #f7f8f8; white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; line-height: 1.75; font-size: 13px; }
.date-field { margin-top: 18px; }
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.compare-grid h3 { margin: 0 0 9px; font-size: 14px; }
.compare-content { max-height: 56vh; overflow: auto; padding: 12px; border: 1px solid #e5e9e8; border-radius: 9px; background: #f8f9f9; }
.compare-content p { min-height: 1.5em; margin: 0; padding: 2px 6px; border-radius: 4px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.55; }
.compare-content p.changed { background: #fff0c9; }
.compare-help { margin-bottom: 0; }
.dialog-intro { margin: 0 0 14px; color: #667085; font-size: 13px; line-height: 1.65; }
.suggestion-list { display: grid; gap: 8px; }
.suggestion-item { width: 100%; height: auto; margin: 0; padding: 11px 12px; border: 1px solid #e5e9e8; border-radius: 9px; align-items: flex-start; }
.suggestion-item :deep(.el-checkbox__label) { min-width: 0; white-space: normal; line-height: 1.6; }
.suggestion-item b { display: block; margin-bottom: 2px; color: #176b62; font-size: 12px; }
@media (max-width: 860px) { .match-controls { grid-template-columns: 1fr 1fr; } .profile-grid { grid-template-columns: 1fr; } }
@media (max-width: 640px) {
  .page-head, .section-heading, .document-row, .tailor-action { align-items: stretch; flex-direction: column; }
  .summary-grid, .match-controls { grid-template-columns: 1fr; }
  .compare-grid { grid-template-columns: 1fr; }
  .result-summary { grid-template-columns: auto 1fr; }
}
</style>
