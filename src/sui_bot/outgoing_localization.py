"""Last-mile localization for every Telegram-facing message and button."""

from __future__ import annotations

import re
from typing import Any

# Phrase replacement deliberately leaves commands, usernames, IDs, URLs and
# server-provided values unchanged. Longest matches run first.
PHRASES: dict[str, dict[str, str]] = {
    "fa": {
        "Your receipt was sent to the administrator. Please wait for approval.": "رسید شما برای مدیر ارسال شد. لطفاً منتظر تأیید بمانید.",
        "SUI Bot Backup & Restore": "پشتیبان‌گیری و بازیابی ربات SUI", "Subscription Reminder Report": "گزارش یادآوری اشتراک‌ها",
        "Create & Send Backup": "ساخت و ارسال پشتیبان", "Restore Instructions": "راهنمای بازیابی", "Back To Settings": "بازگشت به تنظیمات",
        "Create New User": "ساخت کاربر جدید", "Edit User": "ویرایش کاربر", "Delete User": "حذف کاربر", "All Clients": "همه کاربران",
        "All Users": "همه کاربران", "Online Users": "کاربران آنلاین", "Server Status": "وضعیت سرور", "Bot Stats": "آمار ربات",
        "User Details": "جزئیات کاربران", "Inactive Users": "کاربران غیرفعال", "Renewal Plans": "طرح‌های تمدید",
        "Set Card Number": "تنظیم شماره کارت", "Set Card Holder": "تنظیم صاحب کارت", "Backup & Restore": "پشتیبان‌گیری و بازیابی",
        "Regenerate Secrets": "ساخت دوباره اطلاعات محرمانه", "Keep Existing Secrets": "حفظ اطلاعات محرمانه فعلی",
        "Send Broadcast To Specific Users": "ارسال پیام به کاربران انتخابی", "Send Broadcast To All Users": "ارسال پیام به همه کاربران",
        "Send Broadcast": "ارسال پیام همگانی", "Specific Users": "کاربران انتخابی", "Check Inactive Users": "بررسی کاربران غیرفعال",
        "Subscription Links": "لینک‌های اشتراک", "Renewal Request": "درخواست تمدید", "Renewal Payment": "پرداخت تمدید",
        "My Subscription": "اشتراک من", "My Subscriptions": "اشتراک‌های من", "Main Menu": "منوی اصلی",
        "Please Enter a Usename": "لطفاً نام کاربری را وارد کنید", "Please Input The User's Client ID": "لطفاً شناسه کاربر را وارد کنید",
        "Use English Alphabet & Numbers Only": "فقط از حروف انگلیسی و اعداد استفاده کنید", "Username Not Available": "نام کاربری در دسترس نیست",
        "Choose Another": "نام دیگری انتخاب کنید", "Input Description": "توضیحات را وارد کنید", "Type a group name": "نام گروه را وارد کنید",
        "Type a new group name": "نام گروه جدید را وارد کنید", "Input Expiry": "مدت اعتبار را وارد کنید", "Input Volume": "حجم را وارد کنید",
        "Choose Active/Deactive State Of The User": "وضعیت فعال یا غیرفعال کاربر را انتخاب کنید",
        "Choose Secrets Policy": "روش مدیریت اطلاعات محرمانه را انتخاب کنید", "Operation Aborted": "عملیات لغو شد",
        "Creating User Aborted": "ساخت کاربر لغو شد", "Editing User Aborted": "ویرایش کاربر لغو شد",
        "Operation Deleting User Aborted": "حذف کاربر لغو شد", "User Created Successfully": "کاربر با موفقیت ساخته شد",
        "User Successfully Edited": "کاربر با موفقیت ویرایش شد", "User With This Client ID Not Found": "کاربری با این شناسه پیدا نشد",
        "Client ID Must Be a Positive Number": "شناسه کاربر باید عدد مثبت باشد", "Wrong Format": "قالب نادرست است",
        "Input Numbers Only": "فقط عدد وارد کنید", "Volume Should Be a Positive Number": "حجم باید عدد مثبت باشد",
        "Days Must Be a Positive Number": "تعداد روزها باید عدد مثبت باشد", "Description Can't Be Empty": "توضیحات نمی‌تواند خالی باشد",
        "Group cannot be empty": "گروه نمی‌تواند خالی باشد", "Creating User": "در حال ساخت کاربر", "Implementing Changes": "در حال اعمال تغییرات",
        "Admin Settings": "تنظیمات مدیر", "Price Per Month": "قیمت ماهانه", "Enabled Renewal Options": "گزینه‌های فعال تمدید",
        "Card Number": "شماره کارت", "Card Holder": "صاحب کارت", "Enter new card number": "شماره کارت جدید را وارد کنید",
        "Enter new card holder name": "نام صاحب کارت جدید را وارد کنید", "Settings edit canceled": "ویرایش تنظیمات لغو شد",
        "Backup sent to this chat": "فایل پشتیبان به این گفتگو ارسال شد", "Keep it private": "آن را محرمانه نگه دارید",
        "Send the backup as a document": "فایل پشتیبان را به‌صورت سند ارسال کنید", "Backup file is too large": "فایل پشتیبان بیش از حد بزرگ است",
        "Validating and restoring backup": "در حال بررسی و بازیابی پشتیبان", "Backup restored successfully": "پشتیبان با موفقیت بازیابی شد",
        "Backup restore canceled": "بازیابی پشتیبان لغو شد", "Restore failed": "بازیابی ناموفق بود", "Backup failed": "پشتیبان‌گیری ناموفق بود",
        "Successfully Reminded": "یادآوری موفق", "Failed To Remind": "یادآوری ناموفق", "Eligible Users For Reminder": "کاربران واجد شرایط یادآوری",
        "Users Without Telegram Links": "کاربران بدون اتصال تلگرام", "Failed Sends": "ارسال‌های ناموفق", "Successful Sends": "ارسال‌های موفق",
        "Days Remaining": "روز باقی مانده", "Expired Subscriptions": "اشتراک‌های منقضی‌شده", "Daily Backup": "پشتیبان روزانه",
        "Failed To Get Users List": "دریافت فهرست کاربران ناموفق بود", "Failed To Get Online Users List": "دریافت کاربران آنلاین ناموفق بود",
        "Failed To Get Server Stats": "دریافت وضعیت سرور ناموفق بود", "Server Unresponsive": "سرور پاسخ نمی‌دهد", "User Not Found": "کاربر پیدا نشد",
        "Bot Is Not Activated For You": "ربات برای شما فعال نشده است", "No subscription selected": "اشتراکی انتخاب نشده است",
        "You don't have access to this subscription": "به این اشتراک دسترسی ندارید", "Please send a payment screenshot/image": "لطفاً تصویر رسید پرداخت را ارسال کنید",
        "Failed to submit request to admin": "ارسال درخواست به مدیر ناموفق بود", "Please try again": "لطفاً دوباره تلاش کنید",
        "Renewal request cancelled": "درخواست تمدید لغو شد", "Renewal request approved": "درخواست تمدید تأیید شد", "Renewal request rejected": "درخواست تمدید رد شد",
        "Only admin Can Send Broadcasts": "فقط مدیر می‌تواند پیام همگانی ارسال کند", "Message Cannot Be Empty": "پیام نمی‌تواند خالی باشد",
        "Message Too Long": "پیام بیش از حد طولانی است", "Confirm Selection": "تأیید انتخاب", "Clear Selection": "پاک کردن انتخاب",
        "Add New Link": "افزودن اتصال جدید", "View Links": "مشاهده اتصال‌ها", "Return To List": "بازگشت به فهرست",
        "Admin Only": "فقط مدیر", "Only admin": "فقط مدیر", "Unexpected error occurred": "خطای غیرمنتظره‌ای رخ داد",
        "Refresh": "بروزرسانی", "Update": "بروزرسانی", "Previous": "قبلی", "Next": "بعدی", "Back": "بازگشت",
        "Return": "بازگشت", "Abort": "لغو", "Cancel": "لغو", "Unlimited": "نامحدود", "Enable": "فعال", "Disable": "غیرفعال",
        "Username": "نام کاربری", "Description": "توضیحات", "Group": "گروه", "Expiry": "انقضا", "Volume": "حجم",
        "Status": "وضعیت", "Duration": "مدت", "Amount": "مبلغ", "User": "کاربر", "Error": "خطا", "Summary": "خلاصه",
        "Total Users": "کل کاربران", "Total Commands": "کل فرمان‌ها", "Total Errors": "کل خطاها", "Time Running": "مدت اجرا",
        "Choose an option": "یک گزینه را انتخاب کنید", "Yes": "بله", "No": "خیر", "Send": "ارسال",
    },
    "ru": {
        "Your receipt was sent to the administrator. Please wait for approval.": "Ваш чек отправлен администратору. Дождитесь подтверждения.",
        "SUI Bot Backup & Restore": "Резервная копия и восстановление SUI Bot", "Create & Send Backup": "Создать и отправить копию",
        "Restore Instructions": "Инструкция восстановления", "Back To Settings": "Назад к настройкам", "Create New User": "Создать пользователя",
        "Edit User": "Изменить пользователя", "Delete User": "Удалить пользователя", "All Clients": "Все клиенты", "All Users": "Все пользователи",
        "Online Users": "Пользователи онлайн", "Server Status": "Состояние сервера", "Bot Stats": "Статистика бота", "User Details": "Данные пользователей",
        "Inactive Users": "Неактивные пользователи", "Renewal Plans": "Планы продления", "Set Card Number": "Указать номер карты",
        "Set Card Holder": "Указать владельца карты", "Backup & Restore": "Резервная копия и восстановление", "Regenerate Secrets": "Создать новые секреты",
        "Keep Existing Secrets": "Сохранить текущие секреты", "Send Broadcast": "Отправить рассылку", "Specific Users": "Выбранные пользователи",
        "Check Inactive Users": "Проверить неактивных", "Subscription Links": "Ссылки подписки", "Renewal Request": "Запрос продления",
        "Renewal Payment": "Оплата продления", "My Subscription": "Моя подписка", "My Subscriptions": "Мои подписки", "Main Menu": "Главное меню",
        "Please Enter a Usename": "Введите имя пользователя", "Please Input The User's Client ID": "Введите ID клиента",
        "Use English Alphabet & Numbers Only": "Используйте только латинские буквы и цифры", "Username Not Available": "Имя недоступно",
        "Choose Another": "Выберите другое", "Input Description": "Введите описание", "Type a group name": "Введите название группы",
        "Type a new group name": "Введите новое название группы", "Input Expiry": "Введите срок", "Input Volume": "Введите объём",
        "Choose Active/Deactive State Of The User": "Выберите состояние пользователя", "Choose Secrets Policy": "Выберите политику секретов",
        "Operation Aborted": "Операция отменена", "Creating User Aborted": "Создание пользователя отменено", "Editing User Aborted": "Изменение отменено",
        "User Created Successfully": "Пользователь создан", "User Successfully Edited": "Пользователь изменён", "User With This Client ID Not Found": "Клиент не найден",
        "Client ID Must Be a Positive Number": "ID клиента должен быть положительным", "Wrong Format": "Неверный формат", "Input Numbers Only": "Введите только цифры",
        "Volume Should Be a Positive Number": "Объём должен быть положительным", "Days Must Be a Positive Number": "Количество дней должно быть положительным",
        "Description Can't Be Empty": "Описание не может быть пустым", "Group cannot be empty": "Группа не может быть пустой", "Admin Settings": "Настройки администратора",
        "Price Per Month": "Цена за месяц", "Enabled Renewal Options": "Доступные варианты продления", "Card Number": "Номер карты", "Card Holder": "Владелец карты",
        "Backup sent to this chat": "Резервная копия отправлена в этот чат", "Keep it private": "Храните её в тайне", "Backup restored successfully": "Копия успешно восстановлена",
        "Restore failed": "Ошибка восстановления", "Backup failed": "Ошибка резервного копирования", "Expired Subscriptions": "Истёкшие подписки",
        "Server Unresponsive": "Сервер не отвечает", "User Not Found": "Пользователь не найден", "Bot Is Not Activated For You": "Бот для вас не активирован",
        "You don't have access to this subscription": "У вас нет доступа к этой подписке", "Please try again": "Повторите попытку",
        "Renewal request cancelled": "Запрос продления отменён", "Only admin Can Send Broadcasts": "Только администратор может делать рассылку",
        "Message Cannot Be Empty": "Сообщение не может быть пустым", "Confirm Selection": "Подтвердить выбор", "Clear Selection": "Очистить выбор",
        "Admin Only": "Только администратор", "Only admin": "Только администратор", "Refresh": "Обновить", "Update": "Обновить",
        "Previous": "Назад", "Next": "Далее", "Back": "Назад", "Return": "Вернуться", "Abort": "Отмена", "Cancel": "Отмена",
        "Unlimited": "Без ограничений", "Enable": "Включить", "Disable": "Отключить", "Username": "Имя", "Description": "Описание",
        "Group": "Группа", "Expiry": "Срок", "Volume": "Объём", "Status": "Состояние", "Duration": "Срок", "Amount": "Сумма",
        "User": "Пользователь", "Error": "Ошибка", "Summary": "Сводка", "Total Users": "Всего пользователей", "Choose an option": "Выберите действие",
    },
    "zh": {
        "Your receipt was sent to the administrator. Please wait for approval.": "您的收据已发送给管理员，请等待审核。",
        "SUI Bot Backup & Restore": "SUI Bot 备份与恢复", "Create & Send Backup": "创建并发送备份", "Restore Instructions": "恢复说明",
        "Back To Settings": "返回设置", "Create New User": "创建用户", "Edit User": "编辑用户", "Delete User": "删除用户",
        "All Clients": "所有客户端", "All Users": "所有用户", "Online Users": "在线用户", "Server Status": "服务器状态",
        "Bot Stats": "机器人统计", "User Details": "用户详情", "Inactive Users": "非活跃用户", "Renewal Plans": "续订方案",
        "Set Card Number": "设置卡号", "Set Card Holder": "设置持卡人", "Backup & Restore": "备份与恢复", "Regenerate Secrets": "重新生成密钥",
        "Keep Existing Secrets": "保留现有密钥", "Send Broadcast": "发送广播", "Specific Users": "指定用户", "Check Inactive Users": "检查非活跃用户",
        "Subscription Links": "订阅链接", "Renewal Request": "续订请求", "Renewal Payment": "续订付款", "My Subscription": "我的订阅",
        "My Subscriptions": "我的订阅", "Main Menu": "主菜单", "Please Enter a Usename": "请输入用户名", "Please Input The User's Client ID": "请输入客户端 ID",
        "Use English Alphabet & Numbers Only": "只能使用英文字母和数字", "Username Not Available": "用户名不可用", "Choose Another": "请选择其他用户名",
        "Input Description": "输入描述", "Type a group name": "输入分组名称", "Type a new group name": "输入新分组名称", "Input Expiry": "输入有效期",
        "Input Volume": "输入流量", "Choose Active/Deactive State Of The User": "选择用户启用状态", "Choose Secrets Policy": "选择密钥策略",
        "Operation Aborted": "操作已取消", "Creating User Aborted": "创建用户已取消", "Editing User Aborted": "编辑用户已取消",
        "User Created Successfully": "用户创建成功", "User Successfully Edited": "用户编辑成功", "User With This Client ID Not Found": "未找到该客户端",
        "Client ID Must Be a Positive Number": "客户端 ID 必须为正数", "Wrong Format": "格式错误", "Input Numbers Only": "只能输入数字",
        "Volume Should Be a Positive Number": "流量必须为正数", "Days Must Be a Positive Number": "天数必须为正数", "Description Can't Be Empty": "描述不能为空",
        "Group cannot be empty": "分组不能为空", "Admin Settings": "管理员设置", "Price Per Month": "每月价格", "Enabled Renewal Options": "可用续订方案",
        "Card Number": "卡号", "Card Holder": "持卡人", "Backup sent to this chat": "备份已发送到此聊天", "Keep it private": "请妥善保管",
        "Backup restored successfully": "备份恢复成功", "Restore failed": "恢复失败", "Backup failed": "备份失败", "Expired Subscriptions": "已过期订阅",
        "Server Unresponsive": "服务器无响应", "User Not Found": "未找到用户", "Bot Is Not Activated For You": "机器人尚未为您启用",
        "You don't have access to this subscription": "您无权访问此订阅", "Please try again": "请重试", "Renewal request cancelled": "续订请求已取消",
        "Only admin Can Send Broadcasts": "只有管理员可以发送广播", "Message Cannot Be Empty": "消息不能为空", "Confirm Selection": "确认选择",
        "Clear Selection": "清除选择", "Admin Only": "仅限管理员", "Only admin": "仅限管理员", "Refresh": "刷新", "Update": "刷新",
        "Previous": "上一页", "Next": "下一页", "Back": "返回", "Return": "返回", "Abort": "取消", "Cancel": "取消",
        "Unlimited": "无限制", "Enable": "启用", "Disable": "禁用", "Username": "用户名", "Description": "描述", "Group": "分组",
        "Expiry": "到期", "Volume": "流量", "Status": "状态", "Duration": "时长", "Amount": "金额", "User": "用户",
        "Error": "错误", "Summary": "摘要", "Total Users": "用户总数", "Choose an option": "请选择操作",
    },
}

