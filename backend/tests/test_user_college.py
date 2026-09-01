"""用户创建/编辑的所属学院字段测试。

覆盖:
- 创建时不填学院 → 默认计算机学院
- 创建时填学院 → 按填写值保存
- 编辑更新学院
- 老数据(未填学院)回退到教师档案的学院
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401  确保所有表注册到 metadata
from app.api.v1.auth import create_token
from app.api.v1.users import router as users_router
from app.core.database import get_session
from app.models import ClassInfo, Course, SysRole, SysUser, Teacher


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(SysRole(role_id=1, role_name="系统管理员", role_code="admin"))
        s.add(SysRole(role_id=2, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=3, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="admin", password="x", real_name="管理员", role_id=1, status=1))
        s.add(SysUser(user_id=2, username="oldteacher", password="x", real_name="老教师", role_id=2, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="老教师", user_id=2, college="数学学院"))
        s.add(ClassInfo(class_id=1, class_name="计科2401班", college="计算机学院", major="计算机科学与技术", grade="2024级"))
        s.add(ClassInfo(class_id=2, class_name="软件1801班", college="计算机学院", major="软件工程", grade="2018级"))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(users_router, prefix="/api")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'admin')}"}


def _create(client, **kwargs):
    payload = {
        "username": kwargs.get("username", "newuser"),
        "password": "123456",
        "real_name": kwargs.get("real_name", "新用户"),
        "role_id": kwargs.get("role_id", 2),
    }
    if "college" in kwargs:
        payload["college"] = kwargs["college"]
    if "class_id" in kwargs:
        payload["class_id"] = kwargs["class_id"]
    if "status" in kwargs:
        payload["status"] = kwargs["status"]
    if "student_no" in kwargs:
        payload["student_no"] = kwargs["student_no"]
    if "gender" in kwargs:
        payload["gender"] = kwargs["gender"]
    if "teacher_no" in kwargs:
        payload["teacher_no"] = kwargs["teacher_no"]
    if "title" in kwargs:
        payload["title"] = kwargs["title"]
    if "phone" in kwargs:
        payload["phone"] = kwargs["phone"]
    if "email" in kwargs:
        payload["email"] = kwargs["email"]
    return client.post("/api/users", json=payload, headers=_auth())


def test_create_user_without_college_defaults(client):
    """创建时不传学院 → 默认计算机学院。"""
    resp = _create(client, username="t_none")
    assert resp.status_code == 201
    assert resp.json()["department"] == "计算机学院"


def test_create_user_with_empty_college_defaults(client):
    """创建时传空字符串 → 默认计算机学院。"""
    resp = _create(client, username="t_empty", college="")
    assert resp.status_code == 201
    assert resp.json()["department"] == "计算机学院"


def test_create_user_with_college(client):
    """创建时填学院 → 按填写值保存。"""
    resp = _create(client, username="t_math", college="数学学院")
    assert resp.status_code == 201
    assert resp.json()["department"] == "数学学院"


def test_update_user_college(client):
    """编辑用户可更新学院。"""
    created = _create(client, username="t_upd", college="物理学院")
    user_id = created.json()["user_id"]
    resp = client.put(f"/api/users/{user_id}", json={"college": "化学学院"}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["department"] == "化学学院"


def test_legacy_user_falls_back_to_teacher_college(client):
    """老数据(用户表未填学院)回退到教师档案学院。"""
    resp = client.get("/api/users", headers=_auth())
    assert resp.status_code == 200
    by_username = {u["username"]: u for u in resp.json()}
    assert by_username["oldteacher"]["department"] == "数学学院"


def test_create_student_requires_class(client):
    resp = _create(client, username="stu_none", role_id=3)
    assert resp.status_code == 400
    assert "所属班级" in resp.json()["detail"]


def test_create_student_with_class(client):
    resp = _create(client, username="stu_ok", role_id=3, class_id=1)
    assert resp.status_code == 201
    body = resp.json()
    assert body["class_id"] == 1
    assert body["class_name"] == "计科2401班"
    assert body["role_code"] == "student"


def test_list_users_filter_by_class(client):
    _create(client, username="stu_a", role_id=3, class_id=1)
    _create(client, username="stu_b", role_id=3, class_id=2)
    resp = client.get("/api/users", params={"class_id": 2}, headers=_auth())
    assert resp.status_code == 200
    names = {u["username"] for u in resp.json()}
    assert "stu_b" in names
    assert "stu_a" not in names


def test_update_student_class(client):
    created = _create(client, username="stu_move", role_id=3, class_id=1)
    user_id = created.json()["user_id"]
    resp = client.put(f"/api/users/{user_id}", json={"class_id": 2}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["class_id"] == 2
    assert resp.json()["class_name"] == "软件1801班"


def test_list_users_filter_by_status(client):
    """按账号状态筛选：0=停用, 1=正常。"""
    _create(client, username="t_off", status=0)
    _create(client, username="t_on", status=1)

    disabled = client.get("/api/users", params={"status": 0}, headers=_auth()).json()
    names = {u["username"] for u in disabled}
    assert "t_off" in names
    assert "t_on" not in names

    enabled = client.get("/api/users", params={"status": 1}, headers=_auth()).json()
    names = {u["username"] for u in enabled}
    assert "t_on" in names
    assert "t_off" not in names


def test_create_student_with_profile_fields(client):
    """创建学生时学生表字段（学号/性别/手机号/邮箱）同步写入。"""
    resp = _create(
        client, username="stu_full", role_id=3, class_id=1,
        student_no="202626010199", gender=0,
        phone="13800001111", email="s@hunnu.edu.cn",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_no"] == "202626010199"
    assert body["gender"] == 0
    assert body["phone"] == "13800001111"
    assert body["email"] == "s@hunnu.edu.cn"


def test_create_student_defaults_student_no_and_gender(client):
    """不填学号/性别时：学号默认与账号相同，性别默认男。"""
    resp = _create(client, username="stu_def", role_id=3, class_id=1)
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_no"] == "stu_def"
    assert body["gender"] == 1


def test_create_student_duplicate_student_no(client):
    """学号重复 → 400，且不残留半成品用户记录。"""
    _create(client, username="stu_dup1", role_id=3, class_id=1, student_no="NO001")
    resp = _create(client, username="stu_dup2", role_id=3, class_id=1, student_no="NO001")
    assert resp.status_code == 400
    assert "已被占用" in resp.json()["detail"]
    # 用户表不应残留第二条记录
    all_users = client.get("/api/users", headers=_auth()).json()
    assert "stu_dup2" not in {u["username"] for u in all_users}


def test_update_student_contact_fields(client):
    """编辑学生可更新手机号/邮箱，写入学生表。"""
    created = _create(client, username="stu_ct", role_id=3, class_id=1)
    user_id = created.json()["user_id"]
    resp = client.put(
        f"/api/users/{user_id}",
        json={"phone": "13900002222", "email": "ct@hunnu.edu.cn"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13900002222"
    assert resp.json()["email"] == "ct@hunnu.edu.cn"


def test_create_teacher_writes_teacher_table(client, engine):
    """创建教师用户同步写入教师表：教工号默认与账号相同，学院默认计算机学院。"""
    resp = _create(client, username="t_new", role_id=2)
    assert resp.status_code == 201
    body = resp.json()
    assert body["teacher_no"] == "t_new"
    with Session(engine) as s:
        teacher = s.exec(select(Teacher).where(Teacher.user_id == body["user_id"])).first()
        assert teacher is not None
        assert teacher.teacher_no == "t_new"
        assert teacher.college == "计算机学院"


def test_create_teacher_with_profile_fields(client, engine):
    """创建教师可指定教工号/职称/手机号/邮箱，写入教师表。"""
    resp = _create(
        client, username="t_full", role_id=2,
        teacher_no="T2001", title="副教授",
        phone="13700003333", email="t@hunnu.edu.cn",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["teacher_no"] == "T2001"
    assert body["title"] == "副教授"
    assert body["phone"] == "13700003333"
    with Session(engine) as s:
        teacher = s.exec(select(Teacher).where(Teacher.user_id == body["user_id"])).first()
        assert teacher.title == "副教授"
        assert teacher.email == "t@hunnu.edu.cn"


def test_create_teacher_duplicate_teacher_no(client):
    """教工号重复 → 400，且不残留半成品用户记录。"""
    _create(client, username="t_dup1", role_id=2, teacher_no="TNO001")
    resp = _create(client, username="t_dup2", role_id=2, teacher_no="TNO001")
    assert resp.status_code == 400
    assert "已被占用" in resp.json()["detail"]
    all_users = client.get("/api/users", headers=_auth()).json()
    assert "t_dup2" not in {u["username"] for u in all_users}


def test_update_teacher_syncs_teacher_table(client, engine):
    """编辑教师同步更新教师表（职称/学院）。"""
    created = _create(client, username="t_sync", role_id=2)
    user_id = created.json()["user_id"]
    resp = client.put(
        f"/api/users/{user_id}",
        json={"title": "教授", "college": "数学学院"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "教授"
    with Session(engine) as s:
        teacher = s.exec(select(Teacher).where(Teacher.user_id == user_id)).first()
        assert teacher.title == "教授"
        assert teacher.college == "数学学院"


def test_delete_teacher_cleans_teacher_row(client, engine):
    """删除无授课课程的教师 → 教师档案一并清理。"""
    created = _create(client, username="t_del", role_id=2)
    user_id = created.json()["user_id"]
    resp = client.delete(f"/api/users/{user_id}", headers=_auth())
    assert resp.status_code == 204
    with Session(engine) as s:
        assert s.exec(select(Teacher).where(Teacher.user_id == user_id)).first() is None


def test_delete_teacher_with_courses_refused(client, engine):
    """有授课课程的教师 → 拒绝删除账号。"""
    created = _create(client, username="t_keep", role_id=2)
    user_id = created.json()["user_id"]
    with Session(engine) as s:
        teacher = s.exec(select(Teacher).where(Teacher.user_id == user_id)).first()
        s.add(Course(
            course_code="C0001", course_name="数据结构", teacher_id=teacher.teacher_id,
            semester="2025-2026-1", college="计算机学院",
        ))
        s.commit()
    resp = client.delete(f"/api/users/{user_id}", headers=_auth())
    assert resp.status_code == 400
    assert "授课课程" in resp.json()["detail"]
