/**
 * 评价体系配置 API（调用真实后端 /api/v1/eval-config）
 *
 * 数据模型：课程 → 评价维度(eval_dimension) → 评价指标(eval_index)
 */
import request from '@/utils/request'

export interface EvalIndexItem {
  indexId: number
  indexName: string
  weight: number
  scoreRule: Record<string, unknown>
  description?: string | null
}

export interface EvalDimensionItem {
  dimensionId: number
  dimensionName: string
  description?: string | null
  sortNum: number
  indexes: EvalIndexItem[]
  weightSum: number
  weightValid: boolean
}

export interface EvalConfigResponse {
  courseId: number
  courseName: string
  dimensions: EvalDimensionItem[]
}

export interface CreateDimensionParams {
  dimensionName: string
  description?: string
  sortNum?: number
}

export interface UpdateDimensionParams {
  dimensionName?: string
  description?: string
  sortNum?: number
}

export interface CreateIndexParams {
  indexName: string
  weight: number
  scoreRule?: string
  description?: string
}

export interface UpdateIndexParams {
  indexName?: string
  weight?: number
  scoreRule?: string
  description?: string
}

export interface IndexMutationResult extends EvalIndexItem {
  weightSumAfterAdd?: number
  weightSumAfterEdit?: number
  weightValid: boolean
}

/** 计分方式（映射后端 score_rule JSON） */
export const SCORE_RULE_PRESETS = [
  { value: 'score_daily', label: '平时成绩', rule: { type: 'direct', source: 'score_record', batch_type: 1 } },
  { value: 'score_mid', label: '期中/测验成绩', rule: { type: 'direct', source: 'score_record', batch_type: 3 } },
  { value: 'score_final', label: '期末成绩', rule: { type: 'direct', source: 'score_record', batch_type: 4 } },
  { value: 'attendance', label: '出勤率', rule: { type: 'attendance', full_score: 100 } },
  { value: 'interaction', label: '课堂参与度', rule: { type: 'interaction', full_score: 100 } },
] as const

export type ScoreRulePresetValue = (typeof SCORE_RULE_PRESETS)[number]['value']

const BATCH_TYPE_LABELS: Record<number, string> = {
  1: '平时成绩',
  3: '期中/测验成绩',
  4: '期末成绩',
}

/** 串行队列：避免 SQLite 并发写导致 500 */
let evalConfigChain: Promise<unknown> = Promise.resolve()

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function runEvalConfigTask<T>(task: () => Promise<T>, retries = 2): Promise<T> {
  const execute = async (): Promise<T> => {
    let lastError: unknown
    for (let attempt = 0; attempt <= retries; attempt++) {
      if (attempt > 0) await delay(300 * attempt)
      try {
        return await task()
      } catch (error: unknown) {
        lastError = error
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status !== 500 && status !== 503) throw error
      }
    }
    throw lastError
  }

  const result = evalConfigChain.then(execute, execute)
  evalConfigChain = result.then(() => delay(120), () => delay(120))
  return result
}

function toDimensionQuery(
  params: CreateDimensionParams | UpdateDimensionParams,
): Record<string, string | number> {
  const q: Record<string, string | number> = {}
  if (params.dimensionName !== undefined) q.dimension_name = params.dimensionName
  if (params.description !== undefined) q.description = params.description
  if (params.sortNum !== undefined) q.sort_num = params.sortNum
  return q
}

function toIndexQuery(
  params: CreateIndexParams | UpdateIndexParams,
): Record<string, string | number> {
  const q: Record<string, string | number> = {}
  if (params.indexName !== undefined) q.index_name = params.indexName
  if (params.weight !== undefined) q.weight = params.weight
  if (params.scoreRule !== undefined) q.score_rule = params.scoreRule
  if (params.description !== undefined) q.description = params.description
  return q
}

