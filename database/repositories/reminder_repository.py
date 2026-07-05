import logging
from database.repositories.base_repository import BaseRepository
from database.sqlite_manager import SQLiteManager
from database.pool import DatabasePool

logger = logging.getLogger("dalet.repository.reminder")

class ReminderRepository(BaseRepository):
    def __init__(self):
        super().__init__()

    async def add_reminder(
        self, server_id: int, channel_id: int, user_id: int, 
        time_str: str, days_str: str, message: str, timezone: str
    ) -> int | None:
        """
        Guarda un nuevo recordatorio en la base de datos remota PostgreSQL (Neon) 
        o hace un fallback a SQLite local si no está disponible.
        Retorna el ID del recordatorio creado.
        """
        if DatabasePool.is_available():
            try:
                # En Postgres usamos una query con RETURNING para obtener el ID insertado
                query = """
                    INSERT INTO Reminders (ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                    RETURNING ReminderID
                """
                # Intentamos insertar y obtener el ID retornado
                row = await self.fetch_one(query, server_id, channel_id, user_id, time_str, days_str, message, timezone)
                if row:
                    return row[0]
            except Exception as e:
                logger.error(f"Error escribiendo recordatorio en Postgres: {e}")

        # Fallback a SQLite local
        logger.info("Usando SQLite local para guardar recordatorio.")
        query = """
            INSERT INTO Reminders (ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """
        cursor = await SQLiteManager.execute(
            query, server_id, channel_id, user_id, time_str, days_str, message, timezone
        )
        if cursor:
            return cursor.lastrowid
        return None

    async def get_reminders_by_server(self, server_id: int) -> list:
        """
        Retorna todos los recordatorios configurados para un servidor específico.
        Intenta obtenerlos de Postgres si está disponible, o de SQLite local en su defecto.
        """
        if DatabasePool.is_available():
            try:
                query = """
                    SELECT ReminderID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
                    FROM Reminders
                    WHERE ServerID = $1
                    ORDER BY CreatedAt DESC
                """
                rows = await self.fetch_all(query, server_id)
                if rows:
                    return [{
                        "ReminderID": r[0], "ChannelID": r[1], "UserID": r[2],
                        "ReminderTime": r[3], "ReminderDays": r[4], "Message": r[5],
                        "Timezone": r[6], "Active": r[7]
                    } for r in rows]
            except Exception as e:
                logger.error(f"Error al leer recordatorios de Postgres: {e}")

        # Fallback a SQLite local
        query = """
            SELECT ReminderID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
            FROM Reminders
            WHERE ServerID = ?
            ORDER BY CreatedAt DESC
        """
        rows = await SQLiteManager.fetch_all(query, server_id)
        return [dict(row) for row in rows]

    async def get_active_reminders(self) -> list:
        """
        Retorna todos los recordatorios activos en todo el sistema.
        Busca tanto en Postgres (prioridad) como en SQLite local para fusionarlos y no perder ninguno.
        """
        active = []
        seen_ids = set()

        if DatabasePool.is_available():
            try:
                query = """
                    SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
                    FROM Reminders
                    WHERE Active = TRUE
                """
                rows = await self.fetch_all(query)
                for r in rows:
                    active.append({
                        "ReminderID": r[0], "ServerID": r[1], "ChannelID": r[2], 
                        "UserID": r[3], "ReminderTime": r[4], "ReminderDays": r[5], 
                        "Message": r[6], "Timezone": r[7], "Active": r[8]
                    })
                    seen_ids.add(r[0])
            except Exception as e:
                logger.error(f"Error al leer recordatorios activos de Postgres: {e}")

        # Fallback/Combinación con SQLite local
        query = """
            SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
            FROM Reminders
            WHERE Active = 1
        """
        rows = await SQLiteManager.fetch_all(query)
        for r in rows:
            # Si no fue leído ya de Postgres, agregarlo
            r_dict = dict(r)
            if r_dict["ReminderID"] not in seen_ids:
                active.append(r_dict)

        return active

    async def get_reminder(self, reminder_id: int) -> dict | None:
        """
        Obtiene un recordatorio específico por su ID.
        """
        if DatabasePool.is_available():
            try:
                query = """
                    SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
                    FROM Reminders
                    WHERE ReminderID = $1
                """
                r = await self.fetch_one(query, reminder_id)
                if r:
                    return {
                        "ReminderID": r[0], "ServerID": r[1], "ChannelID": r[2], 
                        "UserID": r[3], "ReminderTime": r[4], "ReminderDays": r[5], 
                        "Message": r[6], "Timezone": r[7], "Active": r[8]
                    }
            except Exception as e:
                logger.error(f"Error leyendo recordatorio de Postgres: {e}")

        query = """
            SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
            FROM Reminders
            WHERE ReminderID = ?
        """
        row = await SQLiteManager.fetch_one(query, reminder_id)
        return dict(row) if row else None

    async def delete_reminder(self, reminder_id: int) -> bool:
        """
        Elimina un recordatorio de la base de datos (Postgres y SQLite fallback).
        """
        success = False
        if DatabasePool.is_available():
            try:
                query = "DELETE FROM Reminders WHERE ReminderID = $1"
                # Postgres execute retorna una cadena de status como "DELETE 1"
                res = await self.execute(query, reminder_id)
                if res and "DELETE" in res:
                    success = True
            except Exception as e:
                logger.error(f"Error borrando recordatorio en Postgres: {e}")

        # Borrar también localmente por consistencia
        query = "DELETE FROM Reminders WHERE ReminderID = ?"
        cursor = await SQLiteManager.execute(query, reminder_id)
        if cursor and cursor.rowcount > 0:
            success = True

        return success

    async def toggle_reminder(self, reminder_id: int) -> bool | None:
        """
        Activa/desactiva un recordatorio. Retorna el nuevo estado.
        """
        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return None
        
        new_state = not reminder["Active"]
        success = False

        if DatabasePool.is_available():
            try:
                query = "UPDATE Reminders SET Active = $1 WHERE ReminderID = $2"
                res = await self.execute(query, new_state, reminder_id)
                if res and "UPDATE" in res:
                    success = True
            except Exception as e:
                logger.error(f"Error toggling recordatorio en Postgres: {e}")

        # Actualizar localmente por consistencia
        query = "UPDATE Reminders SET Active = ? WHERE ReminderID = ?"
        cursor = await SQLiteManager.execute(query, 1 if new_state else 0, reminder_id)
        if cursor and cursor.rowcount > 0:
            success = True

        return new_state if success else None

