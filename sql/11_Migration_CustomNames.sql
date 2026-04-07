-- =================================================================
-- Migración 11: Soporte para Nombres Personalizados por Servidor
-- =================================================================

-- 1. Añadir la columna a la tabla Servers si no existe
-- Nota: En PostgreSQL 9.6+, IF NOT EXISTS no funciona con column, se suele usar un bloque DO.
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='servers' AND column_name='customname') THEN
        ALTER TABLE Servers ADD COLUMN CustomName VARCHAR(25) DEFAULT 'Dalet';
    END IF;
END $$;

-- 2. Actualizar procedimiento existente para no sobreescribir CustomName
CREATE OR REPLACE PROCEDURE sp_RegisterOrUpdateServer(
    p_ServerID BIGINT,
    p_ServerName VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName, CustomName)
    VALUES (p_ServerID, p_ServerName, 'Dalet')
    ON CONFLICT (ServerID) DO UPDATE
    SET ServerName = p_ServerName;
END;
$$;

-- 3. Nueva función para obtener el nombre personalizado
CREATE OR REPLACE FUNCTION fn_GetServerCustomName(
    p_ServerID BIGINT
)
RETURNS VARCHAR(25)
LANGUAGE plpgsql
AS $$
DECLARE
    v_CustomName VARCHAR(25);
BEGIN
    SELECT CustomName INTO v_CustomName
    FROM Servers
    WHERE ServerID = p_ServerID;
    
    RETURN COALESCE(v_CustomName, 'Dalet');
END;
$$;

-- 4. Nuevo procedimiento para establecer el nombre personalizado
CREATE OR REPLACE PROCEDURE sp_SetServerCustomName(
    p_ServerID BIGINT,
    p_CustomName VARCHAR(25)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO Servers (ServerID, ServerName, CustomName)
    VALUES (p_ServerID, 'Unknown', p_CustomName)
    ON CONFLICT (ServerID) DO UPDATE
    SET CustomName = p_CustomName;
END;
$$;
