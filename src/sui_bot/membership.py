"""Required-chat configuration and inbound-only membership enforcement."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ConversationHandler

from .membership_i18n import membership_text

MEMBERSHIP_INPUT = 1010
MAX_REQUIRED_CHATS = 8
MAX_MEMBERSHIP_BYTES = 32 * 1024


def validate_join_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 512 or any(c.isspace() for c in value):
        raise ValueError("invalid Telegram join link")
    url = urlsplit(value)
    if url.scheme != "https" or url.netloc != "t.me" or url.query or url.fragment:
        raise ValueError("use an HTTPS t.me join link")
    if not re.fullmatch(r"/(?:[A-Za-z][A-Za-z0-9_]{3,31}|\+[A-Za-z0-9_-]+|joinchat/[A-Za-z0-9_-]+)/?", url.path):
        raise ValueError("invalid Telegram join link")
    return value.rstrip("/")


def validate_membership(data: dict) -> None:
    if not isinstance(data, dict) or data.get("version") != 1 or type(data.get("enabled")) is not bool:
        raise ValueError("invalid membership settings")
    chats = data.get("chats")
    if not isinstance(chats, list) or len(chats) > MAX_REQUIRED_CHATS:
        raise ValueError("invalid required chat list")
    ids = set()
    for chat in chats:
        if not isinstance(chat, dict) or type(chat.get("id")) is not int or chat["id"] >= 0 or chat["id"] in ids:
            raise ValueError("invalid or duplicate chat ID")
        ids.add(chat["id"])
        title = chat.get("title")
        if not isinstance(title, str) or not 1 <= len(title) <= 256 or any(ord(c) < 32 for c in title):
            raise ValueError("invalid chat title")
        validate_join_url(chat.get("url"))
    if data["enabled"] and not chats:
        raise ValueError("enabled membership needs at least one chat")


class MembershipStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.load()

    def load(self) -> None:
        data = {"version": 1, "enabled": False, "chats": []}
        if self.path.exists():
            if self.path.stat().st_size > MAX_MEMBERSHIP_BYTES:
                raise ValueError("membership settings exceed the safety limit")
            data = json.loads(self.path.read_text(encoding="utf-8"))
        validate_membership(data)
        self.data = data

    def save(self, data: dict) -> None:
        validate_membership(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".membership-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        self.data = copy.deepcopy(data)

    def upsert(self, chat: dict) -> None:
        data = copy.deepcopy(self.data)
        data["chats"] = [c for c in data["chats"] if c["id"] != chat["id"]] + [chat]
        self.save(data)

    def remove(self, chat_id: int) -> None:
        data = copy.deepcopy(self.data)
        data["chats"] = [c for c in data["chats"] if c["id"] != chat_id]
        if not data["chats"]:
            data["enabled"] = False
        self.save(data)


def is_member(member) -> bool:
    return member.status in {"creator", "administrator", "member"} or (
        member.status == "restricted" and member.is_member is True
    )


class MembershipUI:
    def __init__(self, bot_module, store: MembershipStore):
        self.b = bot_module
        self.store = store
        self.attempts: dict[int, float] = {}
        self.last_error_log = 0.0

    def t(self, uid, key, **values):
        return membership_text(self.b.language_store.get(uid) or "en", key, **values)

    def button(self, uid, key, callback):
        return InlineKeyboardButton(self.b.preserve_dynamic_text(self.t(uid, key)), callback_data=callback)

    async def say(self, update, key, rows=None, **values):
        await update.effective_message.reply_text(
            self.b.preserve_dynamic_text(self.t(update.effective_user.id, key, **values)),
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )

    async def admin_menu(self, update):
        uid = update.effective_user.id
        rows = [
            [self.button(uid, "disable" if self.store.data["enabled"] else "enable", "membership_toggle")],
            [self.button(uid, "add", "membership_add")],
        ]
        for chat in self.store.data["chats"]:
            rows.append(
                [
                    InlineKeyboardButton(
                        self.b.preserve_dynamic_text("🗑 " + chat["title"]),
                        callback_data=f"membership_remove_{chat['id']}",
                    )
                ]
            )
        rows.append([self.button(uid, "back", "settings_admin_tools")])
        await self.say(
            update,
            "admin_help",
            rows,
            count=len(self.store.data["chats"]),
            status=self.t(uid, "on" if self.store.data["enabled"] else "off"),
        )

    async def bot_can_check(self, bot, chat_id):
        member = await bot.get_chat_member(chat_id, bot.id, read_timeout=5, connect_timeout=5, pool_timeout=5)
        return member.status in {"creator", "administrator"}

    async def callback(self, update, context):
        if update.effective_user.id != self.b.ADMIN_TELEGRAM_ID:
            return ConversationHandler.END
        if update.effective_chat.type != "private":
            await self.say(update, "private")
            return ConversationHandler.END
        await self.b.localized_query_answer(update.callback_query)
        action = update.callback_query.data
        context.user_data.pop("membership_draft", None)
        if action == "membership_add":
            context.user_data["membership_draft"] = {}
            await self.say(update, "enter_chat")
            return MEMBERSHIP_INPUT
        if action == "membership_toggle":
            data = copy.deepcopy(self.store.data)
            if not data["enabled"]:
                if not data["chats"]:
                    await self.say(update, "need_chat")
                    return ConversationHandler.END
                try:
                    for chat in data["chats"]:
                        if not await self.bot_can_check(context.bot, chat["id"]):
                            await self.say(update, "bot_admin")
                            return ConversationHandler.END
                except TelegramError:
                    await self.say(update, "verify_failed")
                    return ConversationHandler.END
            data["enabled"] = not data["enabled"]
            self.store.save(data)
            self.attempts.clear()
        elif action.startswith("membership_remove_"):
            try:
                chat_id = int(action.removeprefix("membership_remove_"))
            except ValueError:
                return ConversationHandler.END
            self.store.remove(chat_id)
            self.attempts.clear()
        await self.admin_menu(update)
        return ConversationHandler.END

    async def text(self, update, context):
        if update.effective_user.id != self.b.ADMIN_TELEGRAM_ID or update.effective_chat.type != "private":
            return ConversationHandler.END
        draft = context.user_data.get("membership_draft")
        if draft is None:
            return ConversationHandler.END
        value = update.message.text.strip()
        try:
            if not draft:
                if re.fullmatch(r"-[1-9][0-9]{0,19}", value):
                    identifier = int(value)
                elif re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,31}", value):
                    identifier = value
                else:
                    raise ValueError("invalid chat identifier")
                chat = await context.bot.get_chat(identifier, read_timeout=5, connect_timeout=5)
                if chat.type not in {"channel", "supergroup", "group"} or not await self.bot_can_check(
                    context.bot, chat.id
                ):
                    await self.say(update, "bot_admin")
                    return MEMBERSHIP_INPUT
                draft.update(id=chat.id, title=chat.title or str(chat.id))
                if chat.username:
                    draft["url"] = validate_join_url("https://t.me/" + chat.username)
                else:
                    await self.say(update, "enter_link")
                    return MEMBERSHIP_INPUT
            else:
                draft["url"] = validate_join_url(value)
            self.store.upsert(draft)
            self.attempts.clear()
            context.user_data.pop("membership_draft", None)
            await self.say(update, "saved")
            await self.admin_menu(update)
            return ConversationHandler.END
        except (ValueError, TelegramError):
            # Do not expose private invite URLs or Telegram request details.
            if "id" not in draft:
                context.user_data["membership_draft"] = {}
            await self.say(update, "invalid")
            return MEMBERSHIP_INPUT

    async def verify(self, bot, uid):
        semaphore = asyncio.Semaphore(4)

        async def check(chat):
            async with semaphore:
                try:
                    if not await self.bot_can_check(bot, chat["id"]):
                        return chat, True
                    member = await bot.get_chat_member(
                        chat["id"], uid, read_timeout=5, connect_timeout=5, pool_timeout=5
                    )
                    return (None, False) if is_member(member) else (chat, False)
                except TelegramError:
                    return chat, True

        try:
            results = await asyncio.wait_for(asyncio.gather(*(check(c) for c in self.store.data["chats"])), timeout=15)
        except asyncio.TimeoutError:
            return list(self.store.data["chats"]), True
        return [chat for chat, _ in results if chat is not None], any(error for _, error in results)

    async def guard(self, update, context):
        """Runs before every conversation/command/media handler; never filters outgoing messages."""
        try:
            await self._guard(update, context)
        except ApplicationHandlerStop:
            raise
        except Exception:
            # PTB may continue to later handler groups after an ordinary error.
            # Never allow an unexpected verification/delivery failure to bypass the gate.
            self.b.logger.error("Membership gate failed; input was blocked")
            raise ApplicationHandlerStop from None

    async def _guard(self, update, context):
        if not update.effective_user or not update.effective_message:
            return
        uid = update.effective_user.id
        if uid == self.b.ADMIN_TELEGRAM_ID:
            return
        query = update.callback_query
        action = query.data if query and isinstance(query.data, str) else ""
        check_clicked = action == "membership_check"
        if not self.store.data["enabled"]:
            if check_clicked:
                await self.b.localized_query_answer(query)
                await self.show_unlocked(update)
                raise ApplicationHandlerStop
            return
        # Language controls are the only pre-membership interaction allowed.
        if action == "language_settings" or (
            self.b.language_store.get(uid) is None and not action.startswith("lang_set_")
        ):
            if query:
                await self.b.localized_query_answer(query)
            await update.effective_message.reply_text(
                self.b.tr(uid, "choose_language"), reply_markup=self.b.language_keyboard()
            )
            raise ApplicationHandlerStop
        if action.startswith("lang_set_"):
            language = action.removeprefix("lang_set_")
            if language not in self.b.SUPPORTED_LANGUAGES:
                raise ApplicationHandlerStop
            self.b.language_store.set(uid, language)
        # No successful-membership cache: leaving a chat is detected on the next action.
        now = time.monotonic()
        if now - self.attempts.get(uid, -10.0) < 1.0:
            if query:
                await self.b.localized_query_answer(query, self.t(uid, "slow"))
            raise ApplicationHandlerStop
        self.attempts[uid] = now
        if len(self.attempts) > 10000:
            self.attempts.pop(next(iter(self.attempts)))
        missing, failed = await self.verify(context.bot, uid)
        if missing or failed:
            if query:
                await self.b.localized_query_answer(query)
            rows = [
                [InlineKeyboardButton(self.b.preserve_dynamic_text("📢 " + chat["title"]), url=chat["url"])]
                for chat in missing
            ]
            rows.append([self.button(uid, "joined", "membership_check")])
            rows.append([InlineKeyboardButton(self.b.tr(uid, "language"), callback_data="language_settings")])
            await self.say(update, "verify_failed" if failed else "join_required", rows)
            if failed and now - self.last_error_log >= 60:
                self.b.logger.warning(
                    "Required-chat membership could not be verified; check Telegram connectivity and bot administrator permissions"
                )
                self.last_error_log = now
            raise ApplicationHandlerStop
        if check_clicked or action.startswith("lang_set_"):
            if query:
                await self.b.localized_query_answer(query)
            await self.show_unlocked(update)
            raise ApplicationHandlerStop

    async def show_unlocked(self, update):
        uid = update.effective_user.id
        await update.effective_message.reply_text(
            self.b.preserve_dynamic_text(self.t(uid, "unlocked")),
            reply_markup=self.b.get_main_menu_keyboard(False, uid),
        )
