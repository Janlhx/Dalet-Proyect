-- =================================================================
-- Script de Migración: Tablas de Moderación de Contenido para DALET
-- =================================================================

CREATE TABLE IF NOT EXISTS ModerationConfig (
    ServerID INTEGER PRIMARY KEY,
    Enabled BOOLEAN DEFAULT 0,
    LogChannelID INTEGER,
    Action TEXT DEFAULT 'notify',
    AutoBanOnIllegal BOOLEAN DEFAULT 1,
    TimeoutMinutes INTEGER DEFAULT 10,
    ScanImages BOOLEAN DEFAULT 1,
    AntiFlood BOOLEAN DEFAULT 1,
    FilterLinks BOOLEAN DEFAULT 1,
    FilterScams BOOLEAN DEFAULT 1,
    IgnoredChannels TEXT DEFAULT '',
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ModActions (
    ActionID INTEGER PRIMARY KEY AUTOINCREMENT,
    ServerID INTEGER NOT NULL,
    ChannelID INTEGER NOT NULL,
    UserID INTEGER NOT NULL,
    UserName TEXT,
    Severity TEXT NOT NULL,
    Method TEXT NOT NULL,
    Reason TEXT,
    ActionTaken TEXT NOT NULL,
    OccurredAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_modactions_server ON ModActions(ServerID, OccurredAt DESC);
CREATE INDEX IF NOT EXISTS idx_modactions_user ON ModActions(UserID, OccurredAt DESC);
