-- PROPOSAL ONLY. Not imported by init_db or production workflows.
-- PostgreSQL design for review. SQLite adaptation belongs to implementation.
-- No ALTER/DROP/UPDATE/DELETE of existing production tables.

CREATE TABLE gpm_app_crm_worker_links (
    source_instance TEXT NOT NULL,
    crm_worker_id TEXT NOT NULL,
    worker_account_id TEXT NOT NULL REFERENCES gpm_app_accounts(account_id),
    linked_by TEXT NOT NULL REFERENCES gpm_app_accounts(account_id),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_instance, crm_worker_id),
    UNIQUE (source_instance, worker_account_id),
    CHECK (length(trim(source_instance)) > 0),
    CHECK (length(trim(crm_worker_id)) > 0)
);

CREATE TABLE gpm_app_crew_attendance_sessions (
    session_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    leader_account_id TEXT NOT NULL REFERENCES gpm_app_accounts(account_id),
    attendance_mode TEXT NOT NULL CHECK (attendance_mode IN ('solo', 'crew')),
    action TEXT NOT NULL CHECK (action IN ('check_in', 'check_out')),
    roster_revision INTEGER NOT NULL CHECK (roster_revision > 0),
    status TEXT NOT NULL CHECK (status IN (
        'collecting', 'awaiting_confirmation', 'pending_review',
        'partially_confirmed', 'confirmed', 'rejected', 'expired'
    )),
    final_challenge_id TEXT UNIQUE REFERENCES gpm_app_attendance_challenges(challenge_id),
    leader_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    frozen_at TIMESTAMPTZ,
    client_confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    CHECK (expires_at > created_at),
    CHECK (status NOT IN ('pending_review', 'partially_confirmed', 'confirmed')
        OR client_confirmed_at IS NOT NULL)
);

CREATE TABLE gpm_app_crew_attendance_members (
    evidence_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    worker_account_id TEXT NOT NULL REFERENCES gpm_app_accounts(account_id),
    action TEXT NOT NULL CHECK (action IN ('check_in', 'check_out')),
    session_id TEXT REFERENCES gpm_app_crew_attendance_sessions(session_id),
    token_hash TEXT UNIQUE,
    token_expires_at TIMESTAMPTZ,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    collected_at TIMESTAMPTZ,
    scanned_by TEXT REFERENCES gpm_app_accounts(account_id),
    worker_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    scanner_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    geo_status TEXT NOT NULL CHECK (geo_status IN ('valid', 'review', 'unavailable')),
    status TEXT NOT NULL CHECK (status IN (
        'issued', 'collected', 'awaiting_confirmation', 'pending_review',
        'confirmed', 'rejected', 'expired'
    )),
    effective_at TIMESTAMPTZ,
    reviewed_by TEXT REFERENCES gpm_app_accounts(account_id),
    reviewed_at TIMESTAMPTZ,
    review_reason TEXT,
    UNIQUE (session_id, worker_account_id),
    CHECK ((token_hash IS NULL) = (token_expires_at IS NULL)),
    CHECK (token_expires_at IS NULL OR token_expires_at > issued_at),
    CHECK (status NOT IN ('collected', 'awaiting_confirmation', 'pending_review', 'confirmed')
        OR (session_id IS NOT NULL AND collected_at IS NOT NULL)),
    CHECK (status <> 'confirmed' OR effective_at IS NOT NULL),
    CHECK ((reviewed_by IS NULL) = (reviewed_at IS NULL)),
    CHECK (reviewed_by IS NULL OR length(trim(coalesce(review_reason, ''))) > 0),
    CHECK (status <> 'rejected' OR length(trim(coalesce(review_reason, ''))) > 0)
);

CREATE UNIQUE INDEX gpm_app_crew_member_active_action_idx
    ON gpm_app_crew_attendance_members(order_id, worker_account_id, action)
    WHERE status IN ('issued', 'collected', 'awaiting_confirmation', 'pending_review', 'confirmed');

CREATE INDEX gpm_app_crew_sessions_order_idx
    ON gpm_app_crew_attendance_sessions(order_id, status, created_at);

CREATE INDEX gpm_app_crew_members_review_idx
    ON gpm_app_crew_attendance_members(order_id, status)
    WHERE status = 'pending_review';
