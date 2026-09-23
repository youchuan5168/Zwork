from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from app.db.session import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import PasswordChangeIn, RegisterIn
from app.services.auth import AuthService
from app.core.security import csrf_token, token_claims
from app.core.errors import BusinessError

router = APIRouter(prefix="/api/auth", tags=["auth"])
ACCESS_COOKIE = "qz_access"
CSRF_COOKIE = "qz_csrf"


def auth_context(request):
    config = request.app.state.settings
    if config.app_env == "production" and request.url.scheme != "https":
        raise BusinessError("认证接口必须通过 HTTPS 访问", 400)
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/"), *config.cors_origins}
    if origin is not None and origin not in allowed:
        raise BusinessError("不允许的请求来源", 403)
    return {
        "client_ip": request.client.host if request.client else "unknown",
        "request_id": getattr(request.state, "request_id", ""),
    }


def set_auth_cookies(response, data, config):
    token = data["access_token"]
    csrf = csrf_token(token_claims(token, config), config)
    options = {
        "secure": config.app_env == "production",
        "samesite": "lax",
        "path": "/",
        "max_age": config.jwt_expire_minutes * 60,
    }
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, **options)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **options)
    response.headers["Cache-Control"] = "no-store"


def clear_cookies(response, config):
    for name in (ACCESS_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name, path="/", secure=config.app_env == "production", samesite="lax"
        )


@router.get("/policy")
def policy(request: Request, session: Session = Depends(get_session)):
    return AuthService(session, request.app.state.settings).policy()


@router.post("/register")
def register(
    body: RegisterIn, request: Request, response: Response, session: Session = Depends(get_session)
):
    config = request.app.state.settings
    data = AuthService(session, config).register(body, **auth_context(request))
    set_auth_cookies(response, data, config)
    return data


@router.post("/login")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    config = request.app.state.settings
    data = AuthService(session, config).login(form.username, form.password, **auth_context(request))
    set_auth_cookies(response, data, config)
    return data


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    auth_context(request)
    AuthService(session, request.app.state.settings).revoke_all(user.id)
    clear_cookies(response, request.app.state.settings)
    return {"ok": True}


@router.post("/password")
def change_password(
    body: PasswordChangeIn,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    context = auth_context(request)
    config = request.app.state.settings
    consume_password_limit(session, config, context["client_ip"])
    AuthService(session, config).change_password(user, body)
    clear_cookies(response, config)
    return {"ok": True}


def consume_password_limit(session, config, client_ip):
    from app.core.throttle import consume

    consume(session, config, "password-ip", client_ip, config.auth_register_ip_limit)
