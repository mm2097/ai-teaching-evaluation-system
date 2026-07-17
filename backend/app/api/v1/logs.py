"""操作日志 API。"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.permissions import require_admin
from app.models import SysOperationLog, SysUser

router = APIRouter()


@router.get("/logs", tags=["系统日志"])
def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """分页查询操作日志。"""
    stmt = select(SysOperationLog).order_by(SysOperationLog.operation_time.desc())
    all_logs = session.exec(stmt).all()

    total = len(all_logs)
    start = (page - 1) * page_size
    logs = all_logs[start:start + page_size]

    result = []
    for log in logs:
        user = session.get(SysUser, log.user_id)
        result.append({
            "id": log.log_id,
            "username": user.username if user else "",
            "operation": log.content,
            "type": log.module,
            "ip": log.ip_address or "",
            "time": log.operation_time.strftime("%Y-%m-%d %H:%M:%S") if log.operation_time else "",
        })

    return {"list": result, "total": total}
