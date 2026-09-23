<script setup>
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { companyApi } from '@/api/resources'
import StageBadge from '@/components/StageBadge.vue'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const store = useDataStore()

const formOpen = ref(false)
const editing = ref(null)
const formRef = ref()
const form = reactive({ name: '', industry: '', website: '', notes: '' })

const rules = {
  name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
}

onMounted(() => {
  if (!store.loaded) store.fetchAll()
})

// 每家公司的投递汇总
const rows = computed(() => {
  return store.companies.map((c) => {
    const apps = store.applications.filter(
      (a) => a.company_id === c.id || a.company_name === c.name,
    )
    const bestStage = ['offer', 'interview', 'written_test', 'screening', 'applied', 'not_started']
    const stage = apps
      .map((a) => a.current_stage)
      .sort((a, b) => bestStage.indexOf(a) - bestStage.indexOf(b))[0]
    return { ...c, appCount: apps.length, bestStage: stage }
  })
})

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', industry: '', website: '', notes: '' })
  formOpen.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    industry: row.industry,
    website: row.website,
    notes: row.notes,
  })
  formOpen.value = true
}

async function submit() {
  await formRef.value.validate()
  if (editing.value) {
    await companyApi.update(editing.value.id, { ...form })
    ElMessage.success('已保存')
  } else {
    await companyApi.create( { ...form })
    ElMessage.success('已添加公司')
  }
  formOpen.value = false
  await store.fetchAll()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除「${row.name}」吗？（已有关联投递记录会保留公司名快照）`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await companyApi.remove(row.id)
  ElMessage.success('已删除')
  await store.fetchAll()
}
</script>

<template>
  <div class="content-wrapper">
    <div class="header-row">
      <h2 class="qz-page-title">公司管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加公司</el-button>
    </div>

    <div class="qz-card">
      <el-table :data="rows" style="width: 100%">
        <el-table-column prop="name" label="公司" min-width="140" />
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column prop="website" label="官网" min-width="160">
          <template #default="{ row }">
            <el-link v-if="row.website" :href="row.website" target="_blank" type="primary">
              {{ row.website }}
            </el-link>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="投递数" width="90" align="center">
          <template #default="{ row }">{{ row.appCount }}</template>
        </el-table-column>
        <el-table-column label="最好进展" width="110">
          <template #default="{ row }">
            <StageBadge v-if="row.bestStage" :stage-key="row.bestStage" />
            <span v-else class="muted">未投递</span>
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
      <el-empty v-if="!rows.length" description="还没有添加公司，点击右上角添加" :image-size="72" />
    </div>

    <el-dialog
      v-model="formOpen"
      :title="editing ? '编辑公司' : '添加公司'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="70px">
        <el-form-item label="公司" prop="name">
          <el-input v-model="form.name" placeholder="如：腾讯" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="form.industry" placeholder="如：互联网 / 游戏" />
        </el-form-item>
        <el-form-item label="官网">
          <el-input v-model="form.website" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="内推码、岗位偏好等" />
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

.muted {
  color: #c0c4cc;
}
</style>
