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
-- Procedimiento: sp_LinkOsuAccount (¡VERSIÓN 2.0 - Con Stats!)
-- Descripción: Vincula cuenta de osu! y guarda estadísticas clave.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_LinkOsuAccount(
    p_UserID BIGINT,
    p_OsuUsername VARCHAR(255),
    p_OsuUserID INT,
    p_PlayMode VARCHAR(50), -- Parámetro nuevo
    p_PP FLOAT,             -- Parámetro nuevo
    p_GlobalRank INT,       -- Parámetro nuevo
    p_CountryRank INT,      -- Parámetro nuevo
    p_Accuracy FLOAT        -- Parámetro nuevo
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
        PlayMode = p_PlayMode, -- Actualizar stats si ya existe
        PP = p_PP,
        GlobalRank = p_GlobalRank,
        CountryRank = p_CountryRank,
        Accuracy = p_Accuracy;
END;
$$;

-- -----------------------------------------------------
-- Función: fn_GetOsuUsername (¡VERSIÓN CORREGIDA!)
-- Descripción: Obtiene el nombre de usuario de osu! vinculado a un UserID.
-- -----------------------------------------------------
CREATE OR REPLACE FUNCTION fn_GetOsuUsername(
    p_UserID BIGINT
)
RETURNS VARCHAR -- Devuelve VARCHAR (el nombre de usuario)
LANGUAGE plpgsql
AS $$
DECLARE
    v_OsuUsername VARCHAR; -- Variable para guardar el resultado
BEGIN
    -- Busca el OsuUsername en la tabla OsuAccounts donde coincida el UserID
    SELECT OsuUsername
    INTO v_OsuUsername -- Guarda el resultado en la variable
    FROM OsuAccounts
    WHERE UserID = p_UserID
    LIMIT 1; -- Asegura que solo devuelva una fila si hubiera duplicados (no debería)

    -- Devuelve el nombre encontrado o NULL si no se encontró ninguna fila
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
-- Procedimiento: sp_LogMessage (¡VERSIÓN 2.0 ACTUALIZADA!)
-- Descripción: Guarda un mensaje, asegurándose de que el usuario,
--              el servidor y el canal existan primero.
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
    -- Paso 1: Asegurarse de que el servidor existe
    CALL sp_RegisterOrUpdateServer(p_ServerID, p_ServerName);
    
    -- Paso 2: Asegurarse de que el canal existe
    CALL sp_RegisterOrUpdateChannel(p_ChannelID, p_ChannelName, p_ServerID);
    
    -- Paso 3: Asegurarse de que el usuario existe (ya lo teníamos)
    CALL sp_RegisterOrUpdateUser(p_UserID, p_UserName);
    
    -- Paso 4: Ahora sí, insertar el mensaje
    INSERT INTO Messages (Content, Timestamp, UserID, ChannelID)
    VALUES (p_Content, NOW(), p_UserID, p_ChannelID);
END;
$$;

-- =================================================================
-- Script de Procedimientos para Comandos de Configuración (Gemini)
-- =================================================================

-- -----------------------------------------------------
-- Procedimientos para 'RolePermissions' (reemplaza roles_permitidos.json)
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_AddRolePermission(
    p_ServerID BIGINT,
    p_RoleID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName)
    VALUES (p_ServerID, 'Nombre de Servidor Desconocido')
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

-- Función que devuelve un array de IDs de roles permitidos
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

-- Función que verifica si un usuario tiene permiso
CREATE OR REPLACE FUNCTION fn_CheckRolePermission(
    p_ServerID BIGINT,
    p_UserRoleIDs BIGINT[] -- Acepta un array de IDs de roles del usuario
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
-- Procedimientos para 'Channels' (reemplaza canales_permitidos.json)
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

-- Función que devuelve un array de IDs de canales proactivos
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
-- Procedimientos para 'Servers' (reemplaza reactive_settings.json)
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

-- Función que verifica si un servidor es reactivo
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
    
    -- Por defecto, un servidor es reactivo (TRUE) si no se encuentra registro
    RETURN COALESCE(v_IsReactive, TRUE);
END;
$$;

-- -----------------------------------------------------
-- Procedimiento: sp_SaveOrUpdateOsuScore (¡VERSIÓN 3.0 - Tipos Corregidos!)
-- Descripción: Guarda o actualiza una jugada, aceptando los tipos correctos.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_SaveOrUpdateOsuScore(
    p_ScoreID BIGINT,         -- Score ID sigue siendo BIGINT
    p_UserID BIGINT,          -- UserID de Discord (el que relaciona con OsuAccounts)
    p_OsuUserID INT,          -- ID de Osu! del jugador (nuevo parámetro)
    p_BeatmapID INT,          -- Beatmap ID sigue INT
    p_Score INT,              -- Score sigue INT
    p_Accuracy NUMERIC,       -- Cambiado a NUMERIC para coincidir
    p_Mods VARCHAR(100),    -- Mantenemos VARCHAR
    p_ScoreType VARCHAR(50),  -- Mantenemos VARCHAR
    p_Timestamp TIMESTAMP WITH TIME ZONE -- Cambiado a TIMESTAMP WITH TIME ZONE
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

-- =================================================================
-- Script de Procedimientos/Funciones para Resúmenes (SmartResume)
-- =================================================================

-- -----------------------------------------------------
-- Procedimiento: sp_SaveSummary
-- Descripción: Guarda un nuevo resumen generado en la tabla Summaries.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_SaveSummary(
    p_ChannelID BIGINT,
    p_SummaryText TEXT,
    p_MensajesResumidos INT -- (Opcional, si quieres guardar este dato)
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Asegurarse de que el canal existe (buena práctica, aunque ya debería existir)
    INSERT INTO Channels (ChannelID, ChannelName, ServerID)
    VALUES (p_ChannelID, 'Nombre Desconocido', 0) -- Usamos valores por defecto si no lo tenemos
    ON CONFLICT (ChannelID) DO NOTHING;

    -- Insertar el nuevo resumen
    INSERT INTO Summaries (GeneratedDate, SummaryText, ChannelID)
    VALUES (NOW(), p_SummaryText, p_ChannelID);
END;
$$;


-- -----------------------------------------------------
-- Función: fn_GetRecentSummaries
-- Descripción: Devuelve los 'N' resúmenes más recientes para un canal.
-- -----------------------------------------------------
-- Primero, creamos un tipo de dato para representar un resumen
CREATE TYPE summary_record AS (
    generated_date TIMESTAMP,
    summary_text TEXT
);

-- Ahora, la función que devuelve una tabla de esos registros
CREATE OR REPLACE FUNCTION fn_GetRecentSummaries(
    p_ChannelID BIGINT,
    p_Limit INT DEFAULT 5 -- Por defecto devuelve 5
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

-- -----------------------------------------------------
-- Función: fn_GetSummaryByIndex (Opcional, para comparar)
-- Descripción: Devuelve un resumen específico por su "índice".
-- -----------------------------------------------------
CREATE OR REPLACE FUNCTION fn_GetSummaryByIndex(
    p_ChannelID BIGINT,
    p_Index INT -- 1 para el más reciente, 2 para el segundo más reciente, etc.
)
RETURNS TEXT -- Devuelve solo el texto del resumen
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
    OFFSET (p_Index - 1) -- OFFSET N salta las primeras N filas
    LIMIT 1;

    RETURN v_SummaryText;
END;
$$;

-- =================================================================
-- Script para la Tabla y Funciones de UserMemories
-- =================================================================

-- -----------------------------------------------------
-- Procedimiento: sp_AddUserMemory
-- Descripción: Guarda un nuevo recuerdo para un usuario, limitando el historial.
-- -----------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_AddUserMemory(
    p_UserID BIGINT,
    p_UserName VARCHAR(255), -- Para asegurar que el usuario exista
    p_Content TEXT,
    p_Topic VARCHAR(100) DEFAULT 'general',
    p_MaxMemories INT DEFAULT 20 -- Límite de recuerdos por usuario (como tenías)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_memory_count INT;
    v_oldest_memory_id INT;
BEGIN
    -- Asegurar que el usuario exista en la tabla Users
    CALL sp_RegisterOrUpdateUser(p_UserID, p_UserName);

    -- Insertar el nuevo recuerdo
    INSERT INTO UserMemories (UserID, Topic, Content, Timestamp)
    VALUES (p_UserID, p_Topic, p_Content, NOW());

    -- Contar cuántos recuerdos tiene ahora el usuario
    SELECT COUNT(*) INTO v_memory_count
    FROM UserMemories
    WHERE UserID = p_UserID;

    -- Si excedió el límite, borrar el más antiguo
    IF v_memory_count > p_MaxMemories THEN
        -- Encontrar el ID del recuerdo más antiguo para este usuario
        SELECT MemoryID INTO v_oldest_memory_id
        FROM UserMemories
        WHERE UserID = p_UserID
        ORDER BY Timestamp ASC
        LIMIT 1;

        -- Borrar ese recuerdo específico
        DELETE FROM UserMemories
        WHERE MemoryID = v_oldest_memory_id;
    END IF;
END;
$$;


-- -----------------------------------------------------
-- Función: fn_GetAllUserMemories
-- Descripción: Devuelve TODOS los recuerdos de un usuario.
-- -----------------------------------------------------
-- Creamos un tipo para el registro de memoria de usuario
CREATE TYPE user_memory_record AS (
    topic VARCHAR(100),
    content TEXT
);

-- Función que devuelve la tabla de recuerdos
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
    ORDER BY um.Timestamp DESC; -- Devolver los más recientes primero
END;
$$;

-- =================================================================
-- Script de Funciones con CTEs (Requisito 4d y 5)
-- =================================================================

-- -----------------------------------------------------
-- CTE 1: fn_GetUserStats (Cumple Req. 4d)
-- -----------------------------------------------------

-- 1. Creamos el tipo de dato que devolverá la función
CREATE TYPE user_stats_record AS (
    msg_count BIGINT,
    score_count BIGINT,
    last_msg_timestamp TIMESTAMP WITH TIME ZONE
);

-- 2. Creamos la función
CREATE OR REPLACE FUNCTION fn_GetUserStats(p_user_id BIGINT)
RETURNS SETOF user_stats_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    -- Req 4d: Inicio de CTE
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
    -- Fin de CTE
    SELECT 
        um.MsgCount, 
        us.ScoreCount, 
        um.LastMsg
    FROM UserMessages um, UserScores us;
END;
$$;


-- -----------------------------------------------------
-- CTE 2: fn_GetScoreHistory (Cumple Req. 4d y 5a - Función de Ventana)
-- -----------------------------------------------------

-- 1. Creamos el tipo de dato
CREATE TYPE score_comparison_record AS (
    score_timestamp TIMESTAMP WITH TIME ZONE,
    accuracy NUMERIC,
    accuracy_change NUMERIC
);

-- 2. Creamos la función
CREATE OR REPLACE FUNCTION fn_GetScoreHistory(p_user_id BIGINT, p_limit INT DEFAULT 10)
RETURNS SETOF score_comparison_record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    -- Req 4d: Inicio de CTE
    WITH RankedScores AS (
        SELECT
            Timestamp,
            Accuracy,
            -- Req 5a: Función de Ventana LAG()
            LAG(Accuracy, 1) OVER (ORDER BY Timestamp ASC) as PreviousAccuracy
        FROM OsuScores
        WHERE UserID = p_user_id AND ScoreType = 'best'
    )
    -- Fin de CTE
    SELECT
        rs.Timestamp,
        rs.Accuracy,
        (rs.Accuracy - rs.PreviousAccuracy) as AccuracyChange
    FROM RankedScores rs
    ORDER BY rs.Timestamp DESC
    LIMIT p_limit;
END;
$$;