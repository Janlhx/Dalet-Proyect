import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
import pytz
from datetime import datetime, timedelta
import re
import asyncio

from database.repositories.reminder_repository import ReminderRepository
from database.turso_client import TursoClient
from ui.atoms import DaletAtoms
from ui.organisms import DaletOrganisms

logger = logging.getLogger("dalet.handlers.reminders")

# Mapeo de nombres de días en español/inglés a estándar en inglés
DAY_MAP = {
    "lunes": "monday", "monday": "monday", "mon": "monday", "lun": "monday",
    "martes": "tuesday", "tuesday": "tuesday", "tue": "tuesday", "mar": "tuesday",
    "miercoles": "wednesday", "wednesday": "wednesday", "wed": "wednesday", "mie": "wednesday", "miércoles": "wednesday",
    "jueves": "thursday", "thursday": "thursday", "thu": "thursday", "jue": "thursday",
    "viernes": "friday", "friday": "friday", "fri": "friday", "vie": "friday",
    "sabado": "saturday", "saturday": "saturday", "sat": "saturday", "sab": "saturday", "sábado": "saturday",
    "domingo": "sunday", "sunday": "sunday", "sun": "sunday", "dom": "sunday"
}

# Traducción inversa para mostrar al usuario de forma bonita
DAY_TRANSLATIONS = {
    "monday": "Lunes",
    "tuesday": "Martes",
    "wednesday": "Miércoles",
    "thursday": "Jueves",
    "friday": "Viernes",
    "saturday": "Sábado",
    "sunday": "Domingo"
}

def parse_time(time_str: str) -> str | None:
    """
    Parsea cadenas de texto de hora como '23:00', '11:00 PM', '11pm', etc.
    y retorna en formato 'HH:MM' de 24 horas, o None si no es válido.
    """
    time_str = time_str.strip().lower()
    
    # Intentar formato de 24 horas estándar HH:MM
    m24 = re.match(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$", time_str)
    if m24:
        h, m = int(m24.group(1)), int(m24.group(2))
        return f"{h:02d}:{m:02d}"
        
    # Intentar formatos con AM/PM (ej: 11:00 pm, 11 pm, 11pm)
    m12 = re.match(r"^([0-9]|1[0-2])(?::([0-5][0-9]))?\s*(am|pm)$", time_str)
    if m12:
        h = int(m12.group(1))
        m = int(m12.group(2)) if m12.group(2) else 0
        meridiem = m12.group(3)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"
        
    return None

def parse_date(date_str: str) -> str | None:
    """
    Intenta parsear una fecha específica en formatos como DD/MM/YYYY, YYYY-MM-DD, DD/MM.
    Retorna en formato YYYY-MM-DD o None si no es válida.
    """
    date_str = date_str.strip()
    
    # Formato YYYY-MM-DD
    m1 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    if m1:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
            
    # Formato DD/MM/YYYY o DD-MM-YYYY
    m2 = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_str)
    if m2:
        day, month, year = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Formato DD/MM o DD-MM (asume año actual)
    m3 = re.match(r"^(\d{1,2})[/-](\d{1,2})$", date_str)
    if m3:
        day, month = int(m3.group(1)), int(m3.group(2))
        year = datetime.now().year
        try:
            dt = datetime(year, month, day)
            # Si la fecha ya pasó en el año actual, asumir el año siguiente
            if dt.date() < datetime.now().date():
                dt = datetime(year + 1, month, day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
            
    return None

def parse_days(days_str: str) -> str | None:
    """
    Valida y normaliza los días ingresados.
    Retorna los días normalizados separados por comas, o None si hay alguno inválido.
    """
    days_str = days_str.strip().lower()
    if days_str in ["daily", "diario", "todos", "cada dia", "cada día", "todo"]:
        return "daily"
        
    parts = [p.strip() for p in days_str.split(",")]
    normalized = []
    for p in parts:
        if p in DAY_MAP:
            normalized.append(DAY_MAP[p])
        else:
            return None
            
    order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    sorted_days = sorted(list(set(normalized)), key=lambda d: order.index(d))
    return ",".join(sorted_days)

def parse_days_or_date(input_str: str) -> str | None:
    """
    Valida y normaliza el campo 'dias' pudiendo ser una fecha específica
    o un patrón de días de la semana.
    """
    parsed_dt = parse_date(input_str)
    if parsed_dt:
        return parsed_dt
    return parse_days(input_str)

def format_days_readable(days_str: str, lang: str = "en") -> str:
    if days_str == "daily":
        return "Every day" if lang == "en" else "Todos los días"
    
    # Comprobar si es fecha específica YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", days_str):
        parts = days_str.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}" if lang == "en" else f"El {parts[2]}/{parts[1]}/{parts[0]}"
        
    parts = days_str.split(",")
    if lang == "es":
        readable = [DAY_TRANSLATIONS.get(p, p.capitalize()) for p in parts]
    else:
        readable = [p.capitalize() for p in parts]
    return ", ".join(readable)


