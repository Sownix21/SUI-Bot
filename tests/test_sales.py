import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from sui_bot.sales import SalesStore, validate_plan
from sui_bot.sales_i18n import LANGUAGES, MESSAGES, sale_text
from sui_bot.sales_ui import ACCOUNT_FIELDS, PLAN_FIELDS, SALES_INPUT, SalesUI


def plan(**overrides):
    value = {
        "title": "30 days",
        "price": 100,
        "currency": "USD",
        "days": 30,
        "volume": 50 * 1024**3,
        "delayed": True,
        "reset_days": 0,
        "active": True,
        "inbounds": [9],
        "group": "",
        "desc": "",
        "remark": "",
    }
    value.update(overrides)
    return value


@pytest.fixture
def store(tmp_path):
    return SalesStore(tmp_path / "sales.json")


def test_sales_disabled_by_default_and_snapshot_survives_restart(store):
    key = store.save_plan(plan())
    with pytest.raises(ValueError, match="disabled"):
        store.checkout(42, key)
    store.configure(enabled=True, mode="automatic")
    order_id, order = store.checkout(42, key)
    store.save_plan(plan(price=200), key)
    assert order["plan"]["price"] == 100
    assert store.checkout(42, key)[0] == order_id
    assert SalesStore(store.path).open_order(42)[1]["plan"]["price"] == 100
    store.update_order(order_id, {"receipt"}, status="pending")
    store.update_order(order_id, {"pending"}, status="approved")
    with pytest.raises(ValueError, match="changed"):
        store.update_order(order_id, {"pending"}, status="approved")


@pytest.mark.parametrize(
    "change",
    [
        {"price": 0},
        {"days": -1},
        {"days": True},
        {"reset_days": 3},
        {"inbounds": [9, 9]},
        {"inbounds": [True]},
        {"currency": "bad"},
    ],
)
def test_invalid_plans_rejected(change):
    with pytest.raises(ValueError):
        validate_plan(plan(**change))


def test_failed_disk_write_does_not_publish_state(store, monkeypatch):
    monkeypatch.setattr("sui_bot.sales.os.replace", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        store.configure(enabled=True)
    assert not store.data["enabled"]


def test_all_sales_messages_have_four_translations_and_matching_placeholders():
    import string

    for key, messages in MESSAGES.items():
        assert len(messages) == len(LANGUAGES)
        placeholders = [{field for _, field, _, _ in string.Formatter().parse(m) if field} for m in messages]
        assert all(p == placeholders[0] for p in placeholders), key
        for language in LANGUAGES:
            assert sale_text(language, key, **dict.fromkeys(placeholders[0], "sample"))


@pytest.fixture
def bot(tmp_path, monkeypatch, store):
    monkeypatch.setenv("SUI_HOST", "https://panel.example.com/private")
    monkeypatch.setenv("SUI_TOKEN", "test-token")
    monkeypatch.setenv("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCD")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BOT_LOG_FILE", "")
    import sui_bot.bot as b
    from sui_bot.localization import LanguageStore

    monkeypatch.setattr(b, "ADMIN_TELEGRAM_ID", 1)
    monkeypatch.setattr(b, "language_store", LanguageStore(str(tmp_path / "languages.json")))
    monkeypatch.setattr(b, "telegram_clients", {})
    monkeypatch.setattr(b, "save_assignments", Mock())
    monkeypatch.setattr(b, "sales_store", store)
    monkeypatch.setattr(b, "sales_ui", SalesUI(b, store))
    monkeypatch.setattr(b, "PAYMENT_CARD_NUMBER", "1234-5678-9012-3456")
    monkeypatch.setattr(b, "get_inbounds_list", AsyncMock(return_value=[{"id": 9, "tag": "main"}]))
    return b


def update(uid=1, data="sales_admin", text=None):
    message = SimpleNamespace(reply_text=AsyncMock(), photo=[], document=None, text=text)
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid),
        effective_chat=SimpleNamespace(type="private"),
        effective_message=message,
        message=message,
        callback_query=SimpleNamespace(
            data=data, answer=AsyncMock(), edit_message_text=AsyncMock(), from_user=SimpleNamespace(id=uid)
        ),
    )


