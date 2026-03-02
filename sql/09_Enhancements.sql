-- =================================================================
-- Script: 09_Enhancements.sql
-- Descripción: Mejoras a tablas existentes para capturar información
-- más útil sin cambiar la lógica central del bot.
-- =================================================================

-- -----------------------------------------------------
-- MEJORA 1: Users — Actividad y presencia
-- -----------------------------------------------------
ALTER TABLE Users
    ADD COLUMN IF NOT EXISTS FirstSeen    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS LastSeen     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS TotalMessages INT DEFAULT 0;

-- Índice para ordenar por usuarios más activos
CREATE INDEX IF NOT EXISTS idx_users_total_messages ON Users(TotalMessages DESC);

-- Actualizar sp_RegisterOrUpdateUser para guardar LastSeen y contar mensajes
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateUser(
    p_UserID   BIGINT,
    p_UserName VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Users (UserID, UserName, FirstSeen, LastSeen, TotalMessages)
    VALUES (p_UserID, p_UserName, NOW(), NOW(), 0)
    ON CONFLICT (UserID) DO UPDATE
    SET UserName      = p_UserName,
        LastSeen      = NOW(),
        TotalMessages = Users.TotalMessages + 1;
END;
$$;

-- -----------------------------------------------------
-- MEJORA 2: Channels — Actividad del canal
-- -----------------------------------------------------
ALTER TABLE Channels
    ADD COLUMN IF NOT EXISTS TotalMessages INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS LastActivity  TIMESTAMP WITH TIME ZONE;

-- Actualizar sp_RegisterOrUpdateChannel para trackear actividad
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateChannel(
    p_ChannelID   BIGINT,
    p_ChannelName VARCHAR(255),
    p_ServerID    BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Channels (ChannelID, ChannelName, ServerID, TotalMessages, LastActivity)
    VALUES (p_ChannelID, p_ChannelName, p_ServerID, 0, NOW())
    ON CONFLICT (ChannelID) DO UPDATE
    SET ChannelName    = p_ChannelName,
        TotalMessages  = Channels.TotalMessages + 1,
        LastActivity   = NOW();
END;
$$;

-- Vista mejorada: canales más activos (reemplaza V_ChannelActivity eliminada)
CREATE OR REPLACE VIEW V_ActiveChannels AS
SELECT
    c.ChannelID,
    c.ChannelName,
    c.ServerID,
    s.ServerName,
    c.TotalMessages,
    c.LastActivity,
    c.IsProactive,
    c.CommandsLocked
FROM Channels c
JOIN Servers s ON c.ServerID = s.ServerID
ORDER BY c.TotalMessages DESC;

-- -----------------------------------------------------
-- MEJORA 3: OsuAccounts — Timestamp de última actualización
-- -----------------------------------------------------
ALTER TABLE OsuAccounts
    ADD COLUMN IF NOT EXISTS LastUpdated TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Actualizar sp_LinkOsuAccount para registrar cuándo se actualizó
CREATE OR REPLACE PROCEDURE sp_LinkOsuAccount(
    p_UserID      BIGINT,
    p_OsuUsername VARCHAR(255),
    p_OsuUserID   INT,
    p_PlayMode    VARCHAR(50),
    p_PP          FLOAT,
    p_GlobalRank  INT,
    p_CountryRank INT,
    p_Accuracy    FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO OsuAccounts (
        UserID, OsuUsername, OsuUserID, PlayMode,
        PP, GlobalRank, CountryRank, Accuracy, LastUpdated
    )
    VALUES (
        p_UserID, p_OsuUsername, p_OsuUserID, p_PlayMode,
        p_PP, p_GlobalRank, p_CountryRank, p_Accuracy, NOW()
    )
    ON CONFLICT (UserID) DO UPDATE
    SET OsuUsername  = p_OsuUsername,
        OsuUserID    = p_OsuUserID,
        PlayMode     = p_PlayMode,
        PP           = p_PP,
        GlobalRank   = p_GlobalRank,
        CountryRank  = p_CountryRank,
        Accuracy     = p_Accuracy,
        LastUpdated  = NOW();
END;
$$;

-- Vista mejorada del ranking osu! (incluye cuándo se actualizó)
CREATE OR REPLACE VIEW V_OsuRankingGlobal AS
SELECT
    u.UserName,
    oa.PP,
    oa.Accuracy,
    oa.GlobalRank,
    oa.PlayMode,
    oa.LastUpdated,
    RANK() OVER (ORDER BY oa.PP DESC) AS CalculatedRank
FROM OsuAccounts oa
JOIN Users u ON oa.UserID = u.UserID
WHERE oa.PP IS NOT NULL AND oa.PP > 0;

-- =================================================================
-- RESULTADO:
-- • Users: FirstSeen, LastSeen, TotalMessages
-- • Channels: TotalMessages, LastActivity → Vista V_ActiveChannels
-- • OsuAccounts: LastUpdated en cada d.link
-- =================================================================
