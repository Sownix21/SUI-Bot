"""Durable public-sale catalogue and approval ledger (no payment automation)."""

from __future__ import annotations

import copy
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

OPEN_STATUSES = {"receipt", "pending", "approved", "creating"}
STATUSES = OPEN_STATUSES | {"fulfilled", "rejected", "cancelled"}
MAX_SALES_BYTES = 8 * 1024 * 1024


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict):
        raise ValueError("invalid plan")
    for key, limit in (("title", 64), ("group", 128), ("desc", 256), ("remark", 128)):
        value = plan.get(key, "")
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
            raise ValueError("invalid plan text")
    if not plan.get("title", "").strip():
        raise ValueError("missing plan title")
    for key, low, high in (("price", 1, 10**15), ("days", 1, 3650), ("volume", 0, 10**18), ("reset_days", 0, 3650)):
        if type(plan.get(key)) is not int or not low <= plan[key] <= high:
            raise ValueError("invalid plan number")
    if plan.get("currency") not in {"TOMAN", "USD", "CNY", "RUB"}:
        raise ValueError("invalid currency")
    if type(plan.get("delayed")) is not bool or type(plan.get("active")) is not bool:
        raise ValueError("invalid plan flag")
    # In S-UI, delayStart + autoReset delays the first RESET, not expiry.
    if plan["delayed"] and plan["reset_days"]:
        raise ValueError("delayed expiry and periodic reset cannot be combined")
    ids = plan.get("inbounds")
    if (
        not isinstance(ids, list)
        or len(ids) > 200
        or any(type(i) is not int or i <= 0 for i in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("invalid inbound preset")


def validate_sales(data: dict) -> None:
    if not isinstance(data, dict) or data.get("version") != 1 or type(data.get("enabled")) is not bool:
        raise ValueError("invalid sales state")
    if data.get("mode") not in {"manual", "automatic"}:
        raise ValueError("invalid fulfilment mode")
    plans, orders = data.get("plans"), data.get("orders")
    if not isinstance(plans, dict) or len(plans) > 24 or not isinstance(orders, dict) or len(orders) > 2000:
        raise ValueError("sales capacity exceeded")
    for key, plan in plans.items():
        if not isinstance(key, str) or len(key) != 16 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("invalid plan ID")
        validate_plan(plan)
    for key, order in orders.items():
        if not isinstance(key, str) or len(key) != 24 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("invalid order ID")
        if not isinstance(order, dict) or order.get("status") not in STATUSES:
            raise ValueError("invalid order status")
        if type(order.get("user_id")) is not int or order["user_id"] <= 0:
            raise ValueError("invalid buyer")
        if type(order.get("created")) is not int or order["created"] <= 0:
            raise ValueError("invalid order timestamp")
        if order.get("mode") not in {"manual", "automatic"}:
            raise ValueError("invalid order mode")
        validate_plan(order.get("plan"))
        if not isinstance(order.get("name"), str) or not order["name"] or len(order["name"]) > 64:
            raise ValueError("invalid account name")
        if order["status"] == "fulfilled" and (type(order.get("client_id")) is not int or order["client_id"] <= 0):
            raise ValueError("invalid fulfilled client")
        if "account" in order:
            validate_plan(order["account"])
            for field in ("days", "price", "currency", "volume", "delayed", "reset_days"):
                if order["account"][field] != order["plan"][field]:
                    raise ValueError("account differs from purchased plan")
        if "fingerprint" in order and (
            not isinstance(order["fingerprint"], str)
            or len(order["fingerprint"]) != 64
            or any(c not in "0123456789abcdef" for c in order["fingerprint"])
        ):
            raise ValueError("invalid account fingerprint")
        if "receipt" in order:
            receipt = order["receipt"]
            if (
                not isinstance(receipt, dict)
                or receipt.get("kind") not in {"photo", "document"}
                or not isinstance(receipt.get("file_id"), str)
                or not 1 <= len(receipt["file_id"]) <= 1024
            ):
                raise ValueError("invalid receipt")
        for field in ("card", "holder"):
            if field in order and (not isinstance(order[field], str) or len(order[field]) > 256):
                raise ValueError("invalid payment details")


class SalesStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.load()

    def load(self) -> None:
        data = {"version": 1, "enabled": False, "mode": "manual", "plans": {}, "orders": {}}
        if self.path.exists():
            if self.path.stat().st_size > MAX_SALES_BYTES:
                raise ValueError("sales file exceeds safety limit")
            data = json.loads(self.path.read_text(encoding="utf-8"))
        validate_sales(data)
        self.data = data

    def commit(self, data: dict) -> None:
        validate_sales(data)
        encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        if len(encoded) > MAX_SALES_BYTES:
            raise ValueError("sales file exceeds safety limit")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".sales-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        self.data = copy.deepcopy(data)

    def configure(self, **values) -> None:
        data = copy.deepcopy(self.data)
        data.update(values)
        self.commit(data)

    def save_plan(self, plan: dict, plan_id: str | None = None) -> str:
        validate_plan(plan)
        data = copy.deepcopy(self.data)
        plan_id = plan_id or secrets.token_hex(8)
        data["plans"][plan_id] = copy.deepcopy(plan)
        self.commit(data)
        return plan_id

    def open_order(self, user_id: int) -> tuple[str, dict] | None:
        for key, order in self.data["orders"].items():
            if order["user_id"] == user_id and order["status"] in OPEN_STATUSES:
                return key, copy.deepcopy(order)
        return None

    def checkout(self, user_id: int, plan_id: str) -> tuple[str, dict]:
        if not self.data["enabled"]:
            raise ValueError("sales disabled")
        existing = self.open_order(user_id)
        if existing:
            return existing
        plan = self.data["plans"].get(plan_id)
        if not plan or not plan["active"]:
            raise ValueError("plan unavailable")
        if self.data["mode"] == "automatic" and not plan["inbounds"]:
            raise ValueError("missing inbound preset")
        now = int(time.time())
        data = copy.deepcopy(self.data)
        data["orders"] = {
            k: v for k, v in data["orders"].items() if v["status"] in OPEN_STATUSES or now - v["created"] < 90 * 86400
        }
        key = secrets.token_hex(12)
        order = {
            "user_id": user_id,
            "plan": copy.deepcopy(plan),
            "mode": data["mode"],
            "status": "receipt",
            "created": now,
            "name": "sale_" + key,
            "notified": False,
        }
        data["orders"][key] = order
        self.commit(data)
        return key, copy.deepcopy(order)

    def update_order(self, key: str, expected: set[str], **values) -> dict:
        data = copy.deepcopy(self.data)
        order = data["orders"].get(key)
        if not order or order["status"] not in expected:
            raise ValueError("order has changed")
        order.update(values)
        self.commit(data)
        return copy.deepcopy(order)
