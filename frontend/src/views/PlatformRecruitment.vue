<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { profileApi } from '@/api/resources'
import { formatApiError } from '@/utils/errors'

const router = useRouter()
const analyzeOpen = ref(false)
const analyzeSaving = ref(false)
const analyzeForm = ref({ title: '', content: '' })

const platforms = [
  { key: 'boss', label: 'BOSS 直聘', url: 'https://www.zhipin.com/', icon: 'https://www.zhipin.com/favicon.ico', desc: '与招聘方直接沟通，互联网岗位活跃度高。' },
  { key: 'liepin', label: '猎聘', url: 'https://www.liepin.com/', icon: 'https://www.liepin.com/favicon.ico', desc: '中高端岗位集中，猎头主动触达较多。' },
  { key: 'zhilian', label: '智联招聘', url: 'https://www.zhaopin.com/', icon: 'https://www.zhaopin.com/favicon.ico', desc: '老牌综合平台，校招与国企岗位覆盖广。' },
  { key: '51job', label: '前程无忧', url: 'https://www.51job.com/', icon: 'https://www.51job.com/favicon.ico', desc: '行业与企业规模覆盖面大，投递渠道成熟。' },
  { key: 'iguopin', label: '国资央企招聘平台', url: 'https://cujiuye.iguopin.com/', icon: 'https://www.iguopin.com/favicon.ico', desc: '央企国企官方招聘渠道，岗位信息真实可靠。' },
  { key: 'ncss', label: '国家大学生就业服务平台', url: 'https://www.ncss.cn/student/jobs/index.html', icon: 'https://www.ncss.cn/favicon.ico', desc: '教育部主管，聚合校招岗位与就业服务。' },
  { key: 'shixiseng', label: '实习僧', url: 'https://www.shixiseng.com/', icon: 'https://www.shixiseng.com/favicon.ico', desc: '专注实习生招聘，大厂实习岗位更新快。' },
  { key: 'maimai', label: '脉脉', url: 'https://maimai.cn/', icon: 'https://maimai.cn/favicon.ico', desc: '职场社交平台，内推机会与公司信息丰富。' },
]
const failedIcons = ref({})

async function startAnalysis() {
  if (!analyzeForm.value.title.trim() || !analyzeForm.value.content.trim()) {
    ElMessage.warning('请填写岗位名称和完整岗位说明')
    return
  }
  analyzeSaving.value = true
  try {
    const jd = await profileApi.createDocument({
      kind: 'jd', title: analyzeForm.value.title.trim(),
      content: analyzeForm.value.content.trim(), source_name: '平台岗位粘贴',
    })
    analyzeOpen.value = false
    analyzeForm.value = { title: '', content: '' }
    router.push({ path: '/resume', query: { tab: 'match', jd: jd.id } })
  } catch (error) { ElMessage.error(formatApiError(error)) }
  finally { analyzeSaving.value = false }
}
</script>

<template>
  <div class="content-wrapper recruitment-page">
    <div class="page-head">
      <div>
        <h1 class="qz-page-title">平台招聘</h1>
        <p>选择招聘平台，点击卡片跳转官网完成投递；投递后可到<router-link to="/applications">投递记录</router-link>登记跟进。</p>
      </div>
      <el-button type="primary" @click="analyzeOpen = true">粘贴岗位说明并分析</el-button>
    </div>

    <div class="platform-grid">
      <a
        v-for="platform in platforms"
        :key="platform.key"
        class="qz-card platform-card"
        :href="platform.url"
        target="_blank"
        rel="noopener noreferrer"
      >
        <div class="platform-main">
          <div class="platform-head">
            <span class="platform-icon">
              <img v-if="!failedIcons[platform.key]" :src="platform.icon" :alt="platform.label" @error="failedIcons[platform.key] = true">
              <span v-else class="icon-fallback">{{ platform.label.charAt(0) }}</span>
            </span>
            <h2>{{ platform.label }}</h2>
          </div>
          <p class="platform-desc">{{ platform.desc }}</p>
        </div>
        <span class="platform-go"><el-icon><Promotion /></el-icon>前往投递</span>
      </a>
    </div>

    <el-dialog v-model="analyzeOpen" title="分析平台岗位" width="min(680px, 95vw)">
      <p class="dialog-intro">从招聘平台复制岗位名称和完整岗位说明，保存后会直接进入简历中心进行分析。</p>
      <el-form label-position="top">
        <el-form-item label="岗位名称"><el-input v-model="analyzeForm.title" maxlength="128" placeholder="例如：某公司 · 后端开发工程师" /></el-form-item>
        <el-form-item label="岗位说明"><el-input v-model="analyzeForm.content" type="textarea" :rows="12" placeholder="粘贴岗位职责、任职要求等内容" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="analyzeOpen = false">取消</el-button><el-button type="primary" :loading="analyzeSaving" @click="startAnalysis">保存并分析</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.recruitment-page { max-width: 1100px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 24px; }
.page-head p { margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.6; }
.page-head p a { color: #247a72; font-weight: 700; text-decoration: none; }
.page-head p a:hover { text-decoration: underline; }
.platform-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.platform-card { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 108px; padding: 14px 22px; color: #1d2939; text-decoration: none; transition: border-color .15s, background .15s; }
.platform-card:hover { border-color: #84cabc; background: #f6fcf9; }
.platform-main { min-width: 0; }
.platform-head { display: flex; align-items: center; gap: 12px; }
.platform-head h2 { margin: 0; font-size: 17px; }
.platform-icon { flex: none; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: #fff; border: 1px solid #e8f0ed; border-radius: 10px; }
.platform-icon img { width: 26px; height: 26px; object-fit: contain; }
.icon-fallback { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #eaf8f3; color: #1d625e; font-size: 17px; font-weight: 700; border-radius: 9px; }
.platform-desc { margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.6; }
.platform-go { flex: none; display: inline-flex; align-items: center; gap: 6px; color: #247a72; font-size: 13px; font-weight: 700; }
.dialog-intro { margin: 0 0 14px; color: #667085; font-size: 13px; line-height: 1.6; }
@media (max-width: 700px) { .platform-grid { grid-template-columns: 1fr; } .page-head { align-items: stretch; flex-direction: column; margin-bottom: 16px; } }
</style>