SOURCE_ALIASES = {
    "✅ رسید شما برای ادمین ارسال شد.\nمنتظر تایید باشید.": "✅ Your receipt was sent to the administrator. Please wait for approval.",
    "لطفا مبلغ مشخص شده رو به شماره کارت بالا واریز کنید و تصویر رسید رو اینجا ارسال کنید.": "Please pay the displayed amount to the card above and send the receipt image here.",
    "بعد از ارسال رسید منتظر تایید ادمین باشید.": "After sending the receipt, please wait for administrator approval.",
}


def localize_outgoing_text(language: str, text: str | None) -> str | None:
    if not text or language == "en":
        return text
    result = text
    for source, english in SOURCE_ALIASES.items():
        result = result.replace(source, english)
    for source, translated in sorted(PHRASES.get(language, {}).items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(re.escape(source), translated, result, flags=re.IGNORECASE)
    return result


def localize_inline_markup(markup: Any, language: str, bot: Any) -> Any:
    if markup is None or language == "en" or not hasattr(markup, "inline_keyboard"):
        return markup
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    rows = []
    for row in markup.inline_keyboard:
        localized_row = []
        for button in row:
            data = button.to_dict()
            data["text"] = localize_outgoing_text(language, data.get("text"))
            localized_row.append(InlineKeyboardButton.de_json(data, bot))
        rows.append(localized_row)
    return InlineKeyboardMarkup(rows)
