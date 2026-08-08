import pytest

from obscura_bot.runtime_settings import load_runtime_settings, save_runtime_setting


def test_only_non_secret_settings_can_be_persisted(tmp_path) -> None:
    target = tmp_path / "settings.json"
    save_runtime_setting("RENEWAL_MONTHLY_PRICE", "120000", str(target))
    assert load_runtime_settings(str(target))["RENEWAL_MONTHLY_PRICE"] == "120000"

    with pytest.raises(ValueError, match="Refusing"):
        save_runtime_setting("BOT_TOKEN", "secret", str(target))

