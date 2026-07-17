"""Administrator governance overview API."""
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.permissions import require_admin
from app.models import SysOperationLog, SysRole, SysUser

router = APIRouter()


def _ai_service_status() -> str:
    """Probe the algorithm service without blocking the admin page for long."""
    try:
        response = httpx.get(
            f"http://127.0.0.1:{settings.AI_SERVICE_PORT}/health",
            timeout=0.6,
        )
        return "online" if response.is_success else "degraded"
    except httpx.RequestError:
        return "offline"


@router.get("/admin/overview", tags=["系统管理"])
def get_admin_overview(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """Return account, audit, and service status data for administrators."""
    users = list(session.exec(select(SysUser)).all())
    roles = list(session.exec(select(SysRole)).all())
    role_by_id = {role.role_id: role.role_code for role in roles}
    role_counts = {"admin": 0, "teacher": 0, "student": 0}
    for user in users:
        role_code = role_by_id.get(user.role_id, "")
        if role_code in role_counts:
            role_counts[role_code] += 1

    recent_logs = list(session.exec(
        select(SysOperationLog)
        .order_by(SysOperationLog.operation_time.desc())
        .limit(6)
    ).all())
    user_names = {user.user_id: user.username for user in users}

    return {
        "summary": {
            "totalUsers": len(users),
            "activeUsers": sum(user.status == 1 for user in users),
            "disabledUsers": sum(user.status == 0 for user in users),
            "roleCount": len(roles),
        },
        "roleCounts": role_counts,
        "recentOperations": [
            {
                "id": log.log_id,
                "username": user_names.get(log.user_id, ""),
                "module": log.module,
                "operation": log.operation,
                "content": log.content,
                "time": (
                    log.operation_time.strftime("%Y-%m-%d %H:%M:%S")
                    if log.operation_time else ""
                ),
            }
            for log in recent_logs
        ],
        "services": {
            "backend": "online",
            "database": "online",
            "aiService": _ai_service_status(),
        },
        "system": {
            "appName": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "currentAdmin": current_user.real_name,
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
