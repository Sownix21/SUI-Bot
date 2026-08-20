import json

import pytest

from sui_bot.connection_guides import ConnectionGuideStore, validate_guide_data


def test_connection_guides_round_trip_and_toggle(tmp_path) -> None:
    path = tmp_path / "connection_guides.json"
    store = ConnectionGuideStore(path)

    with pytest.raises(ValueError, match="at least one"):
        store.set_enabled(True)

    guide_id = store.add("Android", [
        {"type": "text", "text": "Install the recommended app."},
        {"type": "video", "file_id": "telegram-file-id", "caption": "Setup video"},
    ])
    store.set_enabled(True)

    reloaded = ConnectionGuideStore(path)
    assert reloaded.enabled
    assert reloaded.get(guide_id)["title"] == "Android"
    assert len(reloaded.get(guide_id)["messages"]) == 2
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1

    assert reloaded.delete(guide_id)
    assert not reloaded.enabled


def test_connection_guide_validation_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_guide_data({
            "version": 1,
            "enabled": True,
            "guides": [{
                "id": "abcdef123456",
                "title": "iOS",
                "messages": [{"type": "text", "text": "Hello", "unsafe": True}],
            }],
        })
