"""Small, persistent localization layer for Telegram users."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES = {
    "en": "English 🇬🇧",
    "fa": "فارسی 🇮🇷",
    "ru": "Русский 🇷🇺",
    "zh": "中文 🇨🇳",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "choose_language": "🌐 Choose your preferred language:",
        "language_saved": "✅ Language saved.",
        "welcome": "🤖 Welcome to SUI Bot\n\nChoose an option:",
        "my_subscription": "📊 My Subscription",
        "my_subscriptions": "📊 My Subscriptions",
        "all_users": "👥 All Users", "online_users": "🌐 Online Users",
        "server_status": "💻 Server Status", "bot_stats": "📊 Bot Stats",
        "links": "🔗 Links", "broadcast": "📢 Broadcast",
        "inactive_users": "🔍 Inactive Users", "delete_user": "🗑️ Delete User",
        "create_user": "➕ Create User", "edit_user": "📝 Edit User",
        "refresh": "🔄 Refresh", "settings": "⚙️ Settings", "language": "🌐 Language",
        "main_menu": "🏠 Main Menu", "back": "🔙 Back", "back_subscriptions": "🔙 Back to Subscriptions",
        "my_links": "🔗 My Links", "renew": "💳 Renew Subscription", "web_panel": "🌐 Web Panel",
        "not_active": "❌ The bot is not activated for you. Contact the administrator.",
        "no_access": "❌ You do not have access to this subscription.",
        "select_subscription": "📋 You have {count} subscriptions. Select one:",
        "subscription_number": "📱 Subscription #{client_id}",
        "up_to_date": "✅ Data is up to date.",
        "server_unavailable": "❌ Server unavailable. Try again later.",
        "user_not_found": "❌ User not found.",
        "subscription_links": "🔗 Your Subscription Links",
        "use_links": "💡 Use these links in the appropriate application.",
        "status": "Status", "enabled": "✅ Enabled", "disabled": "❌ Disabled",
        "upload": "📤 Upload", "download": "📥 Download", "total_usage": "📊 Total Usage",
        "total_volume": "💾 Total Volume", "expiry": "⏰ Expiry", "unlimited": "♾️ Unlimited",
        "user": "👤 User", "description": "📝 Description", "group": "👥 Group",
    },
    "fa": {
        "choose_language": "🌐 زبان دلخواه خود را انتخاب کنید:", "language_saved": "✅ زبان ذخیره شد.",
        "welcome": "🤖 به ربات SUI خوش آمدید\n\nیک گزینه را انتخاب کنید:",
        "my_subscription": "📊 اشتراک من", "my_subscriptions": "📊 اشتراک‌های من",
        "all_users": "👥 همه کاربران", "online_users": "🌐 کاربران آنلاین", "server_status": "💻 وضعیت سرور",
        "bot_stats": "📊 آمار ربات", "links": "🔗 اتصال‌ها", "broadcast": "📢 پیام همگانی",
        "inactive_users": "🔍 کاربران غیرفعال", "delete_user": "🗑️ حذف کاربر", "create_user": "➕ ساخت کاربر",
        "edit_user": "📝 ویرایش کاربر", "refresh": "🔄 بروزرسانی", "settings": "⚙️ تنظیمات", "language": "🌐 زبان",
        "main_menu": "🏠 منوی اصلی", "back": "🔙 بازگشت", "back_subscriptions": "🔙 بازگشت به اشتراک‌ها",
        "my_links": "🔗 لینک‌های من", "renew": "💳 تمدید اشتراک", "web_panel": "🌐 پنل وب",
        "not_active": "❌ ربات برای شما فعال نیست. با مدیر تماس بگیرید.", "no_access": "❌ به این اشتراک دسترسی ندارید.",
        "select_subscription": "📋 شما {count} اشتراک دارید. یکی را انتخاب کنید:",
        "subscription_number": "📱 اشتراک شماره {client_id}", "up_to_date": "✅ اطلاعات بروز است.",
        "server_unavailable": "❌ سرور در دسترس نیست. بعداً تلاش کنید.", "user_not_found": "❌ کاربر پیدا نشد.",
        "subscription_links": "🔗 لینک‌های اشتراک شما", "use_links": "💡 لینک‌ها را در برنامه مناسب استفاده کنید.",
        "status": "وضعیت", "enabled": "✅ فعال", "disabled": "❌ غیرفعال", "upload": "📤 آپلود",
        "download": "📥 دانلود", "total_usage": "📊 مصرف کل", "total_volume": "💾 حجم کل",
        "expiry": "⏰ انقضا", "unlimited": "♾️ نامحدود", "user": "👤 کاربر", "description": "📝 توضیحات", "group": "👥 گروه",
    },
    "ru": {
        "choose_language": "🌐 Выберите предпочитаемый язык:", "language_saved": "✅ Язык сохранён.",
        "welcome": "🤖 Добро пожаловать в SUI Bot\n\nВыберите действие:",
        "my_subscription": "📊 Моя подписка", "my_subscriptions": "📊 Мои подписки",
        "all_users": "👥 Все пользователи", "online_users": "🌐 Онлайн", "server_status": "💻 Состояние сервера",
        "bot_stats": "📊 Статистика бота", "links": "🔗 Привязки", "broadcast": "📢 Рассылка",
        "inactive_users": "🔍 Неактивные", "delete_user": "🗑️ Удалить", "create_user": "➕ Создать",
        "edit_user": "📝 Изменить", "refresh": "🔄 Обновить", "settings": "⚙️ Настройки", "language": "🌐 Язык",
        "main_menu": "🏠 Главное меню", "back": "🔙 Назад", "back_subscriptions": "🔙 К подпискам",
        "my_links": "🔗 Мои ссылки", "renew": "💳 Продлить", "web_panel": "🌐 Веб-панель",
        "not_active": "❌ Бот для вас не активирован. Свяжитесь с администратором.", "no_access": "❌ Нет доступа к этой подписке.",
        "select_subscription": "📋 У вас {count} подписок. Выберите одну:", "subscription_number": "📱 Подписка №{client_id}",
        "up_to_date": "✅ Данные актуальны.", "server_unavailable": "❌ Сервер недоступен. Повторите позже.",
        "user_not_found": "❌ Пользователь не найден.", "subscription_links": "🔗 Ссылки вашей подписки",
        "use_links": "💡 Используйте ссылки в подходящем приложении.", "status": "Статус", "enabled": "✅ Включена",
        "disabled": "❌ Отключена", "upload": "📤 Отправлено", "download": "📥 Получено",
        "total_usage": "📊 Всего использовано", "total_volume": "💾 Общий объём", "expiry": "⏰ Срок",
        "unlimited": "♾️ Без ограничений", "user": "👤 Пользователь", "description": "📝 Описание", "group": "👥 Группа",
    },
    "zh": {
        "choose_language": "🌐 请选择您的首选语言：", "language_saved": "✅ 语言已保存。",
        "welcome": "🤖 欢迎使用 SUI Bot\n\n请选择操作：", "my_subscription": "📊 我的订阅", "my_subscriptions": "📊 我的订阅",
        "all_users": "👥 所有用户", "online_users": "🌐 在线用户", "server_status": "💻 服务器状态", "bot_stats": "📊 机器人统计",
        "links": "🔗 绑定", "broadcast": "📢 广播", "inactive_users": "🔍 非活跃用户", "delete_user": "🗑️ 删除用户",
        "create_user": "➕ 创建用户", "edit_user": "📝 编辑用户", "refresh": "🔄 刷新", "settings": "⚙️ 设置", "language": "🌐 语言",
        "main_menu": "🏠 主菜单", "back": "🔙 返回", "back_subscriptions": "🔙 返回订阅列表", "my_links": "🔗 我的链接",
        "renew": "💳 续订", "web_panel": "🌐 网页面板", "not_active": "❌ 机器人尚未为您启用，请联系管理员。",
        "no_access": "❌ 您无权访问此订阅。", "select_subscription": "📋 您有 {count} 个订阅，请选择：",
        "subscription_number": "📱 订阅 #{client_id}", "up_to_date": "✅ 数据已是最新。",
        "server_unavailable": "❌ 服务器不可用，请稍后重试。", "user_not_found": "❌ 未找到用户。",
        "subscription_links": "🔗 您的订阅链接", "use_links": "💡 请在相应应用中使用这些链接。",
        "status": "状态", "enabled": "✅ 已启用", "disabled": "❌ 已禁用", "upload": "📤 上传",
        "download": "📥 下载", "total_usage": "📊 总用量", "total_volume": "💾 总流量", "expiry": "⏰ 到期",
        "unlimited": "♾️ 无限制", "user": "👤 用户", "description": "📝 描述", "group": "👥 分组",
    },
}


class LanguageStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._languages: dict[int, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._languages = {
                    int(user_id): language for user_id, language in data.items()
                    if language in SUPPORTED_LANGUAGES
                }
        except (OSError, ValueError, json.JSONDecodeError):
            self._languages = {}

    def get(self, user_id: int) -> str | None:
        return self._languages.get(user_id)

    def set(self, user_id: int, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError("unsupported language")
        with self._lock:
            self._languages[user_id] = language
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._languages, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_name, self.path)
            except BaseException:
                Path(temporary_name).unlink(missing_ok=True)
                raise


def translate(language: str | None, key: str, **values: Any) -> str:
    selected = language if language in TRANSLATIONS else "en"
    template = TRANSLATIONS[selected].get(key, TRANSLATIONS["en"].get(key, key))
    return template.format(**values)


# Complete strings used by scheduled reminders and their administrator reports.
REMINDER_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "reminder_multi_title": "⚠️ Your subscriptions are about to expire",
        "reminder_single_title": "⚠️ Your subscription is about to expire!",
        "days_remaining": "⏳ {days} day(s) remaining",
        "renew_prompt": "Please renew your subscription.",
        "reminder_report": "📊 Subscription Reminder Report",
        "summary": "📈 Summary:", "total_users": "📋 Total users", "eligible_users": "🎯 Eligible for reminder",
        "reminded": "✅ Successfully reminded", "failed_remind": "❌ Failed to remind", "inactive": "🚫 Inactive users",
        "inactive_title": "🚫 Inactive users (bot not started or blocked)", "failed_sends": "❌ Failed sends:",
        "successful_sends": "✅ Successful sends", "days_short": "📅 {days} day(s) remaining",
        "more_users": "and {count} more user(s)…", "more_errors": "and {count} more error(s)…",
        "unassigned_title": "⚠️ Unassigned subscriptions approaching expiry ({count})",
        "unassigned_item": "{index}. {description}\n   👤 Username: {name}\n   🆔 Client ID: {client_id}\n   📅 {days} day(s) remaining\n",
        "assign_hint": "Use /assign <TelegramID> <ClientID> to link them.", "report_time": "🕐 Report time",
    },
    "fa": {
        "reminder_multi_title": "⚠️ اشتراک‌های شما رو به اتمام هستند", "reminder_single_title": "⚠️ اشتراک شما رو به اتمام است!",
        "days_remaining": "⏳ {days} روز باقی مانده", "renew_prompt": "لطفاً برای تمدید اشتراک اقدام کنید.",
        "reminder_report": "📊 گزارش یادآوری اشتراک‌ها", "summary": "📈 خلاصه:", "total_users": "📋 کل کاربران",
        "eligible_users": "🎯 واجد شرایط یادآوری", "reminded": "✅ یادآوری موفق", "failed_remind": "❌ یادآوری ناموفق",
        "inactive": "🚫 کاربران غیرفعال", "inactive_title": "🚫 کاربران غیرفعال (ربات را شروع نکرده یا مسدود کرده‌اند)",
        "failed_sends": "❌ ارسال‌های ناموفق:", "successful_sends": "✅ ارسال‌های موفق", "days_short": "📅 {days} روز باقی مانده",
        "more_users": "و {count} کاربر دیگر…", "more_errors": "و {count} خطای دیگر…",
        "unassigned_title": "⚠️ اشتراک‌های بدون اتصال در آستانه انقضا ({count})",
        "unassigned_item": "{index}. {description}\n   👤 نام کاربری: {name}\n   🆔 شناسه کاربر: {client_id}\n   📅 {days} روز باقی مانده\n",
        "assign_hint": "برای اتصال از ‎/assign <TelegramID> <ClientID>‎ استفاده کنید.", "report_time": "🕐 زمان گزارش",
    },
    "ru": {
        "reminder_multi_title": "⚠️ Срок ваших подписок скоро истечёт", "reminder_single_title": "⚠️ Срок вашей подписки скоро истечёт!",
        "days_remaining": "⏳ Осталось дней: {days}", "renew_prompt": "Пожалуйста, продлите подписку.",
        "reminder_report": "📊 Отчёт о напоминаниях", "summary": "📈 Сводка:", "total_users": "📋 Всего пользователей",
        "eligible_users": "🎯 Получатели напоминания", "reminded": "✅ Успешно уведомлены", "failed_remind": "❌ Ошибки уведомления",
        "inactive": "🚫 Неактивные пользователи", "inactive_title": "🚫 Неактивные пользователи (бот не запущен или заблокирован)",
        "failed_sends": "❌ Ошибки отправки:", "successful_sends": "✅ Успешные отправки", "days_short": "📅 Осталось дней: {days}",
        "more_users": "и ещё {count} польз.", "more_errors": "и ещё {count} ошибок…",
        "unassigned_title": "⚠️ Непривязанные подписки с близким сроком окончания ({count})",
        "unassigned_item": "{index}. {description}\n   👤 Имя: {name}\n   🆔 ID клиента: {client_id}\n   📅 Осталось дней: {days}\n",
        "assign_hint": "Используйте /assign <TelegramID> <ClientID> для привязки.", "report_time": "🕐 Время отчёта",
    },
    "zh": {
        "reminder_multi_title": "⚠️ 您的订阅即将到期", "reminder_single_title": "⚠️ 您的订阅即将到期！",
        "days_remaining": "⏳ 剩余 {days} 天", "renew_prompt": "请及时续订。", "reminder_report": "📊 订阅提醒报告",
        "summary": "📈 摘要：", "total_users": "📋 用户总数", "eligible_users": "🎯 符合提醒条件",
        "reminded": "✅ 提醒成功", "failed_remind": "❌ 提醒失败", "inactive": "🚫 非活跃用户",
        "inactive_title": "🚫 非活跃用户（未启动或已屏蔽机器人）", "failed_sends": "❌ 发送失败：",
        "successful_sends": "✅ 发送成功", "days_short": "📅 剩余 {days} 天", "more_users": "以及另外 {count} 位用户…",
        "more_errors": "以及另外 {count} 个错误…", "unassigned_title": "⚠️ 即将到期但未绑定的订阅（{count}）",
        "unassigned_item": "{index}. {description}\n   👤 用户名：{name}\n   🆔 客户 ID：{client_id}\n   📅 剩余 {days} 天\n",
        "assign_hint": "使用 /assign <TelegramID> <ClientID> 进行绑定。", "report_time": "🕐 报告时间",
    },
}

for _language, _messages in REMINDER_TRANSLATIONS.items():
    TRANSLATIONS[_language].update(_messages)


RENEWAL_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "renew_plan_button": "{months} month(s) — {amount:,} toman",
        "renew_title": "💳 Renewal Request", "renew_choose_duration": "Choose a renewal duration:",
        "renew_payment": "💳 Renewal Payment", "duration_value": "📦 Duration: {months} month(s)",
        "amount_value": "💰 Amount: {amount:,} toman", "card_number_value": "🏦 Card number: {card_number}",
        "card_holder_value": "👤 Card holder: {holder}",
        "payment_instructions": "Pay the displayed amount to the card above, then send the receipt image here. After sending it, wait for administrator approval.",
        "renew_cancelled": "❌ Renewal request cancelled.", "receipt_sent": "✅ Your receipt was sent to the administrator. Please wait for approval.",
        "invalid_server_expiry": "❌ The server returned an invalid expiry value.",
        "display_name_label": "🤖 Message display name", "set_display_name": "🤖 Set message display name",
        "enter_display_name": "Enter a new name for the bot's messages (2-48 characters). This does not change its Telegram profile name or @username.\n\nCancel: /cancel",
        "display_name_updated": "✅ Message display name updated to: {name}. The Telegram profile name was not changed.",
        "display_name_invalid": "❌ Enter a display name containing 2-48 visible characters.",
        "subscription_link_mode": "🌐 Subscription-link port", "subscription_port_hidden": "Removed",
        "subscription_port_kept": "Kept", "remove_subscription_port": "🌐 Remove port from subscription links",
        "keep_subscription_port": "🌐 Restore port in subscription links",
        "subscription_port_warning": "⚠️ Important warning\n\nS-UI normally serves subscription links on an explicit port. Enabling this option removes that port only from links shown by this bot.\n\nBefore proceeding, configure nginx, another reverse proxy, or equivalent routing so requests without the port reach the S-UI subscription service. Otherwise, all cleaned subscription links will fail.\n\nThe bot does not configure your server automatically.",
        "confirm_remove_subscription_port": "⚠️ I understand — remove port",
        "subscription_port_removed": "✅ The port is now removed from subscription links shown by the bot.",
        "subscription_port_restored": "✅ Subscription links will include the S-UI port again.",
        "cancel": "❌ Cancel", "back": "🔙 Back", "approve": "✅ Approve", "reject": "❌ Reject",
        "broadcast_delivery": "📢 Message from administrator\n\n{message}\n\nThis message was sent automatically.",
    },
    "fa": {
        "renew_plan_button": "{months} ماه — {amount:,} تومان", "renew_title": "💳 درخواست تمدید",
        "renew_choose_duration": "مدت تمدید را انتخاب کنید:", "renew_payment": "💳 پرداخت تمدید",
        "duration_value": "📦 مدت: {months} ماه", "amount_value": "💰 مبلغ: {amount:,} تومان",
        "card_number_value": "🏦 شماره کارت: {card_number}", "card_holder_value": "👤 صاحب کارت: {holder}",
        "payment_instructions": "مبلغ نمایش‌داده‌شده را به کارت بالا واریز کنید و تصویر رسید را همین‌جا بفرستید. سپس منتظر تأیید مدیر بمانید.",
        "renew_cancelled": "❌ درخواست تمدید لغو شد.", "receipt_sent": "✅ رسید شما برای مدیر ارسال شد. لطفاً منتظر تأیید بمانید.",
        "invalid_server_expiry": "❌ سرور مقدار انقضای نامعتبری برگرداند.",
        "display_name_label": "🤖 نام نمایشی در پیام‌ها", "set_display_name": "🤖 تنظیم نام نمایشی پیام‌ها",
        "enter_display_name": "نام جدیدی برای پیام‌های ربات وارد کنید (۲ تا ۴۸ نویسه). این گزینه نام نمایه تلگرام یا نام کاربری ربات را تغییر نمی‌دهد.\n\nلغو: /cancel",
        "display_name_updated": "✅ نام نمایشی پیام‌ها به {name} تغییر کرد. نام نمایه تلگرام تغییر نکرد.",
        "display_name_invalid": "❌ یک نام نمایشی شامل ۲ تا ۴۸ نویسه قابل مشاهده وارد کنید.",
        "subscription_link_mode": "🌐 پورت لینک اشتراک", "subscription_port_hidden": "حذف می‌شود",
        "subscription_port_kept": "حفظ می‌شود", "remove_subscription_port": "🌐 حذف پورت از لینک‌های اشتراک",
        "keep_subscription_port": "🌐 بازگرداندن پورت لینک‌های اشتراک",
        "subscription_port_warning": "⚠️ هشدار مهم\n\nS-UI معمولاً لینک‌های اشتراک را روی یک پورت مشخص ارائه می‌کند. فعال‌کردن این گزینه فقط پورت را از لینک‌هایی که ربات نمایش می‌دهد حذف می‌کند.\n\nپیش از ادامه، nginx یا یک reverse proxy یا مسیریابی معادل را طوری تنظیم کنید که درخواست‌های بدون پورت به سرویس اشتراک S-UI برسند؛ در غیر این صورت همه لینک‌های پاک‌سازی‌شده از کار خواهند افتاد.\n\nربات تنظیمات سرور را به‌صورت خودکار انجام نمی‌دهد.",
        "confirm_remove_subscription_port": "⚠️ متوجه شدم — پورت حذف شود",
        "subscription_port_removed": "✅ اکنون پورت از لینک‌های اشتراک نمایش‌داده‌شده توسط ربات حذف می‌شود.",
        "subscription_port_restored": "✅ پورت S-UI دوباره در لینک‌های اشتراک نمایش داده می‌شود.",
        "cancel": "❌ لغو", "back": "🔙 بازگشت", "approve": "✅ تأیید", "reject": "❌ رد",
        "broadcast_delivery": "📢 اطلاعیه مدیر\n\n{message}\n\nاین پیام به‌صورت خودکار ارسال شده است.",
    },
    "ru": {
        "renew_plan_button": "{months} мес. — {amount:,} томан", "renew_title": "💳 Запрос продления",
        "renew_choose_duration": "Выберите срок продления:", "renew_payment": "💳 Оплата продления",
        "duration_value": "📦 Срок: {months} мес.", "amount_value": "💰 Сумма: {amount:,} томан",
        "card_number_value": "🏦 Номер карты: {card_number}", "card_holder_value": "👤 Владелец карты: {holder}",
        "payment_instructions": "Переведите указанную сумму на карту выше и отправьте сюда изображение чека. Затем дождитесь подтверждения администратора.",
        "renew_cancelled": "❌ Запрос продления отменён.", "receipt_sent": "✅ Ваш чек отправлен администратору. Дождитесь подтверждения.",
        "invalid_server_expiry": "❌ Сервер вернул недопустимое значение срока действия.",
        "display_name_label": "🤖 Имя в сообщениях", "set_display_name": "🤖 Изменить имя в сообщениях",
        "enter_display_name": "Введите новое имя для сообщений бота (2–48 символов). Имя профиля Telegram и @username не изменятся.\n\nОтмена: /cancel",
        "display_name_updated": "✅ Имя в сообщениях изменено на: {name}. Имя профиля Telegram не изменялось.",
        "display_name_invalid": "❌ Введите отображаемое имя из 2–48 видимых символов.",
        "subscription_link_mode": "🌐 Порт ссылок подписки", "subscription_port_hidden": "Удаляется",
        "subscription_port_kept": "Сохраняется", "remove_subscription_port": "🌐 Удалить порт из ссылок подписки",
        "keep_subscription_port": "🌐 Вернуть порт в ссылки подписки",
        "subscription_port_warning": "⚠️ Важное предупреждение\n\nS-UI обычно обслуживает ссылки подписки на указанном порту. Эта настройка удаляет порт только из ссылок, показываемых ботом.\n\nПеред продолжением настройте nginx, другой обратный прокси или эквивалентную маршрутизацию, чтобы запросы без порта попадали в сервис подписок S-UI. Иначе все очищенные ссылки перестанут работать.\n\nБот не настраивает сервер автоматически.",
        "confirm_remove_subscription_port": "⚠️ Понимаю — удалить порт",
        "subscription_port_removed": "✅ Порт удалён из ссылок подписки, показываемых ботом.",
        "subscription_port_restored": "✅ Порт S-UI снова будет добавляться в ссылки подписки.",
        "cancel": "❌ Отмена", "back": "🔙 Назад", "approve": "✅ Подтвердить", "reject": "❌ Отклонить",
        "broadcast_delivery": "📢 Сообщение администратора\n\n{message}\n\nЭто сообщение отправлено автоматически.",
    },
    "zh": {
        "renew_plan_button": "{months} 个月 — {amount:,} 托曼", "renew_title": "💳 续订请求",
        "renew_choose_duration": "请选择续订时长：", "renew_payment": "💳 续订付款",
        "duration_value": "📦 时长：{months} 个月", "amount_value": "💰 金额：{amount:,} 托曼",
        "card_number_value": "🏦 卡号：{card_number}", "card_holder_value": "👤 持卡人：{holder}",
        "payment_instructions": "请将显示的金额转入上方银行卡，然后在此发送收据图片并等待管理员审核。",
        "renew_cancelled": "❌ 续订请求已取消。", "receipt_sent": "✅ 您的收据已发送给管理员，请等待审核。",
        "invalid_server_expiry": "❌ 服务器返回了无效的到期时间。",
        "display_name_label": "🤖 消息显示名称", "set_display_name": "🤖 设置消息显示名称",
        "enter_display_name": "请输入用于机器人消息的新名称（2–48 个字符）。这不会更改 Telegram 资料名称或 @username。\n\n取消：/cancel",
        "display_name_updated": "✅ 消息显示名称已更新为：{name}。Telegram 资料名称未更改。",
        "display_name_invalid": "❌ 请输入包含 2–48 个可见字符的显示名称。",
        "subscription_link_mode": "🌐 订阅链接端口", "subscription_port_hidden": "已移除",
        "subscription_port_kept": "已保留", "remove_subscription_port": "🌐 从订阅链接中移除端口",
        "keep_subscription_port": "🌐 恢复订阅链接端口",
        "subscription_port_warning": "⚠️ 重要警告\n\nS-UI 通常通过明确端口提供订阅链接。启用后，只会从机器人显示的链接中移除该端口。\n\n继续之前，请配置 nginx、其他反向代理或等效路由，使不带端口的请求能够到达 S-UI 订阅服务，否则所有清理后的订阅链接都会失效。\n\n机器人不会自动配置服务器。",
        "confirm_remove_subscription_port": "⚠️ 我已了解 — 移除端口",
        "subscription_port_removed": "✅ 机器人显示的订阅链接已移除端口。",
        "subscription_port_restored": "✅ 订阅链接将重新包含 S-UI 端口。",
        "cancel": "❌ 取消", "back": "🔙 返回", "approve": "✅ 批准", "reject": "❌ 拒绝",
        "broadcast_delivery": "📢 管理员消息\n\n{message}\n\n此消息由系统自动发送。",
    },
}

for _language, _messages in RENEWAL_TRANSLATIONS.items():
    TRANSLATIONS[_language].update(_messages)
