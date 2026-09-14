# Auth and attachments — omaishort

Canonical product numbers stay in [REQUIREMENTS.md](REQUIREMENTS.md). This file is the **account and file** contract. Code that disagrees with this file is a bug — unless the same PR updates both.

Why this shape (not Auth0, not Redis sessions, not a cloned GitHub OAuth app):

| Constraint | Decision |
| --- | --- |
| Local-first Windows, **PostgreSQL 16** on `127.0.0.1:5432`, FastAPI, Vite proxy | Identity in Postgres (`DATABASE_URL`). Job bytes stay under `data/`. No Redis, no Keycloak. |
| Studio is one page; `<img>` / `<video>` cannot send `Authorization` | httpOnly cookies for access + refresh so media GETs authenticate. |
| Planner must stay vendor-free | Auth lives in API/db only. Engine receives file paths, not tokens. |
| CLI is the operator tool | `python -m omaishort` does not log in. Jobs it creates have `user_id=NULL`. |
| Secrets stay gitignored | `AUTH_SECRET` in `.env` or `data/.auth_secret`. Never commit it. |
| CI has no cloud keys | Auth tests use a temp `sqlite:///` file. The running API uses PostgreSQL. |

Do **not** fork Clerk/NextAuth/Supabase into this tree. Do not scrape Google login UIs.

---

## 1. Problem

Today anyone who can hit `127.0.0.1:8765` can create jobs and **read every file under `data/`** (`StaticFiles` on `DATA_DIR`). That is fine for a single operator on a laptop; it is not an account model.

Creators need:

1. **Auth** — register / login / logout; jobs and files belong to a user.
2. **Attachments** — upload a face, location, prop, editorial photo, logo, or script **before** `POST /jobs`, then bind those files into the existing pipeline (bible refs, ảnh ghép waterfall, logo overlay). Not a second product. Not user-generated MP4 hosting.

---

## 2. Actors

| Actor | How they enter | What they own |
| --- | --- | --- |
| Creator | Studio register/login | Own jobs, own attachments |
| Operator | First registered user (`role=operator`), or CLI | Own HTTP jobs; may read CLI jobs (`user_id` null); CLI still bypasses HTTP |
| Anonymous | `/health`, `/`, `/docs`, `/providers`, `/voices` | Nothing else |
| Agent / CI | pytest with temp DB | Isolated users, no live providers |

Roles are **not** a permission matrix beyond operator-can-read-unowned-jobs. Do not add admin UI.

---

## 3. Auth scheme

### 3.1 Why this, not the alternatives

| Approach | Fit | Verdict |
| --- | --- | --- |
| OAuth2 password + JWT access + opaque rotating refresh in PostgreSQL | FastAPI-standard, revocable refresh, same tables | **Ship this** |
| Server sessions in Redis | P6 queue only; not in MVP stack | No |
| JWT-only (no refresh store) | Cannot revoke a stolen access token until TTL; refresh replay | No |
| API keys in `.env` as the user | Operator keys already exist for providers; mixing them with creator identity leaks provider secrets | No |
| Hosted IdP (Auth0, Clerk, Google) | Not local-first; needs network and a product account | Out of scope |
| ChatGPT Playwright cookies | Those authenticate **ChatGPT**, not omaishort users | Unrelated |

### 3.2 Tokens

| Token | Format | TTL | Where | Revoke |
| --- | --- | --- | --- | --- |
| Access | HS256 JWT (`sub`, `email`, `role`, `iat`, `exp`, `typ=access`) | **900s** (15 min) | JSON `access_token` **and** httpOnly cookie `omaishort_at` | Expiry only (short) |
| Refresh | Opaque 32-byte urlsafe, **stored SHA-256** in `refresh_tokens` | **14 days** | httpOnly cookie `omaishort_rt` (also JSON on login for tests) | Logout, rotation, expiry |

JWT secret: `AUTH_SECRET` env, else `data/.auth_secret` created on first boot (48-byte urlsafe). Algorithm **HS256** only. No `none`, no RS256 (no keypair ceremony on a laptop).

Refresh **rotates** on every `POST /auth/refresh`: old row `revoked_at` set, new token issued. Reuse of a revoked refresh → revoke **all** refresh rows for that user (stolen-token reuse).

### 3.3 Cookies

| Name | httpOnly | Secure | SameSite | Path | Max-Age |
| --- | --- | --- | --- | --- | --- |
| `omaishort_at` | yes | `AUTH_COOKIE_SECURE` (default **0** on loopback HTTP) | `Lax` | `/` | 900 |
| `omaishort_rt` | yes | same | `Lax` | `/` | 1209600 |

