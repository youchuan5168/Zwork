<script setup>
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { applicationApi } from '@/api/resources'
import { STAGES, STAGE_MAP } from '@/constants/stages'
import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 编辑时的原始记录；null 表示新增
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const store = useDataStore()
const formRef = ref()
const saving = ref(false)

const STAGE_OPTIONS = STAGES.map((s) => ({ label: s.label, value: s.key }))

const DEFAULT_FORM = {
  company_id: null,
  company_name: '',
  position: '',
  channel: '',
  apply_date: new Date().toISOString().slice(0, 10),
  current_stage: 'applied',
  notes: '',
}

const form = reactive({ ...DEFAULT_FORM })
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    if (props.record) {
      Object.assign(form, {
        company_id: props.record.company_id,
        company_name: props.record.company_name,
        position: props.record.position,
        channel: props.record.channel,
        apply_date: props.record.apply_date,
        current_stage: props.record.current_stage,
        notes: props.record.notes || '',
      })
    } else {
      Object.assign(form, { ...DEFAULT_FORM })
    }
  },
)

// 公司名下拉：公司库 + 历史记录中出现过的公司名
const companyOptions = computed(() => {
  const names = new Set(store.companies.map((c) => c.name))
  store.applications.forEach((a) => {
    if (a.company_name) names.add(a.company_name)
  })
  return [...names].sort()
})

const rules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  position: [{ required: true, message: '请输入岗位名称', trigger: 'blur' }],
  apply_date: [{ required: true, message: '选择投递日期', trigger: 'change' }],
}

function onCompanySelect(name) {
  const company = store.companies.find((c) => c.name === name)
  form.company_id = company?.id ?? null
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    // 手输的公司名在选 VALUE 时（allow-create）只触发 change，强制再同步一次 id
    const company = store.companies.find((c) => c.name === form.company_name)
    form.company_id = company?.id ?? null

    if (props.record) {
      await apiPut(props.record.id)
    } else {
      await apiPost()
    }
    ElMessage.success(props.record ? '已保存' : '已添加投递')
    visible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(formatApiError(e))
  } finally {
    saving.value = false
  }
}

async function apiPost() {
  await applicationApi.create( { ...form })
}

async function apiPut(id) {
  await applicationApi.update(id, { ...form })
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="record ? '编辑投递' : '添加投递'"
    width="520px"
    :close-on-click-modal="false"
    class="app-form-dialog"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="公司" prop="company_name">
        <el-select
          v-model="form.company_name"
          filterable
          allow-create
          default-first-option
          placeholder="选择或输入公司名"
          style="width: 100%"
          @change="onCompanySelect"
        >
          <el-option v-for="name in companyOptions" :key="name" :label="name" :value="name" />
        </el-select>
      </el-form-item>
      <el-form-item label="岗位" prop="position">
        <el-input v-model="form.position" placeholder="如：后端开发工程师" />
      </el-form-item>
      <el-form-item label="渠道">
        <el-input v-model="form.channel" placeholder="如：官网 / Boss直聘 / 内推" />
      </el-form-item>
      <el-form-item label="投递日期" prop="apply_date">
        <el-date-picker
          v-model="form.apply_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="当前阶段">
        <el-select v-model="form.current_stage" style="width: 100%">
          <el-option
            v-for="s in STAGE_OPTIONS"
            :key="s.value"
            :label="s.label"
            :value="s.value"
          />
        </el-select>
        <div class="stage-hint">
          已选：<span
            class="stage-badge"
            :style="{
              color: STAGE_MAP[form.current_stage]?.color,
              background: STAGE_MAP[form.current_stage]?.bg,
            }"
          >{{ STAGE_MAP[form.current_stage]?.label }}</span
          >
        </div>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.stage-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