def context():
    return SimpleNamespace(
        user_data={}, bot=SimpleNamespace(send_message=AsyncMock(), send_photo=AsyncMock(), send_document=AsyncMock())
    )


def approved(store, mode="automatic"):
    key = store.save_plan(plan())
    store.configure(enabled=True, mode=mode)
    key, _ = store.checkout(42, key)
    store.update_order(key, {"receipt"}, status="pending")
    store.update_order(key, {"pending"}, status="approved")
    return key


@pytest.mark.asyncio
async def test_automatic_fulfilment_assignment_and_duplicate_approval(bot, store, monkeypatch):
    key = approved(store)
    created = []

    async def save(action, payload):
        assert action == "new"
        assert payload["delayStart"] is True and payload["expiry"] == 0
        assert payload["resetDays"] == 30 and payload["inbounds"] == [9]
        created.append({**copy.deepcopy(payload), "id": 88})
        return {"success": True}

    async def get(endpoint, params=None):
        if endpoint == "apiv2/inbounds":
            return {"success": True, "obj": {"inbounds": [{"id": 9}]}}
        return {"success": True, "obj": {"clients": copy.deepcopy(created)}}

    monkeypatch.setattr(bot, "create_or_edit_client", AsyncMock(side_effect=save))
    monkeypatch.setattr(bot.api_client, "get", AsyncMock(side_effect=get))
    ctx = context()
    await bot.sales_ui.fulfil(update(), ctx, key)
    await bot.sales_ui.fulfil(update(), ctx, key)
    assert bot.create_or_edit_client.await_count == 1
    assert bot.telegram_clients == {42: [88]}
    assert store.data["orders"][key]["status"] == "fulfilled"
    assert store.data["orders"][key]["notified"]


@pytest.mark.asyncio
async def test_uncertain_creation_is_not_replayed_after_restart(bot, store, monkeypatch):
    key = approved(store)

    async def get(endpoint, params=None):
        return (
            {"success": True, "obj": {"inbounds": [{"id": 9}]}}
            if endpoint.endswith("inbounds")
            else {"success": True, "obj": {"clients": []}}
        )

    monkeypatch.setattr(bot.api_client, "get", AsyncMock(side_effect=get))
    monkeypatch.setattr(bot, "create_or_edit_client", AsyncMock(return_value=None))
    await bot.sales_ui.fulfil(update(), context(), key)
    restarted = SalesUI(bot, SalesStore(store.path))
    await restarted.fulfil(update(), context(), key)
    assert bot.create_or_edit_client.await_count == 1
    assert store.data["orders"][key]["status"] == "creating"
    assert not bot.telegram_clients


@pytest.mark.asyncio
async def test_admin_checks_and_buyer_ownership(bot, store):
    key = approved(store)
    before = copy.deepcopy(store.data)
    for action in (
        "sales_admin",
        "sales_a_toggle",
        "sales_a_approve_" + key,
        "sales_a_create_" + key,
        "sales_w_bad_done",
        "sales_cancel_" + key,
    ):
        await bot.sales_ui.callback(update(99, action), context())
    assert store.data == before


@pytest.mark.asyncio
async def test_receipt_delivery_failure_keeps_order_in_queue(bot, store):
    from telegram.error import TimedOut

    key = store.save_plan(plan())
    store.configure(enabled=True)
    key, _ = store.checkout(42, key)
    event, ctx = update(42), context()
    event.message.photo = [SimpleNamespace(file_id="test-receipt")]
    ctx.bot.send_photo.side_effect = TimedOut("network")
    assert await bot.sales_ui.receipt(event, ctx)
    assert SalesStore(store.path).data["orders"][key]["status"] == "pending"
    assert event.message.reply_text.await_count == 1


@pytest.mark.asyncio
async def test_manual_account_requires_setup_and_explicit_confirmation(bot, store):
    key = approved(store, "manual")
    with pytest.raises(ValueError, match="manual setup required"):
        await bot.sales_ui.fulfil(update(), context(), key)
    ctx = context()
    assert await bot.sales_ui.callback(update(data="sales_a_setup_" + key), ctx) == SALES_INPUT
    assert ctx.user_data["sales_draft"]["kind"] == "account"
    assert store.data["orders"][key]["status"] == "approved"


