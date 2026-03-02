-- =================================================================
-- Script: 07_Cleanup.sql
-- Descripción: Elimina tablas, vistas y procedimientos que no tienen
-- uso activo en el código del bot. Reduce complejidad y ruido en la BD.
-- =================================================================

-- ⚠️  EJECUTAR EN ORDEN. Primero dependencias (triggers, funciones, SPs)
--     y al final las tablas.

-- -----------------------------------------------------
-- BLOQUE 1: Limpiar dependencias de OsuScores
-- -----------------------------------------------------

-- 1a. Eliminar el trigger (debe ir antes que la función)
DROP TRIGGER IF EXISTS trg_ValidateScore ON OsuScores;

-- 1b. Eliminar las funciones asociadas a OsuScores
DROP FUNCTION IF EXISTS fn_ValidateOsuScore()         CASCADE;
DROP FUNCTION IF EXISTS fn_GetUserStats(BIGINT)       CASCADE;
DROP FUNCTION IF EXISTS fn_GetScoreHistory(BIGINT, INT) CASCADE;

-- 1c. Eliminar tipos personalizados asociados
DROP TYPE IF EXISTS user_stats_record      CASCADE;
DROP TYPE IF EXISTS score_comparison_record CASCADE;

-- 1d. Eliminar el procedimiento de OsuScores
DROP PROCEDURE IF EXISTS sp_SaveOrUpdateOsuScore(
    BIGINT, BIGINT, INT, INT, INT, NUMERIC, VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE
) CASCADE;

-- 1e. Eliminar la tabla OsuScores
DROP TABLE IF EXISTS OsuScores CASCADE;

-- -----------------------------------------------------
-- BLOQUE 2: Limpiar dependencias de RolePermissions
-- -----------------------------------------------------

-- 2a. Eliminar funciones
DROP FUNCTION IF EXISTS fn_GetRolePermissions(BIGINT)        CASCADE;
DROP FUNCTION IF EXISTS fn_CheckRolePermission(BIGINT, BIGINT[]) CASCADE;

-- 2b. Eliminar procedimientos
DROP PROCEDURE IF EXISTS sp_AddRolePermission(BIGINT, BIGINT)  CASCADE;
DROP PROCEDURE IF EXISTS sp_RemoveRolePermission(BIGINT, BIGINT) CASCADE;
DROP PROCEDURE IF EXISTS sp_ClearRolePermissions(BIGINT)       CASCADE;

-- 2c. Eliminar la tabla RolePermissions
DROP TABLE IF EXISTS RolePermissions CASCADE;

-- -----------------------------------------------------
-- BLOQUE 3: Eliminar Vistas no utilizadas
-- -----------------------------------------------------

DROP VIEW IF EXISTS V_UsersWithoutOsu  CASCADE;
DROP VIEW IF EXISTS V_ChannelActivity  CASCADE;
DROP VIEW IF EXISTS V_UserSummaries    CASCADE;

-- -----------------------------------------------------
-- FIN DEL SCRIPT DE LIMPIEZA
-- -----------------------------------------------------
-- Tablas/vistas conservadas:
--   ✅ Servers, Users, Channels, Messages
--   ✅ OsuAccounts, UserMemories, Summaries
--   ✅ V_ChannelMessages, V_OsuRankingGlobal
-- =================================================================
