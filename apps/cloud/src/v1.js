/**
 * Public REST + JWT Cloud API (/v1/*) for omaishort desktop clients.
 *
 * Stores accounts, sessions, billing, job metadata, small attachments (<=600KB),
 * and reverse-engineered video blueprints in Cloudflare D1.
 * Video MP4 files and FFmpeg rendering always stay local on the user's machine.
 */
import {
  ACCESS_TTL_SEC,
  REFRESH_TTL_SEC,
  canonicalEmail,
  decodeAccess,
  encodeAccess,
  hashPassword,
  normalizeEmail,
  randomHex,
  randomToken,
  sha256Hex,
  validEmail,
  verifyPassword,
} from "./crypto.js";

const SITE_THEMES = ["brutal", "soft"];
const SELLABLE_PLANS = new Set(["starter", "pro"]);
const DEFAULT_TRANSFER_NOTE =
  "Chuyển khoản đúng số tiền đơn hàng, nội dung: OMAI <mã đơn>. Admin sẽ duyệt trong vài giờ làm việc.";
const DEFAULT_PLANS = [
  ["trial", "Dùng thử", 3, 14, 0, 1, JSON.stringify({ kinds: ["drama", "news", "knowledge"] })],
  ["starter", "Starter", 20, 30, 199000, 1, JSON.stringify({ kinds: ["drama", "news", "knowledge"] })],
  ["pro", "Pro", 60, 30, 499000, 1, JSON.stringify({ kinds: ["drama", "news", "knowledge"] })],
];

const _bootstrapped = new WeakSet();
let _dummyHash = null;

function dummyPasswordHash() {
  if (!_dummyHash) _dummyHash = hashPassword("omaishort-timing-pad-not-a-real-password");
  return _dummyHash;
}

function nowIso() {
  return new Date().toISOString();
}

function addDaysIso(days) {
  return new Date(Date.now() + Number(days) * 86400 * 1000).toISOString();
}

function addMinutesIso(mins) {
  return new Date(Date.now() + Number(mins) * 60 * 1000).toISOString();
}

function addSecondsIso(secs) {
  return new Date(Date.now() + Number(secs) * 1000).toISOString();
}

