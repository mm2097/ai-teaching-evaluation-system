/**
 * AI 生成模拟数据
 */
import type { GenerateExerciseParams, GenerateExerciseResult, QuizQuestion } from '@/types'

const questionTemplates: Omit<QuizQuestion, 'id'>[] = [
  {
    type: 'single_choice',
    stem: '对二叉搜索树进行中序遍历，得到的序列是……',
    options: [
      { key: 'A', text: '递增有序序列' },
      { key: 'B', text: '递减有序序列' },
      { key: 'C', text: '无序序列' },
      { key: 'D', text: '只包含叶子结点' },
    ],
    answer: 'A',
    explanation: '二叉搜索树的中序遍历满足左<根<右，因此结果递增有序。',
    difficulty: 'medium',
    knowledgePoint: '二叉树遍历',
    score: 10,
    source: 'ai',
  },
  {
    type: 'multi_choice',
    stem: '以下哪些属于树的平衡相关知识点？（多选）',
    options: [
      { key: 'A', text: '红黑树' },
      { key: 'B', text: '平衡二叉树' },
      { key: 'C', text: 'B 树' },
      { key: 'D', text: '哈希表' },
    ],
    answer: 'ABC',
    explanation: '红黑树、平衡二叉树、B 树均属于平衡树范畴。',
    difficulty: 'medium',
    knowledgePoint: '红黑树',
    score: 10,
    source: 'ai',
  },
  {
    type: 'judge',
    stem: '哈希表查找的平均时间复杂度为 O(1)。',
    answer: 'true',
    explanation: '在理想情况下，哈希表通过哈希函数直接定位，平均时间复杂度为 O(1)。',
    difficulty: 'easy',
    knowledgePoint: '哈希表',
    score: 10,
    source: 'ai',
  },
  {
    type: 'fill_blank',
    stem: '栈的特点是 _____ 出栈。',
    answer: '后进先出',
    answerList: ['后进先出', 'LIFO'],
    explanation: '栈是后进先出（LIFO）的数据结构。',
    difficulty: 'easy',
    knowledgePoint: '栈与队列',
    score: 10,
    source: 'ai',
  },
  {
    type: 'single_choice',
    stem: '红黑树插入新节点后，最多需要进行几次旋转？',
    options: [
      { key: 'A', text: '1 次' },
      { key: 'B', text: '2 次' },
      { key: 'C', text: '3 次' },
      { key: 'D', text: '不限' },
    ],
    answer: 'B',
    explanation: '红黑树插入后最多需要 2 次旋转来恢复平衡性质。',
    difficulty: 'hard',
    knowledgePoint: '红黑树',
    score: 10,
    source: 'ai',
  },
  {
    type: 'single_choice',
    stem: '单链表在已知头节点的情况下，在尾部插入节点的时间复杂度是？',
    options: [
      { key: 'A', text: 'O(1)' },
      { key: 'B', text: 'O(n)' },
      { key: 'C', text: 'O(log n)' },
      { key: 'D', text: 'O(n²)' },
    ],
    answer: 'B',
    explanation: '需要遍历到链表尾部，时间复杂度为 O(n)。',
    difficulty: 'medium',
    knowledgePoint: '链表操作',
    score: 10,
    source: 'ai',
  },
  // 计算机网络
  {
    type: 'single_choice',
    stem: 'TCP 三次握手的第二次握手，服务器发送的标志位是？',
    options: [
      { key: 'A', text: 'SYN' },
      { key: 'B', text: 'ACK' },
      { key: 'C', text: 'SYN+ACK' },
      { key: 'D', text: 'FIN' },
    ],
    answer: 'C',
    explanation: '第二次握手服务器回复 SYN+ACK。',
    difficulty: 'medium',
    knowledgePoint: 'TCP/IP协议',
    score: 5,
    source: 'ai',
  },
  {
    type: 'single_choice',
    stem: 'HTTP/1.1 中，持久连接通过哪个首部字段实现？',
    options: [
      { key: 'A', text: 'Host' },
      { key: 'B', text: 'Connection: keep-alive' },
      { key: 'C', text: 'Content-Type' },
      { key: 'D', text: 'Cache-Control' },
    ],
    answer: 'B',
    explanation: 'Connection: keep-alive 允许在同一 TCP 连接上发送多个 HTTP 请求。',
    difficulty: 'medium',
    knowledgePoint: 'HTTP协议',
    score: 5,
    source: 'ai',
  },
  {
    type: 'judge',
    stem: 'UDP 协议提供可靠的数据传输服务。',
    answer: 'false',
    explanation: 'UDP 是无连接的不可靠传输协议。',
    difficulty: 'easy',
    knowledgePoint: 'TCP/IP协议',
    score: 5,
    source: 'ai',
  },
  {
    type: 'fill_blank',
    stem: 'HTTP 协议默认使用的端口号是 _____。',
    answer: '80',
    answerList: ['80'],
    explanation: 'HTTP 默认端口 80，HTTPS 默认端口 443。',
    difficulty: 'easy',
    knowledgePoint: 'HTTP协议',
    score: 5,
    source: 'ai',
  },
  {
    type: 'single_choice',
    stem: 'RIP 路由协议使用的度量标准是？',
    options: [
      { key: 'A', text: '带宽' },
      { key: 'B', text: '跳数' },
      { key: 'C', text: '时延' },
      { key: 'D', text: '负载' },
    ],
    answer: 'B',
    explanation: 'RIP 以跳数作为路由度量，最大 15 跳。',
    difficulty: 'medium',
    knowledgePoint: '路由算法',
    score: 5,
    source: 'ai',
  },
]

export async function mockGenerateExercises(params: GenerateExerciseParams): Promise<GenerateExerciseResult> {
  const filtered = questionTemplates.filter((q) => {
    const typeMatch = !params.questionTypes.length || params.questionTypes.includes(q.type)
    const kpMatch = !params.knowledgePoints.length || params.knowledgePoints.includes(q.knowledgePoint)
    return typeMatch && kpMatch
  })
  const pool = filtered.length ? filtered : questionTemplates
  const batchId = Date.now()
  const usedStems = new Set<string>()
  const questions: QuizQuestion[] = []

  for (let i = 0; i < params.count; i++) {
    const template = pool[i % pool.length]!
    let stem = template.stem
    if (usedStems.has(stem)) {
      stem = `${template.stem}（变体${i + 1}）`
    }
    usedStems.add(stem)
    questions.push({
      ...template,
      stem,
      id: batchId + i,
      courseId: params.courseId,
      difficulty: params.difficulty,
      status: 'draft' as const,
      batchId,
    })
  }

  return {
    batchId,
    questions,
    meta: {
      model: 'deepseek-chat',
      elapsedMs: 4200,
      tokens: 1820,
    },
  }
}

export const mockAiReport = {
  metrics: {
    avgScore: 71.4,
    passRate: 0.82,
    attendanceRate: 0.91,
    warningCount: 6,
    classSize: 45,
  },
  weakKnowledgePoints: [
    { name: '红黑树', correctRate: 0.32 },
    { name: '平衡二叉树', correctRate: 0.45 },
    { name: 'B 树', correctRate: 0.52 },
  ],
  trend: '近三次作业平均分：82 → 78 → 71，呈持续下滑趋势',
  conclusion:
    '数据结构与算法课程整体处于中等偏下水平，班级均分 71.4，及格率 82%。近三次作业成绩持续下滑，需重点关注「树的平衡」相关知识点。',
  suggestions: [
    '针对红黑树、平衡二叉树开展专题复习',
    '对退步明显学生实施一对一辅导',
    '通过 AI 练习巩固薄弱知识点',
  ],
}
