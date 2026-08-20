import pytest

from sui_bot.runtime_settings import load_runtime_settings, remove_runtime_setting, save_runtime_setting


def test_only_non_secret_settings_can_be_persisted(tmp_path) -> None:
    target = tmp_path / "settings.json"
    save_runtime_setting("RENEWAL_MONTHLY_PRICE", "120000", str(target))
    assert load_runtime_settings(str(target))["RENEWAL_MONTHLY_PRICE"] == "120000"

    with pytest.raises(ValueError, match="Refusing"):
        save_runtime_setting("BOT_TOKEN", "secret", str(target))


def test_display_name_is_an_allowed_runtime_setting(tmp_path) -> None:
    target = tmp_path / "settings.json"
    save_runtime_setting("BOT_DISPLAY_NAME", "Owner VPN", str(target))
    assert load_runtime_settings(str(target))["BOT_DISPLAY_NAME"] == "Owner VPN"


def test_subscription_port_preference_is_an_allowed_runtime_setting(tmp_path) -> None:
    target = tmp_path / "settings.json"
    save_runtime_setting("HIDE_SUBSCRIPTION_PORT", "true", str(target))
    assert load_runtime_settings(str(target))["HIDE_SUBSCRIPTION_PORT"] == "true"
    remove_runtime_setting("HIDE_SUBSCRIPTION_PORT", str(target))
    assert "HIDE_SUBSCRIPTION_PORT" not in load_runtime_settings(str(target))


def test_web_panel_preference_is_an_allowed_runtime_setting(tmp_path) -> None:
    target = tmp_path / "settings.json"
    save_runtime_setting("WEB_PANEL_ENABLED", "true", str(target))
    assert load_runtime_settings(str(target))["WEB_PANEL_ENABLED"] == "true"
