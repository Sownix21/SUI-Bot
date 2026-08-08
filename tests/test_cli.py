import os
from pathlib import Path

import pytest

from obscura_bot import cli


def valid_environment() -> dict[str, str]:
    return {
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "sui-secret",
        "BOT_TOKEN": "123456:telegram-secret",
        "ADMIN_TELEGRAM_ID": "123456",
        "FALLBACK_SUB_URI": "https://subscriptions.example.com/sub",
        "ALLOW_INSECURE_HTTP": "false",
    }


def test_validation_accepts_secure_configuration() -> None:
    assert cli.validate_environment(valid_environment()) == []


def test_validation_rejects_remote_plain_http() -> None:
    values = valid_environment()
    values["SUI_HOST"] = "http://panel.example.com"
    assert any("HTTPS" in error for error in cli.validate_environment(values))


def test_secret_masking() -> None:
    assert cli.mask_value("BOT_TOKEN", "abcdefgh") == "••••••••efgh"
    assert cli.mask_value("ADMIN_TELEGRAM_ID", "123") == "123"


def test_atomic_environment_write_is_reloadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "obscura-bot.env"
    monkeypatch.setattr(cli, "require_root", lambda _action: None)
    cli.write_environment(valid_environment(), target)
    assert cli.load_environment(target) == valid_environment()
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600
