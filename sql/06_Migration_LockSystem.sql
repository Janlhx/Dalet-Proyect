-- =================================================================
-- Migración: Sistema de Seguridad por Defecto (Lock de Comandos)
-- =================================================================

-- 1. Añadir columna a Channels
ALTER TABLE Channels 
ADD COLUMN IF NOT EXISTS CommandsLocked BOOLEAN DEFAULT TRUE;

-- 2. Función para verificar si el canal está bloqueado
CREATE OR REPLACE FUNCTION fn_IsChannelLocked(
    p_ChannelID BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_IsLocked BOOLEAN;
BEGIN
    SELECT CommandsLocked INTO v_IsLocked
    FROM Channels
    WHERE ChannelID = p_ChannelID;
    
    -- Si el canal no existe en la tabla, se considera BLOQUEADO por seguridad.
    RETURN COALESCE(v_IsLocked, TRUE);
END;
$$;

-- 3. Procedimiento para cambiar el estado del candado
CREATE OR REPLACE PROCEDURE sp_SetChannelLock(
    p_ChannelID BIGINT,
    p_ChannelName VARCHAR(255),
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255),
    p_IsLocked BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Asegurar que el servidor y canal existan
    CALL sp_RegisterOrUpdateServer(p_ServerID, p_ServerName);
    CALL sp_RegisterOrUpdateChannel(p_ChannelID, p_ChannelName, p_ServerID);
    
    UPDATE Channels
    SET CommandsLocked = p_IsLocked
    WHERE ChannelID = p_ChannelID;
END;
$$;
