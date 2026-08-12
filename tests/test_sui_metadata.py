import pytest

from sui_bot.sui_metadata import build_subscription_urls, extract_load_metadata


def test_load_metadata_preserves_subscription_port_and_path():
    payload = {
        "success": True,
        "obj": {
            "subURI": "https://evenpath.site:2096/Jf8QpZ0y4mA9R2kXnEwT7cL6B5HDSVY3U/8sD2KpL/",
            "inbounds": [{"id": 1, "tag": "main"}, {"tag": "invalid"}],
        },
    }

    sub_uri, inbounds = extract_load_metadata(payload)
    main, json_url, clash_url = build_subscription_urls(sub_uri, "test user")

    assert sub_uri == "https://evenpath.site:2096/Jf8QpZ0y4mA9R2kXnEwT7cL6B5HDSVY3U/8sD2KpL"
    assert inbounds == [{"id": 1, "tag": "main"}]
    assert main == f"{sub_uri}/test%20user/"
    assert json_url == f"{main}?format=json"
    assert clash_url == f"{main}?format=clash"


@pytest.mark.parametrize("payload", [None, {}, {"success": False}, {"success": True, "obj": {}}])
def test_invalid_load_metadata_is_rejected(payload):
    with pytest.raises(ValueError):
        extract_load_metadata(payload)
