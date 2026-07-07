"""数据模型存放处。

新增模型步骤:
1. 在本目录下新建文件(如 user.py),定义:
       class User(SQLModel, table=True):
           id: int | None = Field(default=None, primary_key=True)
           ...
2. 在本文件里加上: from app.models.user import User
3. 重启后端,init_db() 会自动建表。
"""
