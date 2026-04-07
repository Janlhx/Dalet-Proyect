-- =================================================================
-- Script: 12_WelcomeSystem.sql
-- Descripción: Agrega la funcionalidad de canales de bienvenida
-- =================================================================

-- Agregar la columna WelcomeChannelID a la tabla Servers si no existe
ALTER TABLE Servers ADD COLUMN IF NOT EXISTS WelcomeChannelID BIGINT;

-- Procedimiento para actualizar el canal de bienvenida
CREATE OR REPLACE PROCEDURE sp_SetWelcomeChannel(
    p_ServerID BIGINT,
    p_ChannelID BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE Servers 
    SET WelcomeChannelID = p_ChannelID,
        UpdatedAt = NOW()
    WHERE ServerID = p_ServerID;
END;
$$;

-- Procedimiento para obtener el canal de bienvenida
CREATE OR REPLACE FUNCTION fn_GetWelcomeChannel(
    p_ServerID BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ChannelID BIGINT;
BEGIN
    SELECT WelcomeChannelID INTO v_ChannelID
    FROM Servers
    WHERE ServerID = p_ServerID;
    
    RETURN v_ChannelID;
END;
$$;
