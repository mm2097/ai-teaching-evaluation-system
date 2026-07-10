/**
 * 分析类数据（画像、成绩趋势、知识点热力图、预警、预测、看板 stats）
 */
import { students } from './static'

/* ============================================================ */
/* 看板统计                                                      */
/* ============================================================ */

export function dashboardStats(_courseId?: number) {
  return {
    studentCount: 30,
    courseCount: 4,
    teacherCount: 5,
    passRate: 87.5,
    excellentRate: 23.3,
    attendanceRate: 94.2,
    warningCount: 5,
  }
}

/* ============================================================ */
/* 成绩趋势（班级 / 学生共用）                                    */
/* ============================================================ */

export function gradeTrend(_params: Record<string, unknown>) {
  const months = ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01', '2026-02']
  return {
    months,
    labels: months, // StudentDashboard 用 labels
    passRate: [82.0, 84.5, 85.0, 87.0, 86.5, 87.5],
    excellentRate: [18.0, 19.5, 21.0, 22.5, 22.0, 23.3],
    avgScore: [75, 77, 78, 80, 79, 81],
    avg_score: [75, 77, 78, 80, 79, 81], // StudentDashboard 用 avg_score
    maxScore: [98, 99, 97, 100, 96, 98],
    minScore: [52, 48, 55, 50, 58, 53],
    scores: [75, 77, 78, 80, 79, 81], // 学生维度
    classAvgScores: [72, 74, 75, 77, 76, 78],
  }
}

/* ============================================================ */
/* 学情画像（单个学生）                                          */
/* ============================================================ */

export function studentProfile(studentId: number, _courseId: number) {
  const stu = students.find((s) => s.student_id === studentId) || students[0]!
  return {
    studentId: stu.student_id,
    studentNo: stu.student_no,
    studentName: stu.real_name,
    className: '计科2401',
    courseName: '数据结构与算法',
    tags: ['思维活跃', '基础扎实', '需加强图论'],
    radarValues: [88, 92, 75, 60, 82, 70],
    dimensionScores: [
      { name: '学业成绩', score: 88, desc: '加权平均分排名班级前列' },
      { name: '学习态度', score: 92, desc: '出勤率高，课堂互动积极' },
      { name: '作业完成', score: 75, desc: '提交率良好，部分题目有困难' },
      { name: '知识掌握', score: 60, desc: '图、哈希表等知识点需加强' },
      { name: '学习进步', score: 82, desc: '近三次测验成绩稳步提升' },
      { name: '课堂参与', score: 70, desc: '参与度中等，可更主动' },
    ],
    strongPoints: '线性表、栈与队列掌握扎实，排序算法理解深入',
    weakPoints: '图论相关算法（DFS/BFS 应用）和哈希表冲突解决策略偏薄弱',
  }
}

/* ============================================================ */
/* 知识点热力图                                                  */
/* ============================================================ */

export function knowledgeHeatmap(courseId?: number, _classId?: number, _studentId?: number) {
  const kps = getKnowledgePoints(courseId || 1)
  // 取前 10 个学生
  const sampleStudents = students.slice(0, 10).map((s) => s.real_name)
  const data: number[][] = []

  // 生成 [kpIdx, studentIdx, mastery%] 的三元组数组
  for (let kpIdx = 0; kpIdx < kps.length; kpIdx++) {
    for (let sIdx = 0; sIdx < sampleStudents.length; sIdx++) {
      // 基于索引生成有梯度的数据
      const base = 55 + ((kpIdx * 13 + sIdx * 7) % 45)
      const mastery = Math.min(98, base + (sIdx % 3) * 5)
      data.push([kpIdx, sIdx, mastery])
    }
  }

  // 班级平均
  const classAvgByKp = kps.map((_, kpIdx) => {
    const values = data.filter((d) => d[0] === kpIdx).map((d) => d[2]!)
    return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10
  })

  return {
    knowledgePoints: kps,
    students: sampleStudents,
    data,
    classAvgByKp,
  }
}

function getKnowledgePoints(courseId: number): string[] {
  const map: Record<number, string[]> = {
    1: ['线性表', '栈与队列', '树与二叉树', '图', '排序算法', '查找算法', '哈希表', '递归'],
    2: ['搜索算法', '知识表示', '机器学习', '神经网络', '自然语言处理', '深度学习'],
    3: ['进程管理', '内存管理', '文件系统', 'I/O 管理', '死锁处理'],
    4: ['SQL 查询', '数据库设计', '事务管理', '索引优化', '范式理论'],
  }
  return map[courseId] || map[1]!
}

/* ============================================================ */
/* 预警记录                                                      */
/* ============================================================ */

export function warnings(_params: Record<string, unknown>) {
  return [
    {
      id: 1, studentId: '20240103', studentName: '王浩然', className: '计科2401',
      classId: 1, deptId: 1, courseId: 1, courseName: '数据结构与算法',
      semesterId: 2, type: '成绩下滑', level: '高',
      reason: '近两次测验成绩持续下降（85→72→58），知识掌握度低于 60%',
      warningTime: '2026-03-18 09:00:00', status: 0,
    },
    {
      id: 2, studentId: '20240105', studentName: '刘嘉伟', className: '计科2401',
      classId: 1, deptId: 1, courseId: 1, courseName: '数据结构与算法',
      semesterId: 2, type: '出勤不足', level: '中',
      reason: '近两周缺勤 3 次，出勤率低于 80%',
      warningTime: '2026-03-17 10:00:00', status: 0,
    },
    {
      id: 3, studentId: '20240203', studentName: '孙博文', className: '计科2402',
      classId: 2, deptId: 1, courseId: 1, courseName: '数据结构与算法',
      semesterId: 2, type: '作业缺交', level: '中',
      reason: '连续 2 次作业未提交',
      warningTime: '2026-03-16 15:00:00', status: 1,
    },
    {
      id: 4, studentId: '20240102', studentName: '林雨晴', className: '计科2401',
      classId: 1, deptId: 1, courseId: 1, courseName: '数据结构与算法',
      semesterId: 2, type: '知识点薄弱', level: '低',
      reason: '图论相关知识点掌握度仅 52%，低于班级平均水平',
      warningTime: '2026-03-15 09:00:00', status: 0,
    },
    {
      id: 5, studentId: '20240301', studentName: '郑明轩', className: '软工2401',
      classId: 3, deptId: 2, courseId: 1, courseName: '数据结构与算法',
      semesterId: 2, type: '综合预警', level: '高',
      reason: '成绩下滑 + 出勤不足 + 作业缺交，多维度预警',
      warningTime: '2026-03-14 14:00:00', status: 2,
    },
  ]
}

/* ============================================================ */
/* 成绩预测                                                      */
/* ============================================================ */

export function gradePredictions(_courseId?: number, _classId?: number) {
  const sample = students.slice(0, 8)
  return sample.map((s, i) => {
    const current = 60 + ((i * 37) % 38)
    const predicted = current + (i % 3 === 0 ? -5 : i % 3 === 1 ? 3 : 8)
    const trend: '上升' | '下滑' | '稳定' = i % 3 === 0 ? '下滑' : i % 3 === 1 ? '稳定' : '上升'
    return {
      name: s.real_name,
      current,
      predicted: String(Math.min(100, predicted)),
      trend,
      confidence: 0.72 + (i % 4) * 0.06,
    }
  })
}
