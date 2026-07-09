"""算法服务层。

将所有教学分析算法（成绩预测、画像、掌握度、预警、评价、标签、报告、去重）
集中在此处。API 层只调用本包函数，不直接拼装业务逻辑。

模块清单（对应算法决策记录）：
    predict.py          D01 成绩预测 / D04 学习进步
    profile.py          D02 学业水平 / D03 学习态度 / D04 进步分
    mastery.py          D05 知识点掌握度等级
    warning.py          D06/D07 异常预警规则引擎
    evaluation.py       D08 学习质量评价聚合
    tag.py              D09 学情标签生成
    report_template.py  D10 报告模板兜底
    dedup.py            D12 题目去重
"""