@pytest.mark.asyncio
async def test_plan_wizard_validation_and_optional_text(bot, store):
    ctx = context()
    assert await bot.sales_ui.callback(update(data="sales_a_add"), ctx) == SALES_INPUT
    for text in ("Monthly", "500", "30", "50", "1", "0"):
        assert await bot.sales_ui.text(update(text=text), ctx) == SALES_INPUT
    token = ctx.user_data["sales_draft"]["token"]
    for _ in range(3):
        await bot.sales_ui.callback(update(data=f"sales_w_{token}_blank"), ctx)
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_in_9"), ctx)
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_done"), ctx)
    assert len(store.data["plans"]) == 1
    saved = next(iter(store.data["plans"].values()))
    assert saved["group"] == saved["desc"] == saved["remark"] == ""
    assert saved["inbounds"] == [9] and saved["delayed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,key", [("plan", None), ("plan", "existing"), ("account", "order")])
async def test_inbound_picker_edits_same_keyboard_and_fetches_once(bot, kind, key):
    bot.get_inbounds_list.return_value = [{"id": i, "tag": f"inbound-{i}"} for i in range(1, 18)]
    ctx, event = context(), update()
    fields = PLAN_FIELDS if kind == "plan" else ACCOUNT_FIELDS
    ctx.user_data["sales_draft"] = {
        "token": "picker",
        "kind": kind,
        "key": key,
        "step": fields.index("inbounds"),
        "data": plan(inbounds=[]),
    }
    assert await bot.sales_ui.prompt(event, ctx) == SALES_INPUT
    event.effective_message.reply_text.assert_awaited_once()
    event.callback_query.edit_message_text.assert_not_awaited()

    async def click(choice):
        event.callback_query.data = "sales_w_picker_" + choice
        assert await bot.sales_ui.callback(event, ctx) == SALES_INPUT
        markup = event.callback_query.edit_message_text.await_args.kwargs["reply_markup"]
        return {
            b.callback_data: bot.localize_outgoing_text("en", b.text) for row in markup.inline_keyboard for b in row
        }

    buttons = await click("in_1")
    assert "✅" in buttons["sales_w_picker_in_1"]
    buttons = await click("page_1")
    assert "sales_w_picker_in_16" in buttons and "sales_w_picker_in_1" not in buttons
    buttons = await click("in_16")
    assert "✅" in buttons["sales_w_picker_in_16"]
    buttons = await click("page_0")
    assert "✅" in buttons["sales_w_picker_in_1"]
    buttons = await click("in_1")
    assert "✅" not in buttons["sales_w_picker_in_1"]
    assert ctx.user_data["sales_draft"]["data"]["inbounds"] == [16]
    buttons = await click("page_999")
    assert ctx.user_data["sales_draft"]["page"] == 1
    assert "✅" in buttons["sales_w_picker_in_16"]
    event.effective_message.reply_text.assert_awaited_once()
    assert event.callback_query.edit_message_text.await_count == 6
    bot.get_inbounds_list.assert_awaited_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_inbound_picker_only_ignores_unchanged_markup_error(bot):
    from telegram.error import BadRequest

    ctx, event = context(), update()
    ctx.user_data["sales_draft"] = {
        "token": "picker",
        "kind": "plan",
        "key": None,
        "step": PLAN_FIELDS.index("inbounds"),
        "data": plan(),
    }
    await bot.sales_ui.prompt(event, ctx)
    event.callback_query.data = "sales_w_picker_page_0"
    event.callback_query.edit_message_text.side_effect = BadRequest("Message is not modified")
    assert await bot.sales_ui.callback(event, ctx) == SALES_INPUT
    event.effective_message.reply_text.assert_awaited_once()
    event.callback_query.edit_message_text.side_effect = BadRequest("Message can't be edited")
    with pytest.raises(BadRequest, match="can't be edited"):
        await bot.sales_ui.callback(event, ctx)
    event.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamed_json_waits_for_all_chunks(bot):
    class Stream:
        async def iter_chunked(self, size):
            for chunk in (b'{"success":', b'true,"obj":', b'{"clients":[]}}'):
                yield chunk

    response = SimpleNamespace(content_length=None, content=Stream())
    assert await bot.APIClient.decode_json_response(response) == {"success": True, "obj": {"clients": []}}


