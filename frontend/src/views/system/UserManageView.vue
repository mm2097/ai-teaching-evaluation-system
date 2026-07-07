<!--
  用户与权限管理页面
  支持用户 CRUD、角色分配与账号启停
-->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { systemUserList } from '@/mock'
import { RoleLabels } from '@/types'
import type { UserRole } from '@/types'

/** 用户列表 */
const userList = ref([...systemUserList])
const keyword = ref('')

/** 对话框 */
const dialogVisible = ref(false)
const isEdit = ref(false)
const form = ref({
  id: 0,
  username: '',
  name: '',
  role: 'teacher' as UserRole,
  department: '',
  status: true,
})

/**
 * 新增用户
 */
function handleAdd(): void {
  isEdit.value = false
  form.value = { id: 0, username: '', name: '', role: 'teacher', department: '', status: true }
  dialogVisible.value = true
}

/**
 * 编辑用户
 */
function handleEdit(row: (typeof systemUserList)[0]): void {
  isEdit.value = true
  form.value = { ...row, role: row.role as UserRole }
  dialogVisible.value = true
}

/**
 * 删除用户
 */
async function handleDelete(row: (typeof systemUserList)[0]): Promise<void> {
  await ElMessageBox.confirm(`确定删除用户 "${row.name}" 吗？`, '删除确认', { type: 'warning' })
  userList.value = userList.value.filter((u) => u.id !== row.id)
  ElMessage.success('用户已删除')
}

/**
 * 切换用户状态
 */
function toggleStatus(row: (typeof systemUserList)[0]): void {
  row.status = !row.status
  ElMessage.success(row.status ? '账号已启用' : '账号已禁用')
}

/**
 * 保存用户
 */
function saveUser(): void {
  if (isEdit.value) {
    const idx = userList.value.findIndex((u) => u.id === form.value.id)
    if (idx !== -1) userList.value[idx] = { ...form.value, createTime: userList.value[idx]!.createTime }
  } else {
    userList.value.push({ ...form.value, id: Date.now(), createTime: new Date().toISOString().slice(0, 10) })
  }
  dialogVisible.value = false
  ElMessage.success('保存成功')
}

/**
 * 重置密码
 */
function resetPassword(row: (typeof systemUserList)[0]): void {
  ElMessage.success(`已重置 ${row.name} 的密码为默认密码 123456`)
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="table-toolbar">
        <el-input v-model="keyword" placeholder="搜索用户名/姓名" :prefix-icon="Search" clearable style="width: 240px" />
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
      </div>

      <el-table :data="userList.filter(u => !keyword || u.username.includes(keyword) || u.name.includes(keyword))" stripe border>
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
        <el-button type="primary" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
