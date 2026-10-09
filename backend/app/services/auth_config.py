import hashlib
import hmac
import os
import secrets
import time

from dotenv import dotenv_values, set_key

from app.services.database_config import ENV_PATH

COOKIE_NAME = "auth_session"
ITERATIONS = 210_000
MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _stored() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    return {key: "" if value is None else str(value) for key, value in dotenv_values(ENV_PATH).items()}


def _write(updates: dict[str, str]) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text("PORT=3000\n", encoding="utf-8")
    for key, value in updates.items():
        set_key(str(ENV_PATH), key, value)
        os.environ[key] = value


def password_configured() -> bool:
    stored = _stored()
    return bool(stored.get("AUTH_PASSWORD_SALT") and stored.get("AUTH_PASSWORD_HASH"))


def save_password(password: str) -> None:
    salt = secrets.token_hex(16)
    digest = _digest(password, salt, ITERATIONS)
    updates = {
        "AUTH_PASSWORD_SALT": salt,
        "AUTH_PASSWORD_HASH": digest,
        "AUTH_PASSWORD_ITERATIONS": str(ITERATIONS),
    }
    if not _stored().get("AUTH_SECRET"):
        updates["AUTH_SECRET"] = secrets.token_hex(32)
    _write(updates)


def verify_password(password: str) -> bool:
    stored = _stored()
    salt = stored.get("AUTH_PASSWORD_SALT", "")
    expected = stored.get("AUTH_PASSWORD_HASH", "")
    if not salt or not expected:
        return False
    try:
        iterations = int(stored.get("AUTH_PASSWORD_ITERATIONS") or ITERATIONS)
        digest = _digest(password, salt, iterations)
    except (ValueError, TypeError):
        return False
    if len(digest) != len(expected):
        return False
    return hmac.compare_digest(digest, expected)


def issue_session() -> str:
    secret = _secret()
    expiry = int(time.time()) + MAX_AGE_SECONDS
    payload = str(expiry)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_ok(token: str | None) -> bool:
    if not password_configured() or not token or "." not in token:
        return False
    payload, signature = token.rsplit(".", 1)
    expected = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return False
    try:
        expiry = int(payload)
    except ValueError:
        return False
    return expiry > int(time.time())


def _digest(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()


def _secret() -> str:
    stored = _stored()
    secret = stored.get("AUTH_SECRET", "")
    if secret:
        return secret
    secret = secrets.token_hex(32)
    _write({"AUTH_SECRET": secret})
    return secret