function ruleEquals(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

export function formatScoreRule(rule: Record<string, unknown> | null | undefined): string {
  if (!rule || Object.keys(rule).length === 0) return '—'
  if (typeof rule.description === 'string' && rule.description.trim()) return rule.description

  const type = rule.type as string | undefined
  if (type === 'direct' && rule.source === 'score_record') {
    const batch = Number(rule.batch_type)
    return BATCH_TYPE_LABELS[batch] || '教学成绩'
  }
  if (type === 'attendance') return '出勤率'
  if (type === 'interaction') return '课堂参与度'

  const preset = SCORE_RULE_PRESETS.find((p) => ruleEquals(p.rule, rule))
  return preset?.label || '—'
}

export function detectRulePreset(rule: Record<string, unknown> | null | undefined): ScoreRulePresetValue {
  if (!rule || Object.keys(rule).length === 0) return 'score_daily'
  const matched = SCORE_RULE_PRESETS.find((p) => ruleEquals(p.rule, rule))
  return matched?.value || 'score_daily'
}

export function buildScoreRuleJson(preset: ScoreRulePresetValue): string {
  const found = SCORE_RULE_PRESETS.find((p) => p.value === preset)
  return JSON.stringify(found?.rule ?? SCORE_RULE_PRESETS[0].rule)
}

export function calcWeightSum(weights: number[]): number {
  return Math.round(weights.reduce((sum, w) => sum + (Number(w) || 0), 0) * 10) / 10
}

export async function fetchEvalConfig(courseId: number): Promise<EvalConfigResponse> {
  return runEvalConfigTask(async () => {
    const res = await request.get(`/v1/eval-config/${courseId}`)
    return res.data
  })
}

export async function createDimension(
  courseId: number,
  params: CreateDimensionParams,
): Promise<EvalDimensionItem> {
  return runEvalConfigTask(async () => {
    const res = await request.post(`/v1/eval-config/${courseId}/dimensions`, null, {
      params: toDimensionQuery(params),
    })
    return res.data
  })
}

export async function updateDimension(
  dimensionId: number,
  params: UpdateDimensionParams,
): Promise<EvalDimensionItem> {
  return runEvalConfigTask(async () => {
    const res = await request.put(`/v1/eval-config/dimensions/${dimensionId}`, null, {
      params: toDimensionQuery(params),
    })
    return res.data
  })
}

export async function deleteDimension(dimensionId: number): Promise<void> {
  return runEvalConfigTask(async () => {
    await request.delete(`/v1/eval-config/dimensions/${dimensionId}`)
  })
}

export async function createIndex(
  dimensionId: number,
  params: CreateIndexParams,
): Promise<IndexMutationResult> {
  return runEvalConfigTask(async () => {
    const res = await request.post(`/v1/eval-config/dimensions/${dimensionId}/indexes`, null, {
      params: toIndexQuery(params),
    })
    return res.data
  })
}

export async function updateIndex(
  indexId: number,
  params: UpdateIndexParams,
): Promise<IndexMutationResult> {
  return runEvalConfigTask(async () => {
    const res = await request.put(`/v1/eval-config/indexes/${indexId}`, null, {
      params: toIndexQuery(params),
    })
    return res.data
  })
}

export async function deleteIndex(indexId: number): Promise<{
  weightSumAfterDelete: number
  weightValid: boolean
  dimensionId: number
}> {
  return runEvalConfigTask(async () => {
    const res = await request.delete(`/v1/eval-config/indexes/${indexId}`)
    return res.data
  })
}

/** 批量保存维度权重（先降后升，单次排队提交） */
export async function saveDimensionWeights(
  dimension: EvalDimensionItem,
  draftWeights: Record<number, number>,
): Promise<{ weightSum: number; weightValid: boolean }> {
  return runEvalConfigTask(async () => {
    const tasks: { indexId: number; weight: number; oldWeight: number }[] = []
    for (const idx of dimension.indexes) {
      const next = draftWeights[idx.indexId]
      if (next === undefined || next === idx.weight) continue
      tasks.push({ indexId: idx.indexId, weight: next, oldWeight: idx.weight })
    }

    const finalSum = calcWeightSum(
      dimension.indexes.map((i) => draftWeights[i.indexId] ?? i.weight),
    )

    if (!tasks.length) {
      return { weightSum: finalSum, weightValid: Math.abs(finalSum - 100) < 0.01 }
    }

    const ordered = [
      ...tasks.filter((t) => t.weight < t.oldWeight),
      ...tasks.filter((t) => t.weight > t.oldWeight),
    ]

    let lastValid = false
    let lastSum = finalSum
    for (const task of ordered) {
      const res = await request.put(`/v1/eval-config/indexes/${task.indexId}`, null, {
        params: toIndexQuery({ weight: task.weight }),
      })
      lastValid = res.data.weightValid
      lastSum = res.data.weightSumAfterEdit ?? lastSum
    }

    return { weightSum: lastSum, weightValid: lastValid }
  })
}

/** 将指标变更结果写回本地维度列表，避免保存后再发 GET */
export function patchDimensionAfterIndexChange(
  dimensions: EvalDimensionItem[],
  dimensionId: number,
  result: IndexMutationResult,
  mode: 'create' | 'update',
): EvalDimensionItem[] {
  return dimensions.map((dim) => {
    if (dim.dimensionId !== dimensionId) return dim
    const weightSum = result.weightSumAfterAdd ?? result.weightSumAfterEdit ?? dim.weightSum
    const indexes =
      mode === 'create'
        ? [
            ...dim.indexes,
            {
              indexId: result.indexId,
              indexName: result.indexName,
              weight: result.weight,
              scoreRule: result.scoreRule,
              description: result.description,
            },
          ]
        : dim.indexes.map((idx) =>
            idx.indexId === result.indexId
              ? {
                  indexId: result.indexId,
                  indexName: result.indexName,
                  weight: result.weight,
                  scoreRule: result.scoreRule,
                  description: result.description,
                }
              : idx,
          )
    return {
      ...dim,
      indexes,
      weightSum,
      weightValid: result.weightValid,
    }
  })
}

export function patchDimensionAfterIndexDelete(
  dimensions: EvalDimensionItem[],
  dimensionId: number,
  indexId: number,
  weightSumAfterDelete: number,
  weightValid: boolean,
): EvalDimensionItem[] {
  return dimensions.map((dim) => {
    if (dim.dimensionId !== dimensionId) return dim
    return {
      ...dim,
      indexes: dim.indexes.filter((idx) => idx.indexId !== indexId),
      weightSum: weightSumAfterDelete,
      weightValid,
    }
  })
}
