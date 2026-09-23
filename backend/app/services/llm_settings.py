"""Per-user LLM endpoint settings; the API key is stored encrypted, never returned raw."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlmodel import select

from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import UserLlmConfig, _now


def cipher(config):
    digest = hashlib.sha256(f"llm-config:{config.jwt_secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def mask_key(key: str) -> str:
    return "••••" + key[-4:] if len(key) > 8 else "••••"


def decrypt_key(row: UserLlmConfig, config) -> str:
    try:
        return cipher(config).decrypt(row.encrypted_api_key.encode()).decode()
    except InvalidToken:
        raise BusinessError("大模型密钥解密失败，请在设置中重新保存 API 配置", 503) from None


def effective_config(session, config, user_id):
    """User-saved settings override the server defaults; budgets stay global."""
    row = session.exec(select(UserLlmConfig).where(
        UserLlmConfig.user_id == user_id)).first()
    if row is None:
        return config
    return config.model_copy(update={
        "agent_enabled": True,
        "agent_provider": row.protocol,
        "agent_api_url": row.api_url,
        "agent_model": row.model,
        "openai_api_key": SecretStr(decrypt_key(row, config)),
    })


class LlmSettingsService:
    def __init__(self, session, actor, config):
        self.session = session
        self.config = config
        self.user_id = actor.user_id

    def _row(self):
        return self.session.exec(select(UserLlmConfig).where(
            UserLlmConfig.user_id == self.user_id)).first()

    def view(self, row):
        if row is None:
            return {"configured": False}
        return {
            "configured": True,
            "protocol": row.protocol,
            "api_url": row.api_url,
            "model": row.model,
            "key_masked": mask_key(decrypt_key(row, self.config)),
            "updated_at": row.updated_at.isoformat(timespec="seconds"),
        }

    def get(self):
        return self.view(self._row())

    def save(self, body):
        existing = self._row()
        if body.api_key:
            encrypted = cipher(self.config).encrypt(body.api_key.strip().encode()).decode()
        elif existing is None:
            raise BusinessError("首次保存请填写 API 密钥")
        else:
            encrypted = existing.encrypted_api_key
        with transaction(self.session):
            if existing is None:
                self.session.add(UserLlmConfig(
                    user_id=self.user_id, protocol=body.protocol, api_url=body.api_url,
                    model=body.model.strip(), encrypted_api_key=encrypted,
                ))
            else:
                existing.protocol = body.protocol
                existing.api_url = body.api_url
                existing.model = body.model.strip()
                existing.encrypted_api_key = encrypted
                existing.updated_at = _now()
                self.session.add(existing)
        return self.view(self._row())

    def delete(self):
        existing = self._row()
        if existing is not None:
            with transaction(self.session):
                self.session.delete(existing)
        return {"configured": False}
