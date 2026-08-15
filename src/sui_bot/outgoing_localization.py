"""Last-mile localization for every Telegram-facing message and button."""

from __future__ import annotations

import base64
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

# Longer workflow fragments complete the create/edit/delete, settings,
# broadcast, backup, and diagnostic screens without touching interpolated
# server values such as names, descriptions, IDs, and URLs.
ADDITIONAL_PHRASES = {
    "fa": {
        "All Inbounds": "همه ورودی‌ها", "Confirm Selection": "تأیید انتخاب", "Updating SUB Link & Inbounds": "در حال بروزرسانی لینک اشتراک و ورودی‌ها",
        "Reset Plans": "بازنشانی طرح‌ها", "backup created": "پشتیبان ساخته شد", "The file will be validated before any state is replaced": "پیش از جایگزینی اطلاعات، فایل اعتبارسنجی می‌شود",
        "Send the backup as a document, or use": "فایل پشتیبان را به‌صورت سند بفرستید یا استفاده کنید از", "Validating and restoring backup": "در حال اعتبارسنجی و بازیابی پشتیبان",
        "You can send digits with or without dashes": "می‌توانید ارقام را با یا بدون خط تیره بفرستید", "Invalid card number": "شماره کارت نامعتبر است",
        "Card number updated to": "شماره کارت بروزرسانی شد به", "Holder name too long": "نام صاحب کارت بیش از حد طولانی است",
        "IDs Must Be a Positive Number": "شناسه‌ها باید عدد مثبت باشند", "Use Integer Numbers": "فقط عدد صحیح وارد کنید", "Total subscriptions": "تعداد کل اشتراک‌ها",
        "already assigned to Telegram ID": "از قبل به شناسه تلگرام متصل است", "No links for Telegram ID": "اتصالی برای شناسه تلگرام وجود ندارد",
        "Username Must Be At Least": "حداقل طول نام کاربری", "Username Must Be At Most": "حداکثر طول نام کاربری", "Characters": "نویسه",
        "Choose Inbounds": "ورودی‌ها را انتخاب کنید", "Select Inbounds": "انتخاب ورودی‌ها", "You Can Choose Multiple Options": "می‌توانید چند گزینه انتخاب کنید",
        "Must At Least Select 1 Inbound": "حداقل یک ورودی انتخاب کنید", "Choose At Least 1 Inbound": "حداقل یک ورودی انتخاب کنید",
        "Selected Inbounds": "ورودی‌های انتخاب‌شده", "Item Selected": "مورد انتخاب شده", "Days Format": "قالب روز", "Example": "مثال",
        "Or Choose Unlimited": "یا نامحدود را انتخاب کنید", "Description Must Be At Most": "حداکثر طول توضیحات", "Maximum": "حداکثر",
        "Group must be at most": "حداکثر طول گروه", "Failed To Create User": "ساخت کاربر ناموفق بود", "Try Again": "دوباره تلاش کنید",
        "Input New Username": "نام کاربری جدید را وارد کنید", "To Keep Current Name Input": "برای حفظ نام فعلی وارد کنید",
        "New Name Registered": "نام جدید ثبت شد", "Input New Volume": "حجم جدید را وارد کنید", "To Keep Current Volume Input": "برای حفظ حجم فعلی وارد کنید",
        "Input New Expiry": "اعتبار جدید را وارد کنید", "To Keep Current Expiry Input": "برای حفظ اعتبار فعلی وارد کنید",
        "Input New Description": "توضیحات جدید را وارد کنید", "To Keep Current Description Input": "برای حفظ توضیحات فعلی وارد کنید",
        "Last Change": "آخرین تغییر", "Unchanged": "بدون تغییر", "Current": "فعلی", "Default": "پیش‌فرض", "send '.' to keep it": "برای حفظ مقدار فعلی «.» بفرستید",
        "Regenerate creates new passwords": "بازسازی، گذرواژه‌های جدید می‌سازد", "Keep Existing preserves current config credentials": "حفظ اطلاعات فعلی، اعتبارنامه‌های موجود را نگه می‌دارد",
        "This Action Can't Be Undone": "این عملیات قابل بازگشت نیست", "Are You Sure You Want To Delete User": "آیا از حذف کاربر مطمئن هستید",
        "Successfully Deleted": "با موفقیت حذف شد", "Auto-unlinked from": "اتصال خودکار حذف شد از", "Invalid action": "عملیات نامعتبر است", "Invalid language": "زبان نامعتبر است",
        "Create one validated file containing assignments": "یک فایل معتبر شامل اتصال‌ها ایجاد کنید", "Live bot and S-UI tokens are intentionally excluded": "توکن‌های زنده ربات و S-UI عمداً در فایل قرار نمی‌گیرند",
        "Renewal Plan Options": "گزینه‌های طرح تمدید", "Toggle months ON/OFF": "ماه‌ها را فعال یا غیرفعال کنید", "At least one plan must stay enabled": "حداقل یک طرح باید فعال بماند",
        "Invalid option": "گزینه نامعتبر است", "Invalid duration": "مدت نامعتبر است", "Request not found or already handled": "درخواست پیدا نشد یا قبلاً بررسی شده است",
        "Client not found on server": "کاربر در سرور پیدا نشد", "Renewal approved by admin": "تمدید توسط مدیر تأیید شد", "Renewal Approved": "تمدید تأیید شد",
        "Renewal Rejected": "تمدید رد شد", "If needed, contact admin for details": "در صورت نیاز برای جزئیات با مدیر تماس بگیرید",
        "Failed To Get Online Users List": "دریافت کاربران آنلاین ناموفق بود", "Failed To Get Server Stats": "دریافت وضعیت سرور ناموفق بود", "List Is Up To Date": "فهرست بروز است",
        "Please Input Your Message": "پیام خود را وارد کنید", "Which Group Do You Want To Send To": "پیام برای کدام گروه ارسال شود",
        "Choose At Least 1 User": "حداقل یک کاربر انتخاب کنید", "Selected Subscriptions": "اشتراک‌های انتخاب‌شده", "Are You Sure You Want To Send This Broadcast": "آیا از ارسال این پیام مطمئن هستید",
        "Sending Broadcast": "در حال ارسال پیام", "No. Of Receivers": "تعداد گیرندگان", "Please send a payment screenshot/image": "لطفاً تصویر رسید پرداخت را بفرستید",
        "Unexpected Error , Please Contact Admin": "خطای غیرمنتظره؛ با مدیر تماس بگیرید", "Add New Link": "افزودن اتصال جدید", "Continue To Send": "ادامه ارسال",
    },
    "ru": {
        "All Inbounds": "Все входящие подключения", "Confirm Selection": "Подтвердить выбор", "Updating SUB Link & Inbounds": "Обновление ссылки и входящих подключений",
        "Reset Plans": "Сбросить планы", "The file will be validated before any state is replaced": "Файл будет проверен до замены данных",
        "You can send digits with or without dashes": "Можно отправить цифры с дефисами или без них", "Invalid card number": "Неверный номер карты",
        "IDs Must Be a Positive Number": "ID должны быть положительными числами", "Use Integer Numbers": "Введите целые числа", "Total subscriptions": "Всего подписок",
        "Username Must Be At Least": "Минимальная длина имени", "Username Must Be At Most": "Максимальная длина имени", "Choose Inbounds": "Выберите входящие подключения",
        "Select Inbounds": "Выбор входящих подключений", "You Can Choose Multiple Options": "Можно выбрать несколько вариантов", "Must At Least Select 1 Inbound": "Выберите хотя бы одно подключение",
        "Choose At Least 1 Inbound": "Выберите хотя бы одно подключение", "Selected Inbounds": "Выбранные подключения", "Days Format": "Количество дней", "Example": "Пример",
        "Or Choose Unlimited": "или выберите без ограничений", "Failed To Create User": "Не удалось создать пользователя", "Try Again": "Повторите попытку",
        "Input New Username": "Введите новое имя", "To Keep Current Name Input": "Чтобы сохранить имя, введите", "Input New Volume": "Введите новый объём",
        "Input New Expiry": "Введите новый срок", "Input New Description": "Введите новое описание", "Last Change": "Последнее изменение", "Unchanged": "Без изменений",
        "Current": "Текущее", "Default": "По умолчанию", "This Action Can't Be Undone": "Это действие необратимо", "Are You Sure You Want To Delete User": "Удалить пользователя",
        "Successfully Deleted": "Успешно удалён", "Invalid action": "Недопустимое действие", "Invalid language": "Недопустимый язык",
        "Renewal Plan Options": "Варианты продления", "Toggle months ON/OFF": "Включайте или отключайте месяцы", "At least one plan must stay enabled": "Хотя бы один план должен быть включён",
        "Invalid option": "Недопустимый вариант", "Invalid duration": "Недопустимый срок", "Request not found or already handled": "Запрос не найден или уже обработан",
        "Client not found on server": "Клиент не найден на сервере", "Renewal approved by admin": "Продление одобрено администратором", "Renewal Approved": "Продление одобрено",
        "Renewal Rejected": "Продление отклонено", "If needed, contact admin for details": "При необходимости обратитесь к администратору",
        "Please Input Your Message": "Введите сообщение", "Which Group Do You Want To Send To": "Какой группе отправить сообщение", "Choose At Least 1 User": "Выберите хотя бы одного пользователя",
        "Selected Subscriptions": "Выбранные подписки", "Are You Sure You Want To Send This Broadcast": "Отправить эту рассылку", "Sending Broadcast": "Отправка рассылки",
        "No. Of Receivers": "Получателей", "Please send a payment screenshot/image": "Отправьте изображение чека", "Unexpected Error , Please Contact Admin": "Непредвиденная ошибка; обратитесь к администратору",
    },
    "zh": {
        "All Inbounds": "所有入站", "Confirm Selection": "确认选择", "Updating SUB Link & Inbounds": "正在更新订阅链接和入站", "Reset Plans": "重置方案",
        "The file will be validated before any state is replaced": "替换数据前将验证文件", "You can send digits with or without dashes": "可以发送带或不带短横线的数字", "Invalid card number": "卡号无效",
        "IDs Must Be a Positive Number": "ID 必须为正数", "Use Integer Numbers": "请输入整数", "Total subscriptions": "订阅总数", "Username Must Be At Least": "用户名最少长度",
        "Username Must Be At Most": "用户名最大长度", "Choose Inbounds": "选择入站", "Select Inbounds": "选择入站", "You Can Choose Multiple Options": "可以选择多个选项",
        "Must At Least Select 1 Inbound": "至少选择一个入站", "Choose At Least 1 Inbound": "至少选择一个入站", "Selected Inbounds": "已选入站", "Days Format": "天数格式", "Example": "示例",
        "Or Choose Unlimited": "或选择无限制", "Failed To Create User": "创建用户失败", "Try Again": "请重试", "Input New Username": "输入新用户名",
        "To Keep Current Name Input": "要保留当前名称请输入", "Input New Volume": "输入新流量", "Input New Expiry": "输入新有效期", "Input New Description": "输入新描述",
        "Last Change": "上次更改", "Unchanged": "未更改", "Current": "当前", "Default": "默认", "This Action Can't Be Undone": "此操作无法撤销",
        "Are You Sure You Want To Delete User": "确定删除用户吗", "Successfully Deleted": "删除成功", "Invalid action": "无效操作", "Invalid language": "无效语言",
        "Renewal Plan Options": "续订方案", "Toggle months ON/OFF": "开启或关闭月份", "At least one plan must stay enabled": "至少保留一个启用方案",
        "Invalid option": "无效选项", "Invalid duration": "无效时长", "Request not found or already handled": "请求不存在或已处理", "Client not found on server": "服务器上未找到客户端",
        "Renewal approved by admin": "管理员已批准续订", "Renewal Approved": "续订已批准", "Renewal Rejected": "续订已拒绝", "If needed, contact admin for details": "如需详情请联系管理员",
        "Please Input Your Message": "请输入消息", "Which Group Do You Want To Send To": "要发送到哪个组", "Choose At Least 1 User": "至少选择一名用户",
        "Selected Subscriptions": "已选订阅", "Are You Sure You Want To Send This Broadcast": "确定发送此广播吗", "Sending Broadcast": "正在发送广播", "No. Of Receivers": "接收者数量",
        "Please send a payment screenshot/image": "请发送付款截图", "Unexpected Error , Please Contact Admin": "发生意外错误，请联系管理员",
    },
}

