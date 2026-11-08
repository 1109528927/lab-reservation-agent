<script setup>
/**
 * 领通行码一步完成：弹须知 → 同意 → 自动签署并发码 → 展示二维码
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import request, { getErrorMessage } from '@/utils/request'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  reservationId: { type: Number, default: null },
  showPassLink: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'done'])

const router = useRouter()
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const step = ref('safety') // safety | qr
const safetyText = ref('')
const loading = ref(false)
const agreeing = ref(false)
const passcode = ref(null)
const qrUrl = ref('')

const loadSafety = async () => {
  loading.value = true
  safetyText.value = ''
  try {
    const res = await request.get('/api/access/safety-text')
    safetyText.value =
      res.data?.data?.text ||
      '进入实验室须遵守安全规定：禁止违规用电、食品饮料远离设备、离开前断电关窗。'
  } catch {
    safetyText.value =
      '进入实验室须遵守安全规定：禁止违规用电、食品饮料远离设备、离开前断电关窗。本人已阅读并同意。'
  } finally {
    loading.value = false
  }
}

const renderQr = async (code) => {
  qrUrl.value = ''
  if (!code) return
  try {
    qrUrl.value = await QRCode.toDataURL(String(code), {
      width: 280,
      margin: 2,
      errorCorrectionLevel: 'M'
    })
  } catch {
    qrUrl.value = ''
  }
}

watch(
  () => [props.modelValue, props.reservationId],
  async ([open]) => {
    if (!open) return
    step.value = 'safety'
    passcode.value = null
    qrUrl.value = ''
    agreeing.value = false
    await loadSafety()
  }
)

const agreeAndIssue = async () => {
  const id = props.reservationId
  if (!id) {
    ElMessage.warning('缺少预约')
    return
  }
  agreeing.value = true
  try {
    await request.post('/api/access/safety/ack', { reservation_id: id })
    const res = await request.post('/api/access/passcode/issue', { reservation_id: id })
    const data = res.data?.data
    if (!data?.code) {
      ElMessage.error('发码失败')
      return
    }
    passcode.value = data
    step.value = 'qr'
    await nextTick()
    await renderQr(data.code)
    emit('done', data)
    ElMessage.success(res.data?.message || '已领码，请截图保存')
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '领取失败'))
  } finally {
    agreeing.value = false
  }
}

const close = () => {
  visible.value = false
}

const goPass = () => {
  visible.value = false
  router.push('/m/pass')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="step === 'safety' ? '领取通行码 · 安全须知' : '通行码二维码'"
    width="420px"
    append-to-body
    @closed="step = 'safety'"
  >
    <div v-loading="loading">
      <template v-if="step === 'safety'">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="同意须知后将自动发放通行码二维码"
          style="margin-bottom: 12px"
        />
        <div class="safety">{{ safetyText }}</div>
      </template>
      <template v-else-if="passcode">
        <el-alert
          type="success"
          :closable="false"
          show-icon
          title="到实验室门口向门禁出示；有效期内可多次刷码"
          style="margin-bottom: 12px"
        />
        <div class="meta">
          <div>实验室：{{ passcode.lab_name || `#${passcode.lab_id}` }}</div>
          <div>预约 #{{ passcode.reservation_id }}</div>
          <div v-if="passcode.valid_from || passcode.start_time">
            有效：{{ passcode.valid_from || passcode.start_time }} ~
            {{ passcode.valid_to || passcode.end_time }}
          </div>
        </div>
        <div class="qr-wrap">
          <img v-if="qrUrl" :src="qrUrl" alt="通行码二维码" />
          <div v-else class="code-only">{{ passcode.code }}</div>
        </div>
        <div class="code">{{ passcode.code }}</div>
      </template>
    </div>
    <template #footer>
      <template v-if="step === 'safety'">
        <el-button @click="close">取消</el-button>
        <el-button type="success" :loading="agreeing" @click="agreeAndIssue">
          我已阅读并同意，领取通行码
        </el-button>
      </template>
      <template v-else>
        <el-button v-if="showPassLink" @click="goPass">去通行码页</el-button>
        <el-button type="primary" @click="close">完成</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.safety {
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 14px;
  color: #303133;
  max-height: 280px;
  overflow-y: auto;
  padding: 8px 4px;
}
.meta {
  font-size: 13px;
  color: #606266;
  margin-bottom: 10px;
  line-height: 1.5;
}
.qr-wrap {
  display: flex;
  justify-content: center;
  margin: 8px 0;
}
.qr-wrap img {
  width: 280px;
  height: 280px;
}
.code-only,
.code {
  text-align: center;
  font-family: ui-monospace, monospace;
  word-break: break-all;
  font-size: 13px;
  color: #303133;
  margin-top: 8px;
}
</style>
