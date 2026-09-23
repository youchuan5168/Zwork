"""密码兼容 bcrypt；短期 JWT 携带可撤销版本，拒绝旧格式令牌。"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

DUMMY_HASH = bcrypt.hashpw(b"dummy-password-not-used", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, config=None, *, token_version: int = 0) -> str:
    config = config or settings
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=config.jwt_expire_minutes),
            "iat": now,
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
            "jti": secrets.token_urlsafe(24),
            "ver": token_version,
        },
        config.jwt_secret,
        algorithm="HS256",
    )


def token_claims(token: str, config=None) -> dict:
    config = config or settings
    payload = jwt.decode(
        token,
        config.jwt_secret,
        algorithms=["HS256"],
        issuer=config.jwt_issuer,
        audience=config.jwt_audience,
        options={"require": ["sub", "exp", "iat", "iss", "aud", "jti", "ver"]},
    )
    if not isinstance(payload["sub"], str) or not payload["sub"].isdigit():
        raise jwt.InvalidTokenError("invalid subject")
    if int(payload["sub"]) <= 0 or type(payload["ver"]) is not int or payload["ver"] < 0:
        raise jwt.InvalidTokenError("invalid identity")
    if not isinstance(payload["jti"], str) or len(payload["jti"]) < 16:
        raise jwt.InvalidTokenError("invalid token id")
    return payload


def csrf_token(claims: dict, config=None) -> str:
    config = config or settings
    return hmac.new(
        config.jwt_secret.encode(), ("csrf:" + claims["jti"]).encode(), hashlib.sha256
    ).hexdigest()
