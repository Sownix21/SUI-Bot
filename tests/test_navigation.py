from sui_bot.navigation import assignment_count, has_multiple_subscriptions


def test_subscription_selector_is_only_shown_for_multiple_assignments():
    assignments = {10: [101], 20: [201, 202], 30: 301}

    assert assignment_count(assignments, 10) == 1
    assert assignment_count(assignments, 30) == 1
    assert not has_multiple_subscriptions(assignments, 10)
    assert not has_multiple_subscriptions(assignments, 30)
    assert has_multiple_subscriptions(assignments, 20)
    assert not has_multiple_subscriptions(assignments, 99)
