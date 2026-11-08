<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import router from '@/router'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

const adminQqEmail = ref('admin@qq.com')
const forgotOpen = ref(false)
const forgotLoading = ref(false)
const forgot = reactive({
  username: '',
  employee_no: '',
  contact: '',
  reason: ''
})

const loadPasswordHelp = async () => {
  try {
    const res = await request.get('/api/user/password-help')
    adminQqEmail.value = res.data?.data?.admin_qq_email || adminQqEmail.value
  } catch {
    /* 登录页兜底展示默认邮箱 */
  }
}

const openForgot = () => {
  forgot.username = form.username || ''
  forgot.employee_no = ''
  forgot.contact = ''
  forgot.reason = '忘记密码，申请重置'
  forgotOpen.value = true
}

const submitForgot = async () => {
  if (!forgot.username.trim()) {
    ElMessage.warning('请填写登录账号')
    return
  }
  forgotLoading.value = true
  try {
    const res = await request.post('/api/user/forgot-password', {
      username: forgot.username.trim(),
      employee_no: forgot.employee_no.trim() || null,
      contact: forgot.contact.trim() || null,
      reason: forgot.reason.trim() || null
    })
    ElMessage.success(res.data?.message || '申请已提交')
    forgotOpen.value = false
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '提交失败'))
  } finally {
    forgotLoading.value = false
  }
}

onMounted(loadPasswordHelp)

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
    // 按角色进入对应端；账号由管理端建档，使用默认密码登录
    if (role === 'admin' || role === 'teacher') {
      router.push('/manager/agent')
    } else {
      router.push('/m/agent')
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="box">
      <h3>智能实验室预约通行 · 登录</h3>
      <el-form @submit.prevent="login">
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
            @keyup.enter="login"
          />
        </el-form-item>
        <el-button
          size="large"
          type="primary"
          style="width: 100%"
          :loading="loading"
          native-type="submit"
          @click="login"
        >
          登 录
        </el-button>
        <div class="login-extra">
          <a href="#" @click.prevent="openForgot">忘记密码？</a>
        </div>
        <p class="admin-mail">
          管理员 QQ 邮箱：
          <a :href="'mailto:' + adminQqEmail">{{ adminQqEmail }}</a>
        </p>
      </el-form>

      <el-dialog v-model="forgotOpen" title="忘记密码申请" width="400px" append-to-body>
        <p class="forgot-tip">
          可先邮件联系 <strong>{{ adminQqEmail }}</strong>，或在此提交申请由管理员重置密码。
        </p>
        <el-form label-position="top">
          <el-form-item label="登录账号" required>
            <el-input v-model="forgot.username" placeholder="你的账号" />
          </el-form-item>
          <el-form-item label="学号/工号（可选）">
            <el-input v-model="forgot.employee_no" />
          </el-form-item>
          <el-form-item label="联系方式（手机/QQ，可选）">
            <el-input v-model="forgot.contact" />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="forgot.reason" type="textarea" rows="2" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="forgotOpen = false">取消</el-button>
          <el-button type="primary" :loading="forgotLoading" @click="submitForgot">
            提交申请
          </el-button>
        </template>
      </el-dialog>
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
.login-extra {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  font-size: 13px;
}
.admin-mail {
  margin: 14px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.admin-mail a {
  font-size: 12px;
}
.forgot-tip {
  margin: 0 0 12px;
  font-size: 13px;
  color: #606266;
  text-align: left;
  line-height: 1.5;
}
</style>
