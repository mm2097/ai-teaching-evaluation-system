/**
 * Agent 对话模拟数据与 SSE 流式模拟
 */
import { delay } from '@/utils/auth'
import type { AgentStreamEvent, AgentType } from '@/types'

interface AgentChatContext {
  courseId: number
  courseName: string
  agentType: AgentType
  message: string
}

const toolSummaries: Record<string, string> = {
  get_score_trend: '作业1 82 → 作业2 78 → 期中 71',
  get_score_list: '张三 55、李四 58、王五 60 …',
  get_knowledge_mastery: '红黑树 30%、平衡二叉树 45% …',
  get_course_overview: '均分 71.4、及格率 82%、预警 6 人',
  get_weak_knowledge_points: '红黑树 32%、平衡二叉树 45%、B 树 52%',
  get_warning_students: '张三(成绩下滑)、李四(缺勤)、王五(作业未交)',
  get_student_detail: '张三期中 55 分(-23)、出勤 75%、红黑树 30%',
  get_attendance: '出勤率 75%，缺勤日期：3/5、3/12、3/18',
  get_existing_exercises: '已有 12 道相关题目',
  generate_exercises: '已生成 10 道中等难度题目',
  check_duplicate: '2 道与题库相似度 > 0.8，已剔除',
  explain_concept: '已生成知识点讲解',
  get_my_exercise_records: '近 5 次练习：3 对 2 错',
  get_my_weak_points: '薄弱点：HTTP协议 48%、网络安全 52%',
  generate_hint: '已生成解题提示（不含答案）',
}

function buildQaAnswer(message: string): { content: string; sources: string[]; tools: string[] } {
  const lower = message.toLowerCase()

  if (/均分|及格率|概况|整体/.test(message)) {
    return {
      content:
        '本期班级均分 **71.4**，及格率 **82%**，出勤率 **91%**，当前有 **6** 名学生触发预警。\n\n【建议】重点关注成绩持续下滑的学生群体。\n\n【数据来源】get_course_overview',
      sources: ['get_course_overview'],
      tools: ['get_course_overview'],
    }
  }

  if (/退步|下滑|期中/.test(message)) {
    return {
      content:
        '期中考试班级均分 **71**，相比作业阶段(82→78→71)持续下滑。\n\n退步最明显的三位同学：\n· **张三** 期中 55 分（较前次下降 23 分）\n· **李四** 期中 58 分（下降 19 分）\n· **王五** 期中 60 分（下降 17 分）\n\n张三主要失分在「红黑树」（正确率 30%）和「平衡二叉树」（45%）。\n\n【建议】下节课可针对"树的平衡"做一次专题复习。\n\n【数据来源】get_score_trend / get_score_list / get_knowledge_mastery',
      sources: ['get_score_trend', 'get_score_list', 'get_knowledge_mastery'],
      tools: ['get_score_trend', 'get_score_list', 'get_knowledge_mastery'],
    }
  }

  if (/张三/.test(message) && /出勤|考勤/.test(message)) {
    return {
      content:
        '**张三** 出勤率 **75%**，缺勤日期：3/5、3/12、3/18。出勤偏低与其成绩下滑（期中 55 分）存在关联。\n\n【数据来源】get_attendance',
      sources: ['get_attendance'],
      tools: ['get_attendance'],
    }
  }

  if (/张三/.test(message)) {
    return {
      content:
        '**张三** 最近状态：\n· 期中成绩 **55** 分（较前次下降 23 分）\n· 出勤率 **75%**\n· 薄弱知识点：红黑树 **30%**、平衡二叉树 **45%**\n· 已触发 **成绩下滑** 预警\n\n【建议】建议一对一辅导，重点补强树的平衡相关知识点。\n\n【数据来源】get_student_detail',
      sources: ['get_student_detail'],
      tools: ['get_student_detail'],
    }
  }

  if (/薄弱|最差|知识点/.test(message)) {
    return {
      content:
        '班级掌握度最低的知识点：\n· **红黑树** 32%（45 人中 38 人低于 60%）\n· **平衡二叉树** 45%\n· **B 树** 52%\n\n【建议】优先安排「红黑树」专题练习与讲解。\n\n【数据来源】get_weak_knowledge_points',
      sources: ['get_weak_knowledge_points'],
      tools: ['get_weak_knowledge_points'],
    }
  }

  if (/预警/.test(message)) {
    return {
      content:
        '当前预警学生 **6** 人：\n· **张三** — 成绩下滑（高）\n· **李四** — 缺勤超标（中）\n· **王五** — 作业未交（高）\n\n【数据来源】get_warning_students',
      sources: ['get_warning_students'],
      tools: ['get_warning_students'],
    }
  }

  if (/你好|您好|hi|hello/.test(lower)) {
    return {
      content: '您好！我是学情分析助手，可以帮您查询班级成绩、知识点掌握度、预警学生等信息。请问想了解什么？',
      sources: [],
      tools: [],
    }
  }

  if (/改.*成绩|删除|密码/.test(message)) {
    return {
      content: '抱歉，我只能查询学情数据，无法修改成绩或访问敏感系统信息。如需调整成绩，请通过教务系统操作。',
      sources: [],
      tools: [],
    }
  }

  return {
    content:
      '根据当前课程数据，班级整体表现中等偏下，建议重点关注「红黑树」「平衡二叉树」等薄弱知识点，并对退步学生进行针对性辅导。\n\n【数据来源】get_course_overview / get_weak_knowledge_points',
    sources: ['get_course_overview', 'get_weak_knowledge_points'],
    tools: ['get_course_overview', 'get_weak_knowledge_points'],
  }
}

