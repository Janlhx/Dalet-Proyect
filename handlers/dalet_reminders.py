import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
import pytz
from datetime import datetime
import re

from database.repositories.reminder_repository import ReminderRepository
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

def format_days_readable(days_str: str) -> str:
    if days_str == "daily":
        return "Todos los días"
    
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
                    # Comprobar si coincide el día
                    days = r["ReminderDays"]
                    day_match = (days == "daily" or day_name_en in days.split(","))

                    if day_match:
                        # Disparar recordatorio
                        self._sent_today[reminder_id] = date_str
                        await self._trigger_reminder(r)

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
                
                embed = discord.Embed(
                    title="Recordatorio Programado",
                    description=r["Message"],
                    color=DaletAtoms.COLOR_PRIMARY
                )
                embed.add_field(name="Destinatario", value=user_ping, inline=True)
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
        description="Gestionar recordatorios de mapas u otras actividades diarias/semanales"
    )

    @reminder_group.command(name="add", description="Crea un nuevo recordatorio diario o semanal.")
    @app_commands.describe(
        hora="Hora del recordatorio (ej: 23:00, 11:00 PM, 11pm)",
        usuario="Usuario al que hacer ping en el recordatorio",
        dias="Días separados por comas (ej: lunes,miercoles) o 'daily' (por defecto)",
        canal="Canal donde se enviará (por defecto el actual)",
        mensaje="Mensaje del recordatorio",
        timezone="Zona horaria (por defecto America/Bogota)"
    )
    async def reminder_add(
        self, interaction: discord.Interaction, 
        hora: str, 
        usuario: discord.Member,
        dias: str = "daily",
        canal: discord.TextChannel = None,
        mensaje: str = "¡Es hora del mapa del día!",
        timezone: str = "America/Bogota"
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

        # Validar y parsear días
        parsed_days = parse_days(dias)
        if not parsed_days:
            return await interaction.response.send_message(
                "❌ Días inválidos. Especifica días válidos separados por comas (ej: `lunes,martes`) o usa `daily`.",
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
            created_by=interaction.user.id
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
            embed.add_field(name="Frecuencia", value=readable_days, inline=True)
            embed.add_field(name="Destinatario", value=usuario.mention, inline=True)
            embed.add_field(name="Canal", value=target_channel.mention, inline=True)
            embed.add_field(name="Mensaje", value=mensaje, inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "Ocurrió un error al guardar el recordatorio en la base de datos.",
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
                description="Usa el **ID** con `/reminder remove` o `/reminder toggle`.",
                color=DaletAtoms.COLOR_PRIMARY
            )

            for r in reminders:
                status = "Activo" if r["Active"] else "Inactivo"
                readable_days = format_days_readable(r["ReminderDays"])
                channel_mention = f"<#{r['ChannelID']}>"
                user_mention = f"<@{r['UserID']}>"
                
                val = (
                    f"**ID**: `{r['ReminderID']}`\n"
                    f"**Hora**: `{r['ReminderTime']}` ({r['Timezone']})\n"
                    f"**Frecuencia**: {readable_days}\n"
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


async def setup(bot: commands.Bot):
    await bot.add_cog(DaletReminders(bot))
