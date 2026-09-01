<!--
  用户与权限管理页面
  支持用户 CRUD、角色分配、学生所属班级筛选/编辑与账号启停
-->
<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { userApi } from '@/api/users'
import { fetchClasses } from '@/api/dict'
import { RoleLabels } from '@/types'
import type { ClassInfo, SystemUser, UserRole } from '@/types'

const route = useRoute()
const userList = ref<SystemUser[]>([])
const classOptions = ref<ClassInfo[]>([])
const keyword = ref('')
const roleFilter = ref<UserRole | ''>('')
const classFilter = ref<number | undefined>()
const statusFilter = ref<number | ''>('')
const loading = ref(false)

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const form = ref({
  id: 0,
  username: '',
  name: '',
  role: 'teacher' as UserRole,
  status: true,
  college: '',
  classId: undefined as number | undefined,
  // 学生档案字段（仅学生角色使用，写入 student 表）
  studentNo: '',
  gender: 1 as number,  // 0=女, 1=男，默认男
  // 教师档案字段（仅教师角色使用，写入 teacher 表）
  teacherNo: '',
  title: '',
  phone: '',
  email: '',
})

function emptyForm() {
  return {
    id: 0,
    username: '',
    name: '',
    role: 'teacher' as UserRole,
    status: true,
    college: '',
    classId: undefined as number | undefined,
    studentNo: '',
    gender: 1 as number,
    teacherNo: '',
    title: '',
    phone: '',
    email: '',
  }
}

const filteredUsers = computed(() => {
  const kw = keyword.value.trim()
  return userList.value.filter((u) => {
    if (kw && !u.username.includes(kw) && !u.name.includes(kw)) return false
    if (roleFilter.value && u.role !== roleFilter.value) return false
    if (classFilter.value != null) {
      if (u.role !== 'student' || u.classId !== classFilter.value) return false
    }
    if (statusFilter.value !== '' && (u.status ? 1 : 0) !== statusFilter.value) return false
    return true
  })
})

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    userList.value = await userApi.list({
      role: roleFilter.value || undefined,
      classId: classFilter.value,
      status: statusFilter.value === '' ? undefined : statusFilter.value,
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载用户失败')
  } finally {
    loading.value = false
  }
}

async function loadClasses(): Promise<void> {
  try {
    classOptions.value = await fetchClasses()
  } catch {
    classOptions.value = []
  }
}

function onRoleChange(role: UserRole): void {
  if (role !== 'student') {
    form.value.classId = undefined
    form.value.studentNo = ''
    form.value.gender = 1
  }
  if (role !== 'teacher') {
    form.value.teacherNo = ''
    form.value.title = ''
  }
  if (role === 'admin') {
    form.value.phone = ''
    form.value.email = ''
  }
}

function handleAdd(): void {
  isEdit.value = false
  form.value = emptyForm()
  dialogVisible.value = true
}

function handleEdit(row: SystemUser): void {
  isEdit.value = true
  form.value = {
    id: row.id,
    username: row.username,
    name: row.name,
    role: row.role,
    status: row.status,
    college: row.department,
    classId: row.classId ?? undefined,
    studentNo: row.studentNo || '',
    gender: row.gender ?? 1,
    teacherNo: row.teacherNo || '',
    title: row.title || '',
    phone: row.phone || '',
    email: row.email || '',
  }
  dialogVisible.value = true
}

