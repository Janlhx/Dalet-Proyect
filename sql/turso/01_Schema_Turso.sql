-- =================================================================
-- Script para la Creación de la Base de Datos SQLite/Turso de DALET
-- =================================================================

-- -----------------------------------------------------
-- Tabla: Servers
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Servers (
  ServerID INTEGER PRIMARY KEY,
  ServerName TEXT NOT NULL,
  IsReactive BOOLEAN DEFAULT 0,
  CustomName TEXT DEFAULT 'Dalet',
  WelcomeChannelID INTEGER
);

-- -----------------------------------------------------
-- Tabla: Users
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Users (
  UserID INTEGER PRIMARY KEY,
  UserName TEXT NOT NULL
);

-- -----------------------------------------------------
-- Tabla: Channels
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Channels (
  ChannelID INTEGER PRIMARY KEY,
  ChannelName TEXT NOT NULL,
  ServerID INTEGER NOT NULL,
  IsProactive BOOLEAN DEFAULT 0,
  CommandsLocked BOOLEAN DEFAULT 0,
  FOREIGN KEY (ServerID) REFERENCES Servers(ServerID) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: OsuAccounts
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS OsuAccounts (
  UserID INTEGER PRIMARY KEY,
  OsuUsername TEXT NOT NULL,
  OsuUserID INTEGER,
  PlayMode TEXT DEFAULT 'osu',
  PP REAL,
  GlobalRank INTEGER,
  CountryRank INTEGER,
  Accuracy REAL,
  FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: UserMemories
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS UserMemories (
  MemoryID INTEGER PRIMARY KEY AUTOINCREMENT,
  UserID INTEGER NOT NULL,
  Topic TEXT DEFAULT 'general',
  Content TEXT NOT NULL,
  Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_usermemories_userid ON UserMemories(UserID);

-- -----------------------------------------------------
-- Tabla: Reminders
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS Reminders (
  ReminderID INTEGER PRIMARY KEY AUTOINCREMENT,
  ServerID INTEGER NOT NULL,
  ChannelID INTEGER NOT NULL,
  UserID INTEGER NOT NULL,
  ReminderTime TEXT NOT NULL,
  ReminderDays TEXT NOT NULL,
  Message TEXT DEFAULT '¡Es hora del mapa del día!',
  Timezone TEXT DEFAULT 'America/Bogota',
  Active BOOLEAN DEFAULT 1,
  CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
  CreatedBy INTEGER,
  Pings TEXT,
  FOREIGN KEY (ServerID) REFERENCES Servers(ServerID) ON DELETE CASCADE,
  FOREIGN KEY (ChannelID) REFERENCES Channels(ChannelID) ON DELETE CASCADE,
  FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channels_serverid ON Channels(ServerID);
CREATE INDEX IF NOT EXISTS idx_osuaccounts_username ON OsuAccounts(OsuUsername);
CREATE INDEX IF NOT EXISTS idx_reminders_serverid ON Reminders(ServerID);
CREATE INDEX IF NOT EXISTS idx_reminders_channelid ON Reminders(ChannelID);
CREATE INDEX IF NOT EXISTS idx_reminders_userid ON Reminders(UserID);
CREATE INDEX IF NOT EXISTS idx_reminders_active ON Reminders(Active);