Do not set `Domain` (host-only). CORS `allow_credentials=True` with the existing explicit origins (`http://127.0.0.1:5173`, `http://localhost:5173`). Studio `fetch` uses `credentials: "include"`.

CSRF: SameSite=Lax + loopback + no cross-site cookies. State-changing POSTs from other sites do not send Lax cookies on cross-site POST. Do not invent a CSRF token until the API is bound on a public host.

### 3.4 Request authentication

Protected routes accept **either**:

1. `Authorization: Bearer <access JWT>`
2. Cookie `omaishort_at`

Header wins if both present. Missing/invalid → **401** `{ "detail": "not authenticated" }`. Do not leak whether the email exists on login (same 401 message: `invalid email or password`).

### 3.5 Passwords

- Hash: **scrypt** (`hashlib.scrypt`, n=2¹⁴, r=8, p=1, dklen=32) + 16-byte random salt. Stored as `scrypt$<salt_hex>$<dk_hex>`. Stdlib — no passlib.
- Verify with `hmac.compare_digest`.
- Policy: 8–128 characters. No composition theater. Trim is **not** applied to passwords.
- Email: trim + lowercase. Unique. Max 254. Must contain one `@` and a dot in the domain. Display name optional, max 80, default local-part.

### 3.6 Lockout

Per email (not IP): after **8** failed logins, reject for **15 minutes** with **429**. Counter resets on success. Do not create a user row on failed login for unknown emails (still count against a hashed email key in a small memory map so attackers cannot probe timing as easily — unknown emails share the same 401 and a dummy `compare_digest` against a static hash).

### 3.7 Signup

- `AUTH_SIGNUP` default **1**. When `0`, `POST /auth/register` returns 403 after the first operator exists.
- First user → `role=operator`. Later users → `role=creator`.
- No email verification in v1 (local-first). No password-reset mailer.

### 3.8 Public vs protected

| Public | Protected (Bearer or access cookie) |
| --- | --- |
| `GET /`, `/health`, `/docs`, `/redoc`, `/openapi.json` | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, artifacts, download |
| `GET /providers`, `GET /voices` | `POST/GET/DELETE /attachments`, file bytes |
| `POST /auth/register`, `/auth/login`, `/auth/refresh` | `GET /auth/me`, `POST /auth/logout` |

`GET /files/{path}` is **protected**. Unauthenticated media is 401, not a directory listing.

CLI never calls these routes.

---

## 4. Data model (PostgreSQL)

Store: `DATABASE_URL` (default `postgresql://omaishort:omaishort@127.0.0.1:5432/omaishort`). Bootstrap: [`scripts/init_postgres.sql`](../scripts/init_postgres.sql). `init_db()` creates tables and `ALTER TABLE jobs ADD COLUMN user_id` when missing. Pytest sets `DATABASE_URL=sqlite:///…` so CI does not need a Postgres server.

### 4.1 `users`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | TEXT PK | 12-char hex (same length as job ids) |
| `email` | TEXT UNIQUE NOT NULL | lowercase |
| `password_hash` | TEXT NOT NULL | scrypt string |
| `display_name` | TEXT | |
| `role` | TEXT NOT NULL | `creator` \| `operator` |
| `failed_logins` | INTEGER NOT NULL DEFAULT 0 | |
| `locked_until` | TEXT | ISO UTC or NULL |
| `created_at` | TEXT | ISO UTC |
| `updated_at` | TEXT | ISO UTC |

Never return `password_hash`, `failed_logins`, or `locked_until` on `public_user()`.

### 4.2 `refresh_tokens`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | TEXT PK | |
| `user_id` | TEXT NOT NULL | FK logical (no enforced FK required) |
| `token_hash` | TEXT UNIQUE NOT NULL | SHA-256 hex of the opaque token |
| `expires_at` | TEXT NOT NULL | |
| `revoked_at` | TEXT | |
| `created_at` | TEXT | |
| `user_agent` | TEXT | optional, truncated 200 |

### 4.3 `attachments`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | TEXT PK | 12-char hex |
| `user_id` | TEXT NOT NULL | owner |
| `kind` | TEXT NOT NULL | see §6 |
| `filename` | TEXT NOT NULL | original sanitized basename |
| `mime` | TEXT NOT NULL | sniffed |
| `byte_size` | INTEGER NOT NULL | |
| `sha256` | TEXT NOT NULL | hex of bytes |
| `rel_path` | TEXT NOT NULL | relative to `DATA_DIR` |
| `created_at` | TEXT | |

