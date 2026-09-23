import hmac
import jwt
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session
from app.core.actor import Actor
from app.core.security import csrf_token, token_claims
from app.db.session import get_session
from app.models import User


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    config = request.app.state.settings
    if config.app_env == "production" and request.url.scheme != "https":
        raise HTTPException(400, "必须通过 HTTPS 访问")
    authorization = request.headers.get("authorization")
    bearer = authorization is not None
    if bearer:
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
    else:
        token = request.cookies.get("qz_access", "")
    error = HTTPException(401, "登录已过期，请重新登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = token_claims(token, config)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise error from None
    user = session.get(User, int(claims["sub"]))
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise error
    if not bearer and request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(
            supplied.encode(), csrf_token(claims, config).encode()
        ):
            raise HTTPException(403, "CSRF 校验失败")
    return user


def get_actor(user: User = Depends(get_current_user)) -> Actor:
    return Actor(user.id)
