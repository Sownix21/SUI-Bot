import os
import subprocess
import sys


def test_invalid_configuration_exits_once_without_traceback(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "ITEMS_PER_PAGE": "0",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed module
        [sys.executable, "-m", "sui_bot"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 78
    assert "SUI Bot configuration error" in result.stderr
    assert "Traceback" not in result.stderr


def test_reminder_keyboard_targets_each_expiring_subscription(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import sui_bot.bot as bot
from sui_bot.bot import reminder_remaining_text, renewal_reminder_keyboard, subscription_keyboard
from sui_bot.outgoing_localization import localize_inline_markup

single = renewal_reminder_keyboard(10, [{"client_id": 7, "desc": "Home"}])
assert single.inline_keyboard[0][0].callback_data == "renew_start_7"

multiple = renewal_reminder_keyboard(10, [
    {"client_id": 7, "desc": "Home"},
    {"client_id": 9, "desc": "Work"},
])
assert [row[0].callback_data for row in multiple.inline_keyboard] == ["renew_start_7", "renew_start_9"]
assert len(multiple.inline_keyboard) == 2
localized = localize_inline_markup(multiple, "en", None, display_name="Owner VPN")
assert "Home" in localized.inline_keyboard[0][0].text
assert "\ue100" not in localized.inline_keyboard[0][0].text
assert reminder_remaining_text("en", 1) == "⏳ 24 hours remaining"
without_web_panel = subscription_keyboard(10, 7, None)
assert not any(button.url for row in without_web_panel.inline_keyboard for button in row)
bot.WEB_PANEL_BASE_URL = "https://panel.example.com:2083/private-route"
bot.WEB_PANEL_ENABLED = False
assert bot.web_panel_url_for("alice") is None
bot.WEB_PANEL_ENABLED = True
assert bot.web_panel_url_for("alice").startswith("https://panel.example.com:2083/private-route/alice")
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_callback_acknowledgement_timeout_does_not_abort_button_processing(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import asyncio
from unittest.mock import AsyncMock, patch
from telegram.error import TimedOut
from sui_bot.bot import localized_query_answer

query = type("Query", (), {})()
query.from_user = type("User", (), {"id": 123456})()
query.answer = AsyncMock(side_effect=TimedOut("temporary timeout"))

with patch("sui_bot.bot.logger.warning") as warning:
    result = asyncio.run(localized_query_answer(query))

assert result is None
query.answer.assert_awaited_once_with(None)
warning.assert_called_once()
assert "continuing button action" in warning.call_args.args[0]
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_expired_user_receives_localized_message_and_renew_action(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import asyncio
from unittest.mock import AsyncMock
from sui_bot.bot import send_expiration_notification

class App: pass
app = App()
app.bot = type("Bot", (), {})()
app.bot.send_message = AsyncMock()
expired = [{
    "client_id": 7, "name": "alice", "desc": "Home", "enable": False,
    "tg_id": 10, "tg_ids": [10],
}]
asyncio.run(send_expiration_notification(app, expired))
user_call = next(call for call in app.bot.send_message.await_args_list if call.kwargs["chat_id"] == 10)
assert "expired" in user_call.kwargs["text"].lower()
assert user_call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "renew_start_7"
assert any(call.kwargs["chat_id"] == 123456 for call in app.bot.send_message.await_args_list)
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_video_caption_preservation_is_decoded_before_telegram(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import asyncio
from unittest.mock import AsyncMock, patch
from telegram.ext import ExtBot
from sui_bot.bot import LocalizedExtBot
from sui_bot.outgoing_localization import preserve_dynamic_text

caption = "Install v2.8 — کد 123 / Back"
async def check():
    bot = LocalizedExtBot("123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    with patch.object(ExtBot, "send_video", new_callable=AsyncMock) as sender:
        await bot.send_video(123456, "telegram-file-id", caption=preserve_dynamic_text(caption))
        assert sender.await_args.kwargs["caption"] == caption
asyncio.run(check())
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_client_payloads_match_current_sui_defaults_and_random_util(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com/private-path",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import base64
import inspect
import warnings
from unittest.mock import patch
import sui_bot.bot as bot
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from sui_bot.bot import (
    build_client_data_edit, build_client_data_new, build_client_renewal_data,
    create_optional_field_keyboard, edit_optional_field_keyboard, lifecycle_fields,
    lifecycle_keyboard, lifecycle_policy_text,
)

assert lifecycle_fields("regular", 0) == {
    "delayStart": False, "autoReset": False, "resetDays": 0, "nextReset": 0,
}
assert lifecycle_fields("delayed_expiry", 15) == {
    "delayStart": True, "autoReset": False, "resetDays": 15, "nextReset": 0,
}
assert lifecycle_fields("reset_first", 15) == {
    "delayStart": True, "autoReset": True, "resetDays": 15, "nextReset": 0,
}
assert lifecycle_fields("reset_now", 15, now_timestamp=1000) == {
    "delayStart": False, "autoReset": True, "resetDays": 15,
    "nextReset": 1000 + 15 * 86400,
}
assert "first cycle starts now" in lifecycle_policy_text(False, True, 15).lower()
assert "after vpn traffic" in lifecycle_policy_text(True, True, 15).lower()

create_callbacks = [row[0].callback_data for row in create_optional_field_keyboard("desc").inline_keyboard]
assert create_callbacks == ["create_desc_empty", "create_cancel"]
edit_callbacks = [row[0].callback_data for row in edit_optional_field_keyboard("group").inline_keyboard]
assert edit_callbacks == ["edit_group_keep", "edit_group_empty", "edit_cancel"]
assert [row[0].callback_data for row in lifecycle_keyboard("create").inline_keyboard] == [
    "create_lifecycle_regular", "create_lifecycle_delayed_expiry", "create_lifecycle_reset_now",
    "create_lifecycle_reset_first", "create_cancel",
]

# Stateful editors must share one conversation. Otherwise an abandoned settings
# editor can capture input intended for /createuser or /edituser.
assert inspect.getsource(bot.main).count("mixed_conversation_handler(") == 1

async def noop(update, context):
    return 1

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    bot.mixed_conversation_handler(
        entry_points=[CallbackQueryHandler(noop)],
        states={1: [MessageHandler(filters.TEXT, noop)]},
        fallbacks=[],
    )
assert not any("per_message=False" in str(item.message) for item in caught)

bot.language_store.set(bot.ADMIN_TELEGRAM_ID, "fa")
bot.PAYMENT_CURRENCY = "USD"
payment_text = bot.build_payment_settings_text()
payment_buttons = [button.text for row in bot.build_payment_settings_keyboard().inline_keyboard for button in row]
assert "Price per month" not in payment_text
assert "US dollar" not in payment_text
assert "دلار آمریکا" in payment_text
assert not any("Set currency" in text or "Set exact monthly price" in text for text in payment_buttons)
assert "/cancel" in bot.tr(bot.ADMIN_TELEGRAM_ID, "monthly_price_prompt", currency="USD")

created = build_client_data_new("alice", 0, 0, "Test", "Family", [9, 10])
assert created["remark"] == ""
assert created["delayStart"] is False
assert created["autoReset"] is False
assert created["resetDays"] == created["nextReset"] == 0
assert created["totalUp"] == created["totalDown"] == 0
assert created["createdAt"] == created["onlineAt"] == 0
assert len(base64.b64decode(created["config"]["shadowsocks"]["password"], validate=True)) == 32
assert len(base64.b64decode(created["config"]["shadowsocks16"]["password"], validate=True)) == 16
assert created["config"]["shadowtls"]["password"] == created["config"]["shadowsocks"]["password"]
assert created["config"]["vmess"]["uuid"] == created["config"]["vless"]["uuid"]
assert created["config"]["tuic"]["uuid"] == created["config"]["vmess"]["uuid"]

scheduled = build_client_data_new(
    "scheduled", 0, 0, "Test", "Family", [9], remark="priority",
    delay_start=True, auto_reset=True, reset_days=15, next_reset=0,
)
assert scheduled["remark"] == "priority"
assert scheduled["delayStart"] is True and scheduled["autoReset"] is True
assert scheduled["resetDays"] == 15 and scheduled["nextReset"] == 0

original = {
    **created,
    "id": 95,
    "remark": "private note",
    "delayStart": True,
    "resetDays": 15,
    "nextReset": 123,
    "totalUp": 456,
    "totalDown": 789,
    "createdAt": 1000,
    "onlineAt": 2000,
}
edited = build_client_data_edit(95, "bob", 50 * 1024**3, 3000, "Edited", "Work", [9], original_client=original)
for field in ("remark", "delayStart", "autoReset", "resetDays", "nextReset", "totalUp", "totalDown", "createdAt", "onlineAt"):
    assert edited[field] == original[field]
assert edited["config"]["mixed"]["username"] == "bob"
assert edited["config"]["mixed"]["password"] == original["config"]["mixed"]["password"]

changed_policy = build_client_data_edit(
    95, "bob", 0, 0, "Edited", "Work", [9], original_client=original,
    remark="new note", delay_start=False, auto_reset=True, reset_days=30, next_reset=999,
)
assert changed_policy["remark"] == "new note"
assert changed_policy["autoReset"] is True and changed_policy["delayStart"] is False
assert changed_policy["resetDays"] == 30 and changed_policy["nextReset"] == 999
assert changed_policy["totalUp"] == 456 and changed_policy["totalDown"] == 789
assert changed_policy["createdAt"] == 1000 and changed_policy["onlineAt"] == 2000

renewed = build_client_renewal_data(original, 95, 5000)
assert renewed["expiry"] == 5000 and renewed["enable"] is True
assert renewed["up"] == renewed["down"] == 0
assert renewed["totalUp"] == renewed["totalDown"] == 0
assert renewed["createdAt"] == 1000 and renewed["onlineAt"] == 2000
assert original["totalUp"] == 456 and original["totalDown"] == 789

bot.telegram_clients.clear()
with patch.object(bot, "save_assignments") as saver:
    assert bot.add_client_assignment(123, 95) == (True, 1)
    assert bot.add_client_assignment(123, 96) == (True, 2)
    assert bot.add_client_assignment(123, 95) == (False, 2)
    assert bot.telegram_clients == {123: [95, 96]}
    assert saver.call_count == 2
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_status_response_envelope_is_validated(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update({
        "SUI_HOST": "https://panel.example.com/private-path",
        "SUI_TOKEN": "secret",
        "BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyz_ABCD",
        "ADMIN_TELEGRAM_ID": "123456",
        "DATA_DIR": str(tmp_path),
        "BOT_LOG_FILE": "",
    })
    script = """
import asyncio
from unittest.mock import AsyncMock, patch
import sui_bot.bot as bot
from sui_bot.bot import APIClient, format_client, format_client_timestamp, get_client_usage_record, sui_clients, sui_response_object
from sui_bot.outgoing_localization import localize_outgoing_text

status = {
    "success": True,
    "msg": "",
    "obj": {
        "cpu": 7.25,
        "mem": {"current": 2_000_000_000, "total": 8_000_000_000},
        "net": {"precv": 100, "psent": 200, "recv": 300, "sent": 400},
        "sbd": {"running": True, "stats": {"Alloc": 500, "NumGoroutine": 6, "Uptime": 7}},
        "sys": {"appMem": 800, "appThreads": 9, "bootTime": 10},
        "dsk": {"current": 11, "total": 12},
        "swp": {"current": 13, "total": 14},
        "dio": {"read": 15, "write": 16},
    },
}
assert sui_response_object(status) == status["obj"]
assert sui_response_object({"success": False, "msg": "invalid token", "obj": {}}) is None
assert sui_response_object({"success": True, "obj": []}) is None
assert sui_response_object(None) is None

clients_response = {"success": True, "msg": "", "obj": {"clients": [{
    "id": 7, "name": "alice", "enable": True, "up": 10, "down": 20,
    "volume": 100, "expiry": 0, "desc": "Home", "group": "Family",
    "remark": "priority client", "createdAt": 1704067200, "onlineAt": 1704153600,
}]}}
assert sui_clients(clients_response) == clients_response["obj"]["clients"]
assert sui_clients({"success": True, "msg": "", "obj": {"clients": [None]}}) is None

class Response:
    def raise_for_status(self):
        return None

class ResponseContext:
    async def __aenter__(self):
        return Response()
    async def __aexit__(self, *_args):
        return None

class Session:
    def get(self, *_args, **_kwargs):
        return ResponseContext()

async def check_api_failures_and_request_count():
    client = APIClient("https://panel.example.com", "secret")
    client.ensure_session = AsyncMock()
    client.session = Session()
    client.decode_json_response = AsyncMock(return_value={
        "success": False, "msg": "request failed", "obj": None,
    })
    assert await client.get("apiv2/clients") is None

    with patch.object(bot.api_client, "get", new=AsyncMock(return_value=clients_response)) as getter:
        message, record = await get_client_usage_record(7, True, 123456)
        assert message
        assert record["id"] == 7
        assert record["name"] == "alice"
        rendered = localize_outgoing_text("en", message)
        assert "Remark: priority client" in rendered
        assert "Created: 2024-01-01 00:00:00 UTC+00:00" in rendered
        assert "Last Online: 2024-01-02 00:00:00 UTC+00:00" in rendered
        regular_user = localize_outgoing_text("en", format_client(record, is_admin=False, user_id=10))
        assert "Remark:" not in regular_user and "Last Online:" not in regular_user
        assert format_client_timestamp(0) is None
        getter.assert_awaited_once_with("apiv2/clients", {"id": 7})

asyncio.run(check_api_failures_and_request_count())
"""
    result = subprocess.run(  # noqa: S603 - current test interpreter and fixed test program
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
