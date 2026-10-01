"""Fixed required-membership prompts in all supported bot languages."""

MESSAGES = {
    "title": (
        "📢 Required channels / groups",
        "📢 کانال‌ها و گروه‌های اجباری",
        "📢 Обязательные каналы / группы",
        "📢 必须加入的频道／群组",
    ),
    "on": ("Enabled", "فعال", "Включено", "已启用"),
    "off": ("Disabled", "غیرفعال", "Выключено", "已禁用"),
    "enable": (
        "✅ Enable required membership",
        "✅ فعال‌سازی عضویت اجباری",
        "✅ Включить обязательное вступление",
        "✅ 启用强制加入",
    ),
    "disable": (
        "❌ Disable required membership",
        "❌ غیرفعال‌سازی عضویت اجباری",
        "❌ Отключить обязательное вступление",
        "❌ 禁用强制加入",
    ),
    "add": (
        "➕ Add / update a channel or group",
        "➕ افزودن یا به‌روزرسانی کانال یا گروه",
        "➕ Добавить / обновить канал или группу",
        "➕ 添加／更新频道或群组",
    ),
    "back": ("🔙 Administration", "🔙 مدیریت", "🔙 Администрирование", "🔙 管理"),
    "admin_help": (
        "📢 Required membership: {status}\nConfigured chats: {count}/8\n\nUsers must join every configured chat before using commands, buttons, purchases, or renewals. Existing users are checked too. Broadcasts and reminders continue normally; the bot administrator is exempt.\n\nMake this bot an administrator in each chat first. Add its @username or numeric chat ID; for private chats, provide a working invite link. Adding the same chat again updates its title/link. Changes apply immediately when enabled. Tap 🗑 to remove a requirement.",
        "📢 عضویت اجباری: {status}\nتعداد کانال‌ها و گروه‌ها: {count} از ۸\n\nکاربران برای استفاده از دستورها، دکمه‌ها، خرید و تمدید باید عضو همه موارد باشند. کاربران قدیمی نیز بررسی می‌شوند. پیام‌های همگانی و یادآوری‌ها همچنان ارسال می‌شوند و مدیر ربات از این شرط معاف است.\n\nابتدا ربات را در هر کانال یا گروه مدیر کنید. سپس نام کاربری با @ یا شناسه عددی آن را وارد کنید؛ برای موارد خصوصی، لینک دعوت معتبر لازم است. افزودن دوباره همان مورد، نام و لینک آن را به‌روزرسانی می‌کند. در حالت فعال، تغییرات فوراً اعمال می‌شوند. برای حذف شرط عضویت روی 🗑 بزنید.",
        "📢 Обязательное вступление: {status}\nЧатов: {count}/8\n\nВсе пользователи, включая прежних, должны вступить во все указанные чаты для команд, кнопок, покупок и продления. Рассылки и напоминания продолжаются; администратор бота освобождён от проверки.\n\nСначала назначьте бота администратором каждого чата. Добавьте @имя или числовой ID; для закрытого чата укажите действующую ссылку-приглашение. Повторное добавление обновит название/ссылку. При включённой функции изменения действуют сразу. Нажмите 🗑 для удаления требования.",
        "📢 强制加入：{status}\n已配置：{count}/8\n\n包括老用户在内，所有用户都必须加入全部指定频道／群组后，才能使用命令、按钮、购买和续订。广播和提醒仍照常发送；机器人管理员不受限制。\n\n请先将机器人设为每个频道／群组的管理员，再添加 @用户名或数字聊天 ID。私密聊天需提供有效邀请链接。再次添加同一聊天可更新名称／链接。启用后修改立即生效。点击 🗑 删除要求。",
    ),
    "enter_chat": (
        "Send the channel/group @username or numeric chat ID (for example, -1001234567890). The bot must already be an administrator there.\n\n/cancel",
        "نام کاربری کانال یا گروه با @ یا شناسه عددی آن را بفرستید؛ مثلاً ‎-1001234567890. ربات باید از قبل در آنجا مدیر باشد.\n\n/cancel",
        "Отправьте @имя канала/группы или числовой ID (например, -1001234567890). Бот уже должен быть администратором этого чата.\n\n/cancel",
        "发送频道／群组的 @用户名或数字聊天 ID（例如 -1001234567890）。机器人必须已是该聊天的管理员。\n\n/cancel",
    ),
    "enter_link": (
        "This chat is private. Send its working https://t.me/+… or https://t.me/joinchat/… invite link. Make sure it leads to this exact chat. A pending join request does not count as membership.\n\n/cancel",
        "این کانال یا گروه خصوصی است. لینک دعوت معتبر آن را با قالب https://t.me/+… یا https://t.me/joinchat/… بفرستید. مطمئن شوید لینک متعلق به همین مورد است. درخواست عضویتِ در انتظار تأیید، به معنی عضویت نیست.\n\n/cancel",
        "Чат закрытый. Пришлите действующую ссылку https://t.me/+… или https://t.me/joinchat/… именно на этот чат. Заявка, ожидающая одобрения, ещё не считается вступлением.\n\n/cancel",
        "这是私密聊天。请发送对应的有效邀请链接 https://t.me/+… 或 https://t.me/joinchat/… 。确认链接指向此聊天。等待批准的入群申请不算已加入。\n\n/cancel",
    ),
    "saved": (
        "✅ Required chat saved.",
        "✅ کانال یا گروه اجباری ذخیره شد.",
        "✅ Обязательный чат сохранён.",
        "✅ 已保存必加聊天。",
    ),
    "invalid": (
        "Could not save this chat. Check its ID/link, the bot's administrator access, and the eight-chat limit; then try again or /cancel.",
        "ذخیره انجام نشد. شناسه یا لینک، دسترسی مدیریت ربات و سقف هشت مورد را بررسی کنید؛ سپس دوباره تلاش کنید یا /cancel بفرستید.",
        "Не удалось сохранить чат. Проверьте ID/ссылку, права администратора бота и лимит в восемь чатов. Повторите или отправьте /cancel.",
        "无法保存。请检查 ID／链接、机器人管理员权限以及八个聊天的数量上限，再重试或发送 /cancel。",
    ),
    "need_chat": (
        "Add at least one channel or group first.",
        "ابتدا حداقل یک کانال یا گروه اضافه کنید.",
        "Сначала добавьте хотя бы один канал или группу.",
        "请先添加至少一个频道或群组。",
    ),
    "bot_admin": (
        "The bot must be an administrator in that channel/group to reliably check membership. Add it as an administrator and try again.",
        "برای بررسی قابل‌اعتماد عضویت، ربات باید در آن کانال یا گروه مدیر باشد. ابتدا به ربات دسترسی مدیریت بدهید و دوباره تلاش کنید.",
        "Для надёжной проверки участников бот должен быть администратором канала/группы. Назначьте его администратором и повторите.",
        "为可靠检查成员资格，机器人必须是该频道／群组的管理员。请授予管理员权限后重试。",
    ),
    "join_required": (
        "📢 To use the bot, first join all channels/groups below. Then return here and tap “I joined”.\n\nYour subscriptions and assignments are kept. Broadcasts and reminders will still reach you, but subscription details, purchases, and renewals remain locked until membership is confirmed.",
        "📢 برای استفاده از ربات، ابتدا عضو همه کانال‌ها و گروه‌های زیر شوید. سپس به اینجا برگردید و «عضو شدم» را بزنید.\n\nاشتراک‌ها و تخصیص‌های شما حفظ می‌شوند. پیام‌های همگانی و یادآوری‌ها همچنان برایتان ارسال خواهند شد، اما مشاهده اطلاعات اشتراک، خرید و تمدید تا تأیید عضویت در دسترس نیست.",
        "📢 Для использования бота сначала вступите во все указанные каналы/группы, затем вернитесь и нажмите «Я вступил(а)».\n\nВаши подписки и привязки сохраняются. Рассылки и напоминания продолжатся, но данные подписок, покупки и продление будут недоступны до подтверждения вступления.",
        "📢 使用机器人前，请先加入下方所有频道／群组，然后返回并点击“我已加入”。\n\n您的订阅和绑定不会被删除。广播和提醒仍会发送，但订阅详情、购买和续订需验证成员资格后才能使用。",
    ),
    "joined": (
        "✅ I joined — check membership",
        "✅ عضو شدم — بررسی عضویت",
        "✅ Я вступил(а) — проверить",
        "✅ 我已加入 — 检查成员资格",
    ),
    "verify_failed": (
        "⚠️ Membership could not be verified. Please try again shortly. If the problem continues, contact the administrator; the bot may need its chat administrator permissions restored. Access stays locked until verification succeeds.",
        "⚠️ بررسی عضویت ممکن نشد. کمی بعد دوباره تلاش کنید. اگر مشکل ادامه داشت به مدیر اطلاع دهید؛ ممکن است دسترسی مدیریت ربات در کانال یا گروه نیاز به اصلاح داشته باشد. تا بررسی موفق، دسترسی بسته می‌ماند.",
        "⚠️ Не удалось проверить вступление. Попробуйте чуть позже. Если проблема остаётся, обратитесь к администратору: возможно, нужно восстановить права бота в чате. До успешной проверки доступ закрыт.",
        "⚠️ 无法验证成员资格。请稍后重试。如果问题持续，请联系管理员，机器人可能需要恢复聊天管理员权限。验证成功前访问仍受限。",
    ),
    "unlocked": (
        "✅ Access is available. Choose an option below. Please resend any message or receipt submitted while access was locked.",
        "✅ دسترسی برقرار است. یکی از گزینه‌های زیر را انتخاب کنید. پیام یا رسیدی را که هنگام بسته‌بودن دسترسی فرستاده بودید، دوباره ارسال کنید.",
        "✅ Доступ открыт. Выберите действие ниже. Повторно отправьте сообщения или квитанции, отправленные при заблокированном доступе.",
        "✅ 现已可以使用。请选择下方选项。请重新发送访问受限期间提交的消息或凭证。",
    ),
    "slow": (
        "Please wait a moment before checking again.",
        "لطفاً کمی صبر کنید و دوباره بررسی کنید.",
        "Подождите немного перед повторной проверкой.",
        "请稍等片刻再检查。",
    ),
    "private": (
        "Open the bot's private chat to manage required membership.",
        "برای مدیریت عضویت اجباری، وارد گفت‌وگوی خصوصی ربات شوید.",
        "Для настройки откройте личный чат с ботом.",
        "请在与机器人的私聊中管理加入要求。",
    ),
}


def membership_text(language: str, key: str, **values) -> str:
    languages = ("en", "fa", "ru", "zh")
    return MESSAGES[key][languages.index(language) if language in languages else 0].format(**values)
