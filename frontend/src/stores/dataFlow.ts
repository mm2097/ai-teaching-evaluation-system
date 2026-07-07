/**
 * 数据采集流程状态管理
 * 在「接入 → 清洗 → 管理」各页面间共享当前导入任务上下文
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ImportLog } from '@/types'

export const useDataFlowStore = defineStore('dataFlow', () => {
  /** 当前选中的导入日志 */
  const currentImportLog = ref<ImportLog | null>(null)

  /** 最近一次导入结果 */
  const lastImportResult = ref<ImportLog | null>(null)

  /** 清洗任务关联的导入日志 ID */
  const cleaningImportLogId = ref<number | null>(null)

  /** 清洗是否已完成 */
  const cleaningCompleted = ref(false)

  function setCurrentImportLog(log: ImportLog | null): void {
    currentImportLog.value = log
  }

  function setLastImportResult(log: ImportLog): void {
    lastImportResult.value = log
    currentImportLog.value = log
    cleaningImportLogId.value = log.id
    cleaningCompleted.value = false
  }

  function markCleaningCompleted(): void {
    cleaningCompleted.value = true
  }

  function clearFlow(): void {
    currentImportLog.value = null
    lastImportResult.value = null
    cleaningImportLogId.value = null
    cleaningCompleted.value = false
  }

  return {
    currentImportLog,
    lastImportResult,
    cleaningImportLogId,
    cleaningCompleted,
    setCurrentImportLog,
    setLastImportResult,
    markCleaningCompleted,
    clearFlow,
  }
})
