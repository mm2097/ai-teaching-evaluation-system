<!--
  个人设置弹窗
  展示当前账号基本信息；提供修改登录密码功能
  学生角色额外支持修改本人手机号/邮箱（学生仅可更改手机号、邮箱、密码）
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { authApi } from '@/api/auth'
import { setStoredUser } from '@/utils/auth'
import { useUserStore } from '@/stores/user'

/** 弹窗显隐（v-model） */
const visible = defineModel<boolean>({ default: false })

const userStore = useUserStore()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const isStudent = computed(() => userStore.userRole === 'student')

/** 基本信息（只读展示，来源于登录态） */
const basicInfo = computed(() => {
  const items = [
    { label: '账号', value: userStore.userInfo?.username || '-' },
    { label: '姓名', value: userStore.userInfo?.name || '-' },
    { label: '角色', value: userStore.roleLabel || '-' },
    { label: '院系', value: userStore.userInfo?.department || '-' },
  ]
  if (userStore.userInfo?.studentNo) {
    items.push({ label: '学号', value: userStore.userInfo.studentNo })
  }
  return items
})

/** 修改密码表单 */
const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const rules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.newPassword) {
          callback(new Error('两次输入的新密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

/** 学生联系方式表单（手机号/邮箱可空） */
const contactForm = reactive({
  phone: '',
  email: '',
})
const savingContact = ref(false)

/** 打开弹窗时回填当前值并清空上次的输入 */
watch(visible, (val) => {
  if (val) {
    form.oldPassword = ''
    form.newPassword = ''
    form.confirmPassword = ''
    formRef.value?.clearValidate()
    contactForm.phone = userStore.userInfo?.phone || ''
    contactForm.email = userStore.userInfo?.email || ''
  }
})

/**
 * 提交修改密码
 * 成功后提示并关闭弹窗；错误提示由请求拦截器统一展示（如"原密码错误"）
 */
async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await authApi.changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('密码修改成功')
    visible.value = false
  } finally {
    submitting.value = false
  }
}

/**
 * 学生保存联系方式（手机号/邮箱，留空表示清空）
 */
async function handleSaveContact(): Promise<void> {
  if (savingContact.value) return
  savingContact.value = true
  try {
    await authApi.updateContact(contactForm.phone.trim(), contactForm.email.trim())
    if (userStore.userInfo) {
      userStore.userInfo.phone = contactForm.phone.trim() || undefined
      userStore.userInfo.email = contactForm.email.trim() || undefined
      setStoredUser(JSON.stringify(userStore.userInfo))
    }
    ElMessage.success('联系方式已更新')
  } catch {
    // 错误提示由请求拦截器统一处理
  } finally {
    savingContact.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="个人设置"
    width="480px"
    :close-on-click-modal="false"
    append-to-body
  >
    <!-- 基本信息（只读） -->
    <div class="basic-section">
      <div class="section-title">基本信息</div>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item
          v-for="item in basicInfo"
          :key="item.label"
          :label="item.label"
        >{{ item.value }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 学生联系方式（学生仅可更改手机号、邮箱、密码） -->
    <div v-if="isStudent" class="contact-section">
      <div class="section-title">联系方式</div>
      <el-form label-width="90px" @submit.prevent>
        <el-form-item label="手机号">
          <el-input v-model="contactForm.phone" placeholder="可为空" clearable maxlength="20" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="contactForm.email" placeholder="可为空" clearable maxlength="64" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingContact" @click="handleSaveContact">
            保存联系方式
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 修改密码 -->
    <div class="password-section">
      <div class="section-title">修改密码</div>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
        @submit.prevent
      >
        <el-form-item label="原密码" prop="oldPassword">
          <el-input
            v-model="form.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前登录密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="6 位以上新密码"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入新密码"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
      </el-form>
      <div class="password-tip">修改成功后，请使用新密码登录系统。</div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        确认修改
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.basic-section,
.contact-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #2563eb;
}

.password-tip {
  font-size: 12px;
  color: #94a3b8;
  padding-left: 90px;
}
</style>