On-disk: `data/attachments/<user_id>/<id><ext>`. Extension from sniffed type, not the client name.

### 4.4 `jobs.user_id`

NULL = CLI operator job. HTTP `POST /jobs` always sets the authenticated user id.

### 4.5 Ownership

| Resource | Read | Write / delete |
| --- | --- | --- |
| Job with `user_id=U` | U, or operator | same (no delete-job in v1) |
| Job with `user_id` NULL | operator only | — |
| Attachment | owner | owner |
| Bytes under `data/jobs/<id>/` | same as job read | engine only |
| Bytes under `data/attachments/<U>/` | owner or operator | owner |
| `data/omaishort.db` (legacy sqlite file), `data/.auth_secret`, `data/chatgpt-web/` | **never** via `/files` | — |

Guessing another job id returns **404** (not 403) so ids stay unlisted.

---

## 5. HTTP contract

All JSON. Errors use FastAPI `{ "detail": "..." }` (string or list).

### 5.1 Auth

**`POST /auth/register`** `{ email, password, display_name? }`  
201 `{ user, access_token, token_type: "bearer", expires_in: 900, refresh_token }` + Set-Cookie.  
409 email taken. 403 signup closed. 422 validation.

**`POST /auth/login`** `{ email, password }`  
200 same payload as register. 401 invalid. 429 locked.

**`POST /auth/refresh`** cookie `omaishort_rt` or body `{ refresh_token }`  
200 new access (+ new refresh). 401 missing/revoked/expired.

**`POST /auth/logout`**  
204. Clears cookies. Revokes the presented refresh. Idempotent if already logged out.

**`GET /auth/me`**  
200 `{ id, email, display_name, role }`. 401 if anonymous.

### 5.2 Jobs (delta)

**`POST /jobs`** body remains `StoryInput` (now with `attachments[]`). 401 without user. 400 if any attachment id is missing or not owned. Response still `{ id, status: "queued" }`.

**`GET /jobs`** query `limit` 1–50 default 20. Own jobs, newest `created_at` first. Operator does **not** get everyone's jobs in v1 (avoids leaking CLI dry-runs to a shared operator session by accident). Operator may still `GET /jobs/{id}` for `user_id` NULL when they know the id.

**`GET /jobs/{id}`**, artifacts, download: owner or (operator + unowned). Same `public_job()` rules — no raw `*_json` keys.

### 5.3 Attachments

**`POST /attachments?kind=`** `multipart/form-data` field `file`.  
201 public attachment JSON.

**`GET /attachments`** list own, newest first, max 80 rows.

**`GET /attachments/{id}`** metadata. **`GET /attachments/{id}/file`** bytes (`Content-Disposition: inline`).

**`DELETE /attachments/{id}`** 204. Unlinks disk. Jobs that already copied the file into `data/jobs/<id>/` keep the copy (pipeline snapshot). Do not rewrite running jobs.

### 5.4 Files

**`GET /files/{path:path}`** replaces unauthenticated `StaticFiles`. Resolve under `DATA_DIR`, reject `..`, reject files outside allowed prefixes in §4.5.

---

## 6. Attachments (product)

Attachments are **inputs** to the existing stages. They do not add a kind, do not skip beats, and do not turn news/knowledge into drama faces.

### 6.1 Kinds

| `kind` | MIME allow | Max bytes | Pipeline |
| --- | --- | --- | --- |
| `face` | jpeg / png / webp | 8 MiB | Drama **refs**: copy to `refs/<bind or filename-stem>.png`. Skip Pollinations passport for that character when the file exists. Filename stem or `bind` must match a bible `character.id` (case-insensitive). Unmatched faces assign in order to non-`narrator` characters. Editorial jobs **ignore** `face`. |
| `location` | jpeg / png / webp | 8 MiB | Drama refs: `refs/locations/<id>.png`. Skip generated location passport. |
| `prop` | jpeg / png / webp | 8 MiB | Drama refs: `refs/props/<id>.png`. |
| `editorial` | jpeg / png / webp | 8 MiB | News/knowledge **ảnh ghép**: local files are **first** stills (before article URL photos, before Wikimedia). `conform_photo` into 9:16. Drama jobs ignore. |
| `logo` | jpeg / png / webp | 2 MiB | First logo sets `mix.logo_enabled=true` and `mix.logo_path` to the job-local copy. |
| `script` | `text/plain` / markdown UTF-8 | 256 KiB | Copied to `job_dir/input_attachment.txt` as provenance. Does **not** replace `StoryInput.text` (studio pastes or fills the textarea). |

