from sui_bot.outgoing_localization import copyable_ltr_code, ltr_isolate, localize_outgoing_text, preserve_dynamic_text


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


def test_complete_server_status_output_remains_plain_english():
    status = "💻 SERVER STATUS\nHostname: Server Status\nStatus: Running\nServer response: Back"
    assert localize_outgoing_text("fa", preserve_dynamic_text(status)) == status


def test_bot_commands_are_never_translated_but_surrounding_guidance_is():
    source = "Cancel: /cancel\nReturn with /start or /restore@SuiBot\nhttps://example.com/cancel"
    for language in ("fa", "ru", "zh"):
        localized = localize_outgoing_text(language, source)
        assert "/cancel" in localized
        assert "/start" in localized
        assert "/restore@SuiBot" in localized
        assert "https://example.com/cancel" in localized
        assert "/لغو" not in localized


def test_owner_brand_replaces_fixed_brand_but_not_server_values():
    source = f"Welcome to SUI Bot\nServer: {preserve_dynamic_text('SUI Bot')}"
    assert localize_outgoing_text("en", source, display_name="Owner VPN") == (
        "Welcome to Owner VPN\nServer: SUI Bot"
    )
    assert "Owner VPN" in localize_outgoing_text("fa", "SUI Bot Backup & Restore", display_name="Owner VPN")


def test_ltr_isolate_keeps_card_number_copy_value_unchanged():
    isolated = ltr_isolate("1234-5678-9012-3456")
    assert isolated == "\u20661234-5678-9012-3456\u2069"
    assert isolated.strip("\u2066\u2069") == "1234-5678-9012-3456"
    copyable = copyable_ltr_code("1234-5678")
    assert copyable == "\u200e<code>1234-5678</code>\u200e"
    assert copyable.removeprefix("\u200e<code>").removesuffix("</code>\u200e") == "1234-5678"
