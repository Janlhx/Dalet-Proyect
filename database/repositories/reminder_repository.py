import logging
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.repository.reminder")

class ReminderRepository:
    def __init__(self):
        pass

    async def add_reminder(
        self, server_id: int, channel_id: int, user_id: int, 
        time_str: str, days_str: str, message: str, timezone: str
    ) -> int | None:
        """
        Guarda un nuevo recordatorio en la base de datos SQLite.
        Retorna el ID del recordatorio creado o None si falla.
        """
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
        """
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
        """
        query = """
            SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
            FROM Reminders
            WHERE Active = 1
        """
        rows = await SQLiteManager.fetch_all(query)
        return [dict(row) for row in rows]

    async def get_reminder(self, reminder_id: int) -> dict | None:
        """
        Obtiene un recordatorio específico por su ID.
        """
        query = """
            SELECT ReminderID, ServerID, ChannelID, UserID, ReminderTime, ReminderDays, Message, Timezone, Active
            FROM Reminders
            WHERE ReminderID = ?
        """
        row = await SQLiteManager.fetch_one(query, reminder_id)
        return dict(row) if row else None

    async def delete_reminder(self, reminder_id: int) -> bool:
        """
        Elimina un recordatorio de la base de datos.
        """
        query = "DELETE FROM Reminders WHERE ReminderID = ?"
        cursor = await SQLiteManager.execute(query, reminder_id)
        return cursor is not None and cursor.rowcount > 0

    async def toggle_reminder(self, reminder_id: int) -> bool | None:
        """
        Activa/desactiva un recordatorio. Retorna el nuevo estado o None si falla.
        """
        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return None
        
        new_state = 0 if reminder["Active"] else 1
        query = "UPDATE Reminders SET Active = ? WHERE ReminderID = ?"
        cursor = await SQLiteManager.execute(query, new_state, reminder_id)
        if cursor and cursor.rowcount > 0:
            return bool(new_state)
        return None
