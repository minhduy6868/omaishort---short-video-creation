# Billing — trial, plans, credits

Canonical product numbers stay in [REQUIREMENTS.md](REQUIREMENTS.md). Accounts stay in [AUTH.md](AUTH.md). This file is the **entitlement and payment** contract. Code that disagrees with this file is a bug — unless the same PR updates both.

Why this shape (not Stripe Billing, not Clerk, not a SaaS meter clone):

| Constraint | Decision |
| --- | --- |
| Local-first FastAPI + Cloudflare D1 users | Plans, subscriptions, ledger, and payment orders live in the same DB as users. MP4s stay on disk. |
| Cost is per render, not per minute of UI | **1 credit = 1 HTTP job** (any `kind`). CLI jobs (`user_id` null) are not metered. |
| Trial before card | Register as `creator` → automatic `trial` subscription. No payment provider required for Phase 1. |
| VN cashflow first | Phase 2 checkout creates a **pending** bank-transfer order; operator marks `paid`. Gateway webhooks are later. |
| Planner stays vendor-free | Billing lives in API/`billing.py`/`db.py` only. Engine never imports billing. |

Do **not** fork Stripe Customer Portal, Lemon Squeezy, or Supabase into this tree.

---

## 1. Units

| Term | Rule |
| --- | --- |
| Credit | Integer. One successful `POST /jobs` holds **1** credit. |
| Hold | On create: `credits_remaining -= 1` and `credit_ledger` row `reason=job_hold`, `job_id` unique. |
| Refund | If the job ends `failed`: `credits_remaining += 1` and ledger `reason=job_refund` (idempotent if already refunded). |
| Done | Job `done` keeps the hold. No second ledger row. |
| Operator | `role=operator` bypasses credit checks. |
| CLI | `user_id` null — no hold, no refund. |

Race: credits are checked and held in one DB transaction before the job row is runnable. Two parallel creates with 1 credit left: one succeeds, one gets **402**.

---

## 2. Plans (seed)

| `code` | Name | Credits | Period | `price_vnd` (seed) | Who gets it |
| --- | --- | --- | --- | --- | --- |
| `trial` | Dùng thử | 3 | 14 days | 0 | Auto on `creator` register, **once per account** |
| `starter` | Starter | 20 | 30 days | 199000 | Checkout → admin `paid` |
| `pro` | Pro | 60 | 30 days | 499000 | Checkout → admin `paid` |

Operator may patch `credits`, `price_vnd`, `active` via admin. Do not delete `trial` from seed.

`features_json` is informational for UI (e.g. `{"kinds":["drama","news","knowledge"]}`). Kind gates by plan are **out of scope** for this contract version.

---

## 3. Subscriptions

| Column | Rule |
| --- | --- |
| `status` | `trial` \| `active` \| `expired` \| `canceled` |
| Current | Newest row for the user with `status in (trial, active)` and `ends_at` in the future (UTC). |
| Activate paid plan | Mark previous current as `expired`; insert new `active` with plan credits and period. |
| Trial once | If any historical subscription has `plan_code=trial`, do not create another trial. |

Expired or zero credits → `POST /jobs` returns **402** with billing snapshot (not 403).

---

## 4. Ledger reasons

| `reason` | `delta` | When |
| --- | --- | --- |
| `trial_grant` | +N | `ensure_trial` |
| `job_hold` | −1 | `POST /jobs` |
| `job_refund` | +1 | Job `failed` after a hold |
| `admin_grant` | +N | Operator grant |
| `plan_activate` | +N (set remaining to plan credits on new sub) | Order marked `paid` / activate |
| `expire` | 0 or note-only | Optional audit when marking expired |

`job_id` is unique when set (one hold per job).

---

## 5. Payment orders (manual transfer)

| Field | Rule |
| --- | --- |
| `status` | `pending` \| `paid` \| `rejected` \| `canceled` |
| Create | Authenticated creator `POST /billing/checkout` with `plan_code` in `{starter,pro}` and plan `active`. Amount = plan `price_vnd`. |
| Pay | Operator `PATCH /admin/billing/orders/{id}` → `paid` runs `activate_plan`. |
| Reject | Operator sets `rejected`; no credits. |
| One pending | At most one `pending` order per user; second checkout returns 409. |

Bank instructions for creators live in setting `billing_transfer_note` (default Vietnamese copy). No card capture in v1.

---

## 6. HTTP

### Creator

| Method | Path | Result |
| --- | --- | --- |
| GET | `/billing/plans` | Active sellable plans (`trial` may be listed with `price_vnd=0` for display). |
| GET | `/billing/me` | Entitlement + last 20 ledger rows. |
| POST | `/billing/checkout` | `{ plan_code }` → pending order. |

### Auth payload

`GET /auth/me` and login/register `user` include:

```json
"billing": {
  "plan_code": "trial",
  "status": "trial",
  "credits_remaining": 3,
  "credits_total": 3,
  "ends_at": "…"
}
```

or `billing: null` when none (operators without a sub).

### Admin

| Method | Path |
| --- | --- |
| GET | `/admin/billing/overview` |
| GET | `/admin/billing/orders?status=` |
| PATCH | `/admin/billing/orders/{id}` |
| POST | `/admin/billing/users/{id}/grant` |
| PATCH | `/admin/billing/plans/{code}` |

### 402

```json
{
  "detail": "credits exhausted",
  "billing": { "plan_code": "trial", "status": "trial", "credits_remaining": 0, "ends_at": "…" }
}
```

Use the same shape for expired trial (`detail`: `trial expired` or `subscription expired`).

---

## 7. Studio

- Shell / account: show trial or paid remaining credits.
- Account: plan table + checkout CTA + transfer note when an order is pending.
- Admin tab **Gói & đơn**: overview, grant, approve/reject orders, edit plan price/credits/active.
- Create job: surface 402 with link to Account (do not fail silently).

---

## 8. Out of scope

- SePay / VietQR / Stripe / PayPal webhooks
- Email invoices, VAT, refunds to bank
- Team seats, shared wallets
- Metering by video seconds or I2V-only SKUs
- Auto-renew without a new order

---

## 9. Acceptance

- Register creator → trial 3 credits, ~14 day `ends_at`.
- Operator / CLI create jobs without credit errors.
- Hold on create; refund on failed; second refund is no-op.
- Exhausted credits → 402; admin grant restores create.
- Checkout starter → pending; admin paid → active with 20 credits.
- Second trial for same user is not created.
- `pytest -q` includes billing tests; `npx tsc --noEmit` in `apps/web`.
