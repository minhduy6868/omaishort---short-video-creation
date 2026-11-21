import { handleV1 } from "./v1.js";

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
  "access-control-allow-headers": "authorization,content-type,x-omaishort-key",
};

function withCors(response) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(CORS_HEADERS)) {
    headers.set(k, v);
  }
  return new Response(response.body, { status: response.status, headers });
}

export default {
  async fetch(request, env) {
    const pathname = new URL(request.url).pathname;
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (pathname.startsWith("/v1/")) {
      return withCors(await handleV1(request, env));
    }
    if (request.method === "GET" && pathname === "/health") {
      return Response.json({ ok: true, service: "omaishort-db", v1: true });
    }
    if (!env.APP_KEY || request.headers.get("x-omaishort-key") !== env.APP_KEY) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }
    if (request.method === "POST" && pathname === "/batch") {
      let body;
      try {
        body = await request.json();
      } catch {
        return Response.json({ ok: false, error: "invalid json" }, { status: 400 });
      }
      const queries = Array.isArray(body.queries) ? body.queries : [];
      if (!queries.length || queries.length > 50) {
        return Response.json({ ok: false, error: "invalid batch size" }, { status: 400 });
      }
      try {
        const stmts = queries.map((item) => {
          const sql = typeof item.sql === "string" ? item.sql.trim() : "";
          const params = Array.isArray(item.params) ? item.params : [];
          return env.DB.prepare(sql).bind(...params);
        });
        const out = await env.DB.batch(stmts);
        return Response.json({
          ok: true,
          results: out.map((res) => ({
            rows: res.results ?? [],
            changes: res.meta?.changes ?? 0,
          })),
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const status = /unique/i.test(message) ? 409 : 400;
        return Response.json({ ok: false, error: message }, { status });
      }
    }
    if (request.method !== "POST" || pathname !== "/query") {
      return Response.json({ ok: false, error: "not found" }, { status: 404 });
    }
    let body;
    try {
      body = await request.json();
    } catch {
      return Response.json({ ok: false, error: "invalid json" }, { status: 400 });
    }
    const sql = typeof body.sql === "string" ? body.sql.trim() : "";
    const params = Array.isArray(body.params) ? body.params : [];
    if (!sql || sql.length > 20000) {
      return Response.json({ ok: false, error: "empty sql" }, { status: 400 });
    }
    try {
      const stmt = env.DB.prepare(sql).bind(...params);
      const head = sql.slice(0, 12).toUpperCase();
      if (head.startsWith("SELECT") || head.startsWith("PRAGMA") || head.startsWith("WITH")) {
        const out = await stmt.all();
        return Response.json({ ok: true, rows: out.results ?? [] });
      }
      const out = await stmt.run();
      return Response.json({ ok: true, rows: [], changes: out.meta?.changes ?? 0 });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const status = /unique/i.test(message) ? 409 : 400;
      return Response.json({ ok: false, error: message }, { status });
    }
  },
};