async function handleDelete(row: SystemUser): Promise<void> {
  if (row.role === 'admin') {
    ElMessage.warning('不允许删除系统管理员账号')
    return
  }
  await ElMessageBox.confirm(`确定删除用户 "${row.name}" 吗？`, '删除确认', { type: 'warning' })
  try {
    await userApi.remove(row.id)
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function toggleStatus(row: SystemUser): Promise<void> {
  if (row.role === 'admin') {
    ElMessage.warning('不允许启用/禁用系统管理员账号')
    return
  }
  try {
    await userApi.update(row.id, { status: !row.status })
    row.status = !row.status
    ElMessage.success(row.status ? '账号已启用' : '账号已禁用')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '状态更新失败')
  }
}

async function saveUser(): Promise<void> {
  if (!form.value.username.trim() || !form.value.name.trim()) {
    ElMessage.warning('请填写账号和姓名')
    return
  }
  if (form.value.role === 'student' && !form.value.classId) {
    ElMessage.warning('学生用户必须选择所属班级')
    return
  }
  submitting.value = true
  try {
    const classId = form.value.role === 'student' ? form.value.classId ?? null : undefined
    if (isEdit.value) {
      await userApi.update(form.value.id, {
        name: form.value.name,
        role: form.value.role,
        status: form.value.status,
        college: form.value.college,
        classId,
        studentNo: form.value.studentNo,
        gender: form.value.gender,
        teacherNo: form.value.teacherNo,
        title: form.value.title,
        phone: form.value.phone,
        email: form.value.email,
      })
    } else {
      await userApi.create({
        username: form.value.username,
        name: form.value.name,
        role: form.value.role,
        status: form.value.status,
        college: form.value.college,
        classId,
        studentNo: form.value.studentNo,
        gender: form.value.gender,
        teacherNo: form.value.teacherNo,
        title: form.value.title,
        phone: form.value.phone,
        email: form.value.email,
      })
    }
    dialogVisible.value = false
    ElMessage.success('保存成功')
    await loadUsers()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function resetPassword(row: SystemUser): Promise<void> {
  await ElMessageBox.confirm(`重置 "${row.name}" 的密码为 123456？`, '重置密码', { type: 'warning' })
  try {
    await userApi.update(row.id, { password: '123456' })
    ElMessage.success('密码已重置为 123456')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '重置密码失败')
  }
}

watch([roleFilter, classFilter, statusFilter], () => {
  void loadUsers()
})

/**
 * 从路由 query 读取管理工作台下钻携带的筛选条件并应用
 * 支持 roleCode（teacher/student/admin）与 status（0=停用, 1=正常）
 */
function applyQueryFilters(): void {
  const qRole = route.query.roleCode
  if (typeof qRole === 'string' && (qRole === 'teacher' || qRole === 'student' || qRole === 'admin')) {
    roleFilter.value = qRole
  }
  const qStatus = Number(route.query.status)
  if (qStatus === 0 || qStatus === 1) statusFilter.value = qStatus
}

onMounted(async () => {
  applyQueryFilters()
  await Promise.all([loadUsers(), loadClasses()])
})

// 从管理工作台再次下钻时（同一组件复用），重新应用筛选并刷新
watch(
  () => route.query,
  () => {
    applyQueryFilters()
    void loadUsers()
  },
)
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="table-toolbar">
        <el-input v-model="keyword" placeholder="搜索用户名/姓名" :prefix-icon="Search" clearable style="width: 200px" />
        <el-select v-model="roleFilter" placeholder="全部角色" clearable style="width: 140px">
          <el-option v-for="(label, key) in RoleLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="classFilter" placeholder="按班级筛选学生" clearable filterable style="width: 220px">
          <el-option
            v-for="item in classOptions"
            :key="item.id"
            :label="item.className"
            :value="item.id"
          />
        </el-select>
        <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 130px">
          <el-option label="正常账号" :value="1" />
          <el-option label="停用账号" :value="0" />
        </el-select>
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
      </div>

      <el-table v-loading="loading" :data="filteredUsers" stripe border>
        <el-table-column prop="username" label="账号" width="150" show-overflow-tooltip />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="role" label="角色" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ RoleLabels[row.role as UserRole] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="所属院系" min-width="120" />
        <el-table-column label="所属班级" min-width="160">
          <template #default="{ row }">
            <span v-if="row.role === 'student'">{{ row.className || '未分配' }}</span>
            <span v-else class="is-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tooltip :disabled="row.role !== 'admin'" content="不允许启用/禁用系统管理员账号" placement="top">
              <el-switch :model-value="row.status" :disabled="row.role === 'admin'" @change="toggleStatus(row)" />
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="120" />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="resetPassword(row)">重置密码</el-button>
            <el-tooltip :disabled="row.role !== 'admin'" content="不允许删除系统管理员账号" placement="top">
              <el-button type="danger" link size="small" :disabled="row.role === 'admin'" @click="handleDelete(row)">删除</el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="账号"><el-input v-model="form.username" :disabled="isEdit" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%" @change="onRoleChange">
            <el-option v-for="(label, key) in RoleLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role === 'student'" label="所属班级" required>
          <el-select v-model="form.classId" placeholder="请选择班级" filterable style="width: 100%">
            <el-option
              v-for="item in classOptions"
              :key="item.id"
              :label="`${item.className}${item.grade ? '（' + item.grade + '）' : ''}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <!-- 学生档案字段：写入 student 表；学号留空默认与账号相同，手机号/邮箱可空 -->
        <template v-if="form.role === 'student'">
          <el-form-item label="学号">
            <el-input v-model="form.studentNo" placeholder="留空则默认与账号相同" clearable />
          </el-form-item>
          <el-form-item label="性别">
            <el-radio-group v-model="form.gender">
              <el-radio :value="1">男</el-radio>
              <el-radio :value="0">女</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="form.phone" placeholder="可为空" clearable maxlength="20" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="可为空" clearable maxlength="64" />
          </el-form-item>
        </template>
        <!-- 教师档案字段：写入 teacher 表；教工号留空默认与账号相同 -->
        <template v-if="form.role === 'teacher'">
          <el-form-item label="教工号">
            <el-input v-model="form.teacherNo" placeholder="留空则默认与账号相同" clearable />
          </el-form-item>
          <el-form-item label="职称">
            <el-select v-model="form.title" placeholder="可为空" clearable filterable allow-create default-first-option style="width: 100%">
              <el-option label="教授" value="教授" />
              <el-option label="副教授" value="副教授" />
              <el-option label="讲师" value="讲师" />
              <el-option label="助教" value="助教" />
            </el-select>
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="form.phone" placeholder="可为空" clearable maxlength="20" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="可为空" clearable maxlength="64" />
          </el-form-item>
        </template>
        <el-form-item label="所属学院">
          <el-input v-model="form.college" placeholder="不填默认为计算机学院" clearable />
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.status" :disabled="form.role === 'admin'" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.is-muted {
  color: #94a3b8;
}
.table-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
