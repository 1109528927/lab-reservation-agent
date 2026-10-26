<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const code = ref('')
const deviceId = ref('')
const devices = ref([])
const loading = ref(false)
const result = ref(null)

const loadDevices = async () => {
  try {
    const res = await request.get('/api/access/devices')
    devices.value = res.data?.data?.items || []
    if (devices.value.length && !deviceId.value) {
      deviceId.value = devices.value[0].device_id
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载门禁列表失败'))
  }
}

const verify = async () => {
  if (!code.value.trim()) {
    ElMessage.warning('请输入凭证码')
    return
  }
  if (!deviceId.value) {
    ElMessage.warning('请选择门口设备')
    return
  }
  loading.value = true
  result.value = null
  try {
    const res = await request.post('/api/access/verify', {
      code: code.value.trim(),
      device_id: deviceId.value
    })
    result.value = res.data
    if (res.data?.data?.allowed) {
      ElMessage.success('通行允许（本实验室 · 模拟短鸣）')
    } else {
      ElMessage.warning(res.data?.data?.reason || '拒绝（模拟长鸣）')
    }
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '核验失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadDevices)
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="card-t">模拟扫码通行</div>
      <p class="tip">
        每台硬件只对应一间实验室。预约实验室 A 的码，在门口 B 刷会被拒绝。
      </p>
      <div class="label">门口（设备）</div>
      <el-select v-model="deviceId" style="width: 100%; margin-bottom: 10px" placeholder="选择门口">
        <el-option
          v-for="d in devices"
          :key="d.device_id"
          :label="`${d.name || d.device_id}（实验室#${d.lab_id} ${d.lab_name || ''}）`"
          :value="d.device_id"
        />
      </el-select>
      <div class="label">通行码</div>
      <el-input v-model="code" placeholder="粘贴通行码" style="margin-bottom: 10px" />
      <el-button type="success" style="width: 100%" :loading="loading" @click="verify">
        核验
      </el-button>
    </div>
    <div v-if="result" class="card">
      <pre>{{ result }}</pre>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}
.card-t {
  font-weight: 600;
  margin-bottom: 6px;
}
.tip {
  font-size: 12px;
  color: #888;
  margin-bottom: 12px;
  line-height: 1.5;
}
.label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
pre {
  white-space: pre-wrap;
  margin: 0;
  font-size: 12px;
}
</style>