for _language, _phrases in ADDITIONAL_PHRASES.items():
    PHRASES[_language].update(_phrases)

# Short fixed fragments used inside counters, validation details, pagination,
# and confirmation screens.  Word boundaries in localize_outgoing_text keep
# these from changing longer server-supplied names or URLs.
COMMON_UI_PHRASES = {
    "fa": {
        "Months": "ماه", "Month": "ماه", "Days": "روز", "Expired": "منقضی",
        "Characters": "نویسه", "Items Selected": "مورد انتخاب‌شده", "Item Selected": "مورد انتخاب‌شده",
        "No description": "بدون توضیحات", "Unknown": "نامشخص", "empty": "خالی", "Users": "کاربر",
        "No. Of Users": "تعداد کاربران", "Choose Users": "کاربران را انتخاب کنید", "Page": "صفحه",
        "Click On Each User To Select/Deselect": "برای انتخاب یا لغو انتخاب روی هر کاربر بزنید",
        "Broadcast Send Confirmation": "تأیید ارسال پیام همگانی", "Sending Broadcast Aborted": "ارسال پیام همگانی لغو شد",
        "Error In Receiving Broadcast Info": "دریافت اطلاعات پیام همگانی ناموفق بود",
        "Message Too Long": "پیام بیش از حد طولانی است", "Message": "پیام", "Receivers": "گیرندگان",
        "Type": "نوع", "All links for Telegram ID": "همه اتصال‌های شناسه تلگرام",
        "added to Telegram ID": "به شناسه تلگرام افزوده شد", "deleted": "حذف شد", "unlinked from Telegram ID": "از شناسه تلگرام جدا شد",
        "not assigned to this user": "به این کاربر متصل نیست", "Client ID Not Found": "شناسه کاربر پیدا نشد",
        "Deleting User": "در حال حذف کاربر", "No User Found": "کاربری پیدا نشد", "No User Registered": "کاربری ثبت نشده است",
        "To Check Inactive Users Click The Button Below": "برای بررسی کاربران غیرفعال دکمه زیر را بزنید",
        "Invalid renewal request state": "وضعیت درخواست تمدید نامعتبر است", "Please start again from subscription menu": "لطفاً دوباره از منوی اشتراک شروع کنید",
        "Maximum": "حداکثر", "GB Format": "قالب گیگابایت", "Input Only Numbers Or": "فقط عدد یا این مقدار را وارد کنید",
    },
    "ru": {
        "Months": "мес.", "Month": "мес.", "Days": "дн.", "Expired": "истекла",
        "Characters": "символов", "Items Selected": "выбрано", "Item Selected": "выбрано",
        "No description": "без описания", "Unknown": "неизвестно", "empty": "пусто", "Users": "пользователей",
        "No. Of Users": "Пользователей", "Choose Users": "Выберите пользователей", "Page": "Страница",
        "Click On Each User To Select/Deselect": "Нажмите пользователя, чтобы выбрать или снять выбор",
        "Broadcast Send Confirmation": "Подтверждение рассылки", "Sending Broadcast Aborted": "Рассылка отменена",
        "Error In Receiving Broadcast Info": "Не удалось получить данные рассылки", "Message Too Long": "Сообщение слишком длинное",
        "Message": "Сообщение", "Receivers": "Получатели", "Type": "Тип", "No User Found": "Пользователи не найдены",
        "No User Registered": "Нет зарегистрированных пользователей", "Deleting User": "Удаление пользователя",
        "To Check Inactive Users Click The Button Below": "Нажмите кнопку ниже, чтобы проверить неактивных пользователей",
        "Invalid renewal request state": "Недопустимое состояние запроса продления", "Please start again from subscription menu": "Начните снова из меню подписки",
        "Maximum": "Максимум", "GB Format": "Формат в ГБ", "Input Only Numbers Or": "Введите только цифры или",
    },
    "zh": {
        "Months": "个月", "Month": "个月", "Days": "天", "Expired": "已过期", "Characters": "个字符",
        "Items Selected": "项已选择", "Item Selected": "项已选择", "No description": "无描述", "Unknown": "未知",
        "empty": "空", "Users": "用户", "No. Of Users": "用户数", "Choose Users": "选择用户", "Page": "页",
        "Click On Each User To Select/Deselect": "点击用户以选择或取消选择", "Broadcast Send Confirmation": "广播发送确认",
        "Sending Broadcast Aborted": "广播发送已取消", "Error In Receiving Broadcast Info": "获取广播信息失败",
        "Message Too Long": "消息过长", "Message": "消息", "Receivers": "接收者", "Type": "类型",
        "No User Found": "未找到用户", "No User Registered": "没有已注册用户", "Deleting User": "正在删除用户",
        "To Check Inactive Users Click The Button Below": "点击下方按钮检查非活跃用户",
        "Invalid renewal request state": "续订请求状态无效", "Please start again from subscription menu": "请从订阅菜单重新开始",
        "Maximum": "最多", "GB Format": "GB 格式", "Input Only Numbers Or": "只能输入数字或",
    },
}

