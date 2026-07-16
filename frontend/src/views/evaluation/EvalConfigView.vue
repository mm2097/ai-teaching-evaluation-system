<!--
  评价体系配置
  权重：表格外加减，调好后批量保存；弹窗只改名称和数据来源
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchCourses } from '@/api/dict'
import {
  fetchEvalConfig,
  createDimension,
  updateDimension,
  deleteDimension,
  createIndex,
  updateIndex,
  deleteIndex,
  saveDimensionWeights,
  patchDimensionAfterIndexChange,
  patchDimensionAfterIndexDelete,
  formatScoreRule,
  buildScoreRuleJson,
  detectRulePreset,
  calcWeightSum,
  SCORE_RULE_PRESETS,
  type EvalDimensionItem,
  type EvalIndexItem,
  type ScoreRulePresetValue,
} from '@/api/evalConfig'

const loading = ref(false)
const busy = ref(false)
const savingDimId = ref<number | null>(null)
const courseOptions = ref<{ label: string; value: number }[]>([])
const courseId = ref<number | undefined>()
const dimensions = ref<EvalDimensionItem[]>([])
const activeDimIds = ref<number[]>([])
/** 本地权重草稿，确认后批量提交 */
const draftWeights = ref<Record<number, Record<number, number>>>({})

const dimDialogVisible = ref(false)
const dimIsEdit = ref(false)
const dimForm = ref({ dimensionId: 0, dimensionName: '', description: '' })

const indexDialogVisible = ref(false)
const indexIsEdit = ref(false)
const indexForm = ref({
  indexId: 0,
  dimensionId: 0,
  indexName: '',
  rulePreset: 'score_daily' as ScoreRulePresetValue,
})

function syncDraftWeights(data: EvalDimensionItem[]): void {
  const next: Record<number, Record<number, number>> = {}
  for (const dim of data) {
    next[dim.dimensionId] = {}
    for (const idx of dim.indexes) {
      next[dim.dimensionId]![idx.indexId] = idx.weight
    }
  }
  draftWeights.value = next
}

function getDraftWeight(dimId: number, indexId: number, fallback: number): number {
  return draftWeights.value[dimId]?.[indexId] ?? fallback
}

function setDraftWeight(dimId: number, indexId: number, weight: number): void {
  if (!draftWeights.value[dimId]) draftWeights.value[dimId] = {}
  draftWeights.value[dimId]![indexId] = weight
}

function getDraftWeightSum(dim: EvalDimensionItem): number {
  return calcWeightSum(
    dim.indexes.map((idx) => getDraftWeight(dim.dimensionId, idx.indexId, idx.weight)),
  )
}

function isWeightDirty(dim: EvalDimensionItem): boolean {
  return dim.indexes.some(
    (idx) => getDraftWeight(dim.dimensionId, idx.indexId, idx.weight) !== idx.weight,
  )
}

function resetDraftWeights(dim: EvalDimensionItem): void {
  for (const idx of dim.indexes) {
    setDraftWeight(dim.dimensionId, idx.indexId, idx.weight)
  }
}

async function loadCourses(): Promise<void> {
  const courses = await fetchCourses()
  courseOptions.value = courses.map((c) => ({ label: c.courseName, value: c.id }))
  if (courseOptions.value.length && !courseId.value) {
    courseId.value = courseOptions.value[0]!.value
  }
}

async function loadEvalConfig(): Promise<void> {
  if (!courseId.value) {
    dimensions.value = []
    activeDimIds.value = []
    draftWeights.value = {}
    return
  }
  loading.value = true
  try {
    const data = await fetchEvalConfig(courseId.value)
    dimensions.value = data.dimensions
    activeDimIds.value = data.dimensions.map((d) => d.dimensionId)
    syncDraftWeights(data.dimensions)
  } catch {
    dimensions.value = []
    activeDimIds.value = []
    draftWeights.value = {}
  } finally {
    loading.value = false
  }
}

