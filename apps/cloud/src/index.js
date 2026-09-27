export default {
  async fetch(request, env) {
    if (request.method === "GET" && new URL(request.url).pathname === "/health") {
      return Response.json({ ok: true });
    }
    if (request.headers.get("x-omaishort-key") !== env.APP_KEY) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }
    if (request.method !== "POST" || new URL(request.url).pathname !== "/query") {
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