for _language, _phrases in COMMON_UI_PHRASES.items():
    PHRASES[_language].update(_phrases)

SOURCE_ALIASES = {
    "✅ رسید شما برای ادمین ارسال شد.\nمنتظر تایید باشید.": "✅ Your receipt was sent to the administrator. Please wait for approval.",
    "لطفا مبلغ مشخص شده رو به شماره کارت بالا واریز کنید و تصویر رسید رو اینجا ارسال کنید.": "Please pay the displayed amount to the card above and send the receipt image here.",
    "بعد از ارسال رسید منتظر تایید ادمین باشید.": "After sending the receipt, please wait for administrator approval.",
}

_DYNAMIC_VALUE_RE = re.compile(r"\ue100([A-Za-z0-9_-]+)\ue101")


def preserve_dynamic_text(value: Any) -> str:
    """Mark server/user content so the fixed-text translator cannot alter it."""
    encoded = base64.urlsafe_b64encode(str(value).encode("utf-8")).decode("ascii").rstrip("=")
    return f"\ue100{encoded}\ue101"


def _restore_dynamic_text(text: str) -> str:
    def decode(match: re.Match[str]) -> str:
        encoded = match.group(1)
        encoded += "=" * (-len(encoded) % 4)
        return base64.urlsafe_b64decode(encoded).decode("utf-8")

    return _DYNAMIC_VALUE_RE.sub(decode, text)


def localize_outgoing_text(language: str, text: str | None) -> str | None:
    if not text:
        return text
    result = text
    if language == "en":
        return _restore_dynamic_text(result)
    for source, english in SOURCE_ALIASES.items():
        result = result.replace(source, english)
    for source, translated in sorted(PHRASES.get(language, {}).items(), key=lambda item: len(item[0]), reverse=True):
        prefix = r"(?<![A-Za-z])" if source[:1].isalpha() else ""
        suffix = r"(?![A-Za-z])" if source[-1:].isalpha() else ""
        result = re.sub(prefix + re.escape(source) + suffix, translated, result, flags=re.IGNORECASE)
    return _restore_dynamic_text(result)


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
