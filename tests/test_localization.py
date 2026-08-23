import json

import pytest

from sui_bot.localization import LanguageStore, TRANSLATIONS, translate


def test_language_store_persists_each_users_choice(tmp_path):
    path = tmp_path / "languages.json"
    store = LanguageStore(path)
    store.set(1, "fa")
    store.set(2, "zh")

    reloaded = LanguageStore(path)
    assert reloaded.get(1) == "fa"
    assert reloaded.get(2) == "zh"
    assert json.loads(path.read_text(encoding="utf-8")) == {"1": "fa", "2": "zh"}


def test_language_store_rejects_unknown_language(tmp_path):
    with pytest.raises(ValueError):
        LanguageStore(tmp_path / "languages.json").set(1, "unknown")


def test_translation_falls_back_to_english():
    assert "SUI Bot" in translate("unknown", "welcome")
    assert translate("ru", "language_saved") != translate("en", "language_saved")


def test_renewal_templates_are_native_to_each_selected_language():
    english = translate("en", "renew_plan_button", months=3, amount_text="100,000 USD")
    persian = translate("fa", "renew_plan_button", months=3, amount_text="100,000 USD")
    russian = translate("ru", "renew_plan_button", months=3, amount_text="100,000 USD")
    chinese = translate("zh", "renew_plan_button", months=3, amount_text="100,000 USD")

    assert "ماه" not in english
    assert "Month" not in persian and "ماه" in persian
    assert "Month" not in russian and "мес." in russian
    assert "Month" not in chinese and "个月" in chinese


def test_broadcast_wrapping_is_localized_without_modifying_admin_text():
    original = "Server response: custom-value"
    assert original in translate("fa", "broadcast_delivery", message=original)
    assert original in translate("ru", "broadcast_delivery", message=original)
    assert original in translate("zh", "broadcast_delivery", message=original)


def test_every_catalog_language_has_every_fixed_translation_key():
    english_keys = set(TRANSLATIONS["en"])
    assert english_keys
    for language in ("fa", "ru", "zh"):
        assert set(TRANSLATIONS[language]) == english_keys


def test_last_day_and_expired_messages_are_localized() -> None:
    for language in ("en", "fa", "ru", "zh"):
        assert "24" in translate(language, "hours_remaining_24") or "۲۴" in translate(language, "hours_remaining_24")
        assert translate(language, "subscription_expired_title") != "subscription_expired_title"


def test_bot_handlers_contain_no_hardcoded_persian_ui_fragments():
    source = (__import__("pathlib").Path(__file__).parents[1] / "src" / "sui_bot" / "bot.py").read_text(encoding="utf-8")
    assert not any("\u0600" <= character <= "\u06ff" for character in source)