No PDF, SVG, HTML, HEIC, MP4, audio. SVG is an XSS vector. MP4 upload is not a product (I2V is generated, not user-supplied).

### 6.2 Sniff, do not trust `Content-Type`

| Magic | Result |
| --- | --- |
| `FF D8 FF` | jpeg |
| `89 50 4E 47 0D 0A 1A 0A` | png |
| `RIFF....WEBP` | webp |
| UTF-8 text without NUL, for `kind=script` only, extension `.txt` / `.md` | text/plain |

Mismatch → 400 `file type not allowed`. Empty file → 400.

### 6.3 Quotas (per user)

- 80 attachments stored.
- 200 MiB sum of `byte_size`.
- 12 attachment links per job (`StoryInput.attachments` max_length 12).
- Original filename: basename only, max 120 chars, strip `\\` / `/` / NUL.

Duplicate content (same user + sha256 + kind): return the **existing** row (200/201 with same id). Do not store a second copy.

### 6.4 `StoryInput.attachments`

```json
"attachments": [{ "id": "a1b2c3d4e5f6", "bind": "wife" }]
```

`bind` optional. Empty string → `null`. Engine `apply_attachment_files` is the only mapper. Planner does not import `db`.

### 6.5 Must not

- One uploaded image per sentence (still one still per scene).
- Use a `face` attachment as an editorial collage still.
- Use an `editorial` photo as a drama passport.
- Fetch attachments from Pexels or scrape Gemini UI.
- Serve attachment bytes without auth.

---

## 7. Functional requirements

| ID | Observable |
| --- | --- |
| FR-A1 | Register + login return a user and set cookies; `/auth/me` works with cookie only. |
| FR-A2 | `POST /jobs` without auth is 401. With auth, `jobs.user_id` is the caller. |
| FR-A3 | Creator A cannot `GET` creator B's job (404). |
| FR-A4 | Refresh rotates; reused revoked refresh invalidates the family. |
| FR-A5 | Logout clears cookies; old refresh is 401. |
| FR-A6 | `/files/omaishort.db` and `/files/.auth_secret` are 404 even when authenticated. |
| FR-F1 | Upload png `kind=face`; drama refs stage uses that file for the bound character. |
| FR-F2 | Upload `kind=editorial`; news still waterfall prefers it on early beats. |
| FR-F3 | Upload `kind=logo` + link on job → compose overlay uses that path when `logo_enabled`. |
| FR-F4 | Reject `.svg` and oversize files. |
| FR-F5 | `public_job()` still strips `*_json`; never includes password hashes. |

CLI dry-run without HTTP remains green (no user row required).

---

## 8. Non-functional

| ID | Requirement |
| --- | --- |
| NFR-A1 | No new cloud IdP. Stdlib scrypt + HMAC JWT. `python-multipart` only extra dep (FastAPI uploads). |
| NFR-A2 | Tests do not call live SMTP, OAuth, or provider networks. |
| NFR-A3 | Windows paths: resolve() + `relative_to(DATA_DIR)` so `..` cannot escape. |
| NFR-A4 | Timing: dummy password hash for unknown emails on login. |
| NFR-A5 | Access JWT in logs forbidden. Do not print cookies. |

---

## 9. Studio

One page. No new React router, no UI library.

- Logged out: register/login panel. Job form disabled.
- Logged in: email + Log out. Attachment picker by kind (face / editorial / logo / script). Selected ids go on `POST /jobs` as `attachments`.
- `fetch` always `credentials: "include"`. On 401, drop the in-memory user and show login.
- Stills still use `dataFileUrl()` → `/files/...` (cookie authenticates the GET).

---

## 10. Out of scope

Leave on the roadmap until asked:

- OAuth/OIDC, WebAuthn, TOTP, magic links, email verify, password reset mail
- Per-job share links, public gallery, team orgs
- S3 / MinIO; Redis session store
- Attachment as I2V clip or user BGM (BGM stays `assets/music/`)
- `POST /jobs/{id}/approve` (P3)
- Binding the API on `0.0.0.0` without TLS (keep default `API_HOST=127.0.0.1`)

---

## 11. Acceptance

- `pytest -q` includes auth ownership + attachment sniff tests (no ffmpeg required).
- `npx tsc --noEmit` in `apps/web`.
- Unauthenticated `POST /jobs` is 401.
- Logged-in upload + drama job: `refs/<id>.png` matches the uploaded pixels (or identical SHA after PNG convert).
- `/files` no longer lists `data/` for anonymous clients.
- CLI `python -m omaishort samples/confession-60s.md` still writes an MP4 without registering.
