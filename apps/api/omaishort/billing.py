"""Trial, plans, credits, and manual payment orders.

See docs/BILLING.md. Planner/engine must not import this module.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from omaishort import db
from omaishort.auth import CurrentUser, OperatorUser

router = APIRouter()

SELLABLE_PLANS = frozenset({"starter", "pro"})
DEFAULT_TRANSFER_NOTE = (
    "Chuyển khoản đúng số tiền đơn hàng, nội dung: OMAI <mã đơn>. "
    "Admin sẽ duyệt trong vài giờ làm việc."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def entitlement_snapshot(sub: dict[str, Any] | None) -> dict[str, Any] | None:
    if not sub:
        return None
    return {
        "plan_code": sub.get("plan_code"),
        "status": sub.get("status"),
        "credits_remaining": int(sub.get("credits_remaining") or 0),
        "credits_total": int(sub.get("credits_total") or 0),
        "ends_at": sub.get("ends_at"),
    }


def entitlement(user_id: str) -> dict[str, Any] | None:
    return entitlement_snapshot(db.current_subscription(user_id))


def public_user_with_billing(user: dict[str, Any]) -> dict[str, Any]:
    return db.public_user(user, billing=entitlement(str(user["id"])))


def ensure_trial(user_id: str) -> dict[str, Any] | None:
    """Create a one-time trial subscription. Returns the sub or None if skipped."""
    if db.user_had_trial(user_id):
        return None
    plan = db.get_plan("trial")
    if not plan or not int(plan.get("active") or 0):
        # Seed should always create trial; re-seed if missing.
        db.init_db()
        plan = db.get_plan("trial")
    if not plan:
        return None
    credits = int(plan["credits"])
    days = int(plan["period_days"])
    starts = _now()
    ends = starts + timedelta(days=days)
    sub = db.create_subscription(
        secrets.token_hex(6),
        user_id,
        "trial",
        "trial",
        credits,
        credits,
        _iso(starts),
        _iso(ends),
    )
    db.add_ledger(
        secrets.token_hex(8),
        user_id,
        credits,
        "trial_grant",
        note="signup trial",
    )
    return sub


def _expire_current(user_id: str) -> None:
    sub = db.current_subscription(user_id)
    if sub:
        db.update_subscription(str(sub["id"]), status="expired")


def activate_plan(user_id: str, plan_code: str, note: str | None = None) -> dict[str, Any]:
    plan = db.get_plan(plan_code)
    if not plan:
        raise ValueError("plan not found")
    if plan_code == "trial":
        raise ValueError("cannot activate trial via purchase")
    credits = int(plan["credits"])
    days = int(plan["period_days"])
    _expire_current(user_id)
    starts = _now()
    ends = starts + timedelta(days=days)
    sub = db.create_subscription(
        secrets.token_hex(6),
        user_id,
        plan_code,
        "active",
        credits,
        credits,
        _iso(starts),
        _iso(ends),
    )
    db.add_ledger(
        secrets.token_hex(8),
        user_id,
        credits,
        "plan_activate",
        note=note or f"activate {plan_code}",
    )
    return sub


def admin_grant_credits(
    user_id: str,
    credits: int,
    note: str | None = None,
    extend_days: int | None = None,
) -> dict[str, Any]:
    if credits < 1 or credits > 1000:
        raise ValueError("credits must be 1..1000")
    return db.grant_credits_atomic(
        user_id,
        credits,
        secrets.token_hex(8),
        note=note,
        extend_days=extend_days,
    )


class CreditsExhausted(Exception):
    def __init__(self, detail: str, billing: dict[str, Any] | None):
        self.detail = detail
        self.billing = billing
        super().__init__(detail)


def assert_can_create_job(user: dict[str, Any]) -> None:
    if user.get("role") == "operator":
        return
    sub = db.current_subscription(str(user["id"]))
    snap = entitlement_snapshot(sub)
    if not sub:
        # Might be expired historical trial — surface last known if useful.
        hist = db.list_user_subscriptions(str(user["id"]))
        last = hist[0] if hist else None
        raise CreditsExhausted(
            "subscription expired" if last else "no subscription",
            entitlement_snapshot(last) if last else None,
        )
    if int(sub.get("credits_remaining") or 0) <= 0:
        raise CreditsExhausted("credits exhausted", snap)


def hold_job_credit(user: dict[str, Any], job_id: str) -> None:
    if user.get("role") == "operator":
        return
    try:
        db.hold_credit_atomic(str(user["id"]), job_id, secrets.token_hex(8))
    except ValueError as exc:
        msg = str(exc)
        snap = entitlement(str(user["id"]))
        if "exhausted" in msg:
            raise CreditsExhausted("credits exhausted", snap) from exc
        raise CreditsExhausted("subscription expired", snap) from exc


def refund_job_credit(user_id: str | None, job_id: str) -> None:
    if not user_id:
        return
    user = db.get_user_by_id(user_id)
    if user and user.get("role") == "operator":
        return
    db.refund_credit_atomic(user_id, job_id, secrets.token_hex(8))


def credits_exhausted_response(exc: CreditsExhausted) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={"detail": exc.detail, "billing": exc.billing},
    )


def transfer_note() -> str:
    return db.get_setting("billing_transfer_note") or DEFAULT_TRANSFER_NOTE


def public_plan(row: dict[str, Any]) -> dict[str, Any]:
    features = row.get("features_json")
    parsed: Any = None
    if isinstance(features, str) and features.strip():
        import json

        try:
            parsed = json.loads(features)
        except json.JSONDecodeError:
            parsed = None
    return {
        "code": row["code"],
        "name": row["name"],
        "credits": int(row["credits"]),
        "period_days": int(row["period_days"]),
        "price_vnd": int(row.get("price_vnd") or 0),
        "active": bool(int(row.get("active") or 0)),
        "features": parsed,
    }


@router.get("/billing/plans")
def list_billing_plans() -> dict[str, Any]:
    plans = [public_plan(p) for p in db.list_plans(active_only=True)]
    return {"plans": plans, "transfer_note": transfer_note()}


@router.get("/billing/me")
def billing_me(user: CurrentUser) -> dict[str, Any]:
    return {
        "billing": entitlement(str(user["id"])),
        "ledger": db.list_ledger(str(user["id"]), limit=20),
        "pending_order": db.pending_order_for_user(str(user["id"])),
        "transfer_note": transfer_note(),
    }


class CheckoutBody(BaseModel):
    plan_code: str = Field(min_length=2, max_length=32)


@router.post("/billing/checkout", status_code=201)
def billing_checkout(body: CheckoutBody, user: CurrentUser) -> dict[str, Any]:
    if user.get("role") == "operator":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "operator does not need a paid plan")
    code = body.plan_code.strip().lower()
    if code not in SELLABLE_PLANS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "plan_code must be starter or pro")
    plan = db.get_plan(code)
    if not plan or not int(plan.get("active") or 0):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    if db.pending_order_for_user(str(user["id"])):
        raise HTTPException(status.HTTP_409_CONFLICT, "pending order already exists")
    order = db.create_payment_order(
        secrets.token_hex(6),
        str(user["id"]),
        code,
        int(plan.get("price_vnd") or 0),
    )
    return {"order": order, "transfer_note": transfer_note()}


@router.get("/admin/billing/overview")
def admin_billing_overview(_admin: OperatorUser) -> dict[str, Any]:
    return {
        "stats": db.billing_overview_stats(),
        "plans": [public_plan(p) for p in db.list_plans()],
        "transfer_note": transfer_note(),
    }


@router.get("/admin/billing/orders")
def admin_list_orders(
    _admin: OperatorUser,
    order_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    orders = db.list_payment_orders(status=order_status, limit=limit)
    users = {str(u["id"]): u for u in db.list_users()}
    out = []
    for order in orders:
        uid = str(order.get("user_id") or "")
        owner = users.get(uid)
        item = dict(order)
        item["user_email"] = owner.get("email") if owner else None
        out.append(item)
    return {"orders": out}


class OrderPatchBody(BaseModel):
    status: str
    admin_note: str | None = Field(default=None, max_length=500)


@router.patch("/admin/billing/orders/{order_id}")
def admin_patch_order(order_id: str, body: OrderPatchBody, _admin: OperatorUser) -> dict[str, Any]:
    order = db.get_payment_order(order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    if order.get("status") != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "order is not pending")
    next_status = body.status.strip().lower()
    if next_status not in ("paid", "rejected"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "status must be paid or rejected")
    fields: dict[str, Any] = {"status": next_status, "admin_note": body.admin_note}
    if next_status == "paid":
        fields["paid_at"] = _iso(_now())
        try:
            activate_plan(str(order["user_id"]), str(order["plan_code"]), note=f"order {order_id}")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    updated = db.update_payment_order(order_id, **fields)
    return {"order": updated, "billing": entitlement(str(order["user_id"]))}


class GrantBody(BaseModel):
    credits: int = Field(ge=1, le=1000)
    note: str | None = Field(default=None, max_length=200)
    extend_days: int | None = Field(default=None, ge=1, le=365)


@router.post("/admin/billing/users/{user_id}/grant")
def admin_grant(user_id: str, body: GrantBody, _admin: OperatorUser) -> dict[str, Any]:
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    try:
        # Ensure there is something to grant onto (e.g. expired trial).
        if not db.list_user_subscriptions(user_id):
            ensure_trial(user_id)
        sub = admin_grant_credits(user_id, body.credits, note=body.note, extend_days=body.extend_days)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"subscription": sub, "billing": entitlement(user_id)}


class PlanPatchBody(BaseModel):
    credits: int | None = Field(default=None, ge=1, le=10000)
    price_vnd: int | None = Field(default=None, ge=0)
    active: bool | None = None
    period_days: int | None = Field(default=None, ge=1, le=365)
    name: str | None = Field(default=None, max_length=80)


@router.patch("/admin/billing/plans/{code}")
def admin_patch_plan(code: str, body: PlanPatchBody, _admin: OperatorUser) -> dict[str, Any]:
    plan = db.get_plan(code)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    updates: dict[str, Any] = {}
    if body.credits is not None:
        updates["credits"] = body.credits
    if body.price_vnd is not None:
        updates["price_vnd"] = body.price_vnd
    if body.active is not None:
        updates["active"] = 1 if body.active else 0
    if body.period_days is not None:
        updates["period_days"] = body.period_days
    if body.name is not None:
        updates["name"] = body.name.strip() or plan["name"]
    updated = db.update_plan(code, **updates)
    assert updated
    return {"plan": public_plan(updated)}
