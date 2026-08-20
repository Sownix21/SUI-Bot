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
