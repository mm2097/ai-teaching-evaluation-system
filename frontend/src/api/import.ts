/**
 * 数据导入 API（模拟后端 /api/data/import/* 接口）
 */
import { delay } from '@/utils/auth'
import { importLogs } from '@/mock'
import type { ImportLog, ImportType } from '@/types'

export interface ImportExecuteParams {
  importType: ImportType
  dataSource: 'excel' | 'txt' | 'database'
  fileName: string
  totalCount?: number
  operatorName: string
}

/** 获取导入日志列表 */
export async function fetchImportLogs(importType?: ImportType): Promise<ImportLog[]> {
  await delay(300)
  if (!importType) return [...importLogs]
  return importLogs.filter((log) => log.importType === importType)
}

/** 执行数据导入并写入日志 */
export async function executeImport(params: ImportExecuteParams): Promise<ImportLog> {
  await delay(1500)
  const successCount = params.totalCount ? params.totalCount - Math.floor(Math.random() * 15) : 9856
  const failCount = (params.totalCount || successCount + 12) - successCount
  const newLog: ImportLog = {
    id: Date.now(),
    importType: params.importType,
    dataSource: params.dataSource,
    fileName: params.fileName,
    totalCount: successCount + failCount,
    successCount,
    failCount,
    operatorName: params.operatorName,
    importTime: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-'),
    status: failCount > 0 && failCount > successCount * 0.1 ? 2 : 1,
  }
  importLogs.unshift(newLog)
  return newLog
}

/** 根据 ID 获取导入日志 */
export async function fetchImportLogById(id: number): Promise<ImportLog | undefined> {
  await delay(100)
  return importLogs.find((log) => log.id === id)
}
