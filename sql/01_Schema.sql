-- =================================================================
-- Script para la Creación de la Base de Datos de DALET
-- =================================================================

-- -----------------------------------------------------
-- Tabla: Servers
-- Almacena la información de cada servidor de Discord.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Servers (
  ServerID BIGINT PRIMARY KEY,
  ServerName VARCHAR(255) NOT NULL,
  IsReactive BOOLEAN DEFAULT TRUE
);

-- -----------------------------------------------------
-- Tabla: Users
-- Almacena la información de cada usuario de Discord.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Users (
  UserID BIGINT PRIMARY KEY,
  UserName VARCHAR(255) NOT NULL
);

-- -----------------------------------------------------
-- Tabla: Channels
-- Almacena los canales de cada servidor.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Channels (
  ChannelID BIGINT PRIMARY KEY,
  ChannelName VARCHAR(255) NOT NULL,
  ServerID BIGINT NOT NULL,
  IsProactive BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (ServerID) REFERENCES Servers(ServerID)
);

-- -----------------------------------------------------
-- Tabla: Messages
-- Historial de mensajes para la memoria contextual.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Messages (
  MessageID SERIAL PRIMARY KEY,
  Content TEXT,
  Timestamp TIMESTAMP NOT NULL,
  UserID BIGINT NOT NULL,
  ChannelID BIGINT NOT NULL,
  FOREIGN KEY (UserID) REFERENCES Users(UserID),
  FOREIGN KEY (ChannelID) REFERENCES Channels(ChannelID)
);

-- -----------------------------------------------------
-- Tabla: RolePermissions
-- Roles con permisos para usar comandos restringidos.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS RolePermissions (
  PermissionID SERIAL PRIMARY KEY,
  ServerID BIGINT NOT NULL,
  RoleID BIGINT NOT NULL,
  FOREIGN KEY (ServerID) REFERENCES Servers(ServerID),
  UNIQUE (ServerID, RoleID)
);

-- -----------------------------------------------------
-- Tabla: Summaries
-- Resúmenes generados por la IA.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Summaries (
  SummaryID SERIAL PRIMARY KEY,
  GeneratedDate TIMESTAMP NOT NULL,
  SummaryText TEXT,
  ChannelID BIGINT NOT NULL,
  FOREIGN KEY (ChannelID) REFERENCES Channels(ChannelID)
);

-- -----------------------------------------------------
-- Tabla: OsuAccounts
-- Vinculación de cuentas de Discord con perfiles de osu!.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS OsuAccounts (
  UserID BIGINT PRIMARY KEY,
  OsuUsername VARCHAR(255) NOT NULL,
  OsuUserID INT,
  PlayMode VARCHAR(50) DEFAULT 'osu',
  PP FLOAT,
  GlobalRank INT,
  CountryRank INT,
  Accuracy FLOAT,
  FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- -----------------------------------------------------
-- Tabla: OsuScores
-- Almacena scores notables de los jugadores.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS OsuScores (
  ScoreID BIGINT PRIMARY KEY,
  UserID BIGINT NOT NULL,
  BeatmapID INT,
  Score INT,
  Accuracy FLOAT,
  Mods VARCHAR(100),
  ScoreType VARCHAR(50), -- 'best' o 'recent'
  Timestamp TIMESTAMP,
  FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

-- -----------------------------------------------------
-- Tabla: UserMemories
-- Almacena recuerdos específicos asociados a un usuario.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS UserMemories (
  MemoryID SERIAL PRIMARY KEY,
  UserID BIGINT NOT NULL,
  Topic VARCHAR(100) DEFAULT 'general',
  Content TEXT NOT NULL,
  Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
  FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_usermemories_userid ON UserMemories(UserID);

-- -----------------------------------------------------
-- Fin del Script de Creación de Base de Datos
-- -----------------------------------------------------
