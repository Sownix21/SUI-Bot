import copy
import json
import string
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Chat, Message, Update, User
from telegram.error import TimedOut
from telegram.ext import Application, ApplicationHandlerStop, ExtBot, TypeHandler

from sui_bot.membership import MEMBERSHIP_INPUT, MembershipStore, MembershipUI, is_member, validate_join_url
from sui_bot.membership_i18n import MESSAGES, membership_text


def target(chat_id=-100123):
    return {"id": chat_id, "title": "Service updates", "url": "https://t.me/example_service"}


@pytest.fixture
def store(tmp_path):
    result = MembershipStore(tmp_path / "required_membership.json")
    result.upsert(target())
    result.save({**result.data, "enabled": True})
    return result


@pytest.fixture
def ui(store):
    b = SimpleNamespace(
        ADMIN_TELEGRAM_ID=1,
        language_store=SimpleNamespace(get=Mock(return_value="en"), set=Mock()),
        SUPPORTED_LANGUAGES={"en", "fa", "ru", "zh"},
        preserve_dynamic_text=lambda value: value,
        localized_query_answer=AsyncMock(),
        language_keyboard=Mock(return_value=None),
        get_main_menu_keyboard=Mock(return_value=None),
        tr=lambda uid, key: key,
        logger=Mock(),
    )
    return MembershipUI(b, store)


def event(uid=42, action=None, text=None):
    message = SimpleNamespace(reply_text=AsyncMock(), text=text)
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid),
        effective_message=message,
        effective_chat=SimpleNamespace(type="private"),
        message=message,
        callback_query=SimpleNamespace(data=action) if action else None,
    )


def ctx(status="member"):
    async def get_member(chat_id, user_id, **kwargs):
        return SimpleNamespace(status="administrator" if user_id == 999 else status, is_member=False)

    return SimpleNamespace(user_data={}, bot=SimpleNamespace(id=999, get_chat_member=AsyncMock(side_effect=get_member)))


@pytest.mark.parametrize(
    "status,restricted,expected",
    [
        ("creator", False, True),
        ("administrator", False, True),
        ("member", False, True),
        ("restricted", True, True),
        ("restricted", False, False),
        ("left", False, False),
        ("kicked", False, False),
    ],
)
def test_membership_statuses(status, restricted, expected):
    assert is_member(SimpleNamespace(status=status, is_member=restricted)) is expected


@pytest.mark.parametrize(
    "url",
    [
        "http://t.me/example",
        "https://t.me.evil.example/example",
        "https://t.me@example.com/a",
        "https://t.me/example?x=1",
        "https://t.me/example/123",
        "javascript:alert(1)",
        None,
    ],
)
def test_invalid_join_links_rejected(url):
    with pytest.raises(ValueError):
        validate_join_url(url)


def test_membership_persists_and_last_removal_disables(store):
    assert MembershipStore(store.path).data == store.data
    store.upsert({**target(), "url": "https://t.me/+test_invite", "title": "New title"})
    assert len(store.data["chats"]) == 1
    store.remove(-100123)
    assert store.data == {"version": 1, "enabled": False, "chats": []}


def test_all_prompts_have_four_complete_translations():
    for key, variants in MESSAGES.items():
        assert len(variants) == 4
        parameters = [{field for _, field, _, _ in string.Formatter().parse(value) if field} for value in variants]
        assert all(value == parameters[0] for value in parameters)
        for locale in ("en", "fa", "ru", "zh"):
            assert membership_text(locale, key, **dict.fromkeys(parameters[0], "test"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,text",
    [
        (None, "/start"),
        (None, "/usage"),
        ("get_sub_links_7", None),
        ("renew_choose_7_1", None),
        ("sales_buy_123", None),
        (None, "receipt"),
    ],
)
async def test_all_user_input_is_stopped_for_nonmembers(ui, action, text):
    update = event(action=action, text=text)
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(update, ctx("left"))
    markup = update.message.reply_text.await_args.kwargs["reply_markup"]
    assert any(button.url == target()["url"] for row in markup.inline_keyboard for button in row)
    assert any(button.callback_data == "membership_check" for row in markup.inline_keyboard for button in row)
    ui.b.get_main_menu_keyboard.assert_not_called()


@pytest.mark.asyncio
async def test_all_chats_required_and_leaving_is_detected(ui, store):
    store.upsert(target(-100456))
    context = ctx()
    await ui.guard(event(text="/usage"), context)
    ui.attempts.clear()

    async def membership(chat_id, user_id, **kwargs):
        return SimpleNamespace(status="administrator" if user_id == 999 else "left" if chat_id == -100456 else "member")

    context.bot.get_chat_member.side_effect = membership
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(action="my_usage"), context)
    assert context.bot.get_chat_member.await_count == 8


