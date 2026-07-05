-- =================================================================
-- Migración 14: Rastrear quién creó cada recordatorio
-- =================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'reminders' AND column_name = 'createdby'
    ) THEN
        ALTER TABLE Reminders ADD COLUMN CreatedBy BIGINT REFERENCES Users(UserID) ON DELETE SET NULL;
    END IF;
END $$;

-- Recordatorios existentes: asumir que el destinatario los creó
UPDATE Reminders SET CreatedBy = UserID WHERE CreatedBy IS NULL;
