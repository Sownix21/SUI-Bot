"""On-demand panel backup and persistent resource-alert controls."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler

from .backup import stream_response_to_file, validate_sqlite_database
from .runtime_settings import alert_threshold, save_runtime_setting

ALERT_INPUT = 1020
MESSAGES = {
    "alerts": (
        "⚠️ CPU / RAM alert thresholds",
        "⚠️ آستانه هشدار پردازنده و رم",
        "⚠️ Пороги уведомлений CPU / RAM",
        "⚠️ CPU／内存警报阈值",
    ),
    "backup": (
        "📦 Download panel backup now",
        "📦 دریافت فوری پشتیبان پنل",
        "📦 Скачать резервную копию панели",
        "📦 立即下载面板备份",
    ),
    "prompt": (
        "Enter {resource} alert percentage (1–100). Current: {value}%. /cancel",
        "درصد هشدار {resource} را وارد کنید (۱ تا ۱۰۰). مقدار فعلی: {value}٪. /cancel",
        "Введите порог {resource} (1–100). Сейчас: {value}%. /cancel",
        "输入 {resource} 警报阈值（1–100）。当前：{value}%。/cancel",
    ),
    "saved": ("✅ Alert threshold saved.", "✅ آستانه هشدار ذخیره شد.", "✅ Порог сохранён.", "✅ 已保存警报阈值。"),
    "invalid": (
        "Enter a whole percentage from 1 to 100. /cancel",
        "درصد را به عدد صحیح از ۱ تا ۱۰۰ وارد کنید. /cancel",
        "Введите целое число от 1 до 100. /cancel",
        "请输入1至100的整数。/cancel",
    ),
    "working": (
        "Preparing a private panel backup…",
        "در حال آماده‌سازی نسخه پشتیبان خصوصی پنل…",
        "Подготовка конфиденциальной копии панели…",
        "正在准备面板私密备份…",
    ),
    "sensitive": (
        "Panel database backup — contains sensitive data. Keep private.",
        "پشتیبان پایگاه داده پنل — حاوی اطلاعات حساس است؛ آن را خصوصی نگه دارید.",
        "Резервная копия базы панели — содержит секретные данные. Не публикуйте.",
        "面板数据库备份——包含敏感信息，请勿公开。",
    ),
    "failed": (
        "Backup failed. Check panel connectivity, token and backup size limit.",
        "پشتیبان‌گیری ناموفق بود. اتصال پنل، توکن و محدودیت حجم پشتیبان را بررسی کنید.",
        "Ошибка резервирования. Проверьте соединение, токен и лимит размера.",
        "备份失败。请检查面板连接、令牌和备份大小限制。",
    ),
    "busy": (
        "A backup is already running. Please wait.",
        "پشتیبان‌گیری در حال انجام است؛ لطفاً صبر کنید.",
        "Резервирование уже выполняется. Подождите.",
        "备份正在进行，请稍候。",
    ),
    "back": ("🔙 Administration", "🔙 مدیریت", "🔙 Администрирование", "🔙 管理"),
}


class AdminTools:
    def __init__(self, bot_module):
        self.b = bot_module
        self.backup_lock = asyncio.Lock()

    def t(self, key, **values):
        languages = ("en", "fa", "ru", "zh")
        language = self.b.user_language(self.b.ADMIN_TELEGRAM_ID)
        return self.b.preserve_dynamic_text(MESSAGES[key][languages.index(language)].format(**values))

    def button(self, key, callback):
        return InlineKeyboardButton(self.t(key), callback_data=callback)

    def allowed(self, update):
        return update.effective_user.id == self.b.ADMIN_TELEGRAM_ID and update.effective_chat.type == "private"

    async def callback(self, update, context):
        if not self.allowed(update):
            return ConversationHandler.END
        await self.b.localized_query_answer(update.callback_query)
        action = update.callback_query.data
        if action == "tools_backup":
            await self.backup(update, context)
        elif action == "tools_alerts":
            rows = [
                [InlineKeyboardButton(f"{r}: {getattr(self.b, r + '_ALERT_THRESHOLD')}%", callback_data=f"tools_{r}")]
                for r in ("CPU", "RAM")
            ]
            rows.append([self.button("back", "settings_admin_tools")])
            await update.effective_message.reply_text(self.t("alerts"), reply_markup=InlineKeyboardMarkup(rows))
        elif action in {"tools_CPU", "tools_RAM"}:
            resource = action[6:]
            context.user_data["alert_resource"] = resource
            await update.effective_message.reply_text(
                self.t("prompt", resource=resource, value=getattr(self.b, resource + "_ALERT_THRESHOLD"))
            )
            return ALERT_INPUT
        return ConversationHandler.END

    async def text(self, update, context):
        if not self.allowed(update):
            return ConversationHandler.END
        resource = context.user_data.get("alert_resource")
        if resource not in {"CPU", "RAM"}:
            return ConversationHandler.END
        try:
            value = alert_threshold(update.message.text.strip())
        except ValueError:
            await update.message.reply_text(self.t("invalid"))
            return ALERT_INPUT
        name = resource + "_ALERT_THRESHOLD"
        save_runtime_setting(name, str(value), self.b.RUNTIME_SETTINGS_FILE)
        setattr(self.b, name, value)
        context.user_data.pop("alert_resource", None)
        await update.message.reply_text(
            self.t("saved"), reply_markup=InlineKeyboardMarkup([[self.button("back", "settings_admin_tools")]])
        )
        return ConversationHandler.END

    async def backup(self, update, context):
        if self.backup_lock.locked():
            await update.effective_message.reply_text(self.t("busy"))
            return
        async with self.backup_lock:
            await update.effective_message.reply_text(self.t("working"))
            try:
                with tempfile.TemporaryDirectory(prefix="sui-panel-backup-") as folder:
                    path = Path(folder) / "s-ui.db"
                    await self.b.api_client.ensure_session()
                    async with self.b.api_client.session.get(
                        self.b.api_client.base_url + "/apiv2/getdb",
                        allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as response:
                        if response.status != 200:
                            raise ValueError("backup HTTP failure")
                        if response.content_length and response.content_length > self.b.BACKUP_MAX_BYTES:
                            raise ValueError("backup too large")
                        await stream_response_to_file(response, path, self.b.BACKUP_MAX_BYTES)
                    await asyncio.to_thread(validate_sqlite_database, path)
                    with path.open("rb") as document:
                        await context.bot.send_document(
                            chat_id=self.b.ADMIN_TELEGRAM_ID,
                            document=document,
                            filename="s-ui.db",
                            caption=self.t("sensitive"),
                        )
            except Exception as exc:
                self.b.logger.warning("Manual panel backup failed (%s)", type(exc).__name__)
                await update.effective_message.reply_text(self.t("failed"))
