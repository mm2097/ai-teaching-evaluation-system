/**
 * 题库批量导入标准模板下载
 */
import * as XLSX from 'xlsx'
import { questionTemplateHeaders } from './questionTemplateValidator'

const sampleRows: string[][] = [
  [
    '单选题',
    'TCP 三次握手的第二次握手，服务器发送的标志位是？',
    'SYN',
    'ACK',
    'SYN+ACK',
    'FIN',
    'C',
    '第二次握手服务器回复 SYN+ACK',
    'TCP/IP协议',
    '中等',
    '5',
  ],
  [
    '多选题',
    '以下哪些属于常见的网络安全威胁？（多选）',
    'DDoS 攻击',
    '中间人攻击',
    'SQL 注入',
    '路由收敛',
    'ABC',
    '路由收敛是正常过程',
    '网络安全',
    '中等',
    '5',
  ],
  [
    '判断题',
    'UDP 协议提供可靠的数据传输服务。',
    '',
    '',
    '',
    '',
    '错误',
    'UDP 是无连接不可靠协议',
    'TCP/IP协议',
    '简单',
    '5',
  ],
  [
    '填空题',
    'HTTP 协议默认使用的端口号是 _____。',
    '',
    '',
    '',
    '',
    '80',
    'HTTPS 默认 443',
    'HTTP协议',
    '简单',
    '5',
  ],
  [
    '简答题',
    '简述 TCP 三次握手的过程及其必要性。',
    '',
    '',
    '',
    '',
    'TCP 三次握手用于建立可靠连接：客户端发送 SYN，服务器回复 SYN+ACK，客户端发送 ACK 确认。',
    '评分要点：准确描述三次握手步骤；说明 SYN/ACK 作用；解释为何需要三次',
    'TCP/IP协议',
    '困难',
    '10',
  ],
]

/** 下载题库 Excel 模板 */
export function downloadQuestionExcelTemplate(): void {
  const ws = XLSX.utils.aoa_to_sheet([[...questionTemplateHeaders], ...sampleRows])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '题库')
  XLSX.writeFile(wb, '题库批量导入模板.xlsx')
}

/** 下载题库 Txt 模板 */
export function downloadQuestionTxtTemplate(): void {
  const lines = [questionTemplateHeaders.join(','), ...sampleRows.map((r) => r.join(','))]
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '题库批量导入模板.txt'
  a.click()
  URL.revokeObjectURL(url)
}
