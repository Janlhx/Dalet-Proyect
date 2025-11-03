-- =================================================================
-- Script de Vistas (Requisito 4 y 5)
-- =================================================================

-- -----------------------------------------------------
-- Vista 1: V_ChannelMessages (Cumple Req. 4a - INNER JOIN)
-- Descripción: Une Messages y Users para ver el nombre del autor.
-- Esta vista será usada por d.chatlog y d.resumir_hibrido.
-- -----------------------------------------------------
CREATE VIEW V_ChannelMessages AS
SELECT 
    m.MessageID,
    m.Content,
    m.Timestamp,
    m.ChannelID,
    u.UserName,
    u.UserID
FROM Messages m
JOIN Users u ON m.UserID = u.UserID;

-- -----------------------------------------------------
-- Vista 2: V_UserSummaries (Cumple Req. 4a - INNER JOIN)
-- Descripción: Une Summaries y Channels para ver el nombre del canal resumido.
-- -----------------------------------------------------
CREATE VIEW V_UserSummaries AS
SELECT
    s.SummaryID,
    s.GeneratedDate,
    s.SummaryText,
    s.ChannelID,
    c.ChannelName,
    c.ServerID
FROM Summaries s
JOIN Channels c ON s.ChannelID = c.ChannelID;

-- -----------------------------------------------------
-- Vista 3: V_UsersWithoutOsu (Cumple Req. 4a - LEFT JOIN)
-- Descripción: Muestra usuarios que están en la BD (porque han hablado)
-- pero que NO han vinculado su cuenta de osu!.
-- -----------------------------------------------------
CREATE VIEW V_UsersWithoutOsu AS
SELECT
    u.UserID,
    u.UserName
FROM Users u
LEFT JOIN OsuAccounts oa ON u.UserID = oa.UserID
WHERE oa.UserID IS NULL;

-- -----------------------------------------------------
-- Vista 4: V_ChannelActivity (Cumple Req. 4b - Subconsulta Escalar)
-- Descripción: Muestra canales y la fecha del último mensaje enviado en ellos.
-- -----------------------------------------------------
CREATE VIEW V_ChannelActivity AS
SELECT
    c.ChannelID,
    c.ChannelName,
    c.ServerID,
    (SELECT MAX(m.Timestamp) 
     FROM Messages m 
     WHERE m.ChannelID = c.ChannelID) as LastMessageTimestamp
FROM Channels c;

-- -----------------------------------------------------
-- Vista 5: V_OsuRankingGlobal (Cumple Req. 4c y 5a - Función de Ventana)
-- Descripción: Crea un ranking de usuarios basado en su PP.
-- ¡Usa la función de ventana RANK()!
-- -----------------------------------------------------
CREATE VIEW V_OsuRankingGlobal AS
SELECT
    u.UserName,
    oa.PP,
    oa.Accuracy,
    oa.GlobalRank,
    -- Req 4c y 5a: Función de Ventana
    RANK() OVER (ORDER BY oa.PP DESC) as CalculatedRank
FROM OsuAccounts oa
JOIN Users u ON oa.UserID = u.UserID
WHERE oa.PP IS NOT NULL AND oa.PP > 0;