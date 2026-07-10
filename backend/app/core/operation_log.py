from typing import Optional

import jwt
from jwt import PyJWTError
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.models import SysOperationLog, SysUser

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    session: Session = Depends(get_session),
) -> SysUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token",
        )

    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload.get("sub"))
    except (PyJWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = session.get(SysUser, user_id)
    if not user or user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or disabled user",
        )

    return user


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def save_operation_log(
    session: Session,
    user_id: int,
    module: str,
    operation: str,
    content: str,
    ip_address: Optional[str] = None,
) -> None:
    log = SysOperationLog(
        user_id=user_id,
        module=module,
        operation=operation,
        content=content,
        ip_address=ip_address,
    )
    session.add(log)
    session.commit()
