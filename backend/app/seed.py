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
# from app.models import User  # ← 写好 User model 后,在这里取消注释


def reset() -> None:
    """删除所有表后重建,回到干净起点。"""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("[seed] 数据库已重建")


def seed() -> None:
    """灌入演示数据。"""
    init_db()  # 表不存在时自动创建
    with Session(engine) as session:
        # ====== 在这里插入演示数据 ======
        #
        # 示例:假设你定义了 User model
        #
        # from app.models import User
        # session.add(User(username="teacher01", password="123456", name="张老师", role="teacher"))
        # session.add(User(username="admin",     password="123456", name="管理员",  role="admin"))
        # session.commit()
        #
        # 插入完后可以查一下:
        # users = session.exec(select(User)).all()
        # print(f"  共 {len(users)} 个用户")
        #
        # ====== 结束 ======
        pass
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
