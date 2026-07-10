/**
 * Agent SSE 流式 Mock
 * 模拟 thinking → tool_call → tool_result → content_done 的流式输出
 */
import type { AgentStreamEvent } from '@/types'

/** 模拟延迟 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 根据用户消息内容路由回答
 */
function routeQuestion(message: string): {
  toolName: string
  toolParams: Record<string, unknown>
  toolSummary: string
  toolResult: unknown
  content: string
} {
  const msg = message.toLowerCase()

  if (msg.includes('成绩') || msg.includes('分数') || msg.includes('考了多少')) {
    return {
      toolName: 'query_class_scores',
      toolParams: { courseId: 1, classId: 1 },
      toolSummary: '30 条成绩数据',
      toolResult: { count: 30, avg: 78.5, max: 98, min: 52 },
      content: `计科2401班的数据结构与算法成绩概况如下：\n\n- **班级均分**：78.5 分\n- **最高分**：98 分\n- **最低分**：52 分\n- **及格率**：87.5%\n- **优秀率**：23.3%\n\n从分布来看，成绩整体呈正态分布，中等偏上水平学生占主体。张雅琪（95 分）、陈思远（90 分）表现突出，王浩然（58 分）低于及格线需要关注。相比上次测验，班级均分提升了 3.2 分，学习态势整体向好。\n\n建议：继续保持当前教学节奏，对王浩然等低分学生安排专项辅导。`,
    }
  }

  if (msg.includes('预警') || msg.includes('警告') || msg.includes('危险')) {
    return {
      toolName: 'query_warnings',
      toolParams: { classId: 1, level: 'all' },
      toolSummary: '5 条预警记录',
      toolResult: { count: 5, items: [] },
      content: `当前班级共有 **5 名学生触发预警**：\n\n| 学生 | 类型 | 级别 | 原因 |\n|------|------|------|------|\n| 王浩然 | 成绩下滑 | 高 | 近两次成绩 85→72→58 |\n| 刘嘉伟 | 出勤不足 | 中 | 近两周缺勤 3 次 |\n| 孙博文 | 作业缺交 | 中 | 连续 2 次未提交 |\n| 林雨晴 | 知识点薄弱 | 低 | 图论掌握度 52% |\n| 郑明轩 | 综合预警 | 高 | 多维度预警 |\n\n**建议处理优先级**：\n1. 🔴 王浩然、郑明轩（高级别）—— 本周内进行一对一谈话\n2. 🟡 刘嘉伟、孙博文（中级别）—— 课堂上关注并提醒\n3. 🟢 林雨晴（低级别）—— 推荐专项练习资源`,
    }
  }

  if (msg.includes('薄弱') || msg.includes('知识点') || msg.includes('掌握')) {
    return {
      toolName: 'query_knowledge_mastery',
      toolParams: { courseId: 1, classId: 1 },
      toolSummary: '8 个知识点掌握数据',
      toolResult: { points: 8 },
      content: `班级知识点掌握度分析（数据结构与算法）：\n\n**✅ 掌握良好（≥80%）**：\n- 线性表：88%\n- 栈与队列：86%\n- 排序算法：85%\n\n**⚠️ 需关注（60%-80%）**：\n- 树与二叉树：78%\n- 递归：75%\n- 查找算法：72%\n\n**🔴 薄弱项（<60%）**：\n- 哈希表：58%\n- 图论：62%\n\n**薄弱知识点 Top 3**：哈希表（58%）、图论（62%）、查找算法（72%）。\n\n建议：针对哈希表和图论安排 2 课时专项复习，配合 AI 出题系统生成针对性练习题。`,
    }
  }

  if (msg.includes('建议') || msg.includes('怎么办') || msg.includes('如何') || msg.includes('改进')) {
    return {
      toolName: 'query_class_scores',
      toolParams: { courseId: 1 },
      toolSummary: '30 条成绩数据',
      toolResult: { count: 30 },
      content: `基于班级学情数据，给出以下教学建议：\n\n1. **分层教学**：班级前 30% 学生（≥85 分）可引入拓展题和竞赛题；中间 50% 巩固基础；后 20% 需要基础补强。\n\n2. **薄弱知识点专项突破**：\n   - 哈希表（掌握度 58%）：从哈希函数设计到冲突解决，配合代码实操\n   - 图论（掌握度 62%）：DFS/BFS → 最短路径 → 最小生成树，循序渐进\n\n3. **预警学生干预**：5 名预警学生中，王浩然成绩下滑最明显（85→58），建议优先谈话了解原因。\n\n4. **利用 AI 工具**：可通过"AI 出题"功能，按薄弱知识点自动生成练习题，推送给学生精准练习。\n\n5. **课堂互动**：建议增加课堂提问和小测验频次，及时掌握学生理解情况。`,
    }
  }

  if (msg.includes('趋势') || msg.includes('变化') || msg.includes('进步')) {
    return {
      toolName: 'query_grade_trend',
      toolParams: { courseId: 1, classId: 1 },
      toolSummary: '6 个数据点',
      toolResult: { trend: 6 },
      content: `班级成绩趋势分析（近 6 个月）：\n\n- 2025年9月：均分 75，及格率 82.0%\n- 2025年10月：均分 77，及格率 84.5%\n- 2025年11月：均分 78，及格率 85.0%\n- 2025年12月：均分 80，及格率 87.0%\n- 2026年1月：均分 79，及格率 86.5%\n- 2026年2月：均分 81，及格率 87.5%\n\n**总体趋势向好**：均分从 75 提升至 81（+6 分），及格率从 82% 提升至 87.5%（+5.5pp）。\n\n1月份略有回落（期末考试周后放松），2月份回升。建议保持当前教学策略，持续跟踪。`,
    }
  }

  // 默认回答
  return {
    toolName: 'query_class_scores',
    toolParams: { courseId: 1 },
    toolSummary: '30 条数据',
    toolResult: { count: 30 },
    content: `我已查询了班级学情数据。数据结构与算法课程当前有 30 名学生，班级均分 78.5 分，及格率 87.5%，整体表现良好。\n\n您可以问我：\n- **成绩分析**："班级成绩怎么样？"\n- **预警学生**："有哪些需要关注的学生？"\n- **薄弱知识点**："哪些知识点掌握不好？"\n- **教学建议**："有什么教学改进建议？"\n- **成绩趋势**："成绩变化趋势如何？"\n\n我会调用相应的查询工具为您提供精准的分析。`,
  }
}

/**
 * 流式 Agent 对话 Mock（AsyncGenerator）
 */
export async function* mockStreamAgentChat(message: string): AsyncGenerator<AgentStreamEvent> {
  const route = routeQuestion(message)
  const callId = 'tc-1'

  // 1. thinking
  await sleep(400)
  yield { type: 'thinking' }

  // 2. tool_call
  await sleep(500)
  yield {
    type: 'tool_call',
    call: {
      id: callId,
      tool: route.toolName,
      params: route.toolParams,
      status: 'running' as const,
    },
  }

  // 3. tool_result
  await sleep(600)
  yield {
    type: 'tool_result',
    callId,
    result: route.toolResult,
    summary: route.toolSummary,
  }

  // 4. content_done
  await sleep(400)
  yield {
    type: 'content_done',
    content: route.content,
    sources: [],
  }
}