@pytest.mark.asyncio
async def test_joined_checks_again_and_unlocks_without_replaying_original_request(ui):
    context = ctx("left")
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(action="membership_check"), context)
    ui.b.get_main_menu_keyboard.assert_not_called()
    ui.attempts.clear()
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(action="membership_check"), ctx("member"))
    ui.b.get_main_menu_keyboard.assert_called_once_with(False, 42)


@pytest.mark.asyncio
async def test_admin_and_disabled_gate_do_not_call_telegram(ui, store):
    context = ctx("left")
    await ui.guard(event(uid=1, action="settings_admin_tools"), context)
    store.save({**store.data, "enabled": False})
    await ui.guard(event(text="/usage"), context)
    context.bot.get_chat_member.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_error_or_bot_demotion_fails_closed(ui):
    context = ctx()
    context.bot.get_chat_member.side_effect = TimedOut("temporary")
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(action="membership_check"), context)
    ui.attempts.clear()
    context.bot.get_chat_member.side_effect = None
    context.bot.get_chat_member.return_value = SimpleNamespace(status="member")
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(text="/usage"), context)
    ui.b.get_main_menu_keyboard.assert_not_called()


@pytest.mark.asyncio
async def test_unexpected_error_does_not_fall_through_to_protected_handlers(ui, monkeypatch):
    monkeypatch.setattr(ui, "verify", AsyncMock(side_effect=ValueError("bad response")))
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(text="/usage"), ctx())


@pytest.mark.asyncio
async def test_language_choice_is_allowed_but_no_data_is_revealed(ui):
    ui.b.language_store.get.return_value = None
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(text="/start"), ctx())
    with pytest.raises(ApplicationHandlerStop):
        await ui.guard(event(action="lang_set_fa"), ctx("left"))
    ui.b.language_store.set.assert_called_once_with(42, "fa")
    ui.b.get_main_menu_keyboard.assert_not_called()


@pytest.mark.asyncio
async def test_only_admin_can_change_requirements(ui, store):
    original = copy.deepcopy(store.data)
    context = ctx()
    for action in ("membership_toggle", "membership_add", "membership_remove_-100123"):
        await ui.callback(event(action=action), context)
    context.user_data["membership_draft"] = {}
    await ui.text(event(text="@example_service"), context)
    assert store.data == original


@pytest.mark.asyncio
async def test_admin_adds_public_and_private_chats(ui, store):
    context = ctx()
    context.bot.get_chat = AsyncMock(
        return_value=SimpleNamespace(id=-100777, type="channel", title="News", username="service_news")
    )
    assert await ui.callback(event(uid=1, action="membership_add"), context) == MEMBERSHIP_INPUT
    assert await ui.text(event(uid=1, text="@service_news"), context) == -1
    assert store.data["chats"][-1]["url"] == "https://t.me/service_news"
    context.bot.get_chat.return_value = SimpleNamespace(id=-100888, type="supergroup", title="Support", username=None)
    await ui.callback(event(uid=1, action="membership_add"), context)
    assert await ui.text(event(uid=1, text="-100888"), context) == MEMBERSHIP_INPUT
    assert await ui.text(event(uid=1, text="https://t.me/+test_invite"), context) == -1
    assert store.data["chats"][-1]["id"] == -100888