@pytest.mark.asyncio
async def test_streamed_json_bound_is_enforced(bot, monkeypatch):
    monkeypatch.setattr(bot, "MAX_API_RESPONSE_BYTES", 4)

    class Stream:
        async def iter_chunked(self, size):
            yield b"123"
            yield b"456"

    with pytest.raises(ValueError, match="safety limit"):
        await bot.APIClient.decode_json_response(SimpleNamespace(content_length=None, content=Stream()))


def test_panel_protocol_defaults_and_credential_preservation(bot):
    new = bot.build_client_data_new("alice", 0, 0, "", "", [9])
    assert len(new["config"]["snell"]["userkey"]) == 32
    old = {**new, "id": 7, "config": {"vmess": {"name": "alice", "uuid": "keep-me", "alterId": 0}}}
    edited = bot.build_client_data_edit(7, "bob", 0, 0, "", "", [9], original_client=old)
    assert edited["config"]["vmess"]["uuid"] == "keep-me"
    assert edited["config"]["vmess"]["name"] == "bob"
    assert len(edited["config"]["snell"]["userkey"]) == 32
    assert "snell" not in old["config"]


def test_malformed_client_ids_are_rejected_before_cleanup(bot):
    for clients in ([{}], [{"id": True}], [{"id": 1}, {"id": 1}], [{"id": -2}]):
        assert bot.sui_clients({"success": True, "obj": {"clients": clients}}) is None


@pytest.mark.asyncio
async def test_manual_purchase_complete_flow(bot, store, monkeypatch):
    key = approved(store, "manual")
    created = []

    async def save(action, payload):
        created.append({**copy.deepcopy(payload), "id": 27})
        return {"success": True}

    async def get(endpoint, params=None):
        if endpoint.endswith("inbounds"):
            return {"success": True, "obj": {"inbounds": [{"id": 9}]}}
        return {"success": True, "obj": {"clients": copy.deepcopy(created)}}

    monkeypatch.setattr(bot.api_client, "get", AsyncMock(side_effect=get))
    monkeypatch.setattr(bot, "create_or_edit_client", AsyncMock(side_effect=save))
    ctx = context()
    await bot.sales_ui.callback(update(data="sales_a_setup_" + key), ctx)
    await bot.sales_ui.text(update(text="chosen_name"), ctx)
    token = ctx.user_data["sales_draft"]["token"]
    for _ in range(3):
        await bot.sales_ui.callback(update(data=f"sales_w_{token}_blank"), ctx)
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_done"), ctx)
    assert not created
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_create"), ctx)
    assert len(created) == 1 and created[0]["name"] == "chosen_name"
    assert bot.telegram_clients == {42: [27]}
    assert store.data["orders"][key]["status"] == "fulfilled"
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_create"), ctx)
    assert len(created) == 1


@pytest.mark.asyncio
async def test_removed_inbound_prevents_automatic_creation(bot, store, monkeypatch):
    key = approved(store)
    monkeypatch.setattr(bot.api_client, "get", AsyncMock(return_value={"success": True, "obj": {"inbounds": []}}))
    monkeypatch.setattr(bot, "create_or_edit_client", AsyncMock())
    with pytest.raises(ValueError, match="inbound"):
        await bot.sales_ui.fulfil(update(), context(), key)
    assert bot.create_or_edit_client.await_count == 0
    assert store.data["orders"][key]["status"] == "approved"


