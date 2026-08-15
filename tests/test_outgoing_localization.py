from sui_bot.outgoing_localization import localize_outgoing_text, preserve_dynamic_text


def test_admin_message_is_localized_without_changing_identifiers():
    text = "📝 Edit User\nClient ID: 42\nUsername: alice\n🔙 Back"
    localized = localize_outgoing_text("ru", text)
    assert "Изменить пользователя" in localized
    assert "Назад" in localized
    assert "42" in localized
    assert "alice" in localized


def test_user_error_and_legacy_persian_receipt_are_localized():
    assert "无权访问" in localize_outgoing_text("zh", "❌ You don't have access to this subscription.")
    localized = localize_outgoing_text("ru", "✅ رسید شما برای ادمین ارسال شد.\nمنتظر تایید باشید.")
    assert "administrator" not in localized.lower()


def test_english_output_is_unchanged():
    source = "⚙️ Admin Settings\n🏠 Main Menu"
    assert localize_outgoing_text("en", source) == source


def test_short_phrases_do_not_corrupt_larger_words_or_filenames():
    localized = localize_outgoing_text("fa", "Backup file: sui-backup.json\nNo notification")
    assert "بازگشتup" not in localized
    assert "خیرtification" not in localized
    assert "sui-backup.json" in localized


def test_server_values_are_preserved_even_when_they_match_fixed_ui_words():
    server_name = preserve_dynamic_text("Back")
    source = f"Username: {server_name}\nBack"

    assert localize_outgoing_text("fa", source) == "نام کاربری: Back\nبازگشت"
    assert localize_outgoing_text("en", server_name) == "Back"
