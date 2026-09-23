<script setup>
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { authApi } from '@/api/resources'
import { useRouter } from 'vue-router'

import { useDataStore } from '@/stores/data'
import { formatApiError } from '@/utils/errors'
import BrandMark from '@/components/BrandMark.vue'

const router = useRouter()
const store = useDataStore()

const mode = ref('login') // login | register
const formRef = ref()
const loading = ref(false)
const form = ref({ username: '', password: '' })

const policy = ref({ can_register: false, registration_open: false })
onMounted(async () => {
  try { policy.value = await authApi.policy() } catch (e) { ElMessage.error(formatApiError(e)) }
})
const rules = computed(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: mode.value === 'register' ? 15 : 1, message: '注册密码至少 15 位（UTF-8 最多 72 字节）', trigger: 'blur' },
  ],
}))

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    if (mode.value === 'login') {
      await store.login(form.value.username, form.value.password)
    } else {
      await store.register(form.value.username, form.value.password)
    }
    ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
    router.push({ name: 'agent' })
  } catch (e) {
    ElMessage.error(formatApiError(e))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-title">
        <div class="login-brand"><BrandMark /><h1><span>Z</span><i>w</i>ork</h1></div>
        <p>找工作，更有章法</p>
      </div>

      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" :disabled="!policy.can_register" />
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="mode === 'register' ? '注册密码至少 15 位' : '密码'"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="submit">
          {{ mode === 'login' ? '登 录' : '注册并登录' }}
        </el-button>
      </el-form>

      <p v-if="mode === 'register'" class="tip">
        用户名为 2–64 位英文字母、数字、点、下划线或短横线。数据仅归当前账号所有。
        {{ policy.registration_open ? '管理员已开放注册。' : '仅允许初始化首个账号，之后关闭注册。' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 16% 20%, #defaf5, transparent 42%), radial-gradient(circle at 85% 78%, #f0fbdc, transparent 48%), #f8fefa;
  padding: 16px;
}

.login-card {
  width: 380px;
  max-width: 100%;
  background: #fff;
  border: 1px solid #dcece7;
  border-radius: 18px;
  padding: 34px 30px;
  box-shadow: 0 20px 55px rgba(42, 100, 90, 0.09);
}

.login-title {
  text-align: center;
  margin-bottom: 18px;
}

.login-brand { display: flex; justify-content: center; align-items: center; gap: 7px; margin-bottom: 8px; color: #111827; }
.login-brand :deep(.brand-mark) { width: 35px; height: 35px; }

.login-title h1 {
  margin: 0 0 6px;
  font-size: 27px;
  letter-spacing: -.055em;
  color: #111827;
}
.login-title h1 span { color: #269b86; }
.login-title h1 i { color: #d9784e; font-style: normal; }

.login-title p {
  margin: 0;
  font-size: 13px;
  color: #667085;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
}

.tip {
  margin-top: 14px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}
</style>
