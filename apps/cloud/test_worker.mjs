import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";

import worker from "./src/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_SQL = fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8");

/** Minimal Cloudflare D1 shim backed by Node's built-in in-memory SQLite. */
function makeD1Env() {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA_SQL);

  function wrapStmt(sql, bound = []) {
    return {
      bind(...params) {
        return wrapStmt(sql, params);
      },
      async first() {
        const stmt = db.prepare(sql);
        const row = stmt.get(...bound);
        return row ? { ...row } : null;
      },
      async all() {
        const stmt = db.prepare(sql);
        const rows = stmt.all(...bound).map((r) => ({ ...r }));
        return { results: rows };
      },
      async run() {
        const stmt = db.prepare(sql);
        const info = stmt.run(...bound);
        return { meta: { changes: Number(info.changes || 0) } };
      },
    };
  }

  return {
    APP_KEY: "super-secret-admin-sql-key",
    AUTH_SECRET: "worker-jwt-secret-for-tests-123456",
    DB: {
      prepare: (sql) => wrapStmt(sql),
      async batch(stmts) {
        const out = [];
        for (const s of stmts) out.push(await s.run());
        return out;
      },
    },
  };
}

async function req(env, method, route, { token, body, key } = {}) {
  const headers = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (token) headers["authorization"] = `Bearer ${token}`;
  if (key) headers["x-omaishort-key"] = key;
  const request = new Request(`https://cloud.test${route}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const res = await worker.fetch(request, env);
  const text = await res.text();
  return { status: res.status, data: text ? JSON.parse(text) : null };
}

test("raw /query stays blocked without APP_KEY while /v1/health is public", async () => {
  const env = makeD1Env();
  const denied = await req(env, "POST", "/query", { body: { sql: "SELECT 1" } });
  assert.equal(denied.status, 401);

  const ok = await req(env, "GET", "/v1/health");
  assert.equal(ok.status, 200);
  assert.equal(ok.data.ok, true);
});

test("full multi-user lifecycle: auth, trial credits, jobs isolation, templates, checkout, and admin approval", async () => {
  const env = makeD1Env();

  // 1. First user becomes operator
  const opReg = await req(env, "POST", "/v1/auth/register", {
    body: { email: "admin@omaishort.com", password: "password123", display_name: "Admin" },
  });
  assert.equal(opReg.status, 201);
  assert.equal(opReg.data.user.role, "operator");
  const opToken = opReg.data.access_token;

  // 2. Second user becomes creator with 3 trial credits
  const c1Reg = await req(env, "POST", "/v1/auth/register", {
    body: { email: "alice@example.com", password: "password123", display_name: "Alice" },
  });
  assert.equal(c1Reg.status, 201);
  assert.equal(c1Reg.data.user.role, "creator");
  assert.equal(c1Reg.data.user.billing.plan_code, "trial");
  assert.equal(c1Reg.data.user.billing.credits_remaining, 3);
  const c1Token = c1Reg.data.access_token;

  // Login + refresh rotation works
  const login = await req(env, "POST", "/v1/auth/login", {
    body: { email: "alice@example.com", password: "password123" },
  });
  assert.equal(login.status, 200);
  const refreshed = await req(env, "POST", "/v1/auth/refresh", {
    body: { refresh_token: login.data.refresh_token },
  });
  assert.equal(refreshed.status, 200);
  assert.notEqual(refreshed.data.refresh_token, login.data.refresh_token);

  // 3. Third user (Bob) cannot read Alice's jobs or templates
  const c2Reg = await req(env, "POST", "/v1/auth/register", {
    body: { email: "bob@example.com", password: "password123" },
  });
  const c2Token = c2Reg.data.access_token;

  // 4. Alice holds 1 credit, creates a job metadata row, updates storyboard
  const hold = await req(env, "POST", "/v1/billing/hold", { token: c1Token, body: { job_id: "job_a1" } });
  assert.equal(hold.status, 200);
  assert.equal(hold.data.billing.credits_remaining, 2);

  const createdJob = await req(env, "POST", "/v1/jobs", {
    token: c1Token,
    body: { id: "job_a1", input_json: { kind: "drama", text: "Test story here" } },
  });
  assert.equal(createdJob.status, 201);

  const patchedJob = await req(env, "PATCH", "/v1/jobs/job_a1", {
    token: c1Token,
    body: { status: "done", stage: "done", storage_json: { mp4_ready: true, mp4_bytes: 12345 } },
  });
  assert.equal(patchedJob.status, 200);
  assert.equal(patchedJob.data.job.status, "done");

  // Bob gets 404 on Alice's job; operator can read it
  const bobRead = await req(env, "GET", "/v1/jobs/job_a1", { token: c2Token });
  assert.equal(bobRead.status, 404);
  const opRead = await req(env, "GET", "/v1/jobs/job_a1", { token: opToken });
  assert.equal(opRead.status, 200);

  // 5. Refund restores credit
  const refund = await req(env, "POST", "/v1/billing/refund", { token: c1Token, body: { job_id: "job_a1" } });
  assert.equal(refund.status, 200);
  const billMe = await req(env, "GET", "/v1/billing/me", { token: c1Token });
  assert.equal(billMe.data.billing.credits_remaining, 3);

  // 6. Reverse-engineered video template syncs to D1 (JSON + VIDEO.md only)
  const tplRes = await req(env, "POST", "/v1/templates", {
    token: c1Token,
    body: {
      id: "tpl_demo1",
      name: "Viral Hook",
      source_filename: "sample.mp4",
      duration_sec: 32,
      pacing: "fast",
      video_md: "# VIDEO.md — Viral Hook",
    },
  });
  assert.equal(tplRes.status, 201);
  const bobTpl = await req(env, "GET", "/v1/templates/tpl_demo1", { token: c2Token });
  assert.equal(bobTpl.status, 404);
  const aliceTpls = await req(env, "GET", "/v1/templates", { token: c1Token });
  assert.equal(aliceTpls.data.templates.length, 1);

  // 7. Checkout + Operator approval activates Starter plan (30 credits)
  const checkout = await req(env, "POST", "/v1/billing/checkout", {
    token: c1Token,
    body: { plan_code: "starter" },
  });
  assert.equal(checkout.status, 201);
  const orderId = checkout.data.order.id;

  // Creator cannot approve their own order
  const creatorApprove = await req(env, "PATCH", `/v1/admin/billing/orders/${orderId}`, {
    token: c1Token,
    body: { status: "paid" },
  });
  assert.equal(creatorApprove.status, 403);

  // Operator approves order -> Alice gets 20 starter credits
  const opApprove = await req(env, "PATCH", `/v1/admin/billing/orders/${orderId}`, {
    token: opToken,
    body: { status: "paid", admin_note: "bank ok" },
  });
  assert.equal(opApprove.status, 200);
  assert.equal(opApprove.data.billing.plan_code, "starter");
  assert.equal(opApprove.data.billing.credits_remaining, 20);
});
