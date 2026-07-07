"""数据模型存放处。

新增模型步骤:
1. 在本目录下新建文件(如 user.py),定义 table=True 的 SQLModel
2. 在本文件里加上对应的 import
3. 重启后端,init_db() 会自动建表
"""

from app.models.user import User, UserCreate, UserRead, UserUpdate

__all__ = ["User", "UserCreate", "UserRead", "UserUpdate"]
