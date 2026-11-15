CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    input_json TEXT NOT NULL,
    bible_json TEXT,
    structure_json TEXT,
    storyboard_json TEXT,
    timeline_json TEXT,
    artifacts_json TEXT,
    storage_json TEXT,
    progress TEXT,
    user_id TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    user_agent TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    content_b64 TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    credits INTEGER NOT NULL,
    period_days INTEGER NOT NULL,
    price_vnd INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    features_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_code TEXT NOT NULL,
    status TEXT NOT NULL,
    credits_remaining INTEGER NOT NULL,
    credits_total INTEGER NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id TEXT,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_orders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_code TEXT NOT NULL,
    amount_vnd INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    paid_at TEXT,
    admin_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_attachments_user ON attachments(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role, created_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(user_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_job_hold ON credit_ledger(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_user ON payment_orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON payment_orders(status, created_at);
