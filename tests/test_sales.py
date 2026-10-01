import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from sui_bot.sales import SalesStore, validate_plan
from sui_bot.sales_i18n import LANGUAGES, MESSAGES, sale_text
from sui_bot.sales_ui import SALES_INPUT, SalesUI


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
        callback_query=SimpleNamespace(data=data, answer=AsyncMock(), from_user=SimpleNamespace(id=uid)),
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
