import logging
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.errors import BusinessError
from app.core.security import DUMMY_HASH, create_token, hash_password, verify_password
from app.core.throttle import consume
from app.db.session import transaction
from app.models import User
from app.repositories.catalog import UserRepository

audit = logging.getLogger("qiuzhao.security")


class AuthService:
    def __init__(self, session, config=None):
        self.session = session
        self.config = config or settings
        self.repository = UserRepository(session)

    def response(self, user):
        return {
            "access_token": create_token(user.id, self.config, token_version=user.token_version),
            "token_type": "bearer",
            "username": user.username,
        }

    def policy(self):
        return {
            "registration_open": self.config.registration_open,
            "can_register": self.config.registration_open or self.repository.first() is None,
        }

    def register(self, body, *, client_ip: str, request_id: str = ""):
        consume(
            self.session, self.config, "register-ip", client_ip, self.config.auth_register_ip_limit
        )
        first = self.repository.first()
        if first is not None and not self.config.registration_open:
            raise BusinessError("注册已关闭", 403)
        if self.repository.by_name(body.username) is not None:
            raise BusinessError("无法完成注册，请登录或使用其他用户名", 409)
        password_hash = hash_password(body.password)
        try:
            with transaction(self.session):
                user = self.repository.add(
                    User(
                        username=body.username,
                        password_hash=password_hash,
                        bootstrap_slot=1 if first is None else None,
                    )
                )
        except IntegrityError as error:
            # Unique bootstrap_slot protects the closed-registration race.
            raise BusinessError("无法完成注册，请登录或使用其他用户名", 409) from error
        self.session.refresh(user)
        audit.info("event=register_success user_id=%s request_id=%s", user.id, request_id)
        return self.response(user)

    def login(self, username, password, *, client_ip: str, request_id: str = ""):
        consume(self.session, self.config, "login-ip", client_ip, self.config.auth_login_ip_limit)
        consume(
            self.session,
            self.config,
            "login-account",
            username.strip().casefold(),
            self.config.auth_login_account_limit,
        )
        user = self.repository.by_name(username.strip()) if len(username) <= 64 else None
        valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
        if not valid or user is None or not user.is_active:
            audit.warning("event=login_failed request_id=%s", request_id)
            raise BusinessError("用户名或密码错误", 401)
        audit.info("event=login_success user_id=%s request_id=%s", user.id, request_id)
        return self.response(user)

    def revoke_all(self, user_id):
        with transaction(self.session):
            self.session.execute(
                update(User).where(User.id == user_id).values(token_version=User.token_version + 1)
            )
        audit.info("event=logout_all user_id=%s", user_id)

    def change_password(self, user, body):
        if not verify_password(body.current_password, user.password_hash):
            raise BusinessError("当前密码错误", 400)
        with transaction(self.session):
            self.session.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    password_hash=hash_password(body.new_password),
                    token_version=User.token_version + 1,
                )
            )
        audit.info("event=password_changed user_id=%s", user.id)
