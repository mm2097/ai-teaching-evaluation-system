/**
 * 题库管理 API（调用真实后端 /api/v1/question-bank）
 */
import request from '@/utils/request'

export interface QuestionRecord {
  id: number
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  difficulty: string
  createdTime: string
}

export interface QuestionTypeOption {
  value: string
  label: string
}

export const questionTypeOptions: QuestionTypeOption[] = [
  { value: '单选', label: '单选题' },
  { value: '多选', label: '多选题' },
  { value: '判断', label: '判断题' },
  { value: '填空', label: '填空题' },
]

export interface AddQuestionParams {
  courseName: string
  knowledgePoint: string
  type: string
  content: string
  difficulty: string
}

/** 获取题库列表（当前为空列表，后续接入后端题库表） */
export async function fetchQuestionBankList(): Promise<QuestionRecord[]> {
  return []
}

/** 新增试题（当前为空操作） */
export async function addQuestion(_params: AddQuestionParams): Promise<void> {
  // 后端暂无题目管理表，暂不处理
}
