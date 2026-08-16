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

def format_days_readable(days_str: str) -> str:
    if days_str == "daily":
        return "Todos los días"
    
    # Comprobar si es fecha específica YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", days_str):
        parts = days_str.split("-")
        return f"El {parts[2]}/{parts[1]}/{parts[0]}"
        
    parts = days_str.split(",")
    readable = [DAY_TRANSLATIONS.get(p, p.capitalize()) for p in parts]
    return ", ".join(readable)


class DaletReminders(commands.Cog, name="Recordatorios"):
    """Módulo de recordatorios diarios y semanales configurables."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = ReminderRepository()
        self._sent_today = {}  # Cache de envío: {reminder_id: date_str}
        self.check_reminders.start()
        # Ejecutar migración de Postgres en segundo plano
        asyncio.create_task(self._run_postgres_migrations())

    async def _run_postgres_migrations(self):
        # Esperar un poco a que el bot se inicialice y la BD esté disponible
        await asyncio.sleep(5)
        if TursoClient.is_available():
            try:
                await self.repo.execute("ALTER TABLE Reminders ADD COLUMN IF NOT EXISTS Pings VARCHAR(255) DEFAULT NULL;")
                logger.info("Postgres Reminders migration successful (Pings column added/exists).")
            except Exception as e:
                logger.warning(f"Error running Postgres Reminders migration: {e}")

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
                user_ping = f"<@{r['UserID']}>"
                pings_str = r.get("Pings")
                if pings_str:
                    user_ping += f" {pings_str}"
                
                embed = discord.Embed(
                    title="Recordatorio Programado",
                    description=r["Message"],
                    color=DaletAtoms.COLOR_PRIMARY
                )
                embed.add_field(name="Destinatario(s)", value=user_ping, inline=True)
                embed.add_field(name="Hora programada", value=f"`{r['ReminderTime']}` ({r['Timezone']})", inline=True)
                
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
        description="Gestionar recordatorios de mapas u otras actividades diarias/semanales/específicas"
    )

    @reminder_group.command(name="add", description="Crea un nuevo recordatorio diario, semanal o para una fecha específica.")
    @app_commands.describe(
        hora="Hora del recordatorio (ej: 23:00, 11:00 PM, 11pm)",
        usuario="Usuario principal al que hacer ping en el recordatorio",
        dias="Días separados por comas (ej: lunes,miercoles), 'daily' o fecha específica (ej: 15/07/2026)",
        canal="Canal donde se enviará (por defecto el actual)",
        mensaje="Mensaje del recordatorio",
        timezone="Zona horaria (por defecto America/Bogota)",
        pings="Otros usuarios o roles a pingear (separados por espacio)"
    )
    async def reminder_add(
        self, interaction: discord.Interaction, 
        hora: str, 
        usuario: discord.Member,
        dias: str = "daily",
        canal: discord.TextChannel = None,
        mensaje: str = "¡Es hora del mapa del día!",
        timezone: str = "America/Bogota",
        pings: str = None
    ):
        # Validar huso horario
        try:
            pytz.timezone(timezone)
        except Exception:
            return await interaction.response.send_message(
                f"❌ Zona horaria `{timezone}` inválida. Ejemplos válidos: `America/Bogota`, `America/Mexico_City`, `UTC`.",
                ephemeral=True
            )

        # Validar y parsear hora
        parsed_time = parse_time(hora)
        if not parsed_time:
            return await interaction.response.send_message(
                "❌ Formato de hora inválido. Usa formatos como `23:00`, `11:00 PM` o `11pm`.",
                ephemeral=True
            )

        # Validar y parsear días o fecha
        parsed_days = parse_days_or_date(dias)
        if not parsed_days:
            return await interaction.response.send_message(
                "❌ Días o fecha inválidos. Especifica días separados por comas, `daily` o una fecha válida (ej: `15/07/2026`).",
                ephemeral=True
            )

        target_channel = canal or interaction.channel
        
        # Guardar en base de datos
        reminder_id = await self.repo.add_reminder(
            server_id=interaction.guild_id,
            channel_id=target_channel.id,
            user_id=usuario.id,
            time_str=parsed_time,
            days_str=parsed_days,
            message=mensaje,
            timezone=timezone,
            created_by=interaction.user.id,
            pings=pings
        )

        if reminder_id:
            readable_days = format_days_readable(parsed_days)
            embed = discord.Embed(
                title="Recordatorio Creado",
                description=f"Se ha programado el recordatorio correctamente.",
                color=DaletAtoms.COLOR_SUCCESS
            )
            embed.add_field(name="ID", value=f"`#{reminder_id}`", inline=True)
            embed.add_field(name="Hora", value=f"`{parsed_time}` ({timezone})", inline=True)
            embed.add_field(name="Frecuencia / Fecha", value=readable_days, inline=True)
            
            dest_val = usuario.mention
            if pings:
                dest_val += f" {pings}"
            embed.add_field(name="Destinatario(s)", value=dest_val, inline=True)
            embed.add_field(name="Canal", value=target_channel.mention, inline=True)
            embed.add_field(name="Mensaje", value=mensaje, inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "❌ Ocurrió un error al guardar el recordatorio en la base de datos.",
                ephemeral=True
            )

    @reminder_group.command(name="edit", description="Edita un recordatorio existente.")
    @app_commands.describe(
        id="ID del recordatorio a editar",
        hora="Nueva hora del recordatorio (ej: 23:00, 11:00 PM)",
        usuario="Nuevo usuario principal al que hacer ping",
        dias="Nuevos días (ej: lunes,miercoles), 'daily' o fecha específica (ej: 15/07/2026)",
        canal="Nuevo canal donde enviar el recordatorio",
        mensaje="Nuevo mensaje del recordatorio",
        timezone="Nueva zona horaria (ej: America/Bogota)",
        pings="Otros usuarios o roles a pingear (separados por espacio)"
    )
    async def reminder_edit(
        self, interaction: discord.Interaction, 
        id: int,
        hora: str = None, 
        usuario: discord.Member = None,
        dias: str = None,
        canal: discord.TextChannel = None,
        mensaje: str = None,
        timezone: str = None,
        pings: str = None
    ):
        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            return await interaction.response.send_message(
                f"❌ No se encontró ningún recordatorio con el ID `#{id}` en este servidor.",
                ephemeral=True
            )
        if reminder.get("CreatedBy") != interaction.user.id:
            return await interaction.response.send_message(
                f"❌ Solo puedes editar recordatorios que tú hayas creado.",
                ephemeral=True
            )

        updates = {}

        if timezone is not None:
            try:
                pytz.timezone(timezone)
                updates["Timezone"] = timezone
            except Exception:
                return await interaction.response.send_message(
                    f"❌ Zona horaria `{timezone}` inválida. Ejemplos válidos: `America/Bogota`, `UTC`.",
                    ephemeral=True
                )

        if hora is not None:
            parsed_time = parse_time(hora)
            if not parsed_time:
                return await interaction.response.send_message(
                    "❌ Formato de hora inválido. Usa formatos como `23:00`, `11:00 PM` o `11pm`.",
                    ephemeral=True
                )
            updates["ReminderTime"] = parsed_time

        if dias is not None:
            parsed_days = parse_days_or_date(dias)
            if not parsed_days:
                return await interaction.response.send_message(
                    "❌ Días o fecha inválidos. Especifica días separados por comas, `daily` o una fecha válida (ej: `15/07/2026`).",
                    ephemeral=True
                )
            updates["ReminderDays"] = parsed_days

        if canal is not None:
            updates["ChannelID"] = canal.id

        if usuario is not None:
            updates["UserID"] = usuario.id

        if mensaje is not None:
            updates["Message"] = mensaje

        if pings is not None:
            updates["Pings"] = pings

        if not updates:
            return await interaction.response.send_message(
                "⚠️ No especificaste ningún campo para modificar.",
                ephemeral=True
            )

        success = await self.repo.update_reminder(id, updates)
        if success:
            updated_reminder = await self.repo.get_reminder(id)
            
            readable_days = format_days_readable(updated_reminder["ReminderDays"])
            target_channel_id = updated_reminder["ChannelID"]
            target_user_id = updated_reminder["UserID"]
            
            embed = discord.Embed(
                title="Recordatorio Modificado",
                description=f"Se ha actualizado el recordatorio `#{id}` con éxito.",
                color=DaletAtoms.COLOR_SUCCESS
            )
            embed.add_field(name="ID", value=f"`#{id}`", inline=True)
            embed.add_field(name="Hora", value=f"`{updated_reminder['ReminderTime']}` ({updated_reminder['Timezone']})", inline=True)
            embed.add_field(name="Frecuencia / Fecha", value=readable_days, inline=True)
            
            dest_val = f"<@{target_user_id}>"
            if updated_reminder.get("Pings"):
                dest_val += f" {updated_reminder['Pings']}"
            embed.add_field(name="Destinatario(s)", value=dest_val, inline=True)
            
            embed.add_field(name="Canal", value=f"<#{target_channel_id}>", inline=True)
            embed.add_field(name="Mensaje", value=updated_reminder["Message"], inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "❌ Ocurrió un error al actualizar el recordatorio en la base de datos.",
                ephemeral=True
            )

    @reminder_group.command(name="list", description="Muestra los recordatorios que tú has creado en este servidor.")
    async def reminder_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            reminders = await self.repo.get_reminders_by_creator(
                interaction.guild_id, interaction.user.id
            )
            if not reminders:
                return await interaction.followup.send("No tienes recordatorios creados en este servidor.")

            embed = discord.Embed(
                title=f"Tus recordatorios — {interaction.guild.name}",
                description="Usa el **ID** con `/reminder remove` o `/reminder toggle` o `/reminder edit`.",
                color=DaletAtoms.COLOR_PRIMARY
            )

            for r in reminders:
                status = "Activo" if r["Active"] else "Inactivo"
                readable_days = format_days_readable(r["ReminderDays"])
                channel_mention = f"<#{r['ChannelID']}>"
                user_mention = f"<@{r['UserID']}>"
                if r.get("Pings"):
                    user_mention += f" {r['Pings']}"
                
                val = (
                    f"**ID**: `{r['ReminderID']}`\n"
                    f"**Hora**: `{r['ReminderTime']}` ({r['Timezone']})\n"
                    f"**Frecuencia / Fecha**: {readable_days}\n"
                    f"**Para**: {user_mention} en {channel_mention}\n"
                    f"**Mensaje**: *{r['Message']}*\n"
                    f"**Estado**: {status}"
                )
                embed.add_field(
                    name=f"Recordatorio #{r['ReminderID']}",
                    value=val,
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /reminder list: {e}")
            await interaction.followup.send("Ocurrió un error al obtener la lista de recordatorios.")

    @reminder_group.command(name="remove", description="Elimina un recordatorio por su ID.")
    @app_commands.describe(id="ID del recordatorio a eliminar (ej: 1)")
    async def reminder_remove(self, interaction: discord.Interaction, id: int):
        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            return await interaction.response.send_message(
                f"No se encontró ningún recordatorio con el ID `#{id}` en este servidor.",
                ephemeral=True
            )
        if reminder.get("CreatedBy") != interaction.user.id:
            return await interaction.response.send_message(
                f"Solo puedes eliminar recordatorios que tú hayas creado.",
                ephemeral=True
            )

        success = await self.repo.delete_reminder(id)
        if success:
            await interaction.response.send_message(f"Recordatorio `#{id}` eliminado con éxito.")
        else:
            await interaction.response.send_message("Error al eliminar el recordatorio de la base de datos.", ephemeral=True)

    @reminder_group.command(name="toggle", description="Activa o desactiva un recordatorio por su ID.")
    @app_commands.describe(id="ID del recordatorio a activar/desactivar (ej: 1)")
    async def reminder_toggle(self, interaction: discord.Interaction, id: int):
        reminder = await self.repo.get_reminder(id)
        if not reminder or reminder["ServerID"] != interaction.guild_id:
            return await interaction.response.send_message(
                f"No se encontró ningún recordatorio con el ID `#{id}` en este servidor.",
                ephemeral=True
            )
        if reminder.get("CreatedBy") != interaction.user.id:
            return await interaction.response.send_message(
                f"Solo puedes modificar recordatorios que tú hayas creado.",
                ephemeral=True
            )

        new_state = await self.repo.toggle_reminder(id)
        if new_state is not None:
            status_str = "activado" if new_state else "desactivado"
            await interaction.response.send_message(f"El recordatorio `#{id}` ha sido {status_str}.")
        else:
            await interaction.response.send_message("Error al cambiar el estado del recordatorio.", ephemeral=True)

    # Autocompletado para zona horaria y días/fechas
    async def timezone_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        common_timezones = [
            "America/Bogota", "America/Mexico_City", "America/Santiago",
            "America/Argentina/Buenos_Aires", "America/Lima", "America/Caracas",
            "America/Madrid", "UTC"
        ]
        
        if not current:
            return [app_commands.Choice(name=tz, value=tz) for tz in common_timezones]
            
        current = current.lower()
        matches = [tz for tz in pytz.all_timezones if current in tz.lower()]
        matches = sorted(matches, key=lambda tz: (not tz.lower().startswith(current), tz))
        return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]

    async def dias_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        today_str = datetime.now().strftime("%d/%m/%Y")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        
        options = [
            ("Todos los días", "daily"),
            (f"Hoy ({today_str})", today_str),
            (f"Mañana ({tomorrow_str})", tomorrow_str),
            ("Lunes a Viernes (días laborables)", "lunes,martes,miercoles,jueves,viernes"),
            ("Fin de semana (Sábado y Domingo)", "sabado,domingo"),
            ("Lunes", "lunes"),
            ("Martes", "martes"),
            ("Miércoles", "miercoles"),
            ("Jueves", "jueves"),
            ("Viernes", "viernes"),
            ("Sábado", "sabado"),
            ("Domingo", "domingo")
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

    @reminder_add.autocomplete("dias")
    async def reminder_add_dias_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.dias_autocomplete(interaction, current)

    @reminder_edit.autocomplete("timezone")
    async def reminder_edit_timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.timezone_autocomplete(interaction, current)

    @reminder_edit.autocomplete("dias")
    async def reminder_edit_dias_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.dias_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(DaletReminders(bot))

