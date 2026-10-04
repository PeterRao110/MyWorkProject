import os

from dotenv import dotenv_values, set_key

from app.services.database_config import ENV_PATH


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


def read_akshare() -> dict[str, str | bool]:
    stored = _stored()
    return {
        "enabled": stored.get("AKSHARE_ENABLED", "true").lower() != "false",
        "baseUrl": stored.get("AKSHARE_BASE_URL") or "https://akshare.akfamily.xyz",
        "timeout": stored.get("AKSHARE_TIMEOUT") or "10",
        "retry": stored.get("AKSHARE_RETRY") or "3",
    }


def save_akshare(enabled: bool, base_url: str, timeout: str, retry: str) -> None:
    _write(
        {
            "AKSHARE_ENABLED": "true" if enabled else "false",
            "AKSHARE_BASE_URL": base_url,
            "AKSHARE_TIMEOUT": timeout,
            "AKSHARE_RETRY": retry,
        }
    )


def read_tushare_api(prefix: str) -> dict[str, str | bool]:
    stored = _stored()
    return {
        "baseUrl": stored.get(f"{prefix}_BASE_URL", ""),
        "timeout": stored.get(f"{prefix}_TIMEOUT") or "10",
        "retry": stored.get(f"{prefix}_RETRY") or "3",
        "tokenSet": bool(stored.get(f"{prefix}_TOKEN", "")),
    }


def save_tushare_api(prefix: str, token: str, base_url: str, timeout: str, retry: str) -> None:
    stored = _stored()
    _write(
        {
            f"{prefix}_TOKEN": token or stored.get(f"{prefix}_TOKEN", ""),
            f"{prefix}_BASE_URL": base_url,
            f"{prefix}_TIMEOUT": timeout,
            f"{prefix}_RETRY": retry,
        }
    )


def read_sources() -> dict[str, dict[str, str | bool]]:
    return {
        "akshare": read_akshare(),
        "rds": read_tushare_api("TUSHARE_RDS"),
        "promax": read_tushare_api("TUSHARE_PROMAX"),
    }