function buildExamAnswer(): { content: string; sources: string[]; tools: string[] } {
  return {
    content:
      '【组卷方案 · 数据结构与算法】\n目标：10 题 · 中等难度 · 覆盖班级 Top3 薄弱知识点\n\n知识点分布（基于班级掌握度）：\n· 红黑树（30%掌握）→ 4 题\n· 平衡二叉树（45%）→ 3 题\n· B 树（52%）→ 3 题\n\n题型分布：单选 6 / 多选 2 / 判断 2\n\n【说明】其中 2 道生成题与已有题库相似度>0.8，已自动剔除并补题。\n请审核后点击「发布到班级」。\n\n【数据来源】get_weak_knowledge_points / get_existing_exercises / generate_exercises / check_duplicate',
    sources: ['get_weak_knowledge_points', 'get_existing_exercises', 'generate_exercises', 'check_duplicate'],
    tools: ['get_weak_knowledge_points', 'get_existing_exercises', 'generate_exercises', 'check_duplicate'],
  }
}

function buildTutorAnswer(message: string): { content: string; sources: string[]; tools: string[] } {
  if (/TCP|三次握手/.test(message)) {
    return {
      content:
        '**TCP 三次握手**建立可靠连接：\n1. 客户端发 **SYN**\n2. 服务器回 **SYN+ACK**\n3. 客户端发 **ACK**\n\n小提示：记住「我来了→好的欢迎→确认到达」三步，考试常考标志位组合。\n\n【说明】本助手只提供思路提示，不直接给出作业答案。',
      sources: ['explain_concept'],
      tools: ['explain_concept'],
    }
  }
  if (/红黑树|平衡/.test(message)) {
    return {
      content:
        '**红黑树**是一种自平衡二叉搜索树，通过颜色规则（红/黑节点）和旋转保持近似平衡。\n\n学习建议：先掌握 BST 中序遍历，再理解左旋/右旋，最后记五条红黑性质。\n\n【说明】如需错题分析，请描述你的解题思路，我会帮你找漏洞。',
      sources: ['explain_concept'],
      tools: ['explain_concept'],
    }
  }
  if (/错题|分析/.test(message)) {
    return {
      content:
        '我来帮你分析错题思路：\n1. 先确认题目考查的知识点\n2. 回顾你做答时排除了哪些选项\n3. 对照标准答案找逻辑断点\n\n请把具体题目和你的思路发给我，我会给出针对性提示（不直接给答案）。\n\n【数据来源】get_my_exercise_records / generate_hint',
      sources: ['get_my_exercise_records', 'generate_hint'],
      tools: ['get_my_exercise_records', 'generate_hint'],
    }
  }
  return {
    content:
      '我是学生助学助手，可以帮你：\n· 讲解课程知识点\n· 分析错题思路\n· 提供解题提示（不直接给答案）\n\n你可以问我「TCP 三次握手是什么」「帮我分析这道错题」等问题。',
    sources: [],
    tools: [],
  }
}

/** 模拟 Agent SSE 流式响应 */
export async function* mockAgentStream(ctx: AgentChatContext): AsyncGenerator<AgentStreamEvent> {
  yield { type: 'thinking' }
  await delay(400)

  const answer = ctx.agentType === 'exam'
    ? buildExamAnswer()
    : ctx.agentType === 'tutor'
      ? buildTutorAnswer(ctx.message)
      : buildQaAnswer(ctx.message)

  for (const tool of answer.tools) {
    const callId = `${tool}-${Date.now()}`
    yield {
      type: 'tool_call',
      call: {
        id: callId,
        tool,
        params: { course_id: ctx.courseId },
        status: 'running',
      },
    }
    await delay(600)
    yield {
      type: 'tool_result',
      callId,
      result: { summary: toolSummaries[tool] },
      summary: toolSummaries[tool] || '查询完成',
    }
    await delay(300)
  }

  const chunks = answer.content.match(/[\s\S]{1,20}/g) || [answer.content]
  let accumulated = ''
  for (const chunk of chunks) {
    accumulated += chunk
    yield { type: 'content_delta', delta: chunk }
    await delay(80)
  }

  yield {
    type: 'content_done',
    content: answer.content,
    sources: answer.sources,
  }
}
