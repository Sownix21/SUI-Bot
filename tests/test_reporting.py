from sui_bot.reporting import expiring_clients_with_assignments


def test_unlinked_expiring_clients_are_preserved() -> None:
    clients = [
        {"id": 1, "expiry": 100, "name": "linked"},
        {"id": 2, "expiry": 200, "name": "unlinked"},
        {"id": 3, "expiry": 0, "name": "unlimited"},
    ]
    linked, unlinked = expiring_clients_with_assignments(clients, {1: [42]})
    assert [(item["client_id"], item["tg_id"]) for item in linked] == [(1, 42)]
    assert [item["client_id"] for item in unlinked] == [2]


def test_unassigned_report_data_preserves_identity_fields() -> None:
    clients = [{"id": 7, "name": "alice", "desc": "Office", "expiry": 123, "enable": True}]
    linked, unlinked = expiring_clients_with_assignments(clients, {})
    assert linked == []
    assert unlinked == [{"client_id": 7, "name": "alice", "desc": "Office", "expiry": 123, "enable": True}]
