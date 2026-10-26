<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 发码/列表接口返回的通行码对象 */
  passcode: { type: Object, default: null },
  /** 手机端显示「去通行码页」 */
  showPassLink: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])
const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const qrUrl = ref('')

watch(
  () => [props.modelValue, props.passcode?.code],
  async ([open, code]) => {
    qrUrl.value = ''
    if (!open || !code) return
    try {
      qrUrl.value = await QRCode.toDataURL(String(code), {
        width: 280,
        margin: 2,
        errorCorrectionLevel: 'M'
      })
    } catch {
      qrUrl.value = ''
    }
  },
  { immediate: true }
)

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
    title="通行凭证"
    width="92%"
    class="pass-qr-dlg"
    align-center
    append-to-body
    destroy-on-close
    @closed="qrUrl = ''"
  >
    <div v-if="passcode" class="box">
      <el-alert
        type="success"
        :closable="false"
        show-icon
        title="请截图保存本页二维码"
        description="到实验室门口向门禁出示；有效期内可多次刷码，无需重新领码。"
        style="margin-bottom: 14px"
      />

      <div class="info">
        <div class="row">
          <span class="k">实验室</span>
          <span class="v">{{ passcode.lab_name || `实验室 #${passcode.lab_id || '-'}` }}</span>
        </div>
        <div v-if="passcode.lab_location" class="row">
          <span class="k">位置</span>
          <span class="v">{{ passcode.lab_location }}</span>
        </div>
        <div class="row">
          <span class="k">预约</span>
          <span class="v">#{{ passcode.reservation_id }}</span>
        </div>
        <div v-if="passcode.start_time || passcode.valid_from" class="row">
          <span class="k">时段</span>
          <span class="v mono">
            {{ passcode.start_time || passcode.valid_from }}
            ~
            {{ passcode.end_time || passcode.valid_to }}
          </span>
        </div>
      </div>

      <div class="qr-wrap">
        <img v-if="qrUrl" class="qr" :src="qrUrl" alt="通行二维码" />
        <div v-else class="qr-ph">生成中…</div>
      </div>
      <div class="code">{{ passcode.code }}</div>
      <div class="hint">二维码内容即上方字符串，扫码枪识别后由系统核验</div>
    </div>
    <template #footer>
      <el-button v-if="showPassLink" @click="goPass">去通行码页</el-button>
      <el-button type="primary" @click="close">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.box {
  text-align: center;
}
.info {
  text-align: left;
  background: #f7f8fa;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
  font-size: 13px;
}
.row {
  display: flex;
  gap: 10px;
  margin: 4px 0;
  line-height: 1.45;
}
.k {
  flex: 0 0 52px;
  color: #888;
}
.v {
  flex: 1;
  color: #303133;
  word-break: break-all;
}
.mono {
  font-size: 12px;
}
.qr-wrap {
  display: flex;
  justify-content: center;
  margin: 8px 0;
}
.qr {
  width: min(280px, 72vw);
  height: auto;
  aspect-ratio: 1;
  background: #fff;
}
.qr-ph {
  width: min(280px, 72vw);
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  color: #999;
  border-radius: 8px;
}
.code {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #07c160;
  margin-top: 8px;
  word-break: break-all;
}
.hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>

<style>
/* 弹窗最大宽度，桌面不撑满 */
.pass-qr-dlg.el-dialog {
  max-width: 420px;
}
</style>
