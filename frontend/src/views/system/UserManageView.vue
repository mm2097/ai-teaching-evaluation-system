<!--
  用户与权限管理页面
  支持用户 CRUD、角色分配与账号启停
  数据走后端 /api/users
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { userApi } from '@/api/users'
import { RoleLabels } from '@/types'
import type { SystemUser, UserRole } from '@/types'

/** 用户列表 */
const userList = ref<SystemUser[]>([])
const keyword = ref('')
const loading = ref(false)

/** 对话框 */
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const form = ref({
  id: 0,
  username: '',
  name: '',
  role: 'teacher' as UserRole,
  department: '',
  status: true,
})

/** 加载用户列表 */
async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    userList.value = await userApi.list()
  } finally {
    loading.value = false
  }
}

/** 新增用户 */
function handleAdd(): void {
  isEdit.value = false
  form.value = { id: 0, username: '', name: '', role: 'teacher', department: '', status: true }
  dialogVisible.value = true
}

/** 编辑用户 */
function handleEdit(row: SystemUser): void {
  isEdit.value = true
  form.value = {
    id: row.id,
    username: row.username,
    name: row.name,
    role: row.role,
    department: row.department,
    status: row.status,
  }
  dialogVisible.value = true
}

/** 删除用户 */
async function handleDelete(row: SystemUser): Promise<void> {
  await ElMessageBox.confirm(`确定删除用户 "${row.name}" 吗？`, '删除确认', { type: 'warning' })
  await userApi.remove(row.id)
  ElMessage.success('用户已删除')
  await loadUsers()
}

/** 切换用户状态 */
async function toggleStatus(row: SystemUser): Promise<void> {
  await userApi.update(row.id, { status: !row.status })
  row.status = !row.status
  ElMessage.success(row.status ? '账号已启用' : '账号已禁用')
}

/** 保存用户(新增或编辑) */
async function saveUser(): Promise<void> {
  submitting.value = true
  try {
    if (isEdit.value) {
      await userApi.update(form.value.id, {
        name: form.value.name,
        role: form.value.role,
        department: form.value.department,
        status: form.value.status,
      })
    } else {
      await userApi.create({
        username: form.value.username,
        name: form.value.name,
        role: form.value.role,
        department: form.value.department,
        status: form.value.status,
      })
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await loadUsers()
  } finally {
    submitting.value = false
  }
}

/** 重置密码 */
async function resetPassword(row: SystemUser): Promise<void> {
  await ElMessageBox.confirm(`重置 "${row.name}" 的密码为 123456？`, '重置密码', { type: 'warning' })
  await userApi.update(row.id, { password: '123456' })
  ElMessage.success('密码已重置为 123456')
}

onMounted(loadUsers)
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="table-toolbar">
        <el-input v-model="keyword" placeholder="搜索用户名/姓名" :prefix-icon="Search" clearable style="width: 240px" />
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="userList.filter((u) => !keyword || u.username.includes(keyword) || u.name.includes(keyword))"
        stripe
        border
      >
        <el-table-column prop="username" label="账号" width="120" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="role" label="角色" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ RoleLabels[row.role as UserRole] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="所属院系" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.status" @change="toggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="120" />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="resetPassword(row)">重置密码</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="账号"><el-input v-model="form.username" :disabled="isEdit" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="(label, key) in RoleLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="院系"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.status" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
