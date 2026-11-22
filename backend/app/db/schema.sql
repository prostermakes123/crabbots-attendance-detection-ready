-- CrabBots Attendance schema (SQLite)
-- Embeddings and attendance are append-only-ish; biometric data is stored as
-- normalised float32 BLOBs and is never exposed through the HTTP API.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS members (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    consent       INTEGER NOT NULL DEFAULT 0,
    consent_at    TEXT,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    thumbnail     TEXT,              -- file name under data/thumbnails, may be NULL
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id  TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    vector     BLOB NOT NULL,
    dim        INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_embeddings_member ON embeddings(member_id);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active',  -- active | ended
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at   TEXT,
    is_demo    INTEGER NOT NULL DEFAULT 0,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id             TEXT PRIMARY KEY,
    member_id      TEXT REFERENCES members(id) ON DELETE SET NULL,
    member_name    TEXT NOT NULL,
    session_id     TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    timestamp      TEXT NOT NULL,
    confidence     REAL NOT NULL,
    method         TEXT NOT NULL,   -- live | photo | video | manual
    track_id       INTEGER,
    source         TEXT,            -- camera label / file name
    status         TEXT NOT NULL DEFAULT 'present',  -- present | removed
    removed_at     TEXT,
    removed_reason TEXT,
    removed_by     TEXT,
    is_demo        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_attendance_time ON attendance(timestamp);
CREATE INDEX IF NOT EXISTS ix_attendance_session ON attendance(session_id);
CREATE INDEX IF NOT EXISTS ix_attendance_member ON attendance(member_id);

-- One present record per member per session: the core duplicate guard.
CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_session_member
    ON attendance(session_id, member_id)
    WHERE status = 'present' AND member_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS unknown_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    timestamp  TEXT NOT NULL,
    track_id   INTEGER,
    confidence REAL,
    source     TEXT
);

CREATE INDEX IF NOT EXISTS ix_unknown_time ON unknown_events(timestamp);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   TEXT,
    actor       TEXT,
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS ix_audit_time ON audit_log(timestamp);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
