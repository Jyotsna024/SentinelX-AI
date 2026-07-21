-- ============================================================
-- SentinelX AI — Phase 2 Database Schema
-- PostgreSQL DDL for all three required tables.
-- Run once against the target database before starting the app.
-- ============================================================

-- Enable the pgcrypto extension for gen_random_uuid() (PostgreSQL < 14)
-- PostgreSQL 14+ provides gen_random_uuid() natively.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── events ────────────────────────────────────────────────────
-- One row per agent invocation (predict / investigate / contain).
-- payload captures the full request + response for auditability.
CREATE TABLE IF NOT EXISTS events (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id   TEXT        NOT NULL,
    stage       TEXT        NOT NULL,           -- 'predict' | 'investigate' | 'contain'
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_record_id  ON events (record_id);
CREATE INDEX IF NOT EXISTS idx_events_stage       ON events (stage);
CREATE INDEX IF NOT EXISTS idx_events_created_at  ON events (created_at);

-- ── audit_log ─────────────────────────────────────────────────
-- One row per /contain request; updated by /contain/approve.
CREATE TABLE IF NOT EXISTS audit_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id         TEXT        NOT NULL,
    action            TEXT,                      -- comma-joined list of recommended_actions
    risk_score        INTEGER,
    risk_tier         TEXT,                      -- 'critical' | 'elevated' | 'monitor'
    approval_required BOOLEAN,
    approval_state    TEXT,                      -- 'pending' | 'auto' | 'executed' | 'rejected'
    approver          TEXT,                      -- populated on /contain/approve
    executed_at       TIMESTAMPTZ,               -- populated on /contain/approve
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_record_id     ON audit_log (record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_approval_state ON audit_log (approval_state);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at    ON audit_log (created_at);

-- ── cri_snapshots ─────────────────────────────────────────────
-- One row per GET /cri call; used for trend computation.
CREATE TABLE IF NOT EXISTS cri_snapshots (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    score       INTEGER     NOT NULL,
    status      TEXT        NOT NULL,            -- 'healthy' | 'elevated' | 'critical'
    factors     JSONB,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cri_snapshots_captured_at ON cri_snapshots (captured_at);