@pytest.mark.asyncio
async def test_notification_failure_can_be_retried_without_recreation(bot, store, monkeypatch):
    from telegram.error import Forbidden

    key = approved(store)
    store.update_order(key, {"approved"}, status="fulfilled", client_id=27)
    ctx = context()
    ctx.bot.send_message.side_effect = Forbidden("blocked")
    monkeypatch.setattr(bot, "create_or_edit_client", AsyncMock())
    await bot.sales_ui.fulfil(update(), ctx, key)
    assert not store.data["orders"][key]["notified"]
    ctx.bot.send_message.side_effect = None
    await bot.sales_ui.fulfil(update(), ctx, key)
    assert store.data["orders"][key]["notified"]
    assert bot.create_or_edit_client.await_count == 0


def test_sales_backup_round_trip_and_legacy_port_migration(store, tmp_path):
    from sui_bot.backup_bundle import build_bundle, load_bundle, restore_bundle, write_bundle

    key = approved(store)
    runtime = tmp_path / "runtime_settings.json"
    runtime.write_text('{"HIDE_SUBSCRIPTION_PORT": "true", "WEB_PANEL_ENABLED": "true"}', encoding="utf-8")
    bundle = build_bundle({"sales": store.path, "runtime_settings": runtime}, {})
    assert "HIDE_SUBSCRIPTION_PORT" not in bundle["state"]["runtime_settings"]
    target = tmp_path / "backup.json"
    write_bundle(bundle, target)
    loaded = load_bundle(target)
    dest = tmp_path / "restored-sales.json"
    restore_bundle(loaded, {"sales": dest, "runtime_settings": tmp_path / "restored-runtime.json"})
    assert SalesStore(dest).data["orders"][key]["status"] == "approved"


@pytest.mark.asyncio
async def test_bad_request_is_not_retried_as_network_outage(bot):
    from telegram.error import BadRequest

    sender = SimpleNamespace(send_photo=AsyncMock(side_effect=BadRequest("invalid caption")))
    with pytest.raises(BadRequest):
        await bot.forward_renewal_receipt(
            sender, media_type="photo", media_file_id="test", caption="test", keyboard=None
        )
    assert sender.send_photo.await_count == 1


@pytest.mark.asyncio
async def test_start_clears_abandoned_editor(bot):
    event, ctx = update(), context()
    ctx.user_data["sales_draft"] = {"step": 3}
    assert await bot.start.__wrapped__(event, ctx) == -1
    assert ctx.user_data == {}


def custom_config(**overrides):
    return {**plan(delayed=False), "price_gb": 20, "price_day": 5, "max_gb": 500, "max_days": 365, **overrides}


@pytest.mark.parametrize("rates,gb,days,price", [((20, 5), 10, 30, 350), ((20, 0), 10, 30, 200), ((0, 5), 50, 10, 50)])
def test_custom_pricing_and_immutable_order_snapshot(store, rates, gb, days, price):
    from sui_bot.sales import custom_plan

    config = custom_config(price_gb=rates[0], price_day=rates[1])
    assert custom_plan(config, gb, days)["price"] == price
    store.configure(enabled=True, custom_enabled=True, custom=config, mode="automatic")
    key, order = store.checkout_custom(42, gb, days, config)
    assert order["plan"]["price"] == price
    store.configure(custom={**config, "price_gb": 25})
    assert SalesStore(store.path).data["orders"][key]["plan"]["price"] == price
    with pytest.raises(ValueError, match="pricing changed"):
        store.checkout_custom(99, gb, days, config)


@pytest.mark.parametrize("gb,days", [(0, 30), (-1, 30), (501, 30), (1, 0), (1, 366), (True, 1), (1.5, 1)])
def test_custom_pricing_rejects_invalid_quantities(gb, days):
    from sui_bot.sales import custom_plan

    with pytest.raises(ValueError):
        custom_plan(custom_config(), gb, days)