@pytest.mark.asyncio
async def test_real_application_dispatch_blocks_before_other_groups_and_outgoing_is_unaffected(ui, monkeypatch):
    async def get_member(self, chat_id, user_id, **kwargs):
        return SimpleNamespace(status="administrator" if user_id == 999 else "left")

    monkeypatch.setattr(ExtBot, "get_chat_member", get_member)
    outbound = AsyncMock()
    monkeypatch.setattr(ExtBot, "send_message", outbound)
    monkeypatch.setattr(Message, "reply_text", AsyncMock())
    telegram_bot = ExtBot("123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    telegram_bot._bot_user = User(999, "Test", True)
    app = Application.builder().bot(telegram_bot).build()
    app._initialized = True
    first, second = AsyncMock(), AsyncMock()
    app.add_handler(TypeHandler(Update, ui.guard), group=-1)
    app.add_handler(TypeHandler(Update, first), group=0)
    app.add_handler(TypeHandler(Update, second), group=1)
    message = Message(
        1, datetime.now(timezone.utc), Chat(42, "private"), from_user=User(42, "Buyer", False), text="/usage"
    )
    update = Update(1, message=message)
    await app.process_update(update)
    first.assert_not_awaited()
    second.assert_not_awaited()
    # Reminders/broadcasts call the outgoing API directly, even for nonmembers.
    await app.bot.send_message(chat_id=42, text="Reminder")
    outbound.assert_awaited_once()
    ui.store.save({**ui.store.data, "enabled": False})
    await app.process_update(update)
    first.assert_awaited_once()
    second.assert_awaited_once()


def test_membership_backup_round_trip(store, tmp_path):
    from sui_bot.backup_bundle import build_bundle, restore_bundle

    bundle = build_bundle({"required_membership": store.path}, {})
    destination = tmp_path / "restored.json"
    restore_bundle(bundle, {"required_membership": destination})
    assert MembershipStore(destination).data == store.data


def test_default_admin_subscription_is_unassigned(monkeypatch):
    from sui_bot.config import Settings

    monkeypatch.setenv("SUI_HOST", "https://panel.example.com")
    monkeypatch.setenv("SUI_TOKEN", "test-token")
    monkeypatch.setenv("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    monkeypatch.delenv("ADMIN_CLIENT_ID", raising=False)
    assert Settings.from_env().admin_client_id == 0
    monkeypatch.setenv("ADMIN_CLIENT_ID", "7")
    assert Settings.from_env().admin_client_id == 7
    monkeypatch.setenv("ADMIN_CLIENT_ID", "-1")
    with pytest.raises(RuntimeError, match="ADMIN_CLIENT_ID"):
        Settings.from_env()


def test_assignment_loading_never_guesses_and_preserves_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("SUI_HOST", "https://panel.example.com")
    monkeypatch.setenv("SUI_TOKEN", "test-token")
    monkeypatch.setenv("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BOT_LOG_FILE", "")
    import sui_bot.bot as b

    path = tmp_path / "assignments.json"
    monkeypatch.setattr(b, "ASSIGNMENTS_FILE", str(path))
    monkeypatch.setattr(b, "ADMIN_TELEGRAM_ID", 1)
    monkeypatch.setattr(b, "ADMIN_CLIENT_ID", 0)
    monkeypatch.setattr(b, "telegram_clients", {})
    b.load_assignments()
    assert b.telegram_clients == {}
    monkeypatch.setattr(b, "ADMIN_CLIENT_ID", 7)
    b.load_assignments()
    assert b.telegram_clients == {1: [7]}
    path.write_text(json.dumps({"1": [8], "42": [9]}), encoding="utf-8")
    b.load_assignments()
    assert b.telegram_clients == {1: [8], 42: [9]}
    path.write_text("not valid JSON", encoding="utf-8")
    b.load_assignments()
    assert b.telegram_clients == {}
