-- =================================================================
-- Script: 10_New_Tables.sql
-- Descripción: Crea las nuevas tablas de analítica y monitoreo
-- que expanden la utilidad de la base de datos de Dalet.
-- =================================================================

-- -----------------------------------------------------
-- TABLA 1: CommandUsage — Estadísticas de uso de comandos
-- Registra cada vez que se ejecuta un comando: quién, dónde y si tuvo éxito.
-- Permite identificar comandos populares, muertos o con alta tasa de error.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS CommandUsage (
    UsageID     SERIAL PRIMARY KEY,
    CommandName VARCHAR(100)               NOT NULL,
    UserID      BIGINT                     NOT NULL,
    ServerID    BIGINT                     NOT NULL,
    ChannelID   BIGINT                     NOT NULL,
    Success     BOOLEAN                    DEFAULT TRUE,
    ExecutedAt  TIMESTAMP WITH TIME ZONE   DEFAULT NOW(),
    FOREIGN KEY (UserID)   REFERENCES Users(UserID)   ON DELETE CASCADE,
    FOREIGN KEY (ServerID) REFERENCES Servers(ServerID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cmdusage_command    ON CommandUsage(CommandName);
CREATE INDEX IF NOT EXISTS idx_cmdusage_server     ON CommandUsage(ServerID);
CREATE INDEX IF NOT EXISTS idx_cmdusage_user       ON CommandUsage(UserID);
CREATE INDEX IF NOT EXISTS idx_cmdusage_time       ON CommandUsage(ExecutedAt DESC);

-- Procedimiento para registrar uso de comando (llamado desde Python)
CREATE OR REPLACE PROCEDURE sp_LogCommandUsage(
    p_CommandName VARCHAR(100),
    p_UserID      BIGINT,
    p_UserName    VARCHAR(255),
    p_ServerID    BIGINT,
    p_ChannelID   BIGINT,
    p_Success     BOOLEAN DEFAULT TRUE
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Asegurarse de que el usuario exista
    INSERT INTO Users (UserID, UserName)
    VALUES (p_UserID, p_UserName)
    ON CONFLICT (UserID) DO UPDATE SET UserName = p_UserName;

    INSERT INTO CommandUsage (CommandName, UserID, ServerID, ChannelID, Success)
    VALUES (p_CommandName, p_UserID, p_ServerID, p_ChannelID, p_Success);
END;
$$;

-- Vista: Top comandos + tasa de éxito
CREATE OR REPLACE VIEW V_CommandStats AS
SELECT
    CommandName,
    COUNT(*) AS total_uses,
    COUNT(*) FILTER (WHERE Success = TRUE)  AS successful,
    COUNT(*) FILTER (WHERE Success = FALSE) AS failed,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE Success = TRUE) / NULLIF(COUNT(*), 0),
        1
    ) AS success_rate_pct,
    MAX(ExecutedAt) AS last_used
FROM CommandUsage
GROUP BY CommandName
ORDER BY total_uses DESC;

-- -----------------------------------------------------
-- TABLA 2: OsuHistory — Historial de progreso osu!
-- Snapshot del PP/rank de un jugador. 
-- Limitado a 1 REGISTRO POR DÍA por usuario mediante restricción UNIQUE.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS OsuHistory (
    HistoryID   SERIAL PRIMARY KEY,
    UserID      BIGINT                   NOT NULL,
    LogDate     DATE                     NOT NULL DEFAULT CURRENT_DATE,
    PP          FLOAT,
    GlobalRank  INT,
    CountryRank INT,
    Accuracy    FLOAT,
    PlayMode    VARCHAR(50),
    RecordedAt  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    UNIQUE (UserID, LogDate) -- Evita duplicados el mismo día
);

CREATE INDEX IF NOT EXISTS idx_osuhistory_user ON OsuHistory(UserID);
CREATE INDEX IF NOT EXISTS idx_osuhistory_date ON OsuHistory(LogDate DESC);

-- Procedimiento: guarda o actualiza el snapshot del DÍA ACTUAL
CREATE OR REPLACE PROCEDURE sp_RecordOsuSnapshot(
    p_UserID      BIGINT,
    p_PP          FLOAT,
    p_GlobalRank  INT,
    p_CountryRank INT,
    p_Accuracy    FLOAT,
    p_PlayMode    VARCHAR(50)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO OsuHistory (UserID, LogDate, PP, GlobalRank, CountryRank, Accuracy, PlayMode, RecordedAt)
    VALUES (p_UserID, CURRENT_DATE, p_PP, p_GlobalRank, p_CountryRank, p_Accuracy, p_PlayMode, NOW())
    ON CONFLICT (UserID, LogDate) DO UPDATE
    SET PP          = EXCLUDED.PP,
        GlobalRank  = EXCLUDED.GlobalRank,
        CountryRank = EXCLUDED.CountryRank,
        Accuracy    = EXCLUDED.Accuracy,
        PlayMode    = EXCLUDED.PlayMode,
        RecordedAt  = EXCLUDED.RecordedAt;
END;
$$;

-- Función: obtener progreso de PP de un jugador
CREATE OR REPLACE FUNCTION fn_GetOsuProgress(
    p_UserID BIGINT,
    p_Limit  INT DEFAULT 10
)
RETURNS TABLE(
    recorded_at  TIMESTAMP WITH TIME ZONE,
    pp           FLOAT,
    global_rank  INT,
    pp_change    FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        oh.RecordedAt,
        oh.PP,
        oh.GlobalRank,
        oh.PP - LAG(oh.PP, 1) OVER (ORDER BY oh.RecordedAt ASC) AS pp_change
    FROM OsuHistory oh
    WHERE oh.UserID = p_UserID
    ORDER BY oh.RecordedAt DESC
    LIMIT p_Limit;
END;
$$;

-- Vista: Jugadores con mayor ganancia de PP en los últimos 30 días
CREATE OR REPLACE VIEW V_OsuTopImprovers AS
SELECT
    u.UserName,
    oa.PlayMode,
    MAX(oh.PP) - MIN(oh.PP) AS pp_gained,
    MIN(oh.PP)              AS pp_start,
    MAX(oh.PP)              AS pp_end,
    COUNT(oh.HistoryID)     AS snapshots
FROM OsuHistory oh
JOIN Users u      ON oh.UserID = u.UserID
JOIN OsuAccounts oa ON oh.UserID = oa.UserID
WHERE oh.RecordedAt > NOW() - INTERVAL '30 days'
GROUP BY u.UserName, oa.PlayMode
HAVING COUNT(oh.HistoryID) >= 2
ORDER BY pp_gained DESC;

-- -----------------------------------------------------
-- TABLA 3: AIInteractions — Métricas de respuestas de Dalet
-- Registra cada respuesta de la IA: tipo de trigger, proveedor,
-- tiempo de respuesta y si fue exitosa.
-- Útil para ajustar parámetros de proactividad con datos reales.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS AIInteractions (
    InteractionID  SERIAL PRIMARY KEY,
    ServerID       BIGINT                   NOT NULL,
    ChannelID      BIGINT                   NOT NULL,
    TriggerType    VARCHAR(20)              NOT NULL, -- 'mention', 'proactive', 'name_trigger'
    Provider       VARCHAR(20),                       -- 'gemini', 'groq', 'groq_fallback'
    ResponseTimeMs INT,                               -- Latencia en ms
    Success        BOOLEAN                  DEFAULT TRUE,
    InteractedAt   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (ServerID)  REFERENCES Servers(ServerID)  ON DELETE CASCADE,
    FOREIGN KEY (ChannelID) REFERENCES Channels(ChannelID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aiint_server  ON AIInteractions(ServerID);
CREATE INDEX IF NOT EXISTS idx_aiint_channel ON AIInteractions(ChannelID);
CREATE INDEX IF NOT EXISTS idx_aiint_time    ON AIInteractions(InteractedAt DESC);
CREATE INDEX IF NOT EXISTS idx_aiint_trigger ON AIInteractions(TriggerType);

-- Procedimiento para loguear interacción de la IA
CREATE OR REPLACE PROCEDURE sp_LogAIInteraction(
    p_ServerID      BIGINT,
    p_ChannelID     BIGINT,
    p_TriggerType   VARCHAR(20),
    p_Provider      VARCHAR(20),
    p_ResponseTimeMs INT,
    p_Success       BOOLEAN DEFAULT TRUE
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO AIInteractions (ServerID, ChannelID, TriggerType, Provider, ResponseTimeMs, Success)
    VALUES (p_ServerID, p_ChannelID, p_TriggerType, p_Provider, p_ResponseTimeMs, p_Success);
END;
$$;

-- Vista: Resumen de actividad de la IA por servidor
CREATE OR REPLACE VIEW V_AIActivitySummary AS
SELECT
    s.ServerName,
    ai.TriggerType,
    ai.Provider,
    COUNT(*)                                        AS total_interactions,
    ROUND(AVG(ai.ResponseTimeMs))                   AS avg_response_ms,
    COUNT(*) FILTER (WHERE ai.Success = FALSE)      AS errors,
    MAX(ai.InteractedAt)                            AS last_interaction
FROM AIInteractions ai
JOIN Servers s ON ai.ServerID = s.ServerID
GROUP BY s.ServerName, ai.TriggerType, ai.Provider
ORDER BY total_interactions DESC;

-- Vista: Horas pico de actividad de la IA (global)
CREATE OR REPLACE VIEW V_AIHourlyActivity AS
SELECT
    EXTRACT(HOUR FROM InteractedAt)::INT AS hour_of_day,
    COUNT(*)                             AS interactions,
    ROUND(AVG(ResponseTimeMs))           AS avg_response_ms
FROM AIInteractions
WHERE InteractedAt > NOW() - INTERVAL '7 days'
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- -----------------------------------------------------
-- TABLA 4: BotErrors — Registro persistente de errores
-- Los errores crítcos del bot sobreviven a los reinicios en Render.
-- Permite diagnóstico histórico sin depender de dalet.log
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS BotErrors (
    ErrorID      SERIAL PRIMARY KEY,
    ErrorType    VARCHAR(100),   -- 'discord_429', 'db_error', 'gemini_quota', 'gemini_error', etc.
    ErrorMsg     TEXT,           -- Mensaje de excepción
    Context      VARCHAR(255),   -- Handler/módulo donde ocurrió
    ServerID     BIGINT,         -- Opcional, puede ser NULL
    OccurredAt   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_boterrors_type ON BotErrors(ErrorType);
CREATE INDEX IF NOT EXISTS idx_boterrors_time ON BotErrors(OccurredAt DESC);

-- Procedimiento para registrar errores
CREATE OR REPLACE PROCEDURE sp_LogBotError(
    p_ErrorType VARCHAR(100),
    p_ErrorMsg  TEXT,
    p_Context   VARCHAR(255),
    p_ServerID  BIGINT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO BotErrors (ErrorType, ErrorMsg, Context, ServerID)
    VALUES (p_ErrorType, p_ErrorMsg, p_Context, p_ServerID);
END;
$$;

-- Vista: Errores más frecuentes de los últimos 7 días
CREATE OR REPLACE VIEW V_RecentErrors AS
SELECT
    ErrorType,
    Context,
    COUNT(*)           AS occurrences,
    MAX(OccurredAt)    AS last_seen,
    MIN(OccurredAt)    AS first_seen
FROM BotErrors
WHERE OccurredAt > NOW() - INTERVAL '7 days'
GROUP BY ErrorType, Context
ORDER BY occurrences DESC;

-- =================================================================
-- RESUMEN DE TABLAS CREADAS:
--
--  CommandUsage   → Analítica de comandos + V_CommandStats
--  OsuHistory     → Progreso de jugadores + fn_GetOsuProgress + V_OsuTopImprovers
--  AIInteractions → Métricas de IA + V_AIActivitySummary + V_AIHourlyActivity
--  BotErrors      → Errores persistentes + V_RecentErrors
--
-- TOTAL NUEVAS VISTAS: 6
-- TOTAL NUEVOS PROCEDIMIENTOS/FUNCIONES: 5
-- =================================================================