async function onCourseChange(): Promise<void> {
  if (busy.value) return
  await loadEvalConfig()
}

onMounted(async () => {
  await loadCourses()
  await loadEvalConfig()
})

function openAddDimension(): void {
  dimIsEdit.value = false
  dimForm.value = { dimensionId: 0, dimensionName: '', description: '' }
  dimDialogVisible.value = true
}

function openEditDimension(dim: EvalDimensionItem): void {
  dimIsEdit.value = true
  dimForm.value = {
    dimensionId: dim.dimensionId,
    dimensionName: dim.dimensionName,
    description: dim.description || '',
  }
  dimDialogVisible.value = true
}

async function saveDimension(): Promise<void> {
  const name = dimForm.value.dimensionName.trim()
  if (!name) {
    ElMessage.warning('请输入维度名称')
    return
  }
  if (!courseId.value || busy.value) return

  busy.value = true
  try {
    if (dimIsEdit.value) {
      const updated = await updateDimension(dimForm.value.dimensionId, {
        dimensionName: name,
        description: dimForm.value.description.trim() || undefined,
      })
      dimensions.value = dimensions.value.map((d) =>
        d.dimensionId === updated.dimensionId ? { ...d, ...updated } : d,
      )
      ElMessage.success('维度已保存')
    } else {
      const created = await createDimension(courseId.value, {
        dimensionName: name,
        description: dimForm.value.description.trim() || undefined,
        sortNum: dimensions.value.length,
      })
      dimensions.value = [...dimensions.value, { ...created, indexes: created.indexes ?? [] }]
      activeDimIds.value = [...activeDimIds.value, created.dimensionId]
      draftWeights.value[created.dimensionId] = {}
      ElMessage.success('维度已添加')
    }
    dimDialogVisible.value = false
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

async function handleDeleteDimension(dim: EvalDimensionItem): Promise<void> {
  if (busy.value) return
  try {
    await ElMessageBox.confirm(
      `删除维度「${dim.dimensionName}」将同时删除其下 ${dim.indexes.length} 个指标，是否继续？`,
      '删除确认',
      { type: 'warning' },
    )
    busy.value = true
    await deleteDimension(dim.dimensionId)
    dimensions.value = dimensions.value.filter((d) => d.dimensionId !== dim.dimensionId)
    activeDimIds.value = activeDimIds.value.filter((id) => id !== dim.dimensionId)
    delete draftWeights.value[dim.dimensionId]
    ElMessage.success('已删除')
  } catch {
    /* 取消或失败 */
  } finally {
    busy.value = false
  }
}

function openAddIndex(dim: EvalDimensionItem): void {
  indexIsEdit.value = false
  indexForm.value = {
    indexId: 0,
    dimensionId: dim.dimensionId,
    indexName: '',
    rulePreset: 'score_daily',
  }
  indexDialogVisible.value = true
}

function openEditIndex(_dim: EvalDimensionItem, idx: EvalIndexItem): void {
  indexIsEdit.value = true
  indexForm.value = {
    indexId: idx.indexId,
    dimensionId: _dim.dimensionId,
    indexName: idx.indexName,
    rulePreset: detectRulePreset(idx.scoreRule),
  }
  indexDialogVisible.value = true
}

async function saveIndex(): Promise<void> {
  const name = indexForm.value.indexName.trim()
  if (!name) {
    ElMessage.warning('请输入指标名称')
    return
  }
  if (busy.value) return

  busy.value = true
  try {
    const textPayload = {
      indexName: name,
      scoreRule: buildScoreRuleJson(indexForm.value.rulePreset),
    }

    if (indexIsEdit.value) {
      const res = await updateIndex(indexForm.value.indexId, textPayload)
      dimensions.value = patchDimensionAfterIndexChange(
        dimensions.value,
        indexForm.value.dimensionId,
        res,
        'update',
      )
      ElMessage.success('指标信息已保存')
    } else {
      const res = await createIndex(indexForm.value.dimensionId, {
        ...textPayload,
        weight: 0,
      })
      dimensions.value = patchDimensionAfterIndexChange(
        dimensions.value,
        indexForm.value.dimensionId,
        res,
        'create',
      )
      setDraftWeight(indexForm.value.dimensionId, res.indexId, 0)
      ElMessage.success('指标已添加，请在表格中设置权重后点「保存权重」')
    }
    indexDialogVisible.value = false
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

async function handleDeleteIndex(dim: EvalDimensionItem, idx: EvalIndexItem): Promise<void> {
  if (busy.value) return
  try {
    await ElMessageBox.confirm(`确定删除指标「${idx.indexName}」？`, '删除确认', { type: 'warning' })
    busy.value = true
    const res = await deleteIndex(idx.indexId)
    dimensions.value = patchDimensionAfterIndexDelete(
      dimensions.value,
      dim.dimensionId,
      idx.indexId,
      res.weightSumAfterDelete,
      res.weightValid,
    )
    if (draftWeights.value[dim.dimensionId]) {
      delete draftWeights.value[dim.dimensionId]![idx.indexId]
    }
    ElMessage.success('已删除')
  } catch {
    /* 取消或失败 */
  } finally {
    busy.value = false
  }
}

async function handleSaveWeights(dim: EvalDimensionItem): Promise<void> {
  if (busy.value) return
  const sum = getDraftWeightSum(dim)
  if (sum > 100.01) {
    ElMessage.warning(`权重合计 ${sum}%，须调整为 100% 后再保存`)
    return
  }
  if (!isWeightDirty(dim)) {
    ElMessage.info('权重未修改')
    return
  }

  savingDimId.value = dim.dimensionId
  busy.value = true
  try {
    const dw = draftWeights.value[dim.dimensionId] || {}
    const res = await saveDimensionWeights(dim, dw)
    dimensions.value = dimensions.value.map((d) => {
      if (d.dimensionId !== dim.dimensionId) return d
      return {
        ...d,
        indexes: d.indexes.map((i) => ({ ...i, weight: dw[i.indexId] ?? i.weight })),
        weightSum: res.weightSum,
        weightValid: res.weightValid,
      }
    })
    syncDraftWeights(dimensions.value)
    ElMessage.success(res.weightValid ? '权重已保存' : `权重已保存，合计 ${res.weightSum}%`)
  } catch {
    await loadEvalConfig()
  } finally {
    savingDimId.value = null
    busy.value = false
  }
}

function weightTagType(dim: EvalDimensionItem): 'success' | 'info' | 'danger' {
  const sum = getDraftWeightSum(dim)
  if (Math.abs(sum - 100) < 0.01) return 'success'
  if (sum > 100) return 'danger'
  return 'info'
}
</script>

<template>
  <div class="page-container">
    <div class="content-card">
      <div class="table-toolbar">
        <div class="filter-bar" style="margin-bottom: 0">
          <span>课程</span>
          <el-select
            v-model="courseId"
            placeholder="选择课程"
            style="width: 240px"
            :disabled="busy"
            @change="onCourseChange"
          >
            <el-option v-for="o in courseOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
        <el-button type="primary" :disabled="!courseId || busy" @click="openAddDimension">
          新增维度
        </el-button>
      </div>

      <p class="hint">权重在表格里用 +/- 调整，几个指标都调好后点「保存权重」一次性提交；编辑弹窗只改名称和数据来源。</p>

      <div v-loading="loading" class="dim-list">
        <el-empty v-if="!loading && !dimensions.length" description="暂无配置，点击「新增维度」开始" />

        <el-collapse v-else v-model="activeDimIds">
          <el-collapse-item v-for="dim in dimensions" :key="dim.dimensionId" :name="dim.dimensionId">
            <template #title>
              <div class="dim-title">
                <span class="dim-name">{{ dim.dimensionName }}</span>
                <el-tag :type="weightTagType(dim)" size="small" effect="plain">
                  合计 {{ getDraftWeightSum(dim) }}%
                </el-tag>
                <el-tag v-if="isWeightDirty(dim)" type="warning" size="small" effect="plain">未保存</el-tag>
                <span class="dim-count">{{ dim.indexes.length }} 个指标</span>
              </div>
            </template>

            <div class="dim-body">
              <p v-if="dim.description" class="dim-desc">{{ dim.description }}</p>
              <div class="dim-actions">
                <el-button type="primary" size="small" :disabled="busy" @click="openAddIndex(dim)">
                  新增指标
                </el-button>
                <el-button
                  type="success"
                  size="small"
                  :loading="savingDimId === dim.dimensionId"
                  :disabled="busy || !isWeightDirty(dim)"
                  @click="handleSaveWeights(dim)"
                >
                  保存权重
                </el-button>
                <el-button
                  v-if="isWeightDirty(dim)"
                  size="small"
                  :disabled="busy"
                  @click="resetDraftWeights(dim)"
                >
                  撤销
                </el-button>
                <el-button size="small" :disabled="busy" @click="openEditDimension(dim)">编辑维度</el-button>
                <el-button type="danger" size="small" plain :disabled="busy" @click="handleDeleteDimension(dim)">
                  删除维度
                </el-button>
              </div>

              <el-table :data="dim.indexes" stripe border size="small" empty-text="暂无指标">
                <el-table-column prop="indexName" label="指标" min-width="120" />
                <el-table-column label="权重 (%)" width="150" align="center">
                  <template #default="{ row }">
                    <el-input-number
                      :model-value="getDraftWeight(dim.dimensionId, row.indexId, row.weight)"
                      :min="0"
                      :max="100"
                      :step="5"
                      size="small"
                      controls-position="right"
                      :disabled="busy"
                      @update:model-value="(v: number | undefined) => {
                        if (v !== undefined) setDraftWeight(dim.dimensionId, row.indexId, v)
                      }"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="数据来源" min-width="120">
                  <template #default="{ row }">{{ formatScoreRule(row.scoreRule) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="130" align="center">
                  <template #default="{ row }">
                    <el-button type="primary" link size="small" :disabled="busy" @click="openEditIndex(dim, row)">
                      编辑
                    </el-button>
                    <el-button type="danger" link size="small" :disabled="busy" @click="handleDeleteIndex(dim, row)">
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <el-dialog
      v-model="dimDialogVisible"
      :title="dimIsEdit ? '编辑维度' : '新增维度'"
      width="440px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="80px">
        <el-form-item label="维度名称" required>
          <el-input v-model="dimForm.dimensionName" maxlength="32" placeholder="如：学业成绩、学习态度" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="dimForm.description" type="textarea" :rows="2" maxlength="255" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="busy" @click="dimDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="saveDimension">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="indexDialogVisible"
      :title="indexIsEdit ? '编辑指标' : '新增指标'"
      width="440px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="指标名称" required>
          <el-input v-model="indexForm.indexName" maxlength="64" placeholder="如：期末成绩、出勤率" />
        </el-form-item>
        <el-form-item label="数据来源">
          <el-select v-model="indexForm.rulePreset" style="width: 100%">
            <el-option v-for="o in SCORE_RULE_PRESETS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <p v-if="!indexIsEdit" class="dialog-tip">权重请在表格中设置，完成后点「保存权重」。</p>
      </el-form>
      <template #footer>
        <el-button :disabled="busy" @click="indexDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="saveIndex">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.dialog-tip {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.dim-list {
  margin-top: 16px;
  min-height: 120px;
}

.dim-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  padding-right: 8px;
}

.dim-name {
  font-weight: 600;
}

.dim-count {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.dim-body {
  padding: 0 4px 8px;
}

.dim-desc {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.dim-actions {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
