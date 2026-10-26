<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import router from '@/router'
import request, { getErrorMessage } from '@/utils/request'

const isLogin = ref(true)
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
  repassword: '',
  employee_no: ''
})

const toggleMode = () => {
  isLogin.value = !isLogin.value
  form.password = ''
  form.repassword = ''
}

const login = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    const res = await request.post('/api/user/login', {
      username: form.username,
      password: form.password
    })
    const body = res.data
    if (body.code !== 200) {
      ElMessage.error(body.message || '登录失败')
      return
    }
    localStorage.setItem('token', body.data.token)
    localStorage.setItem('userInfo', JSON.stringify(body.data.user))
    ElMessage.success(body.message || '登录成功')
    const role = body.data.user?.role
    // 学生 → 移动端；老师 → 实验室预约；学校管理 → 看板首页
    if (role === 'admin') {
      router.push('/manager/home')
    } else if (role === 'teacher') {
      router.push('/manager/lab')
    } else {
      router.push('/m/home')
    }

  } catch (e) {
    ElMessage.error(getErrorMessage(e, '登录失败'))
  } finally {
    loading.value = false
  }
}

const register = async () => {
  if (!form.username?.trim() || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  if (form.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (!form.repassword) {
    ElMessage.warning('请再次输入确认密码')
    return
  }
  if (form.password !== form.repassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    const res = await request.post('/api/user/register', {
      username: form.username.trim(),
      password: form.password,
      repassword: form.repassword,
      employee_no: form.employee_no?.trim() || undefined
    })

    const body = res.data
    if (body.code !== 200) {
      ElMessage.error(body.message || '注册失败')
      return
    }
    ElMessage.success(body.message || '注册成功，请登录')
    isLogin.value = true
    form.password = ''
    form.repassword = ''
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '注册失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="box">
      <h3>智能实验室预约通行 · {{ isLogin ? '登录' : '注册' }}</h3>
      <el-form v-if="isLogin">
        <el-form-item>
          <el-input
            v-model="form.username"
            size="large"
            placeholder="请输入账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          size="large"
          type="primary"
          style="width: 100%"
          :loading="loading"
          @click="login"
        >
          登 录
        </el-button>
        <div style="text-align: right; margin-top: 20px">
          <a href="#" @click.prevent="toggleMode">还没有账号？请点击注册</a>
        </div>
        <div class="entry-links">
          <a href="#" @click.prevent="router.push('/m/home')">学生端（小程序态）</a>
          <span>·</span>
          <a href="#" @click.prevent="router.push('/manager/home')">管理端</a>
        </div>
      </el-form>

      <el-form v-else>
        <el-form-item>
          <el-input
            v-model="form.username"
            size="large"
            placeholder="请输入注册账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.employee_no"
            size="large"
            placeholder="学号/工号（可空，自动生成）"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            placeholder="请输入注册密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.repassword"
            type="password"
            size="large"
            placeholder="请重新输入注册密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          size="large"
          type="primary"
          style="width: 100%"
          :loading="loading"
          @click="register"
        >
          注 册
        </el-button>
        <div style="text-align: right; margin-top: 20px">
          <a href="#" @click.prevent="toggleMode">已有账号？请登录</a>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(160deg, #e8f5f0 0%, #f5f7fa 45%, #eef2f7 100%);
}
.box {
  width: 380px;
  padding: 32px 28px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  text-align: center;
}
.box h3 {
  margin: 0 0 24px;
  font-size: 22px;
  font-weight: 600;
}
.box a {
  color: var(--el-color-primary);
  text-decoration: none;
  cursor: pointer;
  font-size: 14px;
}
.box a:hover {
  text-decoration: underline;
}
.entry-links {
  margin-top: 16px;
  font-size: 13px;
  color: #909399;
  display: flex;
  justify-content: center;
  gap: 8px;
}
.entry-links a {
  color: #07c160;
}
</style>

