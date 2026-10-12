import { copyFileSync, createReadStream, existsSync, mkdirSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const demoDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/demo");
const demoNames = new Set(["knowledge-history.mp4", "knowledge-skills.mp4"]);

function sendDemo(req: IncomingMessage, res: ServerResponse, file: string) {
  const size = statSync(file).size;
  const header = req.headers.range;
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("Content-Type", "video/mp4");
  if (!header) {
    res.statusCode = 200;
    res.setHeader("Content-Length", String(size));
    createReadStream(file).pipe(res);
    return;
  }
  const match = /^bytes=(\d*)-(\d*)$/.exec(header);
  if (!match) {
    res.statusCode = 416;
    res.setHeader("Content-Range", `bytes */${size}`);
    res.end();
    return;
  }
  const start = match[1] ? Number(match[1]) : 0;
  const end = match[2] ? Number(match[2]) : size - 1;
  if (start > end || start >= size) {
    res.statusCode = 416;
    res.setHeader("Content-Range", `bytes */${size}`);
    res.end();
    return;
  }
  res.statusCode = 206;
  res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
  res.setHeader("Content-Length", String(end - start + 1));
  createReadStream(file, { start, end }).pipe(res);
}

function demoVideos(): Plugin {
  return {
    name: "omaishort-demo-videos",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        const name = url.startsWith("/demo/") ? url.slice("/demo/".length) : "";
        if (!demoNames.has(name)) {
          next();
          return;
        }
        const file = path.join(demoDir, name);
        if (!existsSync(file)) {
          next();
          return;
        }
        sendDemo(req, res, file);
      });
    },
    writeBundle(options) {
      if (!options.dir) return;
      const out = path.join(options.dir, "demo");
      mkdirSync(out, { recursive: true });
      for (const name of demoNames) {
        const from = path.join(demoDir, name);
        if (existsSync(from)) copyFileSync(from, path.join(out, name));
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), demoVideos()],
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/jobs": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
      "/files": "http://127.0.0.1:8765",
      "/voices": "http://127.0.0.1:8765",
      "/providers": "http://127.0.0.1:8765",
      "/auth": "http://127.0.0.1:8765",
      "/attachments": "http://127.0.0.1:8765",
    },
  },
});