@pytest.mark.asyncio
async def test_custom_admin_wizard_and_buyer_purchase(bot, store):
    from sui_bot.sales_ui import CUSTOM_BUY_INPUT

    ctx = context()
    await bot.sales_ui.callback(update(data="sales_a_custom_config"), ctx)
    for value in ("20", "5", "30", "50", "500", "365", "1"):
        assert await bot.sales_ui.text(update(text=value), ctx) == SALES_INPUT
    token = ctx.user_data["sales_draft"]["token"]
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_in_9"), ctx)
    await bot.sales_ui.callback(update(data=f"sales_w_{token}_done"), ctx)
    assert store.data["custom"]["inbounds"] == [9]
    await bot.sales_ui.callback(update(data="sales_a_custom_toggle"), ctx)
    assert store.data["custom_enabled"] and not store.data["enabled"]
    await bot.sales_ui.callback(update(data="sales_a_toggle"), ctx)
    assert store.data["enabled"] and not store.data["plans"]
    assert await bot.sales_ui.callback(update(42, "sales_shop"), ctx) == CUSTOM_BUY_INPUT
    for value in ("10", "30"):
        assert await bot.sales_ui.custom_text(update(42, text=value), ctx) == CUSTOM_BUY_INPUT
    assert not store.data["orders"]
    token = ctx.user_data["custom_purchase"]["token"]
    await bot.sales_ui.callback(update(42, f"sales_custom_confirm_{token}"), ctx)
    order = store.open_order(42)[1]
    assert order["status"] == "receipt" and order["plan"]["price"] == 350
    assert order["plan"]["volume"] == 10 * 1024**3 and order["plan"]["delayed"]
    await bot.sales_ui.callback(update(42, f"sales_custom_confirm_{token}"), ctx)
    assert len(store.data["orders"]) == 1
    before = copy.deepcopy(store.data)
    for action in ("sales_a_custom_config", "sales_a_custom_toggle"):
        await bot.sales_ui.callback(update(42, action), context())
    assert store.data == before


@pytest.mark.asyncio
async def test_custom_quotes_rejected_after_price_change_or_sales_disabled(bot, store):
    config = custom_config()
    store.configure(enabled=True, custom_enabled=True, custom=config)
    ctx = context()
    await bot.sales_ui.callback(update(42, "sales_shop"), ctx)
    for value in ("10", "30"):
        await bot.sales_ui.custom_text(update(42, text=value), ctx)
    token = ctx.user_data["custom_purchase"]["token"]
    store.configure(custom={**config, "price_gb": 30})
    await bot.sales_ui.callback(update(42, f"sales_custom_confirm_{token}"), ctx)
    assert not store.data["orders"]
    store.configure(custom=config, enabled=False)
    await bot.sales_ui.callback(update(42, f"sales_custom_confirm_{token}"), ctx)
    assert not store.data["orders"]


@pytest.mark.asyncio
async def test_alert_controls_permissions_validation_persistence(bot, monkeypatch, tmp_path):
    from sui_bot.admin_tools import ALERT_INPUT, AdminTools
    from sui_bot.runtime_settings import load_runtime_settings

    path = str(tmp_path / "runtime.json")
    monkeypatch.setattr(bot, "RUNTIME_SETTINGS_FILE", path)
    monkeypatch.setattr(bot, "CPU_ALERT_THRESHOLD", 90)
    tools, ctx = AdminTools(bot), context()
    assert await tools.callback(update(42, "tools_CPU"), ctx) == -1
    assert not ctx.user_data
    assert await tools.callback(update(data="tools_CPU"), ctx) == ALERT_INPUT
    for value in ("0", "101", "80.5", "bad"):
        assert await tools.text(update(text=value), ctx) == ALERT_INPUT
    assert await tools.text(update(text="70"), ctx) == -1
    assert bot.CPU_ALERT_THRESHOLD == 70
    assert load_runtime_settings(path)["CPU_ALERT_THRESHOLD"] == "70"


@pytest.mark.asyncio
async def test_manual_panel_backup_is_bounded_private_and_cleaned(bot, monkeypatch):
    from sui_bot.admin_tools import AdminTools
    from sui_bot.backup import SQLITE_HEADER

    class Response:
        status = 200
        content_length = len(SQLITE_HEADER)
        content = SimpleNamespace()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def chunks(size):
        yield SQLITE_HEADER

    Response.content.iter_chunked = chunks
    response = Response()
    session = SimpleNamespace(get=Mock(return_value=response))
    monkeypatch.setattr(bot.api_client, "ensure_session", AsyncMock())
    monkeypatch.setattr(bot.api_client, "session", session)
    tools, ctx = AdminTools(bot), context()
    await tools.callback(update(42, "tools_backup"), ctx)
    session.get.assert_not_called()
    paths = []

    async def send(**kwargs):
        from pathlib import Path

        assert kwargs["chat_id"] == 1
        assert kwargs["document"].read() == SQLITE_HEADER
        paths.append(Path(kwargs["document"].name))

    ctx.bot.send_document.side_effect = send
    await tools.callback(update(data="tools_backup"), ctx)
    assert len(paths) == 1 and not paths[0].exists()
    assert session.get.call_args.kwargs["allow_redirects"] is False
    response.content_length = bot.BACKUP_MAX_BYTES + 1
    await tools.callback(update(data="tools_backup"), ctx)
    assert ctx.bot.send_document.await_count == 1