class DaletReminders(commands.Cog, name="Recordatorios"):
    """Módulo de recordatorios diarios y semanales configurables."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = ReminderRepository()
        self._sent_today = {}  # Cache de envío: {reminder_id: date_str}
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()


    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Tarea en segundo plano que revisa y dispara los recordatorios."""
        if not self.bot.is_ready():
            return

        try:
            active_reminders = await self.repo.get_active_reminders()
            if not active_reminders:
                return

            now_utc = datetime.now(pytz.utc)

            for r in active_reminders:
                reminder_id = r["ReminderID"]
                tz_name = r["Timezone"]
                
                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    tz = pytz.timezone("America/Bogota")

                # Obtener la hora local en la zona horaria del recordatorio
                now_local = now_utc.astimezone(tz)
                time_str = now_local.strftime("%H:%M")
                day_name_en = now_local.strftime("%A").lower() # e.g. "monday"
                date_str = now_local.strftime("%Y-%m-%d")

                # Verificar si ya se envió hoy
                if self._sent_today.get(reminder_id) == date_str:
                    continue

                # Comprobar si coincide la hora
                if time_str == r["ReminderTime"]:
                    # Comprobar si coincide el día o la fecha específica
                    days = r["ReminderDays"]
                    is_specific_date = re.match(r"^\d{4}-\d{2}-\d{2}$", days)

                    if is_specific_date:
                        day_match = (days == date_str)
                    else:
                        day_match = (days == "daily" or day_name_en in days.split(","))

                    if day_match:
                        # Disparar recordatorio
                        self._sent_today[reminder_id] = date_str
                        await self._trigger_reminder(r)

                        # Si era una fecha específica, desactivarlo
                        if is_specific_date:
                            if TursoClient.is_available():
                                try:
                                    await self.repo.execute("UPDATE Reminders SET Active = FALSE WHERE ReminderID = $1", reminder_id)
                                except Exception:
                                    pass
                            await SQLiteManager.execute("UPDATE Reminders SET Active = 0 WHERE ReminderID = ?", reminder_id)
                            logger.info(f"Recordatorio de fecha específica #{reminder_id} ejecutado y desactivado.")

            # Limpieza periódica de caché de envíos (eliminar registros de días anteriores)
            current_date_str = now_utc.astimezone(pytz.timezone("America/Bogota")).strftime("%Y-%m-%d")
            expired_keys = [k for k, v in self._sent_today.items() if v != current_date_str]
            for k in expired_keys:
                self._sent_today.pop(k, None)

        except Exception as e:
            logger.error(f"Error en el ciclo de recordatorios: {e}", exc_info=True)

    async def _trigger_reminder(self, r: dict):
        """Envía el mensaje de recordatorio al canal correspondiente."""
        try:
            channel = self.bot.get_channel(r["ChannelID"])
            if not channel:
                # Intentar buscarlo de forma asíncrona
                channel = await self.bot.fetch_channel(r["ChannelID"])

            if channel:
                server_lang = "en"
                if hasattr(channel, "guild") and channel.guild and hasattr(self.bot, "admin_repo"):
                    server_lang = await self.bot.admin_repo.get_server_language(channel.guild.id)

                user_ping = f"<@{r['UserID']}>"
                pings_str = r.get("Pings")
                if pings_str:
                    user_ping += f" {pings_str}"
                
                title = "Scheduled Reminder" if server_lang == "en" else "Recordatorio Programado"
                lbl_recipient = "Recipient(s)" if server_lang == "en" else "Destinatario(s)"
                lbl_time = "Scheduled Time" if server_lang == "en" else "Hora programada"

                embed = discord.Embed(
                    title=title,
                    description=r["Message"],
                    color=DaletAtoms.COLOR_PRIMARY
                )
                embed.add_field(name=lbl_recipient, value=user_ping, inline=True)
                embed.add_field(name=lbl_time, value=f"`{r['ReminderTime']}` ({r['Timezone']})", inline=True)
                
                # Enviar ping + embed
                await channel.send(content=user_ping, embed=embed)
                logger.info(f"Recordatorio #{r['ReminderID']} enviado con éxito a {channel.name}")
            else:
                logger.warning(f"No se pudo enviar el recordatorio #{r['ReminderID']}: Canal {r['ChannelID']} no encontrado.")
        except Exception as e:
            logger.error(f"Error al disparar recordatorio #{r['ReminderID']}: {e}")

    # Grupo de Comandos Slash para /reminder
    reminder_group = app_commands.Group(
        name="reminder", 
        description="Manage scheduled reminders for daily, weekly, or specific date activities."
    )

    @reminder_group.command(name="add", description="Creates a new daily, weekly, or specific date reminder.")
    @app_commands.describe(
        time="Reminder time (e.g., 23:00, 11:00 PM, 11pm)",
        user="Primary user to ping for this reminder",
        days="Days separated by commas (e.g., monday,wednesday), 'daily', or date (DD/MM/YYYY)",
        channel="Channel where the reminder will be posted (defaults to current)",
        message="Reminder message content",
        timezone="Timezone (default: America/Bogota)",
        pings="Additional users or roles to ping (space-separated)"
    )
    async def reminder_add(
        self, interaction: discord.Interaction, 
        time: str, 
        user: discord.Member,
        days: str = "daily",
        channel: discord.TextChannel = None,
        message: str = "¡Es hora del recordatorio!",
        timezone: str = "America/Bogota",
        pings: str = None
    ):
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        # Validar huso horario
        try:
            pytz.timezone(timezone)
        except Exception:
            err_msg = f"❌ Invalid timezone `{timezone}`. Valid examples: `America/Bogota`, `America/New_York`, `UTC`." if server_lang == "en" else f"❌ Zona horaria `{timezone}` inválida. Ejemplos válidos: `America/Bogota`, `America/Mexico_City`, `UTC`."
            return await interaction.response.send_message(err_msg, ephemeral=True)

        # Validar y parsear hora
        parsed_time = parse_time(time)
        if not parsed_time:
            err_msg = "❌ Invalid time format. Use formats like `23:00`, `11:00 PM` or `11pm`." if server_lang == "en" else "❌ Formato de hora inválido. Usa formatos como `23:00`, `11:00 PM` o `11pm`."
            return await interaction.response.send_message(err_msg, ephemeral=True)

        # Validar y parsear días o fecha
        parsed_days = parse_days_or_date(days)
        if not parsed_days:
            err_msg = "❌ Invalid days or date. Specify comma-separated days, `daily`, or a valid date (e.g., `15/07/2026`)." if server_lang == "en" else "❌ Días o fecha inválidos. Especifica días separados por comas, `daily` o una fecha válida (ej: `15/07/2026`)."
            return await interaction.response.send_message(err_msg, ephemeral=True)

        target_channel = channel or interaction.channel
        
        # Guardar en base de datos
        reminder_id = await self.repo.add_reminder(
            server_id=interaction.guild_id,
            channel_id=target_channel.id,
            user_id=user.id,
            time_str=parsed_time,
            days_str=parsed_days,
            message=message,
            timezone=timezone,
            created_by=interaction.user.id,
            pings=pings
        )

        if reminder_id:
            readable_days = format_days_readable(parsed_days, lang=server_lang)
            title = "Reminder Created" if server_lang == "en" else "Recordatorio Creado"
            desc = "The reminder has been successfully scheduled." if server_lang == "en" else "Se ha programado el recordatorio correctamente."
            lbl_time = "Time" if server_lang == "en" else "Hora"
            lbl_freq = "Frequency / Date" if server_lang == "en" else "Frecuencia / Fecha"
            lbl_dest = "Recipient(s)" if server_lang == "en" else "Destinatario(s)"
            lbl_chan = "Channel" if server_lang == "en" else "Canal"
            lbl_msg = "Message" if server_lang == "en" else "Mensaje"

            embed = discord.Embed(
                title=title,
                description=desc,
                color=DaletAtoms.COLOR_SUCCESS
            )
            embed.add_field(name="ID", value=f"`#{reminder_id}`", inline=True)
            embed.add_field(name=lbl_time, value=f"`{parsed_time}` ({timezone})", inline=True)
            embed.add_field(name=lbl_freq, value=readable_days, inline=True)
            
            dest_val = user.mention
            if pings:
                dest_val += f" {pings}"
            embed.add_field(name=lbl_dest, value=dest_val, inline=True)
            embed.add_field(name=lbl_chan, value=target_channel.mention, inline=True)
            embed.add_field(name=lbl_msg, value=message, inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            fail_msg = "❌ An error occurred while saving the reminder." if server_lang == "en" else "❌ Ocurrió un error al guardar el recordatorio en la base de datos."
            await interaction.response.send_message(fail_msg, ephemeral=True)

    @reminder_group.command(name="edit", description="Edits an existing scheduled reminder.")
    @app_commands.describe(
        id="ID of the reminder to edit",
        time="New reminder time (e.g., 23:00, 11:00 PM)",
        user="New primary user to ping",
        days="New days (e.g., monday,wednesday), 'daily', or date (DD/MM/YYYY)",
        channel="New channel for the reminder",
        message="New reminder message content",
        timezone="New timezone (e.g., America/Bogota)",
        pings="Additional users or roles to ping (space-separated)"
    )
    async def reminder_edit(
        self, interaction: discord.Interaction, 
        id: int,
        time: str = None, 
        user: discord.Member = None,
        days: str = None,
        channel: discord.TextChannel = None,
        message: str = None,
        timezone: str = None,
        pings: str = None
    ):
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            msg = f"❌ No reminder found with ID `#{id}` in this server." if server_lang == "en" else f"❌ No se encontró ningún recordatorio con el ID `#{id}` en este servidor."
            return await interaction.response.send_message(msg, ephemeral=True)
        if reminder.get("CreatedBy") != interaction.user.id:
            msg = "❌ You can only edit reminders that you created." if server_lang == "en" else "❌ Solo puedes editar recordatorios que tú hayas creado."
            return await interaction.response.send_message(msg, ephemeral=True)

        updates = {}

        if timezone is not None:
            try:
                pytz.timezone(timezone)
                updates["Timezone"] = timezone
            except Exception:
                msg = f"❌ Invalid timezone `{timezone}`." if server_lang == "en" else f"❌ Zona horaria `{timezone}` inválida."
                return await interaction.response.send_message(msg, ephemeral=True)

        if time is not None:
            parsed_time = parse_time(time)
            if not parsed_time:
                msg = "❌ Invalid time format." if server_lang == "en" else "❌ Formato de hora inválido."
                return await interaction.response.send_message(msg, ephemeral=True)
            updates["ReminderTime"] = parsed_time

        if days is not None:
            parsed_days = parse_days_or_date(days)
            if not parsed_days:
                msg = "❌ Invalid days or date." if server_lang == "en" else "❌ Días o fecha inválidos."
                return await interaction.response.send_message(msg, ephemeral=True)
            updates["ReminderDays"] = parsed_days

        if channel is not None:
            updates["ChannelID"] = channel.id

        if user is not None:
            updates["UserID"] = user.id

        if message is not None:
            updates["Message"] = message

        if pings is not None:
            updates["Pings"] = pings

        if not updates:
            msg = "⚠️ You did not specify any fields to update." if server_lang == "en" else "⚠️ No especificaste ningún campo para modificar."
            return await interaction.response.send_message(msg, ephemeral=True)

        success = await self.repo.update_reminder(id, updates)
        if success:
            updated_reminder = await self.repo.get_reminder(id)
            
            readable_days = format_days_readable(updated_reminder["ReminderDays"], lang=server_lang)
            target_channel_id = updated_reminder["ChannelID"]
            target_user_id = updated_reminder["UserID"]
            
            title = "Reminder Updated" if server_lang == "en" else "Recordatorio Modificado"
            desc = f"Reminder `#{id}` has been successfully updated." if server_lang == "en" else f"Se ha actualizado el recordatorio `#{id}` con éxito."
            lbl_time = "Time" if server_lang == "en" else "Hora"
            lbl_freq = "Frequency / Date" if server_lang == "en" else "Frecuencia / Fecha"
            lbl_dest = "Recipient(s)" if server_lang == "en" else "Destinatario(s)"
            lbl_chan = "Channel" if server_lang == "en" else "Canal"
            lbl_msg = "Message" if server_lang == "en" else "Mensaje"

            embed = discord.Embed(
                title=title,
                description=desc,
                color=DaletAtoms.COLOR_SUCCESS
            )
            embed.add_field(name="ID", value=f"`#{id}`", inline=True)
            embed.add_field(name=lbl_time, value=f"`{updated_reminder['ReminderTime']}` ({updated_reminder['Timezone']})", inline=True)
            embed.add_field(name=lbl_freq, value=readable_days, inline=True)
            
            dest_val = f"<@{target_user_id}>"
            if updated_reminder.get("Pings"):
                dest_val += f" {updated_reminder['Pings']}"
            embed.add_field(name=lbl_dest, value=dest_val, inline=True)
            
            embed.add_field(name=lbl_chan, value=f"<#{target_channel_id}>", inline=True)
            embed.add_field(name=lbl_msg, value=updated_reminder["Message"], inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            msg = "❌ An error occurred while updating the reminder." if server_lang == "en" else "❌ Ocurrió un error al actualizar el recordatorio en la base de datos."
            await interaction.response.send_message(msg, ephemeral=True)

    @reminder_group.command(name="list", description="Lists the scheduled reminders you created in this server.")
    async def reminder_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        try:
            reminders = await self.repo.get_reminders_by_creator(
                interaction.guild_id, interaction.user.id
            )
            if not reminders:
                msg = "You don't have any scheduled reminders in this server." if server_lang == "en" else "No tienes recordatorios creados en este servidor."
                return await interaction.followup.send(msg)

            title = f"Your Reminders — {interaction.guild.name}" if server_lang == "en" else f"Tus recordatorios — {interaction.guild.name}"
            desc = "Use the **ID** with `/reminder remove`, `/reminder toggle`, or `/reminder edit`." if server_lang == "en" else "Usa el **ID** con `/reminder remove`, `/reminder toggle` o `/reminder edit`."

            embed = discord.Embed(
                title=title,
                description=desc,
                color=DaletAtoms.COLOR_PRIMARY
            )

            for r in reminders:
                if server_lang == "en":
                    status = "Active" if r["Active"] else "Inactive"
                    lbl_rem = f"Reminder #{r['ReminderID']}"
                    lbl_for = "For"
                    lbl_freq = "Frequency / Date"
                    lbl_msg = "Message"
                    lbl_status = "Status"
                    lbl_time = "Time"
                else:
                    status = "Activo" if r["Active"] else "Inactivo"
                    lbl_rem = f"Recordatorio #{r['ReminderID']}"
                    lbl_for = "Para"
                    lbl_freq = "Frecuencia / Fecha"
                    lbl_msg = "Mensaje"
                    lbl_status = "Estado"
                    lbl_time = "Hora"

                readable_days = format_days_readable(r["ReminderDays"], lang=server_lang)
                channel_mention = f"<#{r['ChannelID']}>"
                user_mention = f"<@{r['UserID']}>"
                if r.get("Pings"):
                    user_mention += f" {r['Pings']}"
                
                val = (
                    f"**ID**: `{r['ReminderID']}`\n"
                    f"**{lbl_time}**: `{r['ReminderTime']}` ({r['Timezone']})\n"
                    f"**{lbl_freq}**: {readable_days}\n"
                    f"**{lbl_for}**: {user_mention} in {channel_mention}\n"
                    f"**{lbl_msg}**: *{r['Message']}*\n"
                    f"**{lbl_status}**: {status}"
                )
                embed.add_field(
                    name=lbl_rem,
                    value=val,
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /reminder list: {e}")
            err = "An error occurred while fetching your reminders." if server_lang == "en" else "Ocurrió un error al obtener la lista de recordatorios."
            await interaction.followup.send(err)

    @reminder_group.command(name="remove", description="Deletes a scheduled reminder by its ID.")
    @app_commands.describe(id="ID of the reminder to delete (e.g., 1)")
    async def reminder_remove(self, interaction: discord.Interaction, id: int):
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            msg = f"❌ No reminder found with ID `#{id}` in this server." if server_lang == "en" else f"❌ No se encontró ningún recordatorio con el ID `#{id}` en este servidor."
            return await interaction.response.send_message(msg, ephemeral=True)
        if reminder.get("CreatedBy") != interaction.user.id:
            msg = "❌ You can only delete reminders that you created." if server_lang == "en" else "❌ Solo puedes eliminar recordatorios que tú hayas creado."
            return await interaction.response.send_message(msg, ephemeral=True)

        success = await self.repo.delete_reminder(id)
        if success:
            msg = f"✅ Reminder `#{id}` deleted successfully." if server_lang == "en" else f"✅ Recordatorio `#{id}` eliminado con éxito."
            await interaction.response.send_message(msg)
        else:
            msg = "❌ Error deleting the reminder." if server_lang == "en" else "❌ Error al eliminar el recordatorio de la base de datos."
            await interaction.response.send_message(msg, ephemeral=True)

    @reminder_group.command(name="toggle", description="Enables or disables a scheduled reminder by its ID.")
    @app_commands.describe(id="ID of the reminder to toggle (e.g., 1)")
    async def reminder_toggle(self, interaction: discord.Interaction, id: int):
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            msg = f"❌ No reminder found with ID `#{id}` in this server." if server_lang == "en" else f"❌ No se encontró ningún recordatorio con el ID `#{id}` en este servidor."
            return await interaction.response.send_message(msg, ephemeral=True)
        if reminder.get("CreatedBy") != interaction.user.id:
            msg = "❌ You can only modify reminders that you created." if server_lang == "en" else "❌ Solo puedes modificar recordatorios que tú hayas creado."
            return await interaction.response.send_message(msg, ephemeral=True)

        new_state = await self.repo.toggle_reminder(id)
        if new_state is not None:
            if server_lang == "en":
                status_str = "enabled" if new_state else "disabled"
                msg = f"Reminder `#{id}` has been {status_str}."
            else:
                status_str = "activado" if new_state else "desactivado"
                msg = f"El recordatorio `#{id}` ha sido {status_str}."
            await interaction.response.send_message(msg)
        else:
            msg = "❌ Error toggling reminder status." if server_lang == "en" else "❌ Error al cambiar el estado del recordatorio."
            await interaction.response.send_message(msg, ephemeral=True)

    # Autocompletado para zona horaria y días/fechas
    async def timezone_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        common_timezones = [
            "America/Bogota", "America/New_York", "America/Los_Angeles", "America/Chicago",
            "America/Mexico_City", "America/Santiago", "America/Argentina/Buenos_Aires",
            "America/Lima", "America/Caracas", "America/Sao_Paulo", "Europe/London",
            "Europe/Madrid", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo", "UTC"
        ]
        
        if not current:
            return [app_commands.Choice(name=tz, value=tz) for tz in common_timezones]
            
        current = current.lower()
        matches = [tz for tz in pytz.all_timezones if current in tz.lower()]
        matches = sorted(matches, key=lambda tz: (not tz.lower().startswith(current), tz))
        return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]

    async def days_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        today_str = datetime.now().strftime("%d/%m/%Y")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        
        options = [
            ("Every day (Daily) • Todos los días", "daily"),
            (f"Today ({today_str}) • Hoy", today_str),
            (f"Tomorrow ({tomorrow_str}) • Mañana", tomorrow_str),
            ("Monday to Friday (Weekdays) • Lunes a Viernes", "monday,tuesday,wednesday,thursday,friday"),
            ("Weekend (Sat & Sun) • Fin de semana", "saturday,sunday"),
            ("Monday • Lunes", "monday"),
            ("Tuesday • Martes", "tuesday"),
            ("Wednesday • Miércoles", "wednesday"),
            ("Thursday • Jueves", "thursday"),
            ("Friday • Viernes", "friday"),
            ("Saturday • Sábado", "saturday"),
            ("Sunday • Domingo", "sunday")
        ]
        
        if not current:
            return [app_commands.Choice(name=name, value=value) for name, value in options]
            
        current = current.lower()
        matches = [
            app_commands.Choice(name=name, value=value)
            for name, value in options
            if current in name.lower() or current in value.lower()
        ]
        return matches[:25]

    @reminder_add.autocomplete("timezone")
    async def reminder_add_timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.timezone_autocomplete(interaction, current)

    @reminder_add.autocomplete("days")
    async def reminder_add_days_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.days_autocomplete(interaction, current)

    @reminder_edit.autocomplete("timezone")
    async def reminder_edit_timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.timezone_autocomplete(interaction, current)

    @reminder_edit.autocomplete("days")
    async def reminder_edit_days_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.days_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(DaletReminders(bot))

