from datetime import datetime, timedelta, timezone
from typing import Any
import hmac
import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext
import os

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24       # 1 day
REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token({"sub": str(user_id), "type": "access"},
                         timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: int) -> str:
    return _create_token({"sub": str(user_id), "type": "refresh"},
                         timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def create_telegram_link_token(user_id: int) -> str:
    """Short-lived token (24h) for linking a Telegram account via deep link."""
    return _create_token({"sub": str(user_id), "type": "tg_link"},
                         timedelta(hours=24))


def create_web_login_token(user_id: int) -> str:
    """Short-lived token (15 min) for one-time web login via magic link from bot."""
    return _create_token({"sub": str(user_id), "type": "web_login"},
                         timedelta(minutes=15))


def decode_token(token: str) -> dict[str, Any]:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def create_child_tg_token(child_id: int) -> str:
    """Create a Telegram-compatible token for child account linking.

    Format: ch{child_id}_{16_hex} — only alphanumeric + underscore,
    safe to use in Telegram ?start= deep links (no dots like JWT).
    """
    msg = f"child:{child_id}"
    sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    return f"ch{child_id}_{sig}"


def verify_child_tg_token(token: str) -> int | None:
    """Verify a child TG link token. Returns child_id or None if invalid."""
    if not token.startswith("ch") or "_" not in token:
        return None
    prefix, sig = token.split("_", 1)
    try:
        child_id = int(prefix[2:])
    except ValueError:
        return None
    msg = f"child:{child_id}"
    expected = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    return child_id
