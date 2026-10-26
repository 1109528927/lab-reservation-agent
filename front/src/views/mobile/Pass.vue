<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import PasscodeQrDialog from '@/components/PasscodeQrDialog.vue'
import request, { getErrorMessage } from '@/utils/request'

const items = ref([])
const loading = ref(false)
/** @type {import('vue').Ref<Record<string, string>>} */
const qrMap = ref({})

const load = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/access/passcode/mine')
    items.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const buildQr = async (list) => {
  const next = {}
  for (const p of list) {
    if (!p?.code) continue
    try {
      next[p.code] = await QRCode.toDataURL(String(p.code), {
        width: 220,
        margin: 2,
        errorCorrectionLevel: 'M'
      })
    } catch {
      /* 单条失败不影响其它 */
    }
  }
  qrMap.value = next
}

watch(items, (list) => {
  buildQr(list || [])
}, { immediate: true })

const copy = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('已复制')
  } catch {
    ElMessage.info(code)
  }
}

const passDlg = ref(false)
const passPayload = ref(null)
const openDlg = (p) => {
  passPayload.value = p
  passDlg.value = true
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page">
    <PasscodeQrDialog v-model="passDlg" :passcode="passPayload" show-pass-link />
    <div class="tip">
      向门禁出示下方<strong>二维码</strong>（内容即通行字符串）。领码时会弹出大图提示截图；也可点卡片再次打开。
      首次刷码成功后「消息」会提示「已扫码完成」；<strong>有效期内仍可再用</strong>。
    </div>
    <div v-if="!items.length" class="empty card">暂无通行码，请先在「预约」里签须知并领码</div>
    <div v-for="p in items" :key="p.id" class="card" @click="openDlg(p)">
      <div v-if="(p.scan_ok_count || 0) > 0" class="badge">已扫码 {{ p.scan_ok_count }} 次 · 有效期内可再用</div>
      <div v-if="p.lab_name" class="lab">{{ p.lab_name }}<span v-if="p.lab_location"> · {{ p.lab_location }}</span></div>
      <div class="qr-wrap">
        <img v-if="qrMap[p.code]" class="qr" :src="qrMap[p.code]" :alt="`通行码 ${p.code}`" />
        <div v-else class="qr-ph">生成中…</div>
      </div>
      <div class="code">{{ p.code }}</div>
      <div class="meta">预约 #{{ p.reservation_id }} · {{ p.status }}</div>
      <div class="meta">{{ p.valid_from }} ~ {{ p.valid_to }}</div>
      <div v-if="p.last_allowed_at" class="meta ok">最近成功：{{ p.last_allowed_at }}</div>
      <el-button type="success" plain style="width: 100%; margin-top: 10px" @click.stop="copy(p.code)">
        复制凭证码
      </el-button>
    </div>
    <el-button style="width: 100%" @click="load">刷新</el-button>
  </div>
</template>

<style scoped>
.tip {
  font-size: 13px;
  color: #666;
  margin-bottom: 12px;
  line-height: 1.5;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
}
.badge {
  font-size: 12px;
  color: #07c160;
  background: #e8f8ef;
  border-radius: 6px;
  padding: 6px 10px;
  text-align: center;
  margin-bottom: 10px;
}
.lab {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  text-align: center;
  margin-bottom: 8px;
}
.meta.ok {
  color: #07c160;
}
.qr-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}
.qr {
  width: 220px;
  height: 220px;
  image-rendering: pixelated;
  background: #fff;
}
.qr-ph {
  width: 220px;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 13px;
  background: #f5f5f5;
  border-radius: 8px;
}
.code {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
  text-align: center;
  color: #07c160;
  margin-bottom: 8px;
  word-break: break-all;
}
.meta {
  font-size: 12px;
  color: #888;
  text-align: center;
  margin-top: 2px;
}
.empty {
  text-align: center;
  color: #999;
}
</style>
