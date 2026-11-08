<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request, { getErrorMessage } from '@/utils/request'

const tab = ref('list')
const loading = ref(false)
const items = ref([])
const keyword = ref('')

const createOpen = ref(false)
const createForm = reactive({
  username: '',
  employee_no: '',
  password: 'Lab@123456'
})

const editOpen = ref(false)
const editTarget = ref(null)
const editForm = reactive({
  employee_no: '',
  password: ''
})

const bulkLoading = ref(false)
const bulkForm = reactive({
  employee_nos: '',
  default_password: 'Lab@123456'
})
const bulkResult = ref(null)

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/user/admin/students', {
      params: keyword.value.trim() ? { q: keyword.value.trim() } : {}
    })
    items.value = res.data?.data?.items || []
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  createForm.username = ''
  createForm.employee_no = ''
  createForm.password = 'Lab@123456'
  createOpen.value = true
}

const submitCreate = async () => {
  if (!createForm.username.trim() || !createForm.password.trim()) {
    ElMessage.warning('请填写账号和密码')
    return
  }
  if (createForm.password.trim().length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  try {
    await request.post('/api/user/admin/students', {
      username: createForm.username.trim(),
      password: createForm.password.trim(),
      employee_no: createForm.employee_no.trim() || null
    })
    ElMessage.success('已创建')
    createOpen.value = false
    tab.value = 'list'
    await loadList()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '创建失败'))
  }
}

const openEdit = (row) => {
  editTarget.value = row
  editForm.employee_no = row.employee_no || ''
  editForm.password = ''
  editOpen.value = true
}

const submitEdit = async () => {
  if (!editTarget.value) return
  const payload = {}
  const no = editForm.employee_no.trim()
  if (no && no !== editTarget.value.employee_no) {
    payload.employee_no = no
  }
  if (editForm.password.trim()) {
    if (editForm.password.trim().length < 6) {
      ElMessage.warning('新密码至少 6 位')
      return
    }
    payload.password = editForm.password.trim()
  }
  if (!payload.employee_no && !payload.password) {
    ElMessage.warning('请修改学号或填写新密码')
    return
  }
  try {
    await request.put(`/api/user/admin/students/${editTarget.value.id}`, payload)
    ElMessage.success('已更新')
    editOpen.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '更新失败'))
  }
}

const submitBulk = async () => {
  if (!bulkForm.employee_nos.trim()) {
    ElMessage.warning('请粘贴学号清单')
    return
  }
  if (bulkForm.default_password.trim().length < 6) {
    ElMessage.warning('默认密码至少 6 位')
    return
  }
  bulkLoading.value = true
  bulkResult.value = null
  try {
    const res = await request.post('/api/user/admin/bulk-students', {
      employee_nos: bulkForm.employee_nos,
      default_password: bulkForm.default_password.trim()
    })
    bulkResult.value = res.data?.data || null
    ElMessage.success(res.data?.message || '导入完成')
    await loadList()
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '导入失败'))
  } finally {
    bulkLoading.value = false
  }
}

const statusType = (s) =>
  ({ created: 'success', skipped: 'warning', failed: 'danger' }[s] || 'info')
const statusLabel = (s) =>
  ({ created: '已创建', skipped: '已跳过', failed: '失败' }[s] || s)

onMounted(loadList)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 8px; flex-wrap: wrap">
      <h3 style="margin: 0">学生账号管理</h3>
      <el-button type="primary" @click="openCreate">新建学生账号</el-button>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="账号列表" name="list">
        <div style="display: flex; gap: 8px; margin-bottom: 12px">
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索账号 / 学号"
            style="max-width: 260px"
            @keyup.enter="loadList"
          />
          <el-button @click="loadList">查询</el-button>
        </div>
        <el-table v-loading="loading" :data="items" border stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="登录账号" min-width="120" />
          <el-table-column prop="employee_no" label="学号" min-width="120" />
          <el-table-column prop="credit_score" label="信用分" width="90" />
          <el-table-column prop="create_at" label="创建时间" min-width="160" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">修改</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="批量开户" name="bulk">
        <p class="hint">
          从教务名单复制学号粘贴。规则：<strong>学号 = 登录账号</strong>，统一初始密码；已存在则跳过。
        </p>
        <el-form label-position="top" style="max-width: 720px">
          <el-form-item label="学号清单（换行 / 逗号 / 分号均可）">
            <el-input
              v-model="bulkForm.employee_nos"
              type="textarea"
              :rows="10"
              placeholder="例如：&#10;20230001&#10;20230002"
            />
          </el-form-item>
          <el-form-item label="统一初始密码">
            <el-input
              v-model="bulkForm.default_password"
              style="max-width: 280px"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="bulkLoading" @click="submitBulk">
              一键注册
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="bulkResult" style="margin-top: 16px">
          <el-alert
            :title="`合计 ${bulkResult.total}：新建 ${bulkResult.created}，跳过 ${bulkResult.skipped}，失败 ${bulkResult.failed}`"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 12px"
          />
          <el-table :data="bulkResult.items || []" border stripe max-height="360">
            <el-table-column prop="employee_no" label="学号" min-width="120" />
            <el-table-column prop="username" label="登录账号" min-width="120" />
            <el-table-column label="结果" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="说明" min-width="140" show-overflow-tooltip />
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="createOpen" title="新建学生账号" width="440px">
      <el-form label-position="top">
        <el-form-item label="登录账号" required>
          <el-input v-model="createForm.username" maxlength="50" />
        </el-form-item>
        <el-form-item label="学号（可空，默认与账号相同）">
          <el-input v-model="createForm.employee_no" maxlength="50" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="createForm.password" show-password maxlength="128" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editOpen" title="修改学生账号" width="440px">
      <el-form v-if="editTarget" label-position="top">
        <p style="margin-top: 0">
          账号 <strong>{{ editTarget.username }}</strong>（登录名不可改，防历史数据乱）
        </p>
        <el-form-item label="学号">
          <el-input v-model="editForm.employee_no" maxlength="50" />
        </el-form-item>
        <el-form-item label="重置密码（留空则不改）">
          <el-input
            v-model="editForm.password"
            show-password
            placeholder="填写则覆盖为新密码"
            maxlength="128"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hint {
  color: #666;
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 16px;
  max-width: 720px;
}
</style>
