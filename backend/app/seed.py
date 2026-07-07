"""Seed 脚本:灌入统一的演示数据。

用法:
    python -m app.seed              # 灌入数据(表不存在会自动建)
    python -m app.seed --reset      # 删库重建后再灌入(推荐,回到干净起点)

新增表后,在 seed() 函数里照着注释示例加插入语句即可。
"""
from __future__ import annotations

import argparse

from sqlmodel import Session, SQLModel

from app.core.database import engine, init_db
from app.models import User


def reset() -> None:
    """删除所有表后重建,回到干净起点。"""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("[seed] 数据库已重建")


def seed() -> None:
    """灌入演示数据。"""
    init_db()  # 表不存在时自动创建
    with Session(engine) as session:
        # ====== 演示数据 ======
        users = [
            User(username="admin", password="123456", name="张管理", role="admin", department="信息中心", status=True),
            User(username="manager", password="123456", name="李教务", role="manager", department="教务处", status=True),
            User(username="teacher", password="123456", name="王教授", role="teacher", department="计算机学院", status=True),
            User(username="teacher2", password="123456", name="李副教授", role="teacher", department="数学学院", status=False),
            User(username="student", password="123456", name="陈同学", role="student", department="计算机学院", status=True),
        ]
        session.add_all(users)
        session.commit()

        # 确认一下
        from sqlmodel import select
        all_users = session.exec(select(User)).all()
        print(f"  共 {len(all_users)} 个用户: {[u.username for u in all_users]}")
    print("[seed] 演示数据已灌入")


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入演示数据")
    parser.add_argument("--reset", action="store_true", help="删库重建后再灌入")
    args = parser.parse_args()

    if args.reset:
        reset()
    seed()


if __name__ == "__main__":
    main()
