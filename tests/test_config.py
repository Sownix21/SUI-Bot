import pytest

from sui_bot.config import Settings, validate_display_name


def test_runtime_settings_reject_invalid_positive_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUI_HOST", "https://panel.example.com")
    monkeypatch.setenv("SUI_TOKEN", "secret")
    monkeypatch.setenv("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "123456")
    monkeypatch.setenv("ITEMS_PER_PAGE", "0")

    with pytest.raises(RuntimeError, match="ITEMS_PER_PAGE"):
        Settings.from_env()


def test_runtime_settings_reject_invalid_renewal_months(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUI_HOST", "https://panel.example.com")
    monkeypatch.setenv("SUI_TOKEN", "secret")
    monkeypatch.setenv("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "123456")
    monkeypatch.setenv("RENEWAL_MONTH_OPTIONS", "1,invalid,3")

    with pytest.raises(RuntimeError, match="RENEWAL_MONTH_OPTIONS"):
        Settings.from_env()


def test_display_name_accepts_unicode_but_rejects_control_characters() -> None:
    assert validate_display_name("  سرویس من  ") == "سرویس من"
    with pytest.raises(RuntimeError, match="BOT_DISPLAY_NAME"):
        validate_display_name("bad\nname")
