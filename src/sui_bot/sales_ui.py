"""Telegram public-sale workflows, isolated from the legacy administration UI."""

from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import secrets
import time
from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ConversationHandler

from .sales import OPEN_STATUSES, SalesStore, validate_plan
from .sales_i18n import sale_text

SALES_INPUT = 1000
PLAN_FIELDS = ("title", "price", "days", "volume", "delayed", "reset_days", "group", "desc", "remark", "inbounds")
ACCOUNT_FIELDS = ("name", "group", "desc", "remark", "inbounds")


class SalesUI:
    def __init__(self, bot_module, store: SalesStore):
        self.b = bot_module
        self.store = store

    def t(self, uid: int, key: str, **values) -> str:
        return sale_text(self.b.language_store.get(uid) or "en", key, **values)

    def button(self, uid, key, data):
        return InlineKeyboardButton(self.b.preserve_dynamic_text(self.t(uid, key)), callback_data=data)

    async def say(self, update, text, rows=None, **kwargs):
        # Explicit translations and merchant-entered text must not be translated again.
        await update.effective_message.reply_text(
            self.b.preserve_dynamic_text(text),
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
            **kwargs,
        )

    def summary(self, uid, plan):
        policy = self.t(uid, "first_use" if plan["delayed"] else "at_creation")
        if plan["reset_days"]:
            policy += "\n" + self.t(uid, "reset_info", days=plan["reset_days"])
        return self.t(
            uid,
            "summary",
            title=plan["title"],
            days=plan["days"],
            volume=f"{plan['volume'] / 1024**3:g}",
            price=f"{plan['price']:,}",
            currency=plan["currency"],
            policy=policy,
        )

    async def admin_menu(self, update):
        uid = update.effective_user.id
        data = self.store.data
        rows = [
            [self.button(uid, "toggle", "sales_a_toggle")],
            [self.button(uid, "mode", "sales_a_mode")],
            [self.button(uid, "add", "sales_a_add")],
            [self.button(uid, "orders", "sales_a_orders_0")],
        ]
        for key, plan in data["plans"].items():
            label = ("✅ " if plan["active"] else "⏸ ") + plan["title"]
            rows.append(
                [InlineKeyboardButton(self.b.preserve_dynamic_text(label), callback_data=f"sales_a_plan_{key}")]
            )
        rows.append([self.button(uid, "back", "admin_settings")])
        await self.say(
            update,
            "\n\n".join(
                (
                    self.t(uid, "admin"),
                    self.t(uid, "enabled" if data["enabled"] else "disabled"),
                    self.t(uid, data["mode"]),
                    self.t(uid, "ready"),
                )
            ),
            rows,
        )

    def order_rows(self, uid, key, order):
        rows = []
        if uid == self.b.ADMIN_TELEGRAM_ID:
            if order.get("receipt"):
                rows.append([self.button(uid, "receipt", f"sales_a_receipt_{key}")])
            if order["status"] == "pending":
                rows.append(
                    [
                        self.button(uid, "approve", f"sales_a_approve_{key}"),
                        self.button(uid, "reject", f"sales_a_reject_{key}"),
                    ]
                )
            if order["status"] == "approved":
                action = "create" if order["mode"] == "automatic" else "setup"
                rows.append([self.button(uid, "setup", f"sales_a_{action}_{key}")])
                rows.append([self.button(uid, "reject", f"sales_a_reject_{key}")])
            if order["status"] in {"creating", "fulfilled"}:
                rows.append([self.button(uid, "reconcile", f"sales_a_check_{key}")])
            if order["status"] == "rejected" and not order.get("notified"):
                rows.append([self.button(uid, "reconcile", f"sales_a_notify_{key}")])
            rows.append([self.button(uid, "orders", "sales_a_orders_0")])
        elif order["status"] == "receipt":
            rows.append([self.button(uid, "cancel", f"sales_cancel_{key}")])
        rows.append([self.button(uid, "back", "main_menu")])
        return rows

    async def show_order(self, update, key, order):
        uid = update.effective_user.id
        text = self.t(uid, "order", id=key, user=order["user_id"], summary=self.summary(uid, order["plan"]))
        text += "\n" + self.t(uid, "status_" + order["status"])
        if uid != self.b.ADMIN_TELEGRAM_ID and order["status"] == "receipt":
            if int(time.time()) - order["created"] > 1800:
                await self.say(update, self.t(uid, "expired", id=key), self.order_rows(uid, key, order))
                return
            text = html.escape(text) + "\n\n" + self.b.copyable_ltr_code(order["card"])
            text += "\n" + html.escape(order.get("holder", "")) + "\n" + html.escape(self.t(uid, "tap"))
            text += "\n\n" + html.escape(self.t(uid, "pay"))
            await self.say(update, text, self.order_rows(uid, key, order), parse_mode="HTML")
        else:
            await self.say(update, text, self.order_rows(uid, key, order))

    async def callback(self, update, context):
        uid, action = update.effective_user.id, update.callback_query.data
        await self.b.localized_query_answer(update.callback_query)
        if update.effective_chat.type != "private":
            await self.say(update, self.t(uid, "private"))
            return ConversationHandler.END
        if (action == "sales_admin" or action.startswith(("sales_a_", "sales_w_"))) and uid != self.b.ADMIN_TELEGRAM_ID:
            return ConversationHandler.END
        try:
            return await self._callback(update, context, uid, action)
        except (ValueError, KeyError, InvalidOperation):
            await self.say(update, self.t(uid, "invalid"))
            return SALES_INPUT if context.user_data.get("sales_draft") else ConversationHandler.END

    async def _callback(self, update, context, uid, action):
        if action.startswith("sales_w_"):
            return await self.wizard_callback(update, context, action)
        # A fresh entry replaces any abandoned sales editor.
        context.user_data.pop("sales_draft", None)
        if action == "sales_admin":
            if uid != self.b.ADMIN_TELEGRAM_ID:
                return ConversationHandler.END
            await self.admin_menu(update)
        elif action in {"sales_a_toggle", "sales_a_mode"}:
            data = self.store.data
            enabled = not data["enabled"] if action.endswith("toggle") else data["enabled"]
            mode = ("automatic" if data["mode"] == "manual" else "manual") if action.endswith("mode") else data["mode"]
            active = [p for p in data["plans"].values() if p["active"]]
            if enabled and (
                not active
                or not self.payment_ready()
                or (mode == "automatic" and any(not p["inbounds"] for p in active))
            ):
                await self.say(update, self.t(uid, "ready"))
            else:
                self.store.configure(enabled=enabled, mode=mode)
            await self.admin_menu(update)
        elif action == "sales_a_add" or action.startswith("sales_a_edit_"):
            key = action.removeprefix("sales_a_edit_") if action.startswith("sales_a_edit_") else None
            plan = (
                copy.deepcopy(self.store.data["plans"][key])
                if key
                else {
                    "title": "",
                    "price": 1,
                    "days": 30,
                    "volume": 0,
                    "currency": self.b.PAYMENT_CURRENCY,
                    "delayed": False,
                    "reset_days": 0,
                    "active": True,
                    "inbounds": [],
                    "group": "",
                    "desc": "",
                    "remark": "",
                }
            )
            context.user_data["sales_draft"] = {
                "token": secrets.token_hex(4),
                "kind": "plan",
                "key": key,
                "data": plan,
                "step": 0,
            }
            return await self.prompt(update, context)
        elif action.startswith("sales_a_plan_"):
            key = action.removeprefix("sales_a_plan_")
            await self.say(
                update,
                self.summary(uid, self.store.data["plans"][key]),
                [
                    [self.button(uid, "edit", f"sales_a_edit_{key}")],
                    [self.button(uid, "active", f"sales_a_active_{key}")],
                    [self.button(uid, "back", "sales_admin")],
                ],
            )
        elif action.startswith("sales_a_active_"):
            key = action.removeprefix("sales_a_active_")
            plan = copy.deepcopy(self.store.data["plans"][key])
            plan["active"] = not plan["active"]
            if plan["active"] and self.store.data["mode"] == "automatic" and not plan["inbounds"]:
                raise ValueError("missing preset")
            self.store.save_plan(plan, key)
            await self.admin_menu(update)
        elif action.startswith("sales_a_orders_"):
            page = max(0, int(action.rsplit("_", 1)[1]))
            orders = [
                (k, o)
                for k, o in self.store.data["orders"].items()
                if o["status"] in OPEN_STATUSES or not o.get("notified", True)
            ]
            rows = [
                [
                    InlineKeyboardButton(
                        f"{o['user_id']} · {self.t(uid, 'status_' + o['status'])}", callback_data=f"sales_a_order_{k}"
                    )
                ]
                for k, o in orders[page * 10 : page * 10 + 10]
            ]
            if page:
                rows.append([InlineKeyboardButton("◀", callback_data=f"sales_a_orders_{page - 1}")])
            if len(orders) > page * 10 + 10:
                rows.append([InlineKeyboardButton("▶", callback_data=f"sales_a_orders_{page + 1}")])
            rows.append([self.button(uid, "back", "sales_admin")])
            await self.say(update, self.t(uid, "orders" if orders else "empty"), rows)
        elif action == "sales_shop":
            existing = self.store.open_order(uid)
            if existing:
                await self.show_order(update, *existing)
            elif not self.store.data["enabled"] or not self.payment_ready():
                await self.say(update, self.t(uid, "unavailable"))
            else:
                rows = [
                    [
                        InlineKeyboardButton(
                            self.b.preserve_dynamic_text(f"{p['title']} — {p['price']:,} {p['currency']}"),
                            callback_data=f"sales_buy_{k}",
                        )
                    ]
                    for k, p in self.store.data["plans"].items()
                    if p["active"]
                ]
                await self.say(update, self.t(uid, "shop" if rows else "empty"), rows)
        elif action.startswith("sales_buy_"):
            if not self.payment_ready():
                raise ValueError("payment details missing")
            key, order = self.store.checkout(uid, action.removeprefix("sales_buy_"))
            if "card" not in order:
                order = self.store.update_order(
                    key, {"receipt"}, card=self.b.PAYMENT_CARD_NUMBER, holder=self.b.PAYMENT_CARD_HOLDER
                )
            context.user_data.pop("pending_renew_submission", None)
            await self.show_order(update, key, order)
        elif action.startswith("sales_cancel_"):
            key = action.removeprefix("sales_cancel_")
            if self.store.data["orders"][key]["user_id"] != uid:
                raise ValueError("wrong buyer")
            self.store.update_order(key, {"receipt"}, status="cancelled", notified=True)
            await self.say(update, self.t(uid, "status_cancelled"))
        elif action.startswith("sales_a_"):
            operation, key = action.removeprefix("sales_a_").split("_", 1)
            order = copy.deepcopy(self.store.data["orders"][key])
            if operation == "receipt":
                receipt = order["receipt"]
                method = context.bot.send_photo if receipt["kind"] == "photo" else context.bot.send_document
                await method(chat_id=uid, **{receipt["kind"]: receipt["file_id"]})
            elif operation == "reject":
                order = self.store.update_order(key, {"pending", "approved"}, status="rejected")
                await self.notify(context, key, order, "rejected")
            elif operation == "notify" and order["status"] == "rejected":
                await self.notify(context, key, order, "rejected")
            elif operation == "approve":
                order = self.store.update_order(key, {"pending"}, status="approved")
                if order["mode"] == "automatic":
                    await self.fulfil(update, context, key)
                else:
                    return await self.begin_account(update, context, key, order)
            elif operation == "setup":
                return await self.begin_account(update, context, key, order)
            elif operation in {"create", "check"}:
                await self.fulfil(update, context, key)
            await self.show_order(update, key, self.store.data["orders"][key])
        return ConversationHandler.END

    def payment_ready(self):
        digits = re.sub(r"\D", "", self.b.PAYMENT_CARD_NUMBER)
        return len(digits) >= 8 and bool(set(digits) - {"0"})

    async def begin_account(self, update, context, key, order):
        if order["status"] != "approved" or order["mode"] != "manual":
            raise ValueError("not awaiting setup")
        data = copy.deepcopy(order["plan"])
        data["name"] = order["name"]
        context.user_data["sales_draft"] = {
            "token": secrets.token_hex(4),
            "kind": "account",
            "key": key,
            "data": data,
            "step": 0,
        }
        return await self.prompt(update, context)

    async def prompt(self, update, context):
        draft = context.user_data["sales_draft"]
        uid = update.effective_user.id
        fields = PLAN_FIELDS if draft["kind"] == "plan" else ACCOUNT_FIELDS
        field = fields[draft["step"]]
        prefix = f"sales_w_{draft['token']}_"
        rows = []
        if field == "inbounds":
            inbounds = await self.b.get_inbounds_list(force_refresh=True)
            draft["allowed_inbounds"] = [int(i["id"]) for i in inbounds]
            page = draft.get("page", 0)
            for inbound in inbounds[page * 15 : page * 15 + 15]:
                key = int(inbound["id"])
                label = ("✅ " if key in draft["data"]["inbounds"] else "") + str(inbound.get("tag", key))[:55]
                rows.append(
                    [InlineKeyboardButton(self.b.preserve_dynamic_text(label), callback_data=prefix + f"in_{key}")]
                )
            if page:
                rows.append([InlineKeyboardButton("◀", callback_data=prefix + f"page_{page - 1}")])
            if len(inbounds) > page * 15 + 15:
                rows.append([InlineKeyboardButton("▶", callback_data=prefix + f"page_{page + 1}")])
            rows.append([self.button(uid, "done", prefix + "done")])
        else:
            if draft.get("key"):
                rows.append([self.button(uid, "keep", prefix + "keep")])
            if field in {"group", "desc", "remark"}:
                rows.append([self.button(uid, "blank", prefix + "blank")])
        rows.append([self.button(uid, "cancel", "sales_admin")])
        prompt_key = "reset_prompt" if field == "reset_days" else field + "_prompt"
        text = self.t(uid, prompt_key, currency=draft["data"]["currency"])
        if draft.get("key") and field != "inbounds":
            value = draft["data"].get(field, "")
            if field == "volume":
                value = value / 1024**3
            text += f"\n[{value}]"
        await self.say(update, text + "\n/cancel", rows)
        return SALES_INPUT

    async def text(self, update, context):
        if update.effective_user.id != self.b.ADMIN_TELEGRAM_ID or update.effective_chat.type != "private":
            return ConversationHandler.END
        draft = context.user_data.get("sales_draft")
        if not draft:
            return ConversationHandler.END
        fields = PLAN_FIELDS if draft["kind"] == "plan" else ACCOUNT_FIELDS
        field = fields[draft["step"]]
        raw = update.message.text.strip()
        try:
            if field == "inbounds":
                raise ValueError("use buttons")
            if field in {"price", "days", "reset_days"}:
                value = int(raw)
                low, high = (1, 10**15) if field == "price" else (0 if field == "reset_days" else 1, 3650)
                if not low <= value <= high or (field == "reset_days" and value and draft["data"]["delayed"]):
                    raise ValueError("invalid range")
            elif field == "volume":
                number = Decimal(raw)
                if not number.is_finite() or not 0 <= number <= Decimal(10**18) / 1024**3:
                    raise ValueError("invalid volume")
                value = int(number * 1024**3)
            elif field == "delayed":
                if raw not in {"0", "1"}:
                    raise ValueError("invalid boolean")
                value = raw == "1"
                if value:
                    draft["data"]["reset_days"] = 0
            else:
                value = raw
                limit = {"title": 64, "name": 64, "desc": 256, "group": 128, "remark": 128}[field]
                if not raw or len(raw) > limit or any(ord(c) < 32 for c in raw):
                    raise ValueError("invalid text")
                if field == "name" and not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", raw):
                    raise ValueError("invalid username")
            draft["data"][field] = value
            draft["step"] += 1
            return await self.prompt(update, context)
        except (ValueError, InvalidOperation):
            await self.say(update, self.t(update.effective_user.id, "invalid"))
            return SALES_INPUT

    async def wizard_callback(self, update, context, action):
        draft = context.user_data.get("sales_draft")
        if not draft or not action.startswith(f"sales_w_{draft['token']}_"):
            raise ValueError("stale wizard")
        choice = action.removeprefix(f"sales_w_{draft['token']}_")
        fields = PLAN_FIELDS if draft["kind"] == "plan" else ACCOUNT_FIELDS
        field = fields[draft["step"]]
        if choice == "create" and draft.get("confirmed"):
            key = draft["key"]
            self.store.update_order(key, {"approved"}, name=draft["data"]["name"], account=copy.deepcopy(draft["data"]))
            context.user_data.pop("sales_draft", None)
            await self.fulfil(update, context, key)
            await self.show_order(update, key, self.store.data["orders"][key])
            return ConversationHandler.END
        if field == "inbounds":
            if choice.startswith("page_"):
                draft["page"] = max(0, int(choice[5:]))
            elif choice.startswith("in_"):
                draft.pop("confirmed", None)
                key = int(choice[3:])
                if key not in draft["allowed_inbounds"]:
                    raise ValueError("unknown inbound")
                selected = draft["data"]["inbounds"]
                selected.remove(key) if key in selected else selected.append(key)
            elif choice == "done":
                selected = draft["data"]["inbounds"]
                if not set(selected) <= set(draft["allowed_inbounds"]):
                    raise ValueError("stale inbound")
                if not selected and (draft["kind"] == "account" or self.store.data["mode"] == "automatic"):
                    raise ValueError("empty inbound preset")
                if draft["kind"] == "plan":
                    self.store.save_plan(draft["data"], draft["key"])
                    context.user_data.pop("sales_draft", None)
                    await self.admin_menu(update)
                    return ConversationHandler.END
                draft["confirmed"] = True
                await self.say(
                    update,
                    self.t(update.effective_user.id, "confirm"),
                    [[self.button(update.effective_user.id, "create", f"sales_w_{draft['token']}_create")]],
                )
                return SALES_INPUT
            else:
                raise ValueError("wrong step")
        elif choice == "keep" and draft.get("key"):
            draft["step"] += 1
        elif choice == "blank" and field in {"group", "desc", "remark"}:
            draft["data"][field] = ""
            draft["step"] += 1
        else:
            raise ValueError("wrong step")
        return await self.prompt(update, context)

    async def receipt(self, update, context) -> bool:
        uid = update.effective_user.id
        existing = self.store.open_order(uid)
        if not existing or update.effective_chat.type != "private":
            return False
        key, order = existing
        if order["status"] != "receipt":
            # Let an explicitly selected renewal consume its own receipt.
            if context.user_data.get("pending_renew_submission"):
                return False
            await self.say(update, self.t(uid, "waiting"))
            return True
        photo, document = update.message.photo, update.message.document
        if photo:
            media = {"kind": "photo", "file_id": photo[-1].file_id}
        elif document and str(document.mime_type).startswith("image/"):
            media = {"kind": "document", "file_id": document.file_id}
        else:
            await self.say(update, self.b.tr(uid, "renew_send_image"))
            return True
        # An expired quote with an actual payment must remain reviewable, not discarded.
        order = self.store.update_order(key, {"receipt"}, receipt=media, status="pending")
        admin = self.b.ADMIN_TELEGRAM_ID
        text = self.t(admin, "order", id=key, user=uid, summary=self.summary(admin, order["plan"]))
        try:
            method = context.bot.send_photo if media["kind"] == "photo" else context.bot.send_document
            await method(
                chat_id=admin,
                **{media["kind"]: media["file_id"]},
                caption=self.b.preserve_dynamic_text(text),
                reply_markup=InlineKeyboardMarkup(self.order_rows(admin, key, order)),
            )
        except TelegramError:
            self.b.logger.warning("Sale receipt delivery failed; saved order remains in admin order list")
        await self.say(update, self.t(uid, "submitted"))
        return True

    async def notify(self, context, key, order, message):
        uid = order["user_id"]
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=self.b.preserve_dynamic_text(self.t(uid, message)),
                reply_markup=self.b.get_main_menu_keyboard(False, uid),
            )
        except TelegramError:
            self.b.logger.warning("Sale notification delivery failed; admin can retry from the order list")
            return
        self.store.update_order(key, {order["status"]}, notified=True)

    @staticmethod
    def fingerprint(config):
        return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    async def fulfil(self, update, context, key):
        order = copy.deepcopy(self.store.data["orders"][key])
        if order["status"] == "fulfilled":
            await self.notify(context, key, order, "created")
            return
        if order["status"] not in {"approved", "creating"}:
            raise ValueError("not approved")
        if order["status"] == "approved":
            if order["mode"] == "manual" and "account" not in order:
                raise ValueError("manual setup required")
            plan = order.get("account", order["plan"])
            validate_plan(plan)
            # Fresh API data, not cached metadata, is required before charging fulfilment.
            response = self.b.sui_response_object(await self.b.api_client.get("apiv2/inbounds"))
            if not response or not isinstance(response.get("inbounds"), list):
                raise ValueError("cannot validate inbounds")
            available = {i["id"] for i in response["inbounds"] if isinstance(i, dict) and "id" in i}
            if not plan["inbounds"] or not set(plan["inbounds"]) <= available:
                raise ValueError("inbound no longer exists")
            clients = self.b.sui_clients(await self.b.api_client.get("apiv2/clients"))
            if clients is None or any(c.get("name") == order["name"] for c in clients):
                raise ValueError("name unavailable or server unavailable")
            now = int(time.time())
            payload = self.b.build_client_data_new(
                order["name"],
                plan["volume"],
                0 if plan["delayed"] else now + plan["days"] * 86400,
                plan["desc"],
                plan["group"],
                plan["inbounds"],
                remark=plan["remark"],
                delay_start=plan["delayed"],
                auto_reset=bool(plan["reset_days"]),
                reset_days=plan["days"] if plan["delayed"] else plan["reset_days"],
                next_reset=now + plan["reset_days"] * 86400 if plan["reset_days"] else 0,
            )
            # Commit before POST. Never replay an ambiguous mutation after a timeout/restart.
            order = self.store.update_order(
                key, {"approved"}, status="creating", fingerprint=self.fingerprint(payload["config"])
            )
            await self.b.create_or_edit_client("new", payload)
        clients = self.b.sui_clients(await self.b.api_client.get("apiv2/clients"))
        matches = [c for c in clients or [] if c.get("name") == order["name"]]
        if len(matches) != 1:
            await self.say(update, self.t(update.effective_user.id, "uncertain"))
            return
        client_id = matches[0]["id"]
        details = self.b.sui_clients(await self.b.api_client.get("apiv2/clients", params={"id": str(client_id)}))
        if not details or len(details) != 1 or self.fingerprint(details[0].get("config")) != order.get("fingerprint"):
            await self.say(update, self.t(update.effective_user.id, "uncertain"))
            return
        # Idempotent assignment; save before fulfilment so a crash can safely reconcile again.
        uid = order["user_id"]
        for owner, ids in self.b.telegram_clients.items():
            if owner != uid and client_id in ids:
                raise ValueError("client already assigned to another account")
        assigned = self.b.telegram_clients.setdefault(uid, [])
        if client_id not in assigned:
            assigned.append(client_id)
        self.b.save_assignments()
        self.b.clients_cache = None
        self.b.clients_cache_time = 0
        order = self.store.update_order(key, {"creating"}, status="fulfilled", client_id=client_id)
        await self.notify(context, key, order, "created")
