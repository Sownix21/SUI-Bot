import json

import pytest

from sui_bot.localization import LanguageStore, translate


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
