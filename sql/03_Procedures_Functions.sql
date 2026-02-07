-- =================================================================
-- Script para la Creación de Procedimientos Almacenados de DALET
-- =================================================================

-- -----------------------------------------------------
-- Procedimiento: sp_RegisterOrUpdateUser
-- Descripción: Registra un nuevo usuario o actualiza su nombre si ya existe.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateUser(
    p_UserID BIGINT,
    p_UserName VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Users (UserID, UserName)
    VALUES (p_UserID, p_UserName)
    ON CONFLICT (UserID) DO UPDATE
    SET UserName = p_UserName;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_LinkOsuAccount
-- Descripción: Vincula cuenta de osu! y guarda estadísticas clave.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_LinkOsuAccount(
    p_UserID BIGINT,
    p_OsuUsername VARCHAR(255),
    p_OsuUserID INT,
    p_PlayMode VARCHAR(50),
    p_PP FLOAT,
    p_GlobalRank INT,
    p_CountryRank INT,
    p_Accuracy FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO OsuAccounts (
        UserID, OsuUsername, OsuUserID, PlayMode, 
        PP, GlobalRank, CountryRank, Accuracy
    )
    VALUES (
        p_UserID, p_OsuUsername, p_OsuUserID, p_PlayMode,
        p_PP, p_GlobalRank, p_CountryRank, p_Accuracy
    )
    ON CONFLICT (UserID) DO UPDATE
    SET OsuUsername = p_OsuUsername,
        OsuUserID = p_OsuUserID,
        PlayMode = p_PlayMode,
        PP = p_PP,
        GlobalRank = p_GlobalRank,
        CountryRank = p_CountryRank,
        Accuracy = p_Accuracy;
END;
$$;

-- -----------------------------------------------------
-- Función: fn_GetOsuUsername
-- Descripción: Obtiene el nombre de usuario de osu! vinculado a un UserID.
-- -----------------------------------------------------
CREATE OR REPLACE FUNCTION fn_GetOsuUsername(
    p_UserID BIGINT
)
RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    v_OsuUsername VARCHAR;
BEGIN
    SELECT OsuUsername
    INTO v_OsuUsername
    FROM OsuAccounts
    WHERE UserID = p_UserID
    LIMIT 1;

    RETURN v_OsuUsername;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_UnlinkOsuAccount
-- Descripción: Elimina la vinculación de una cuenta de osu! de un usuario.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_UnlinkOsuAccount(
    p_UserID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM OsuAccounts
    WHERE UserID = p_UserID;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_RegisterOrUpdateServer
-- Descripción: Registra un servidor si no existe, o actualiza su nombre.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateServer(
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName)
    VALUES (p_ServerID, p_ServerName)
    ON CONFLICT (ServerID) DO UPDATE
    SET ServerName = p_ServerName;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_RegisterOrUpdateChannel
-- Descripción: Registra un canal si no existe, o actualiza su nombre.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateChannel(
    p_ChannelID BIGINT,
    p_ChannelName VARCHAR(255),
    p_ServerID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Channels (ChannelID, ChannelName, ServerID)
    VALUES (p_ChannelID, p_ChannelName, p_ServerID)
    ON CONFLICT (ChannelID) DO UPDATE
    SET ChannelName = p_ChannelName;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_LogMessage
-- Descripción: Guarda un mensaje y asegura integridad de IDs.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_LogMessage(
    p_UserID BIGINT,
    p_UserName VARCHAR(255),
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255),
    p_ChannelID BIGINT,
    p_ChannelName VARCHAR(255),
    p_Content TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    CALL sp_RegisterOrUpdateServer(p_ServerID, p_ServerName);
    CALL sp_RegisterOrUpdateChannel(p_ChannelID, p_ChannelName, p_ServerID);
    CALL sp_RegisterOrUpdateUser(p_UserID, p_UserName);
    
    INSERT INTO Messages (Content, Timestamp, UserID, ChannelID)
    VALUES (p_Content, NOW(), p_UserID, p_ChannelID);
END;
$$;

-- -----------------------------------------------------
-- Procedimientos para Configuración
-- -----------------------------------------------------

CREATE OR REPLACE PROCEDURE sp_AddRolePermission(
    p_ServerID BIGINT,
    p_RoleID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName)
    VALUES (p_ServerID, 'Unknown')
    ON CONFLICT (ServerID) DO NOTHING;

    INSERT INTO RolePermissions (ServerID, RoleID)
    VALUES (p_ServerID, p_RoleID)
    ON CONFLICT (ServerID, RoleID) DO NOTHING;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_RemoveRolePermission(
    p_ServerID BIGINT,
    p_RoleID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM RolePermissions
    WHERE ServerID = p_ServerID AND RoleID = p_RoleID;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_ClearRolePermissions(
    p_ServerID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM RolePermissions
    WHERE ServerID = p_ServerID;
END;
$$;

CREATE OR REPLACE FUNCTION fn_GetRolePermissions(
    p_ServerID BIGINT
)
RETURNS BIGINT[]
LANGUAGE plpgsql
AS $$
DECLARE
    v_RoleIDs BIGINT[];
BEGIN
    SELECT COALESCE(array_agg(RoleID), ARRAY[]::BIGINT[])
    INTO v_RoleIDs
    FROM RolePermissions
    WHERE ServerID = p_ServerID;
    
    RETURN v_RoleIDs;
END;
$$;

CREATE OR REPLACE FUNCTION fn_CheckRolePermission(
    p_ServerID BIGINT,
    p_UserRoleIDs BIGINT[]
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM RolePermissions
        WHERE ServerID = p_ServerID
        AND RoleID = ANY(p_UserRoleIDs)
    );
END;
$$;

-- -----------------------------------------------------
-- Procedimientos para Proactividad de Canales
-- -----------------------------------------------------

CREATE OR REPLACE PROCEDURE sp_SetChannelProactive(
    p_ChannelID BIGINT,
    p_ChannelName VARCHAR(255),
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255),
    p_IsProactive BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    CALL sp_RegisterOrUpdateServer(p_ServerID, p_ServerName);
    CALL sp_RegisterOrUpdateChannel(p_ChannelID, p_ChannelName, p_ServerID);
    
    UPDATE Channels
    SET IsProactive = p_IsProactive
    WHERE ChannelID = p_ChannelID;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_ClearProactiveChannels(
    p_ServerID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE Channels
    SET IsProactive = FALSE
    WHERE ServerID = p_ServerID;
END;
$$;

CREATE OR REPLACE FUNCTION fn_GetProactiveChannels(
    p_ServerID BIGINT
)
RETURNS BIGINT[]
LANGUAGE plpgsql
AS $$
DECLARE
    v_ChannelIDs BIGINT[];
BEGIN
    SELECT COALESCE(array_agg(ChannelID), ARRAY[]::BIGINT[])
    INTO v_ChannelIDs
    FROM Channels
    WHERE ServerID = p_ServerID AND IsProactive = TRUE;
    
    RETURN v_ChannelIDs;
END;
$$;

-- -----------------------------------------------------
-- Procedimientos para Reactividad de Servidores
-- -----------------------------------------------------

CREATE OR REPLACE PROCEDURE sp_SetServerReactive(
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255),
    p_IsReactive BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName, IsReactive)
    VALUES (p_ServerID, p_ServerName, p_IsReactive)
    ON CONFLICT (ServerID) DO UPDATE
    SET ServerName = p_ServerName,
        IsReactive = p_IsReactive;
END;
$$;

CREATE OR REPLACE FUNCTION fn_IsServerReactive(
    p_ServerID BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_IsReactive BOOLEAN;
BEGIN
    SELECT IsReactive INTO v_IsReactive
    FROM Servers
    WHERE ServerID = p_ServerID;
    
    RETURN COALESCE(v_IsReactive, TRUE);
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_SaveOrUpdateOsuScore
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_SaveOrUpdateOsuScore(
    p_ScoreID BIGINT,
    p_UserID BIGINT,
    p_OsuUserID INT,
    p_BeatmapID INT,
    p_Score INT,
    p_Accuracy NUMERIC,
    p_Mods VARCHAR(100),
    p_ScoreType VARCHAR(50),
    p_Timestamp TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO OsuScores (
        ScoreID, UserID, BeatmapID, Score,
        Accuracy, Mods, ScoreType, Timestamp
    )
    VALUES (
        p_ScoreID, p_UserID, p_BeatmapID, p_Score,
        p_Accuracy, p_Mods, p_ScoreType, p_Timestamp
    )
    ON CONFLICT (ScoreID) DO UPDATE
    SET
        Accuracy = p_Accuracy,
        Mods = p_Mods,
        ScoreType = p_ScoreType,
        Timestamp = p_Timestamp;
END;
$$;

-- -----------------------------------------------------
-- Procedimientos para SmartResume
-- -----------------------------------------------------

CREATE OR REPLACE PROCEDURE sp_SaveSummary(
    p_ChannelID BIGINT,
    p_SummaryText TEXT,
    p_MensajesResumidos INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Channels (ChannelID, ChannelName, ServerID)
    VALUES (p_ChannelID, 'Unknown', 0)
    ON CONFLICT (ChannelID) DO NOTHING;

    INSERT INTO Summaries (GeneratedDate, SummaryText, ChannelID)
    VALUES (NOW(), p_SummaryText, p_ChannelID);
END;
$$;

CREATE TYPE summary_record AS (
    generated_date TIMESTAMP,
    summary_text TEXT
);

CREATE OR REPLACE FUNCTION fn_GetRecentSummaries(
    p_ChannelID BIGINT,
    p_Limit INT DEFAULT 5
)
RETURNS SETOF summary_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT s.GeneratedDate, s.SummaryText
    FROM Summaries s
    WHERE s.ChannelID = p_ChannelID
    ORDER BY s.GeneratedDate DESC
    LIMIT p_Limit;
END;
$$;

CREATE OR REPLACE FUNCTION fn_GetSummaryByIndex(
    p_ChannelID BIGINT,
    p_Index INT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_SummaryText TEXT;
BEGIN
    SELECT s.SummaryText
    INTO v_SummaryText
    FROM Summaries s
    WHERE s.ChannelID = p_ChannelID
    ORDER BY s.GeneratedDate DESC
    OFFSET (p_Index - 1)
    LIMIT 1;

    RETURN v_SummaryText;
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_AddUserMemory
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_AddUserMemory(
    p_UserID BIGINT,
    p_UserName VARCHAR(255),
    p_Content TEXT,
    p_Topic VARCHAR(100) DEFAULT 'general',
    p_MaxMemories INT DEFAULT 20
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_memory_count INT;
    v_oldest_memory_id INT;
BEGIN
    CALL sp_RegisterOrUpdateUser(p_UserID, p_UserName);

    INSERT INTO UserMemories (UserID, Topic, Content, Timestamp)
    VALUES (p_UserID, p_Topic, p_Content, NOW());

    SELECT COUNT(*) INTO v_memory_count
    FROM UserMemories
    WHERE UserID = p_UserID;

    IF v_memory_count > p_MaxMemories THEN
        SELECT MemoryID INTO v_oldest_memory_id
        FROM UserMemories
        WHERE UserID = p_UserID
        ORDER BY Timestamp ASC
        LIMIT 1;

        DELETE FROM UserMemories
        WHERE MemoryID = v_oldest_memory_id;
    END IF;
END;
$$;

CREATE TYPE user_memory_record AS (
    topic VARCHAR(100),
    content TEXT
);

CREATE OR REPLACE FUNCTION fn_GetAllUserMemories(
    p_UserID BIGINT
)
RETURNS SETOF user_memory_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT um.Topic, um.Content
    FROM UserMemories um
    WHERE um.UserID = p_UserID
    ORDER BY um.Timestamp DESC;
END;
$$;

-- -----------------------------------------------------
-- Lógica de Estadísticas
-- -----------------------------------------------------

CREATE TYPE user_stats_record AS (
    msg_count BIGINT,
    score_count BIGINT,
    last_msg_timestamp TIMESTAMP WITH TIME ZONE
);

CREATE OR REPLACE FUNCTION fn_GetUserStats(p_user_id BIGINT)
RETURNS SETOF user_stats_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH UserMessages AS (
        SELECT 
            COUNT(*) as MsgCount, 
            MAX(Timestamp) as LastMsg
        FROM Messages
        WHERE UserID = p_user_id
    ),
    UserScores AS (
        SELECT 
            COUNT(*) as ScoreCount
        FROM OsuScores
        WHERE UserID = p_user_id
    )
    SELECT 
        um.MsgCount, 
        us.ScoreCount, 
        um.LastMsg
    FROM UserMessages um, UserScores us;
END;
$$;

CREATE TYPE score_comparison_record AS (
    score_timestamp TIMESTAMP WITH TIME ZONE,
    accuracy NUMERIC,
    accuracy_change NUMERIC
);

CREATE OR REPLACE FUNCTION fn_GetScoreHistory(p_user_id BIGINT, p_limit INT DEFAULT 10)
RETURNS SETOF score_comparison_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH RankedScores AS (
        SELECT
            Timestamp,
            Accuracy,
            LAG(Accuracy, 1) OVER (ORDER BY Timestamp ASC) as PreviousAccuracy
        FROM OsuScores
        WHERE UserID = p_user_id AND ScoreType = 'best'
    )
    SELECT
        rs.Timestamp,
        rs.Accuracy,
        (rs.Accuracy - rs.PreviousAccuracy) as AccuracyChange
    FROM RankedScores rs
    ORDER BY rs.Timestamp DESC
    LIMIT p_limit;
END;
$$;
