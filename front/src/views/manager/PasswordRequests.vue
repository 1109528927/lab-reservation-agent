<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const loading = ref(false)
const items = ref([])
const adminEmail = ref('')
const filterStatus = ref('')
const dialog = ref(false)
const current = ref(null)
const form = reactive({
  action: 'done',
  new_password: 'Lab@123456',
  admin_note: ''
})

const statusLabel = (s) =>
  ({ pending: '待处理', done: '已处理', rejected: '已驳回' }[s] || s)

const load = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/user/admin/password-requests', {
      params: filterStatus.value ? { status: filterStatus.value } : {}
    })
    items.value = res.data?.data?.items || []
    adminEmail.value = res.data?.data?.admin_qq_email || ''
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const open = (row) => {
  current.value = row
  form.action = 'done'
  form.new_password = 'Lab@123456'
  form.admin_note = ''
  dialog.value = true
}

const save = async () => {
  if (form.action === 'done' && form.new_password && form.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位；若不重置密码可留空并改备注')
  }
  try {
    const payload = {
      action: form.action,
      admin_note: form.admin_note || null,
      new_password:
        form.action === 'done' && form.new_password.trim()
          ? form.new_password.trim()
          : null
    }
    const res = await request.post(
      `/api/user/admin/password-requests/${current.value.id}/resolve`,
      payload
    )
    ElMessage.success(res.data?.message || '已处理')
    dialog.value = false
    await load()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '处理失败'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 8px; flex-wrap: wrap">
      <div>
        <h3 style="margin: 0">忘记密码申请</h3>
        <p v-if="adminEmail" style="margin: 6px 0 0; color: #666; font-size: 13px">
          登录页公示邮箱：{{ adminEmail }}（可用邮件或本页工单两种渠道）
        </p>
      </div>
      <div style="display: flex; gap: 8px">
        <el-select v-model="filterStatus" clearable placeholder="状态" style="width: 120px" @change="load">
          <el-option label="待处理" value="pending" />
          <el-option label="已处理" value="done" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="items" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="账号" min-width="110" />
      <el-table-column prop="employee_no" label="学号" min-width="110" />
      <el-table-column prop="contact" label="联系方式" min-width="120" show-overflow-tooltip />
      <el-table-column prop="reason" label="说明" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">{{ statusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column prop="create_at" label="提交时间" min-width="160" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'pending'"
            link
            type="primary"
            @click="open(row)"
          >
            处理
          </el-button>
          <span v-else style="color: #999">—</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="处理找回申请" width="480px">
      <el-form label-position="top" v-if="current">
        <p style="margin-top: 0">
          账号 <strong>{{ current.username }}</strong>
          <span v-if="current.employee_no"> / 学号 {{ current.employee_no }}</span>
        </p>
        <el-form-item label="处理方式">
          <el-radio-group v-model="form.action">
            <el-radio label="done">通过并重置密码</el-radio>
            <el-radio label="rejected">驳回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.action === 'done'" label="新密码（将写回该账号）">
          <el-input v-model="form.new_password" show-password />
        </el-form-item>
        <el-form-item label="备注（可选）">
          <el-input v-model="form.admin_note" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
