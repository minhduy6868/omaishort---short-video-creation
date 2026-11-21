/**
 * Crypto & JWT helpers compatible with apps/api/omaishort/auth.py.
 * Uses node:crypto (enabled via nodejs_compat in Cloudflare Workers).
 */
import { createHash, createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const SCRYPT_N = 16384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const SCRYPT_DKLEN = 32;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const ACCESS_TTL_SEC = 900;
export const REFRESH_TTL_SEC = 14 * 24 * 3600;

export function randomHex(bytes = 6) {
  return randomBytes(bytes).toString("hex");
}

export function randomToken(bytes = 32) {
  return randomBytes(bytes).toString("base64url");
}

export function sha256Hex(text) {
  return createHash("sha256").update(String(text)).digest("hex");
}

export function hashPassword(password) {
  const salt = randomBytes(16);
  const dk = scryptSync(String(password), salt, SCRYPT_DKLEN, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });
  return `scrypt$${salt.toString("hex")}$${dk.toString("hex")}`;
}

export function verifyPassword(password, stored) {
  if (typeof stored !== "string") return false;
  const parts = stored.split("$");
  if (parts.length !== 3 || parts[0] !== "scrypt") return false;
  try {
    const salt = Buffer.from(parts[1], "hex");
    const expected = Buffer.from(parts[2], "hex");
    const got = scryptSync(String(password), salt, expected.length, {
      N: SCRYPT_N,
      r: SCRYPT_R,
      p: SCRYPT_P,
    });
    return got.length === expected.length && timingSafeEqual(got, expected);
  } catch {
    return false;
  }
}

export function normalizeEmail(raw) {
  return String(raw || "").trim().toLowerCase();
}

export function canonicalEmail(raw) {
  const email = normalizeEmail(raw);
  const idx = email.indexOf("@");
  if (idx < 0) return email;
  let local = email.slice(0, idx);
  let domain = email.slice(idx + 1);
  if (domain === "gmail.com" || domain === "googlemail.com") {
    local = local.split("+", 1)[0].replaceAll(".", "");
    domain = "gmail.com";
  }
  return `${local}@${domain}`;
}

export function validEmail(email) {
  return EMAIL_RE.test(email) && !email.includes("..");
}

function b64urlJson(obj) {
  return Buffer.from(JSON.stringify(obj)).toString("base64url");
}

export function jwtSecret(env) {
  const raw = String(env.AUTH_SECRET || env.APP_KEY || "").trim();
  if (!raw) throw new Error("AUTH_SECRET is not configured on Cloudflare Worker");
  return raw;
}

export function encodeAccess(user, env) {
  const now = Math.floor(Date.now() / 1000);
  const header = b64urlJson({ alg: "HS256", typ: "JWT" });
  const payload = b64urlJson({
    sub: String(user.id),
    email: String(user.email),
    role: String(user.role),
    typ: "access",
    iat: now,
    exp: now + ACCESS_TTL_SEC,
  });
  const sig = createHmac("sha256", jwtSecret(env)).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${sig}`;
}

export function decodeAccess(token, env) {
  if (!token || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [headerB64, bodyB64, sigB64] = parts;
  try {
    const header = JSON.parse(Buffer.from(headerB64, "base64url").toString("utf8"));
    if (header.alg !== "HS256") return null;
    const expected = createHmac("sha256", jwtSecret(env)).update(`${headerB64}.${bodyB64}`).digest();
    const got = Buffer.from(sigB64, "base64url");
    if (expected.length !== got.length || !timingSafeEqual(expected, got)) return null;
    const payload = JSON.parse(Buffer.from(bodyB64, "base64url").toString("utf8"));
    if (payload.typ !== "access") return null;
    if (Number(payload.exp) < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}
