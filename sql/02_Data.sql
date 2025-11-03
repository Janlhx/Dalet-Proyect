-- =================================================================
-- Script para Poblar la Base de Datos de DALET con Datos de Muestra
-- =================================================================

-- Primero, insertamos los usuarios de linked_accounts.json
INSERT INTO Users (UserID, UserName) VALUES
(434394143452561408, 'Litxe'),
(537156803834675230, 'Blast4'),
(707031778778677300, '- TknHoshino -'),
(990783738738786304, 'XxLarry'),
(395623267530047489, 'Jeiden'),
(746806442824171623, 'CoolBlueberry'),
(1195933673560739880, 'The Suffering'),
(793886347634147349, 'Rudrii'),
(713039799128293489, 'Tepipan'),
(320280775452917761, 'Rinyj'),
(884504077340401766, 'Mondatalker')
ON CONFLICT (UserID) DO NOTHING; -- Evita errores si el usuario ya existe

-- Ahora, poblamos la tabla OsuAccounts
INSERT INTO OsuAccounts (UserID, OsuUsername) VALUES
(434394143452561408, 'Litxe'),
(537156803834675230, 'Blast4'),
(707031778778677300, '- TknHoshino -'),
(990783738738786304, 'XxLarry'),
(395623267530047489, 'Jeiden'),
(746806442824171623, 'CoolBlueberry'),
(1195933673560739880, 'The Suffering'),
(793886347634147349, 'Rudrii'),
(713039799128293489, 'Tepipan'),
(320280775452917761, 'Rinyj'),
(884504077340401766, 'Mondatalker')
ON CONFLICT (UserID) DO UPDATE SET OsuUsername = EXCLUDED.OsuUsername;