function jsonRes(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function errRes(status, detail, extra = {}) {
  return jsonRes({ detail, ...extra }, status);
}

async function readJson(request) {
  try {
    const data = await request.json();
    return data && typeof data === "object" ? data : {};
  } catch {
    return null;
  }
}

async function ensureBootstrap(env) {
  if (_bootstrapped.has(env.DB)) return;
  const ts = nowIso();
  // Ensure templates table exists on older D1 instances without breaking existing tables.
  await env.DB.prepare(
    `CREATE TABLE IF NOT EXISTS templates (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      name TEXT NOT NULL,
      source_filename TEXT NOT NULL,
      duration_sec REAL NOT NULL DEFAULT 0,
      pacing TEXT NOT NULL DEFAULT 'medium',
      blueprint_json TEXT NOT NULL,
      video_md TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )`
  ).run();
  await env.DB.prepare("CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id, created_at)").run();
  // Upgrade legacy idx_ledger_job_hold (job_id only) -> composite (job_id, reason) so hold & refund are both idempotent.
  await env.DB.prepare("DROP INDEX IF EXISTS idx_ledger_job_hold").run();
  await env.DB.prepare(
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_job_reason ON credit_ledger(job_id, reason) WHERE job_id IS NOT NULL"
  ).run();

  for (const [code, name, credits, days, price, active, features] of DEFAULT_PLANS) {
    await env.DB.prepare(
      `INSERT OR IGNORE INTO plans (code, name, credits, period_days, price_vnd, active, features_json, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(code, name, credits, days, price, active, features, ts)
      .run();
  }
  _bootstrapped.add(env.DB);
}

async function getSetting(env, key) {
  const row = await env.DB.prepare("SELECT value FROM settings WHERE key = ?").bind(key).first();
  return row ? String(row.value) : null;
}

async function setSetting(env, key, value) {
  await env.DB.prepare(
    `INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`
  )
    .bind(key, String(value), nowIso())
    .run();
}

async function siteThemeValue(env) {
  const val = await getSetting(env, "site_theme");
  return SITE_THEMES.includes(val) ? val : SITE_THEMES[0];
}

async function signupEnabled(env) {
  const val = await getSetting(env, "signup_enabled");
  if (val === null) return true;
  return !["0", "false", "no", "off"].includes(val.trim().toLowerCase());
}

async function transferNote(env) {
  return (await getSetting(env, "billing_transfer_note")) || DEFAULT_TRANSFER_NOTE;
}

function publicPlan(row) {
  let features = null;
  if (typeof row.features_json === "string" && row.features_json.trim()) {
    try {
      features = JSON.parse(row.features_json);
    } catch {
      features = null;
    }
  }
  return {
    code: row.code,
    name: row.name,
    credits: Number(row.credits),
    period_days: Number(row.period_days),
    price_vnd: Number(row.price_vnd || 0),
    active: Boolean(Number(row.active || 0)),
    features,
  };
}

function entitlementSnapshot(sub) {
  if (!sub) return null;
  return {
    plan_code: sub.plan_code,
    status: sub.status,
    credits_remaining: Number(sub.credits_remaining || 0),
    credits_total: Number(sub.credits_total || 0),
    ends_at: sub.ends_at,
  };
}

async function currentSubscription(env, userId) {
  const ts = nowIso();
  const row = await env.DB.prepare(
    `SELECT * FROM subscriptions
     WHERE user_id = ? AND status IN ('trial', 'active') AND ends_at > ?
     ORDER BY created_at DESC LIMIT 1`
  )
    .bind(userId, ts)
    .first();
  return row || null;
}

async function listUserSubscriptions(env, userId) {
  const res = await env.DB.prepare("SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC")
    .bind(userId)
    .all();
  return res.results || [];
}

async function ensureTrial(env, userId) {
  const had = await env.DB.prepare("SELECT 1 AS ok FROM subscriptions WHERE user_id = ? AND plan_code = 'trial' LIMIT 1")
    .bind(userId)
    .first();
  if (had) return null;
  const plan = await env.DB.prepare("SELECT * FROM plans WHERE code = 'trial'").first();
  if (!plan || !Number(plan.active || 0)) return null;
  const ts = nowIso();
  const ends = addDaysIso(plan.period_days);
  const subId = randomHex(6);
  await env.DB.prepare(
    `INSERT INTO subscriptions (id, user_id, plan_code, status, credits_remaining, credits_total, starts_at, ends_at, created_at, updated_at)
     VALUES (?, ?, 'trial', 'trial', ?, ?, ?, ?, ?, ?)`
  )
    .bind(subId, userId, Number(plan.credits), Number(plan.credits), ts, ends, ts, ts)
    .run();
  await env.DB.prepare(
    `INSERT INTO credit_ledger (id, user_id, job_id, delta, reason, note, created_at)
     VALUES (?, ?, NULL, ?, 'trial_grant', 'signup trial', ?)`
  )
    .bind(randomHex(8), userId, Number(plan.credits), ts)
    .run();
  return await env.DB.prepare("SELECT * FROM subscriptions WHERE id = ?").bind(subId).first();
}

async function activatePlan(env, userId, planCode, note = "") {
  const plan = await env.DB.prepare("SELECT * FROM plans WHERE code = ?").bind(planCode).first();
  if (!plan) throw new Error("plan not found");
  if (planCode === "trial") throw new Error("cannot activate trial via purchase");
  const cur = await currentSubscription(env, userId);
  const ts = nowIso();
  if (cur) {
    await env.DB.prepare("UPDATE subscriptions SET status = 'expired', updated_at = ? WHERE id = ?")
      .bind(ts, cur.id)
      .run();
  }
  const subId = randomHex(6);
  const ends = addDaysIso(plan.period_days);
  await env.DB.prepare(
    `INSERT INTO subscriptions (id, user_id, plan_code, status, credits_remaining, credits_total, starts_at, ends_at, created_at, updated_at)
     VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)`
  )
    .bind(subId, userId, planCode, Number(plan.credits), Number(plan.credits), ts, ends, ts, ts)
    .run();
  await env.DB.prepare(
    `INSERT INTO credit_ledger (id, user_id, job_id, delta, reason, note, created_at)
     VALUES (?, ?, NULL, ?, 'plan_activate', ?, ?)`
  )
    .bind(randomHex(8), userId, Number(plan.credits), note || `activate ${planCode}`, ts)
    .run();
  return await env.DB.prepare("SELECT * FROM subscriptions WHERE id = ?").bind(subId).first();
}

async function publicUserWithBilling(env, user) {
  const sub = await currentSubscription(env, String(user.id));
  return {
    id: String(user.id),
    email: user.email,
    display_name: user.display_name || null,
    role: user.role,
    billing: entitlementSnapshot(sub),
  };
}

async function issueSession(env, user, userAgent) {
  const refreshRaw = randomToken(32);
  const ts = nowIso();
  const expires = addSecondsIso(REFRESH_TTL_SEC);
  await env.DB.prepare(
    `INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, revoked_at, created_at, user_agent)
     VALUES (?, ?, ?, ?, NULL, ?, ?)`
  )
    .bind(randomHex(8), String(user.id), sha256Hex(refreshRaw), expires, ts, String(userAgent || "").slice(0, 200) || null)
    .run();
  const access = encodeAccess(user, env);
  return {
    user: await publicUserWithBilling(env, user),
    access_token: access,
    token_type: "bearer",
    expires_in: ACCESS_TTL_SEC,
    refresh_token: refreshRaw,
  };
}

async function findAccount(env, rawEmail) {
  const normalized = normalizeEmail(rawEmail);
  const wanted = canonicalEmail(normalized);
  const direct =
    (await env.DB.prepare("SELECT * FROM users WHERE email = ?").bind(normalized).first()) ||
    (await env.DB.prepare("SELECT * FROM users WHERE email = ?").bind(wanted).first());
  if (direct) return direct;
  if (!wanted.endsWith("@gmail.com")) return null;
  const all = await env.DB.prepare("SELECT * FROM users").all();
  for (const row of all.results || []) {
    if (canonicalEmail(row.email) === wanted) return row;
  }
  return null;
}

function isLocked(user) {
  if (!user || !user.locked_until) return false;
  return new Date(user.locked_until).getTime() > Date.now();
}

async function authenticateRequest(request, env) {
  const auth = request.headers.get("authorization") || "";
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.slice(7).trim();
  const payload = decodeAccess(token, env);
  if (!payload || !payload.sub) return null;
  const user = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(String(payload.sub)).first();
  if (!user || isLocked(user)) return null;
  return user;
}

function parseJsonSafe(raw) {
  if (!raw || typeof raw !== "string") return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function publicJob(row) {
  return {
    id: row.id,
    status: row.status,
    stage: row.stage,
    error: row.error || null,
    progress: row.progress || null,
    user_id: row.user_id || null,
    created_at: row.created_at,
    updated_at: row.updated_at,
    input: parseJsonSafe(row.input_json),
    bible: parseJsonSafe(row.bible_json),
    structure: parseJsonSafe(row.structure_json),
    storyboard: parseJsonSafe(row.storyboard_json),
    timeline: parseJsonSafe(row.timeline_json),
    artifacts: parseJsonSafe(row.artifacts_json) || {},
    storage: parseJsonSafe(row.storage_json) || {},
  };
}

function publicAttachment(row) {
  return {
    id: row.id,
    user_id: row.user_id,
    kind: row.kind,
    filename: row.filename,
    mime: row.mime,
    byte_size: Number(row.byte_size || 0),
    sha256: row.sha256,
    rel_path: row.rel_path,
    content_b64: row.content_b64 || null,
    created_at: row.created_at,
  };
}

export async function handleV1(request, env) {
  await ensureBootstrap(env);
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method.toUpperCase();

  if (method === "GET" && path === "/v1/health") {
    return jsonRes({ ok: true, service: "omaishort-cloud", version: "v1" });
  }

  if (method === "GET" && path === "/v1/site/theme") {
    return jsonRes({ theme: await siteThemeValue(env), themes: SITE_THEMES });
  }

  if (method === "GET" && path === "/v1/billing/plans") {
    const res = await env.DB.prepare("SELECT * FROM plans WHERE active = 1 ORDER BY price_vnd ASC").all();
    return jsonRes({
      plans: (res.results || []).map(publicPlan),
      transfer_note: await transferNote(env),
    });
  }

  // ---- Auth ----
  if (method === "POST" && path === "/v1/auth/register") {
    const body = await readJson(request);
    if (!body) return errRes(400, "invalid json");
    const email = canonicalEmail(body.email);
    const password = String(body.password || "");
    if (!validEmail(email)) return errRes(422, "invalid email");
    if (password.length < 8 || password.length > 128) return errRes(422, "password must be 8..128 chars");
    if (await findAccount(env, email)) {
      return errRes(409, "Email này đã có tài khoản. Hãy đăng nhập.");
    }
    const countRow = await env.DB.prepare("SELECT COUNT(*) AS n FROM users").first();
    const totalUsers = Number(countRow?.n || 0);
    let role = "creator";
    if (totalUsers === 0) {
      role = "operator";
    } else if (!(await signupEnabled(env))) {
      return errRes(403, "signup closed");
    }
    const displayName = String(body.display_name || "").trim().slice(0, 80) || email.split("@", 1)[0];
    const uid = randomHex(6);
    const ts = nowIso();
    try {
      await env.DB.prepare(
        `INSERT INTO users (id, email, password_hash, display_name, role, failed_logins, locked_until, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)`
      )
        .bind(uid, email, hashPassword(password), displayName, role, ts, ts)
        .run();
    } catch {
      return errRes(409, "Email này đã có tài khoản. Hãy đăng nhập.");
    }
    if (role === "creator") {
      await ensureTrial(env, uid);
    }
    const user = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(uid).first();
    const session = await issueSession(env, user, request.headers.get("user-agent"));
    return jsonRes(session, 201);
  }

  if (method === "POST" && path === "/v1/auth/login") {
    const body = await readJson(request);
    if (!body) return errRes(400, "invalid json");
    const email = normalizeEmail(body.email);
    const password = String(body.password || "");
    const user = validEmail(email) ? await findAccount(env, email) : null;
    if (!user) {
      verifyPassword(password, dummyPasswordHash());
      return errRes(401, "invalid email or password");
    }
    if (isLocked(user)) return errRes(429, "account locked");
    if (verifyPassword(password, user.password_hash)) {
      await env.DB.prepare("UPDATE users SET failed_logins = 0, locked_until = NULL, updated_at = ? WHERE id = ?")
        .bind(nowIso(), user.id)
        .run();
      const fresh = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(user.id).first();
      const session = await issueSession(env, fresh, request.headers.get("user-agent"));
      return jsonRes(session, 200);
    }
    const fails = Number(user.failed_logins || 0) + 1;
    const lockUntil = fails >= 8 ? addMinutesIso(15) : null;
    await env.DB.prepare("UPDATE users SET failed_logins = ?, locked_until = ?, updated_at = ? WHERE id = ?")
      .bind(fails, lockUntil, nowIso(), user.id)
      .run();
    if (lockUntil) return errRes(429, "account locked");
    return errRes(401, "invalid email or password");
  }

  if (method === "POST" && path === "/v1/auth/refresh") {
    const body = await readJson(request);
    const raw = String(body?.refresh_token || "").trim();
    if (!raw) return errRes(401, "not authenticated");
    const row = await env.DB.prepare("SELECT * FROM refresh_tokens WHERE token_hash = ?")
      .bind(sha256Hex(raw))
      .first();
    if (!row || row.revoked_at) return errRes(401, "not authenticated");
    if (new Date(row.expires_at).getTime() < Date.now()) {
      await env.DB.prepare("UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?").bind(nowIso(), row.id).run();
      return errRes(401, "not authenticated");
    }
    const user = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(row.user_id).first();
    if (!user || isLocked(user)) return errRes(401, "not authenticated");
    await env.DB.prepare("UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?").bind(nowIso(), row.id).run();
    const session = await issueSession(env, user, request.headers.get("user-agent"));
    return jsonRes(session, 200);
  }

  if (method === "POST" && path === "/v1/auth/logout") {
    const body = await readJson(request);
    const raw = String(body?.refresh_token || "").trim();
    if (raw) {
      await env.DB.prepare("UPDATE refresh_tokens SET revoked_at = ? WHERE token_hash = ?")
        .bind(nowIso(), sha256Hex(raw))
        .run();
    }
    return new Response(null, { status: 204 });
  }

  // ---- Authenticated routes below ----
  const user = await authenticateRequest(request, env);
  if (!user) return errRes(401, "not authenticated");
  const uid = String(user.id);
  const isOp = user.role === "operator";

  if (method === "GET" && path === "/v1/auth/me") {
    return jsonRes(await publicUserWithBilling(env, user));
  }

  if (method === "PUT" && path === "/v1/site/theme") {
    if (!isOp) return errRes(403, "Chỉ admin (operator) đổi được giao diện.");
    const body = await readJson(request);
    if (!body || !SITE_THEMES.includes(body.theme)) {
      return errRes(422, `theme must be one of ${SITE_THEMES.join(", ")}`);
    }
    await setSetting(env, "site_theme", body.theme);
    return jsonRes({ theme: body.theme, themes: SITE_THEMES });
  }

  // ---- Billing (User) ----
  if (method === "GET" && path === "/v1/billing/me") {
    const sub = await currentSubscription(env, uid);
    const ledger = await env.DB.prepare("SELECT * FROM credit_ledger WHERE user_id = ? ORDER BY created_at DESC LIMIT 20")
      .bind(uid)
      .all();
    const pending = await env.DB.prepare(
      "SELECT * FROM payment_orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1"
    )
      .bind(uid)
      .first();
    return jsonRes({
      billing: entitlementSnapshot(sub),
      ledger: ledger.results || [],
      pending_order: pending || null,
      transfer_note: await transferNote(env),
    });
  }

  if (method === "POST" && path === "/v1/billing/checkout") {
    if (isOp) return errRes(400, "operator does not need a paid plan");
    const body = await readJson(request);
    const code = String(body?.plan_code || "").trim().toLowerCase();
    if (!SELLABLE_PLANS.has(code)) return errRes(422, "plan_code must be starter or pro");
    const plan = await env.DB.prepare("SELECT * FROM plans WHERE code = ?").bind(code).first();
    if (!plan || !Number(plan.active || 0)) return errRes(404, "plan not found");
    const pending = await env.DB.prepare(
      "SELECT * FROM payment_orders WHERE user_id = ? AND status = 'pending' LIMIT 1"
    )
      .bind(uid)
      .first();
    if (pending) return errRes(409, "pending order already exists");
    const oid = randomHex(6);
    const ts = nowIso();
    await env.DB.prepare(
      `INSERT INTO payment_orders (id, user_id, plan_code, amount_vnd, status, created_at, updated_at, paid_at, admin_note)
       VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL, NULL)`
    )
      .bind(oid, uid, code, Number(plan.price_vnd || 0), ts, ts)
      .run();
    const order = await env.DB.prepare("SELECT * FROM payment_orders WHERE id = ?").bind(oid).first();
    return jsonRes({ order, transfer_note: await transferNote(env) }, 201);
  }

  if (method === "POST" && path === "/v1/billing/hold") {
    const body = await readJson(request);
    const jobId = String(body?.job_id || "").trim();
    if (!jobId) return errRes(422, "job_id required");
    if (isOp) return jsonRes({ ok: true, billing: null });
    const sub = await currentSubscription(env, uid);
    if (!sub) {
      const hist = await listUserSubscriptions(env, uid);
      return errRes(402, hist.length ? "subscription expired" : "no subscription", {
        billing: entitlementSnapshot(hist[0] || null),
      });
    }
    const ts = nowIso();
    const ledgerId = randomHex(8);
    // Reserve the unique (job_id, 'job_hold') ledger entry FIRST so concurrent retries never double-decrement.
    try {
      await env.DB.prepare(
        `INSERT INTO credit_ledger (id, user_id, job_id, delta, reason, note, created_at)
         VALUES (?, ?, ?, -1, 'job_hold', NULL, ?)`
      )
        .bind(ledgerId, uid, jobId, ts)
        .run();
    } catch {
      const fresh = await currentSubscription(env, uid);
      return jsonRes({ ok: true, billing: entitlementSnapshot(fresh) });
    }
    const upd = await env.DB.prepare(
      "UPDATE subscriptions SET credits_remaining = credits_remaining - 1, updated_at = ? WHERE id = ? AND credits_remaining > 0"
    )
      .bind(ts, sub.id)
      .run();
    if (!upd.meta || Number(upd.meta.changes || 0) === 0) {
      await env.DB.prepare("DELETE FROM credit_ledger WHERE id = ?").bind(ledgerId).run();
      const fresh = await currentSubscription(env, uid);
      return errRes(402, "credits exhausted", { billing: entitlementSnapshot(fresh) });
    }
    const fresh = await currentSubscription(env, uid);
    return jsonRes({ ok: true, billing: entitlementSnapshot(fresh) });
  }

  if (method === "POST" && path === "/v1/billing/refund") {
    const body = await readJson(request);
    const jobId = String(body?.job_id || "").trim();
    if (!jobId || isOp) return jsonRes({ ok: true });
    const held = await env.DB.prepare(
      "SELECT * FROM credit_ledger WHERE user_id = ? AND job_id = ? AND reason = 'job_hold' LIMIT 1"
    )
      .bind(uid, jobId)
      .first();
    if (!held) return jsonRes({ ok: true });
    const ts = nowIso();
    // Claim the unique (job_id, 'job_refund') row FIRST so concurrent refunds never double-credit.
    try {
      await env.DB.prepare(
        `INSERT INTO credit_ledger (id, user_id, job_id, delta, reason, note, created_at)
         VALUES (?, ?, ?, 1, 'job_refund', ?, ?)`
      )
        .bind(randomHex(8), uid, jobId, `refund:${jobId}`, ts)
        .run();
    } catch {
      return jsonRes({ ok: true });
    }
    const sub = await currentSubscription(env, uid);
    if (sub) {
      await env.DB.prepare("UPDATE subscriptions SET credits_remaining = credits_remaining + 1, updated_at = ? WHERE id = ?")
        .bind(ts, sub.id)
        .run();
    }
    return jsonRes({ ok: true });
  }

  // ---- Jobs (Metadata only — MP4 stays local) ----
  if (method === "GET" && path === "/v1/jobs") {
    const limit = Math.max(1, Math.min(50, Number(url.searchParams.get("limit") || 20)));
    const res = await env.DB.prepare("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?")
      .bind(uid, limit)
      .all();
    return jsonRes({ jobs: (res.results || []).map(publicJob) });
  }

  if (method === "POST" && path === "/v1/jobs") {
    const body = await readJson(request);
    if (!body || !body.id || !body.input_json) return errRes(422, "id and input_json required");
    const jobId = String(body.id);
    const existing = await env.DB.prepare("SELECT user_id FROM jobs WHERE id = ?").bind(jobId).first();
    if (existing && !isOp && String(existing.user_id || "") !== uid) {
      return errRes(409, "job id already exists");
    }
    const ts = nowIso();
    const inputStr = typeof body.input_json === "string" ? body.input_json : JSON.stringify(body.input_json);
    if (existing) {
      await env.DB.prepare(
        `UPDATE jobs SET status = ?, stage = ?, updated_at = ?, input_json = ?, progress = ? WHERE id = ?`
      )
        .bind(String(body.status || "queued"), String(body.stage || "queued"), ts, inputStr, String(body.progress || "queued"), jobId)
        .run();
    } else {
      await env.DB.prepare(
        `INSERT INTO jobs (id, status, stage, error, created_at, updated_at, input_json, progress, user_id)
         VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)`
      )
        .bind(jobId, String(body.status || "queued"), String(body.stage || "queued"), ts, ts, inputStr, String(body.progress || "queued"), uid)
        .run();
    }
    const row = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first();
    return jsonRes({ job: publicJob(row) }, 201);
  }

  const jobMatch = path.match(/^\/v1\/jobs\/([^/]+)$/);
  if (jobMatch) {
    const jobId = decodeURIComponent(jobMatch[1]);
    const row = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first();
    if (!row || (!isOp && String(row.user_id || "") !== uid)) return errRes(404, "job not found");

    if (method === "GET") {
      return jsonRes({ job: publicJob(row) });
    }
    if (method === "PATCH") {
      const body = await readJson(request);
      if (!body) return errRes(400, "invalid json");
      const allowed = [
        "status",
        "stage",
        "error",
        "progress",
        "input_json",
        "bible_json",
        "structure_json",
        "storyboard_json",
        "timeline_json",
        "artifacts_json",
        "storage_json",
      ];
      const sets = ["updated_at = ?"];
      const params = [nowIso()];
      for (const col of allowed) {
        if (col in body) {
          sets.push(`${col} = ?`);
          const val = body[col];
          params.push(val === null || val === undefined ? null : typeof val === "string" ? val : JSON.stringify(val));
        }
      }
      params.push(jobId);
      await env.DB.prepare(`UPDATE jobs SET ${sets.join(", ")} WHERE id = ?`).bind(...params).run();
      const fresh = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first();
      return jsonRes({ job: publicJob(fresh) });
    }
    if (method === "DELETE") {
      await env.DB.prepare("DELETE FROM jobs WHERE id = ?").bind(jobId).run();
      return new Response(null, { status: 204 });
    }
  }

  // ---- Attachments (metadata + small <=600KB content_b64) ----
  if (method === "GET" && path === "/v1/attachments") {
    const res = await env.DB.prepare("SELECT * FROM attachments WHERE user_id = ? ORDER BY created_at DESC")
      .bind(uid)
      .all();
    return jsonRes({ attachments: (res.results || []).map(publicAttachment) });
  }

  if (method === "POST" && path === "/v1/attachments") {
    const body = await readJson(request);
    if (!body || !body.id || !body.kind || !body.filename || !body.sha256) {
      return errRes(422, "missing attachment fields");
    }
    const existing = await env.DB.prepare(
      "SELECT * FROM attachments WHERE user_id = ? AND kind = ? AND sha256 = ? LIMIT 1"
    )
      .bind(uid, String(body.kind), String(body.sha256))
      .first();
    if (existing) return jsonRes({ attachment: publicAttachment(existing) }, 200);
    const b64 = typeof body.content_b64 === "string" && body.content_b64.length <= 900_000 ? body.content_b64 : null;
    const ts = nowIso();
    await env.DB.prepare(
      `INSERT INTO attachments (id, user_id, kind, filename, mime, byte_size, sha256, rel_path, content_b64, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(
        String(body.id),
        uid,
        String(body.kind),
        String(body.filename),
        String(body.mime || "application/octet-stream"),
        Number(body.byte_size || 0),
        String(body.sha256),
        String(body.rel_path || ""),
        b64,
        ts
      )
      .run();
    const row = await env.DB.prepare("SELECT * FROM attachments WHERE id = ?").bind(String(body.id)).first();
    return jsonRes({ attachment: publicAttachment(row) }, 201);
  }

  const attMatch = path.match(/^\/v1\/attachments\/([^/]+)$/);
  if (attMatch) {
    const attId = decodeURIComponent(attMatch[1]);
    const row = await env.DB.prepare("SELECT * FROM attachments WHERE id = ?").bind(attId).first();
    if (!row || (!isOp && String(row.user_id || "") !== uid)) return errRes(404, "attachment not found");
    if (method === "GET") return jsonRes({ attachment: publicAttachment(row) });
    if (method === "DELETE") {
      await env.DB.prepare("DELETE FROM attachments WHERE id = ?").bind(attId).run();
      return new Response(null, { status: 204 });
    }
  }

  // ---- Reverse-Engineered Video Templates (JSON + VIDEO.md only) ----
  if (method === "GET" && path === "/v1/templates") {
    const res = await env.DB.prepare("SELECT * FROM templates WHERE user_id = ? ORDER BY created_at DESC LIMIT 30")
      .bind(uid)
      .all();
    const templates = (res.results || [])
      .map((r) => parseJsonSafe(r.blueprint_json))
      .filter(Boolean);
    return jsonRes({ templates });
  }

  if (method === "POST" && path === "/v1/templates") {
    const body = await readJson(request);
    if (!body || !body.id || !body.name) return errRes(422, "invalid template blueprint");
    const tplId = String(body.id);
    const existing = await env.DB.prepare("SELECT user_id FROM templates WHERE id = ?").bind(tplId).first();
    if (existing && !isOp && String(existing.user_id || "") !== uid) {
      return errRes(409, "template id already exists");
    }
    const ts = nowIso();
    if (existing) {
      await env.DB.prepare(
        `UPDATE templates SET name = ?, source_filename = ?, duration_sec = ?, pacing = ?, blueprint_json = ?, video_md = ?, updated_at = ? WHERE id = ?`
      )
        .bind(
          String(body.name),
          String(body.source_filename || "reference.mp4"),
          Number(body.duration_sec || 0),
          String(body.pacing || "medium"),
          JSON.stringify(body),
          String(body.video_md || ""),
          ts,
          tplId
        )
        .run();
    } else {
      await env.DB.prepare(
        `INSERT INTO templates (id, user_id, name, source_filename, duration_sec, pacing, blueprint_json, video_md, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
        .bind(
          tplId,
          uid,
          String(body.name),
          String(body.source_filename || "reference.mp4"),
          Number(body.duration_sec || 0),
          String(body.pacing || "medium"),
          JSON.stringify(body),
          String(body.video_md || ""),
          String(body.created_at || ts),
          ts
        )
        .run();
    }
    return jsonRes({ template: body }, 201);
  }

  const tplMatch = path.match(/^\/v1\/templates\/([^/]+)$/);
  if (tplMatch) {
    const tplId = decodeURIComponent(tplMatch[1]);
    const row = await env.DB.prepare("SELECT * FROM templates WHERE id = ?").bind(tplId).first();
    if (!row || (!isOp && String(row.user_id || "") !== uid)) return errRes(404, "template not found");
    if (method === "GET") return jsonRes({ template: parseJsonSafe(row.blueprint_json) });
    if (method === "DELETE") {
      await env.DB.prepare("DELETE FROM templates WHERE id = ?").bind(tplId).run();
      return new Response(null, { status: 204 });
    }
  }

  // ---- Admin routes (operator only) ----
  if (path.startsWith("/v1/admin/")) {
    if (!isOp) return errRes(403, "Chỉ admin (operator) mới có quyền thực hiện thao tác này.");

    if (method === "GET" && path === "/v1/admin/overview") {
      const usersTotal = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM users").first())?.n || 0);
      const opsTotal = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'operator'").first())?.n || 0);
      const jobsTotal = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs").first())?.n || 0);
      const jobsQueued = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs WHERE status = 'queued'").first())?.n || 0);
      const jobsActive = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs WHERE status = 'running'").first())?.n || 0);
      const jobsPaused = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs WHERE status = 'paused'").first())?.n || 0);
      const jobsDone = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs WHERE status = 'done'").first())?.n || 0);
      const jobsFailed = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM jobs WHERE status = 'failed'").first())?.n || 0);
      const jobsRunning = jobsQueued + jobsActive;
      const attRow = await env.DB.prepare("SELECT COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS b FROM attachments").first();
      return jsonRes({
        stats: {
          db_backend: "cloudflare-d1",
          users_total: usersTotal,
          operators_total: opsTotal,
          jobs_total: jobsTotal,
          jobs_done: jobsDone,
          jobs_failed: jobsFailed,
          jobs_running: jobsRunning,
          jobs_by_status: {
            queued: jobsQueued,
            running: jobsActive,
            paused: jobsPaused,
            done: jobsDone,
            failed: jobsFailed,
          },
          attachments_total: Number(attRow?.n || 0),
          attachments_bytes: Number(attRow?.b || 0),
        },
        settings: {
          site_theme: await siteThemeValue(env),
          themes: SITE_THEMES,
          signup_enabled: await signupEnabled(env),
        },
      });
    }

    if (method === "PUT" && path === "/v1/admin/settings") {
      const body = await readJson(request);
      if (body?.site_theme !== undefined && body.site_theme !== null) {
        if (!SITE_THEMES.includes(body.site_theme)) return errRes(422, "invalid site_theme");
        await setSetting(env, "site_theme", body.site_theme);
      }
      if (body?.signup_enabled !== undefined && body.signup_enabled !== null) {
        await setSetting(env, "signup_enabled", body.signup_enabled ? "1" : "0");
      }
      return jsonRes({
        site_theme: await siteThemeValue(env),
        themes: SITE_THEMES,
        signup_enabled: await signupEnabled(env),
      });
    }

    if (method === "GET" && path === "/v1/admin/users") {
      const usersRes = await env.DB.prepare("SELECT * FROM users ORDER BY created_at DESC").all();
      const jobsRes = await env.DB.prepare("SELECT user_id, COUNT(*) AS n FROM jobs GROUP BY user_id").all();
      const attRes = await env.DB.prepare(
        "SELECT user_id, COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS b FROM attachments GROUP BY user_id"
      ).all();
      const jobMap = Object.fromEntries((jobsRes.results || []).map((r) => [String(r.user_id), Number(r.n || 0)]));
      const attMap = Object.fromEntries(
        (attRes.results || []).map((r) => [String(r.user_id), [Number(r.n || 0), Number(r.b || 0)]])
      );
      const out = [];
      for (const row of usersRes.results || []) {
        const id = String(row.id);
        const sub = await currentSubscription(env, id);
        const billing = entitlementSnapshot(sub);
        const locked = isLocked(row);
        const [ac, ab] = attMap[id] || [0, 0];
        out.push({
          id,
          email: row.email,
          display_name: row.display_name || null,
          role: row.role,
          locked,
          locked_until: locked ? row.locked_until : null,
          failed_logins: Number(row.failed_logins || 0),
          jobs_count: jobMap[id] || 0,
          attachments_count: ac,
          attachments_bytes: ab,
          billing,
          plan_code: billing ? billing.plan_code : null,
          credits_remaining: billing ? billing.credits_remaining : null,
          created_at: row.created_at,
          updated_at: row.updated_at,
        });
      }
      return jsonRes({ users: out });
    }

    const adminUserMatch = path.match(/^\/v1\/admin\/users\/([^/]+)$/);
    if (adminUserMatch && method === "PATCH") {
      const targetId = decodeURIComponent(adminUserMatch[1]);
      const target = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(targetId).first();
      if (!target) return errRes(404, "user not found");
      const body = await readJson(request);
      const sets = ["updated_at = ?"];
      const params = [nowIso()];
      if (body?.role !== undefined && body.role !== null) {
        if (!["operator", "creator"].includes(body.role)) return errRes(422, "role must be operator or creator");
        if (target.role === "operator" && body.role === "creator") {
          const ops = Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'operator'").first())?.n || 0);
          if (ops <= 1) return errRes(400, "Không thể hạ quyền admin (operator) cuối cùng.");
        }
        sets.push("role = ?");
        params.push(body.role);
      }
      if (body?.display_name !== undefined && body.display_name !== null) {
        sets.push("display_name = ?");
        params.push(String(body.display_name).trim() || String(target.email).split("@", 1)[0]);
      }
      if (body?.locked !== undefined && body.locked !== null) {
        if (body.locked) {
          if (targetId === uid) return errRes(400, "Không thể tự khóa tài khoản của chính mình.");
          sets.push("locked_until = ?", "failed_logins = ?");
          params.push(addDaysIso(365), 8);
          await env.DB.prepare("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ?").bind(nowIso(), targetId).run();
        } else {
          sets.push("locked_until = NULL", "failed_logins = 0");
        }
      }
      if (sets.length > 1) {
        params.push(targetId);
        await env.DB.prepare(`UPDATE users SET ${sets.join(", ")} WHERE id = ?`).bind(...params).run();
      }
      if (body?.revoke_sessions) {
        await env.DB.prepare("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ?").bind(nowIso(), targetId).run();
      }
      const fresh = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(targetId).first();
      const sub = await currentSubscription(env, targetId);
      const billing = entitlementSnapshot(sub);
      const locked = isLocked(fresh);
      return jsonRes({
        user: {
          id: String(fresh.id),
          email: fresh.email,
          display_name: fresh.display_name || null,
          role: fresh.role,
          locked,
          locked_until: locked ? fresh.locked_until : null,
          failed_logins: Number(fresh.failed_logins || 0),
          billing,
          plan_code: billing ? billing.plan_code : null,
          credits_remaining: billing ? billing.credits_remaining : null,
          created_at: fresh.created_at,
          updated_at: fresh.updated_at,
        },
      });
    }

    if (method === "GET" && path === "/v1/admin/jobs") {
      const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") || 50)));
      const statusFilter = url.searchParams.get("status");
      const userFilter = url.searchParams.get("user_id");
      const conds = [];
      const params = [];
      if (statusFilter) {
        conds.push("status = ?");
        params.push(statusFilter);
      }
      if (userFilter) {
        conds.push("user_id = ?");
        params.push(userFilter);
      }
      const where = conds.length ? `WHERE ${conds.join(" AND ")}` : "";
      params.push(limit);
      const res = await env.DB.prepare(`SELECT * FROM jobs ${where} ORDER BY created_at DESC LIMIT ?`).bind(...params).all();
      const usersRes = await env.DB.prepare("SELECT id, email FROM users").all();
      const emailMap = Object.fromEntries((usersRes.results || []).map((u) => [String(u.id), u.email]));
      const jobs = (res.results || []).map((r) => ({
        ...publicJob(r),
        user_email: r.user_id ? emailMap[String(r.user_id)] || null : "cli",
      }));
      return jsonRes({ jobs });
    }

    if (method === "GET" && path === "/v1/admin/billing/overview") {
      const ts = nowIso();
      const todayPrefix = ts.slice(0, 10);
      const activeSubs = Number(
        (await env.DB.prepare("SELECT COUNT(*) AS n FROM subscriptions WHERE status = 'active' AND ends_at > ?").bind(ts).first())?.n || 0
      );
      const trialSubs = Number(
        (await env.DB.prepare("SELECT COUNT(*) AS n FROM subscriptions WHERE status = 'trial' AND ends_at > ?").bind(ts).first())?.n || 0
      );
      const pendingOrders = Number(
        (await env.DB.prepare("SELECT COUNT(*) AS n FROM payment_orders WHERE status = 'pending'").first())?.n || 0
      );
      const paidRev = Number(
        (await env.DB.prepare("SELECT COALESCE(SUM(amount_vnd), 0) AS s FROM payment_orders WHERE status = 'paid'").first())?.s || 0
      );
      const creditsUsedToday = Number(
        (
          await env.DB.prepare(
            "SELECT COALESCE(SUM(-delta), 0) AS s FROM credit_ledger WHERE reason = 'job_hold' AND created_at >= ?"
          )
            .bind(todayPrefix)
            .first()
        )?.s || 0
      );
      const plansRes = await env.DB.prepare("SELECT * FROM plans ORDER BY price_vnd ASC").all();
      return jsonRes({
        stats: {
          trials_active: trialSubs,
          subscriptions_active: activeSubs,
          orders_pending: pendingOrders,
          credits_used_today: creditsUsedToday,
          active_subscriptions: activeSubs,
          trial_subscriptions: trialSubs,
          pending_orders: pendingOrders,
          paid_revenue_vnd: paidRev,
        },
        plans: (plansRes.results || []).map(publicPlan),
        transfer_note: await transferNote(env),
      });
    }

    if (method === "GET" && path === "/v1/admin/billing/orders") {
      const statusFilter = url.searchParams.get("status");
      const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") || 50)));
      const res = statusFilter
        ? await env.DB.prepare("SELECT * FROM payment_orders WHERE status = ? ORDER BY created_at DESC LIMIT ?")
            .bind(statusFilter, limit)
            .all()
        : await env.DB.prepare("SELECT * FROM payment_orders ORDER BY created_at DESC LIMIT ?").bind(limit).all();
      const usersRes = await env.DB.prepare("SELECT id, email FROM users").all();
      const emailMap = Object.fromEntries((usersRes.results || []).map((u) => [String(u.id), u.email]));
      const orders = (res.results || []).map((o) => ({
        ...o,
        user_email: emailMap[String(o.user_id)] || null,
      }));
      return jsonRes({ orders });
    }

    const orderMatch = path.match(/^\/v1\/admin\/billing\/orders\/([^/]+)$/);
    if (orderMatch && method === "PATCH") {
      const orderId = decodeURIComponent(orderMatch[1]);
      const order = await env.DB.prepare("SELECT * FROM payment_orders WHERE id = ?").bind(orderId).first();
      if (!order) return errRes(404, "order not found");
      if (order.status !== "pending") return errRes(400, "order is not pending");
      const body = await readJson(request);
      const nextStatus = String(body?.status || "").trim().toLowerCase();
      if (!["paid", "rejected"].includes(nextStatus)) return errRes(422, "status must be paid or rejected");
      const ts = nowIso();
      // Atomically claim the pending order FIRST so concurrent admin approvals cannot double-activate.
      const claim = await env.DB.prepare(
        "UPDATE payment_orders SET status = ?, admin_note = ?, paid_at = ?, updated_at = ? WHERE id = ? AND status = 'pending'"
      )
        .bind(nextStatus, body?.admin_note || null, nextStatus === "paid" ? ts : null, ts, orderId)
        .run();
      if (!claim.meta || Number(claim.meta.changes || 0) !== 1) {
        return errRes(400, "order is not pending");
      }
      if (nextStatus === "paid") {
        try {
          await activatePlan(env, String(order.user_id), String(order.plan_code), `order ${orderId}`);
        } catch (err) {
          await env.DB.prepare(
            "UPDATE payment_orders SET status = 'pending', paid_at = NULL, updated_at = ? WHERE id = ?"
          )
            .bind(nowIso(), orderId)
            .run();
          return errRes(400, err instanceof Error ? err.message : "activate failed");
        }
      }
      const updated = await env.DB.prepare("SELECT * FROM payment_orders WHERE id = ?").bind(orderId).first();
      const sub = await currentSubscription(env, String(order.user_id));
      return jsonRes({ order: updated, billing: entitlementSnapshot(sub) });
    }

    const grantMatch = path.match(/^\/v1\/admin\/billing\/users\/([^/]+)\/grant$/);
    if (grantMatch && method === "POST") {
      const targetId = decodeURIComponent(grantMatch[1]);
      const target = await env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(targetId).first();
      if (!target) return errRes(404, "user not found");
      const body = await readJson(request);
      const credits = Number(body?.credits);
      if (!Number.isInteger(credits) || credits < 1 || credits > 1000) {
        return errRes(422, "credits must be an integer 1..1000");
      }
      let subs = await listUserSubscriptions(env, targetId);
      if (!subs.length) {
        await ensureTrial(env, targetId);
        subs = await listUserSubscriptions(env, targetId);
      }
      const sub = subs[0];
      const ts = nowIso();
      const currentEndsMs = new Date(sub.ends_at).getTime() || 0;
      const nowMs = Date.now();
      const extendDays = body?.extend_days !== undefined && body?.extend_days !== null ? Number(body.extend_days) : 0;
      if (extendDays && (!Number.isFinite(extendDays) || extendDays < 0 || extendDays > 3650)) {
        return errRes(422, "extend_days must be 0..3650");
      }
      let newEnds = sub.ends_at;
      if (extendDays > 0) {
        newEnds = new Date(Math.max(nowMs, currentEndsMs) + extendDays * 86400 * 1000).toISOString();
      } else if (currentEndsMs <= nowMs) {
        // Ensure granted credits on an expired subscription are immediately usable.
        newEnds = addDaysIso(14);
      }
      const newStatus = sub.status === "expired" ? "active" : sub.status;
      await env.DB.prepare(
        `UPDATE subscriptions
         SET credits_remaining = credits_remaining + ?, credits_total = credits_total + ?,
             ends_at = ?, status = ?, updated_at = ?
         WHERE id = ?`
      )
        .bind(credits, credits, newEnds, newStatus, ts, sub.id)
        .run();
      await env.DB.prepare(
        `INSERT INTO credit_ledger (id, user_id, job_id, delta, reason, note, created_at)
         VALUES (?, ?, NULL, ?, 'admin_grant', ?, ?)`
      )
        .bind(randomHex(8), targetId, credits, body?.note || "admin grant", ts)
        .run();
      const freshSub = await env.DB.prepare("SELECT * FROM subscriptions WHERE id = ?").bind(sub.id).first();
      return jsonRes({ subscription: freshSub, billing: entitlementSnapshot(freshSub) });
    }

    const planMatch = path.match(/^\/v1\/admin\/billing\/plans\/([^/]+)$/);
    if (planMatch && method === "PATCH") {
      const code = decodeURIComponent(planMatch[1]);
      const plan = await env.DB.prepare("SELECT * FROM plans WHERE code = ?").bind(code).first();
      if (!plan) return errRes(404, "plan not found");
      const body = await readJson(request);
      const sets = ["updated_at = ?"];
      const params = [nowIso()];
      if (body?.credits !== undefined && body.credits !== null) {
        const val = Number(body.credits);
        if (!Number.isInteger(val) || val < 1 || val > 100000) return errRes(422, "credits must be integer 1..100000");
        sets.push("credits = ?");
        params.push(val);
      }
      if (body?.price_vnd !== undefined && body.price_vnd !== null) {
        const val = Number(body.price_vnd);
        if (!Number.isInteger(val) || val < 0 || val > 1000000000) return errRes(422, "price_vnd must be integer >= 0");
        sets.push("price_vnd = ?");
        params.push(val);
      }
      if (body?.active !== undefined && body.active !== null) {
        sets.push("active = ?");
        params.push(body.active ? 1 : 0);
      }
      if (body?.period_days !== undefined && body.period_days !== null) {
        const val = Number(body.period_days);
        if (!Number.isInteger(val) || val < 1 || val > 3650) return errRes(422, "period_days must be integer 1..3650");
        sets.push("period_days = ?");
        params.push(val);
      }
      if (body?.name !== undefined && body.name !== null) {
        sets.push("name = ?");
        params.push(String(body.name).trim() || plan.name);
      }
      params.push(code);
      await env.DB.prepare(`UPDATE plans SET ${sets.join(", ")} WHERE code = ?`).bind(...params).run();
      const fresh = await env.DB.prepare("SELECT * FROM plans WHERE code = ?").bind(code).first();
      return jsonRes({ plan: publicPlan(fresh) });
    }
  }

  return errRes(404, "not found");
}
