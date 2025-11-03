-- =================================================================
-- Script de Triggers (Requisito 6)
-- =================================================================

-- -----------------------------------------------------
-- Trigger 1: Auditoría de PP (AFTER UPDATE)
-- Descripción: Registra en una tabla de auditoría cada vez
-- que el PP de un usuario cambia.
-- -----------------------------------------------------

-- 1. Crear la Función del Trigger
CREATE OR REPLACE FUNCTION fn_LogPPChange()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- 'OLD' tiene el valor antiguo, 'NEW' tiene el valor nuevo
    INSERT INTO Log_PPAudits (UserID, OldPP, NewPP, ChangeDate)
    VALUES (NEW.UserID, OLD.PP, NEW.PP, NOW());
    RETURN NEW;
END;
$$;

-- 2. Crear el Trigger
CREATE TRIGGER trg_AuditPPChanges
AFTER UPDATE ON OsuAccounts
FOR EACH ROW
-- Se activa solo si el PP antiguo es distinto del nuevo
WHEN (OLD.PP IS DISTINCT FROM NEW.PP) 
EXECUTE FUNCTION fn_LogPPChange();


-- -----------------------------------------------------
-- Trigger 2: Validación de Score (BEFORE INSERT)
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