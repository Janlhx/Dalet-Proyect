-- =================================================================
-- Script: 13_Migration_Reminders.sql
-- Descripción: Agrega la tabla Reminders a la base de datos PostgreSQL remota
-- =================================================================

CREATE TABLE IF NOT EXISTS Reminders (
    ReminderID   SERIAL PRIMARY KEY,
    ServerID     BIGINT NOT NULL REFERENCES Servers(ServerID) ON DELETE CASCADE,
    ChannelID    BIGINT NOT NULL REFERENCES Channels(ChannelID) ON DELETE CASCADE,
    UserID       BIGINT NOT NULL REFERENCES Users(UserID) ON DELETE CASCADE,
    ReminderTime VARCHAR(5) NOT NULL,
    ReminderDays VARCHAR(100) NOT NULL,
    Message      TEXT DEFAULT '¡Es hora del mapa del día!',
    Timezone     VARCHAR(50) DEFAULT 'America/Bogota',
    Active       BOOLEAN DEFAULT TRUE,
    CreatedAt    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
