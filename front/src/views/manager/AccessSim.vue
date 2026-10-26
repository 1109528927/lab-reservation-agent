<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PasscodeQrDialog from '@/components/PasscodeQrDialog.vue'
import request, { getErrorMessage } from '@/utils/request'

const code = ref('')
const deviceId = ref('')
const devices = ref([])
const loading = ref(false)
const result = ref(null)
const myCodes = ref([])
const logs = ref([])

const user = (() => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
})()
const isAdmin = user.role === 'admin'


const loadDevices = async () => {
  try {
    const res = await request.get('/api/access/devices')
    devices.value = res.data?.data?.items || []
    if (devices.value.length && !deviceId.value) {
      deviceId.value = devices.value[0].device_id
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载门禁设备失败'))
  }
}

const loadMine = async () => {
  try {
    const res = await request.get('/api/access/passcode/mine')
    myCodes.value = res.data?.data?.items || []
  } catch {
    /* ignore */
  }
}

const loadLogs = async () => {
  if (!isAdmin) return
  try {
    const res = await request.get('/api/access/logs', { params: { limit: 30 } })
    logs.value = res.data?.data?.items || []
  } catch {
    /* ignore */
  }
}

const verify = async () => {
  loading.value = true
  result.value = null
  try {
    const res = await request.post('/api/access/verify', {
      code: code.value,
      device_id: deviceId.value
    })
    result.value = res.data
    const allowed = res.data?.data?.allowed
    const buzz = res.data?.data?.buzz
    if (allowed) {
      const tip = res.data?.data?.notified
        ? '已写入站内消息「已扫码完成」；有效期内码仍可再用'
        : '通行允许（再次刷码）；有效期内码仍可用'
      ElMessage.success(`${tip}（模拟蜂鸣器：${buzz || 'short'}）`)
    } else {
      ElMessage.warning(
        `${res.data?.data?.reason || '拒绝'}（模拟蜂鸣器：${buzz || 'long'}）`
      )
    }
    loadLogs()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '核验失败'))
  } finally {
    loading.value = false
  }
}

const useCode = (c) => {
  code.value = c
}

const passDlg = ref(false)
const passPayload = ref(null)
const showQr = (row) => {
  passPayload.value = row
  passDlg.value = true
}

onMounted(() => {
  loadDevices()
  loadMine()
  loadLogs()
})
</script>

<template>
  <div>
    <PasscodeQrDialog v-model="passDlg" :passcode="passPayload" />
    <h2>模拟门禁</h2>
    <p class="sub">
      每台设备绑定一间实验室。预约实验室 A 的码，用门口 B 的 device_id 核验会被拒绝。
    </p>

    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>我的通行码</template>
      <el-table :data="myCodes" empty-text="暂无：请在预约页签署须知并领码" size="small">
        <el-table-column prop="code" label="凭证码" width="140" />
        <el-table-column prop="lab_name" label="实验室" min-width="120" />
        <el-table-column prop="lab_location" label="位置" min-width="100" />
        <el-table-column prop="reservation_id" label="预约ID" width="90" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="valid_from" label="起" />
        <el-table-column prop="valid_to" label="止" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="success" @click="showQr(row)">二维码</el-button>
            <el-button link type="primary" @click="useCode(row.code)">填入</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-form label-width="110px" style="max-width: 560px">
      <el-form-item label="门口设备">
        <el-select v-model="deviceId" style="width: 100%" placeholder="选择门口">
          <el-option
            v-for="d in devices"
            :key="d.device_id"
            :label="`${d.device_id} · ${d.name || ''}（实验室#${d.lab_id} ${d.lab_name || ''}）`"
            :value="d.device_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="凭证码">
        <el-input v-model="code" placeholder="扫码或粘贴通行码" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="verify">模拟扫码核验</el-button>
      </el-form-item>
    </el-form>

    <el-card v-if="result" shadow="never" style="margin-bottom: 16px">
      <pre>{{ result }}</pre>
    </el-card>

    <el-card v-if="isAdmin" shadow="never">
      <template #header>通行流水（管理员）</template>
      <el-table :data="logs" size="small" empty-text="暂无流水">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="code" label="码" width="120" />
        <el-table-column prop="device_id" label="设备" width="120" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">{{ row.allowed ? '允许' : '拒绝' }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" />
        <el-table-column prop="create_at" label="时间" width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.sub {
  color: #606266;
  margin: 8px 0 16px;
}
pre {
  white-space: pre-wrap;
  margin: 0;
}
</style>
