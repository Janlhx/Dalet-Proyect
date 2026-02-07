-- =================================================================
-- Script de Triggers
-- =================================================================

-- -----------------------------------------------------
-- Trigger: Validación de Score (BEFORE INSERT)
-- Descripción: Evita que se inserten datos inválidos
-- en la tabla OsuScores.
-- -----------------------------------------------------

-- 1. Crear la Función del Trigger
CREATE OR REPLACE FUNCTION fn_ValidateOsuScore()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Validar Precisión
    IF NEW.Accuracy < 0 OR NEW.Accuracy > 100 THEN
        RAISE EXCEPTION 'La precisión (Accuracy) debe estar entre 0 y 100. Valor recibido: %', NEW.Accuracy;
    END IF;
    
    -- Validar Score
    IF NEW.Score < 0 THEN
        RAISE EXCEPTION 'El score no puede ser negativo. Valor recibido: %', NEW.Score;
    END IF;
    
    RETURN NEW;
END;
$$;

-- 2. Crear el Trigger
CREATE TRIGGER trg_ValidateScore
BEFORE INSERT OR UPDATE ON OsuScores
FOR EACH ROW
EXECUTE FUNCTION fn_ValidateOsuScore();