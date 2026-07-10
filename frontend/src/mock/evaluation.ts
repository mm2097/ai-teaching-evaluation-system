/**
 * 学习质量评价数据（学生/教师/课程评价）
 */
import { students, teachers, courses } from './static'

/* ============================================================ */
/* 学生评价列表                                                  */
/* ============================================================ */

export function studentEvaluations() {
  const sample = students.slice(0, 12)
  const grades = ['优秀', '优秀', '良好', '良好', '良好', '中等', '中等', '中等', '合格', '合格', '良好', '优秀'] as const
  return sample.map((s, i) => {
    const total = 58 + ((i * 37) % 42)
    return {
      id: i + 1,
      targetName: s.real_name,
      targetType: 'student',
      totalScore: total,
      grade: total >= 90 ? '优秀' : total >= 80 ? '良好' : total >= 70 ? '中等' : total >= 60 ? '合格' : '不合格',
      dimensions: [
        { name: '学业成绩', score: total, weight: 40 },
        { name: '学习态度', score: Math.min(100, total + 5 + (i % 5)), weight: 25 },
        { name: '学习进步', score: Math.max(50, total - 3 + ((i * 3) % 10)), weight: 20 },
        { name: '知识掌握', score: Math.max(50, total - 5 + (i % 7)), weight: 15 },
      ],
      rank: i + 1,
    }
  })
}

/* ============================================================ */
/* 教师评价（复用学生评价数据结构）                                */
/* ============================================================ */

export function teacherEvaluations() {
  const sample = teachers.slice(0, 4)
  return sample.map((t, i) => {
    const total = 82 + (i * 4) - (i % 2) * 2
    return {
      id: i + 1,
      targetName: t.real_name,
      targetType: 'teacher',
      totalScore: total,
      grade: total >= 90 ? '优秀' : total >= 80 ? '良好' : '中等',
      dimensions: [
        { name: '教学效果', score: total, weight: 35 },
        { name: '教学态度', score: Math.min(100, total + 3), weight: 20 },
        { name: '考核质量', score: Math.max(70, total - 2), weight: 25 },
        { name: '学生评价', score: Math.max(70, total - 1), weight: 20 },
      ],
      rank: i + 1,
    }
  })
}

/* ============================================================ */
/* 课程评价                                                      */
/* ============================================================ */

export function courseEvaluations() {
  const sample = courses.slice(0, 3)
  return sample.map((c, i) => {
    const total = 78 + i * 5
    return {
      id: i + 1,
      targetName: c.course_name,
      targetType: 'course',
      totalScore: total,
      grade: total >= 90 ? '优秀' : total >= 80 ? '良好' : '中等',
      dimensions: [
        { name: '考核质量', score: total, weight: 30 },
        { name: '学生参与', score: Math.min(100, total + 5), weight: 25 },
        { name: '成绩合理', score: Math.max(70, total - 3), weight: 25 },
        { name: '教学效果', score: Math.max(70, total + 1), weight: 20 },
      ],
      rank: i + 1,
    }
  })
}

/* ============================================================ */
/* 学生个人评价结果（StudentEvalView）                            */
/* ============================================================ */

export function studentEvaluationResults(studentId?: number) {
  const stu = students.find((s) => s.student_id === studentId) || students[0]!
  return [
    {
      student_id: stu.student_id,
      student_name: stu.real_name,
      total_score: 88.5,
      grade: '优秀',
      created_at: '2026-03-01 10:00:00',
    },
    {
      student_id: stu.student_id,
      student_name: stu.real_name,
      total_score: 85.2,
      grade: '良好',
      created_at: '2025-12-01 10:00:00',
    },
    {
      student_id: stu.student_id,
      student_name: stu.real_name,
      total_score: 82.0,
      grade: '良好',
      created_at: '2025-09-01 10:00:00',
    },
  ]
}
