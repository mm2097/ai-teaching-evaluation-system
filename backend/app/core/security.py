"""密码哈希与旧明文密码兼容迁移。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_SCHEME = "scrypt"
_N = 2**14
_R = 8
_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    """使用带随机盐的 scrypt 生成可存储密码串。"""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_KEY_BYTES,
    )
    return "$".join((
        _SCHEME,
        str(_N),
        str(_R),
        str(_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    ))


def verify_password(password: str, stored_password: str) -> bool:
    """校验密码；未迁移的旧明文记录仍可登录一次。"""
    if not stored_password.startswith(f"{_SCHEME}$"):
        return hmac.compare_digest(password, stored_password)

    try:
        scheme, n, r, p, salt_text, hash_text = stored_password.split("$", 5)
        if scheme != _SCHEME:
            return False
        expected = base64.b64decode(hash_text, validate=True)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_text, validate=True),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def password_needs_rehash(stored_password: str) -> bool:
    """判断是否为旧明文或参数已过期的哈希。"""
    try:
        scheme, n, r, p, *_ = stored_password.split("$", 5)
        return (
            scheme != _SCHEME
            or int(n) != _N
            or int(r) != _R
            or int(p) != _P
        )
    except (ValueError, TypeError):
        return True
