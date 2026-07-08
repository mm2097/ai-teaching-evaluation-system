/**
 * 数据导入 API（调用真实后端 /api/v1/* 接口）
 */
import request from '@/utils/request'
import type { ImportLog, ImportType } from '@/types'

export interface ImportExecuteParams {
  importType: ImportType
  dataSource: 'excel' | 'txt' | 'database'
  fileName: string
  totalCount?: number
  operatorName: string
}

/** 获取导入日志列表（当前后端暂无导入日志表，返回空列表） */
export async function fetchImportLogs(_importType?: ImportType): Promise<ImportLog[]> {
  return []
}

/** 执行数据导入（模拟成功，后续可接入真实后端） */
export async function executeImport(params: ImportExecuteParams): Promise<ImportLog> {
  const newLog: ImportLog = {
    id: Date.now(),
    importType: params.importType,
    dataSource: params.dataSource,
    fileName: params.fileName,
    totalCount: params.totalCount || 0,
    successCount: (params.totalCount || 0) - Math.floor(Math.random() * 5),
    failCount: Math.floor(Math.random() * 5),
    operatorName: params.operatorName,
    importTime: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-'),
    status: 1,
  }
  return newLog
}

/** 根据 ID 获取导入日志 */
export async function fetchImportLogById(_id: number): Promise<ImportLog | undefined> {
  return undefined
}
