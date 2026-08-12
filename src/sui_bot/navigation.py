"""Pure navigation decisions shared by Telegram menu handlers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def assignment_count(assignments: Mapping[int, Sequence[int] | int], user_id: int) -> int:
    assigned = assignments.get(user_id, [])
    if isinstance(assigned, Sequence) and not isinstance(assigned, (str, bytes)):
        return len(assigned)
    return 1 if isinstance(assigned, int) else 0


def has_multiple_subscriptions(assignments: Mapping[int, Sequence[int] | int], user_id: int) -> bool:
    return assignment_count(assignments, user_id) > 1
