-- =================================================================
-- Script: 08_Privacy_TTL.sql
-- Descripción: Implementa política de privacidad en la tabla Messages.
-- Los mensajes se eliminan automáticamente después de 48 horas.
-- Esto mantiene contexto conversacional útil para la IA sin acumular
-- el historial indefinidamente.
-- =================================================================

-- -----------------------------------------------------
-- PASO 1: Añadir columna de expiración a Messages
-- (GENERATED ALWAYS -> se calcula automáticamente al insertar)
-- -----------------------------------------------------
ALTER TABLE Messages
ADD COLUMN IF NOT EXISTS ExpiresAt TIMESTAMP WITH TIME ZONE
    GENERATED ALWAYS AS (Timestamp + INTERVAL '48 hours') STORED;

-- -----------------------------------------------------
-- PASO 2: Índice para que el DELETE periódico sea eficiente
-- (sin índice, cada limpieza haría un full scan)
-- -----------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_messages_expiry
    ON Messages(ExpiresAt);

-- Índice adicional para acelerar las queries de contexto
CREATE INDEX IF NOT EXISTS idx_messages_channel_time
    ON Messages(ChannelID, Timestamp DESC);

-- -----------------------------------------------------
-- PASO 3: Función de limpieza
-- Borra todos los mensajes expirados y devuelve cuántos eliminó.
-- Esta función será llamada periódicamente desde el bot Python.
-- -----------------------------------------------------
CREATE OR REPLACE FUNCTION fn_PurgeExpiredMessages()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM Messages
    WHERE ExpiresAt < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- -----------------------------------------------------
-- PASO 4: Purgar mensajes ya existentes que superen las 48h
-- (limpieza inicial al aplicar este script)
-- -----------------------------------------------------
SELECT fn_PurgeExpiredMessages() AS mensajes_eliminados_en_migracion;

-- =================================================================
-- RESULTADO:
-- • Mensajes nuevos expiran automáticamente a las 48h de su Timestamp
-- • La función fn_PurgeExpiredMessages() se llamará desde Python
--   cada hora mediante una tarea asyncio
-- • El índice idx_messages_expiry garantiza que el DELETE sea O(log n)
-- =================================================================