def test_custom_settings_and_thresholds_backup_restore(store, tmp_path):
    from sui_bot.backup_bundle import build_bundle, restore_bundle

    store.configure(custom=custom_config(), custom_enabled=True)
    runtime = tmp_path / "runtime.json"
    runtime.write_text('{"CPU_ALERT_THRESHOLD":"75","RAM_ALERT_THRESHOLD":"65"}', encoding="utf-8")
    bundle = build_bundle({"sales": store.path, "runtime_settings": runtime}, {})
    destination = tmp_path / "restored-sales.json"
    restore_bundle(bundle, {"sales": destination, "runtime_settings": tmp_path / "restored-runtime.json"})
    assert SalesStore(destination).data["custom"] == custom_config()
    runtime.write_text('{"CPU_ALERT_THRESHOLD":"101"}', encoding="utf-8")
    with pytest.raises(ValueError):
        build_bundle({"runtime_settings": runtime}, {})


def test_private_menu_contains_only_language(bot, store):
    markup = bot.get_main_menu_keyboard(False, 42)
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == ["language_settings"]
    bot.telegram_clients[42] = [9]
    markup = bot.get_main_menu_keyboard(False, 42)
    assert "my_usage" in [button.callback_data for row in markup.inline_keyboard for button in row]


def test_latest_panel_client_edit_and_renewal_contract(bot):
    original = {
        **bot.build_client_data_new("alice", 1000, 1000000, "", "", [9]),
        "id": 7,
        "up": 20,
        "down": 30,
        "totalUp": 100,
        "totalDown": 200,
        "createdAt": 123,
        "onlineAt": 456,
    }
    edited = bot.build_client_data_edit(7, "alice", 2000, 2000000, "", "", [9], original_client=original)
    for field in ("up", "down", "totalUp", "totalDown", "createdAt", "onlineAt", "config"):
        assert edited[field] == original[field]
    renewed = bot.build_client_renewal_data(original, 7, 2000000)
    assert renewed["up"] == renewed["down"] == 0
    assert (renewed["totalUp"], renewed["totalDown"]) == (120, 230)
    assert renewed["createdAt"] == 123 and renewed["onlineAt"] == 456
    # The panel's first-traffic reset uses resetDays for either expiry OR nextReset.
    assert bot.lifecycle_fields("delayed_expiry", 15) == {
        "delayStart": True,
        "autoReset": False,
        "resetDays": 15,
        "nextReset": 0,
    }
    assert bot.lifecycle_fields("reset_first", 15) == {
        "delayStart": True,
        "autoReset": True,
        "resetDays": 15,
        "nextReset": 0,
    }
    assert bot.lifecycle_fields("reset_now", 15, now_timestamp=100)["nextReset"] == 100 + 15 * 86400


def test_new_admin_translations_have_matching_placeholders():
    import string

    from sui_bot.admin_tools import MESSAGES

    for translations in MESSAGES.values():
        assert len(translations) == 4
        fields = [{field for _, field, _, _ in string.Formatter().parse(text) if field} for text in translations]
        assert all(field == fields[0] for field in fields)


@pytest.mark.asyncio
async def test_error_handler_never_posts_to_channel(bot):
    event = update()
    event.effective_chat.type = "channel"
    event.effective_user = None
    await bot.error_handler(event, SimpleNamespace(error=ValueError("test error")))
    event.effective_message.reply_text.assert_not_awaited()
