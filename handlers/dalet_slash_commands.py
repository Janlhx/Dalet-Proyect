"""
Slash Commands (Application Commands) de Dalet.
Unifica y expone los comandos principales como comandos de barra / para Discord.
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
import logging

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from handlers.dalet_osu_presenter import OsuPresenter

logger = logging.getLogger("dalet.handlers.slash")


class SlashCommands(commands.Cog, name="Slash Commands"):
    """Versiones slash (/) de los comandos principales de Dalet."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @app_commands.command(name="ping", description="Muestra la latencia del bot en ms.")
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 respondiendo en **{latency}ms**. no me presiones.", ephemeral=True
        )

    @app_commands.command(name="stats", description="Muestra tus estadísticas sociales en el servidor.")
    @app_commands.describe(usuario="Usuario del que ver las stats (por defecto tú)")
    async def slash_stats(self, interaction: discord.Interaction, usuario: discord.Member = None):
        member = usuario or interaction.user
        await interaction.response.defer()
        try:
            stats = await self.bot.user_repo.get_user_social_stats(member.id)
            avatar = member.avatar.url if member.avatar else None
            embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /stats: {e}")
            await interaction.followup.send("no pude obtener tus stats ahora mismo.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Muestra información de un usuario del servidor.")
    @app_commands.describe(usuario="Usuario del que ver la info")
    async def slash_userinfo(self, interaction: discord.Interaction, usuario: discord.Member = None):
        member = usuario or interaction.user
        desc = (
            f"🆔 **ID**: `{member.id}`\n"
            f"📅 **Cuenta creada**: {format_dt(member.created_at, 'D')}\n"
            f"🤝 **Se unió**: {format_dt(member.joined_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(f"Expediente: {member.display_name}", desc)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Información del servidor actual.")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        desc = (
            f"👥 **Miembros**: `{g.member_count}`\n"
            f"👑 **Dueño**: {g.owner.mention}\n"
            f"📅 **Creado**: {format_dt(g.created_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(f"Territorio: {g.name}", desc)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # osu!
    # ------------------------------------------------------------------

    @app_commands.command(name="op", description="Perfil de osu! de un jugador.")
    @app_commands.describe(
        usuario="Nombre en osu! (o dejar vacío para tu cuenta vinculada)",
        modo="Modo de juego (por defecto: osu)"
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_op(
        self, interaction: discord.Interaction,
        usuario: str = None, modo: str = "osu"
    ):
        await interaction.response.defer()
        try:
            username = usuario
            if not username:
                username = await self.bot.osu_repo.get_linked_username(interaction.user.id)
            if not username:
                return await interaction.followup.send(
                    "❌ no tienes cuenta vinculada. usa `/link` primero.",
                    ephemeral=True
                )
            user = await self.bot.osu_service.get_user(username, modo)
            embed = OsuPresenter.build_profile_card(user, modo)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /op: {e}")
            await interaction.followup.send("⚠️ error obteniendo el perfil.", ephemeral=True)

    @app_commands.command(name="link", description="Vincula tu Discord con tu cuenta de osu!.")
    @app_commands.describe(usuario="Tu nombre de usuario en osu!")
    async def slash_link(self, interaction: discord.Interaction, usuario: str):
        await interaction.response.defer(ephemeral=True)
        try:
            user_data = await self.bot.osu_service.get_user(usuario)
            if not user_data or "statistics" not in user_data:
                return await interaction.followup.send(
                    f"❌ no encontré a '{usuario}' en osu!.", ephemeral=True
                )
            stats = user_data.get("statistics", {})
            await self.bot.osu_repo.link_account(
                interaction.user.id,
                user_data["username"],
                user_data["id"],
                user_data.get("playmode", "osu"),
                stats.get("pp", 0.0),
                stats.get("global_rank"),
                stats.get("country_rank"),
                stats.get("hit_accuracy", 0.0),
            )
            await interaction.followup.send(
                f"✅ vinculado con **{user_data['username']}**.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /link: {e}")
            await interaction.followup.send("❌ error al vincular.", ephemeral=True)

    @app_commands.command(name="recent", description="Muestra tu última jugada de osu!.")
    @app_commands.describe(
        usuario="Nombre en osu! (o dejar vacío para tu cuenta vinculada)",
        modo="Modo de juego"
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_recent(
        self, interaction: discord.Interaction,
        usuario: str = None, modo: str = "osu"
    ):
        await interaction.response.defer()
        username = usuario
        if not username:
            username = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not username:
            return await interaction.followup.send(
                "❌ no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            user = await self.bot.osu_service.get_user(username, modo)
            recent = await self.bot.osu_service.get_user_recent_scores(
                user["id"], modo, limit=1, include_fails=1
            )
            if not recent:
                return await interaction.followup.send(
                    f"**{username}** no tiene jugadas recientes."
                )

            embed = OsuPresenter.build_recent_card(user.get("username", username), modo, recent[0], user_data=user)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en /recent: {e}")
            await interaction.followup.send("⚠️ error obteniendo la jugada.", ephemeral=True)

    @app_commands.command(name="top", description="Muestra tus mejores plays de osu!.")
    @app_commands.describe(
        usuario="Nombre en osu! (o dejar vacío para tu cuenta vinculada)",
        modo="Modo de juego"
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_top(self, interaction: discord.Interaction, usuario: str = None, modo: str = "osu"):
        await interaction.response.defer()
        username = usuario
        if not username:
            username = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not username:
            return await interaction.followup.send(
                "❌ no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            user = await self.bot.osu_service.get_user(username, modo)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=modo, limit=5)
            embed = OsuPresenter.build_top_card(user.get("username", username), modo, best, user_data=user)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /top: {e}")
            await interaction.followup.send("⚠️ error obteniendo top plays.", ephemeral=True)

    @app_commands.command(name="rank", description="Ranking osu! de los jugadores vinculados en este servidor.")
    async def slash_rank(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            guild_member_ids = [str(m.id) for m in interaction.guild.members if not m.bot]
            all_rows = await self.bot.osu_repo.get_ranking(limit=200)
            server_rows = [
                row for row in all_rows
                if str(row.get("UserID") or row.get("userid") or "") in guild_member_ids
            ][:10]

            if not server_rows:
                return await interaction.followup.send(
                    "nadie en este servidor tiene cuenta vinculada aún. usa `/link` para entrar al ranking."
                )
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`{i+1}.`"
                name = row.get("UserName") or row.get("username") or row.get("osuusername") or "??"
                pp = float(row.get("PP") or row.get("pp") or 0)
                acc = float(row.get("Accuracy") or row.get("accuracy") or 0)
                lines.append(f"{medal} **{name}** — {pp:,.0f}pp • {acc:.2f}%")
            embed = discord.Embed(
                title="🏆 Ranking osu! del Servidor",
                description="\n".join(lines),
                color=0xFFD700
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /rank: {e}")
            await interaction.followup.send("⚠️ error obteniendo el ranking.", ephemeral=True)

    @app_commands.command(name="compare", description="Compara tu perfil de osu! contra otro jugador.")
    @app_commands.describe(usuario="Jugador con el que compararte")
    async def slash_compare(self, interaction: discord.Interaction, usuario: str):
        await interaction.response.defer()
        user1_name = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not user1_name:
            return await interaction.followup.send(
                "❌ necesitas vincular tu cuenta primero.", ephemeral=True
            )
        try:
            u1, u2 = await asyncio.gather(
                self.bot.osu_service.get_user(user1_name),
                self.bot.osu_service.get_user(usuario),
            )
            embed = OsuPresenter.build_compare_card(u1, u2)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /compare: {e}")
            await interaction.followup.send("⚠️ error comparando.", ephemeral=True)

    # ------------------------------------------------------------------
    # Conversaciones / Memoria
    # ------------------------------------------------------------------

    @app_commands.command(name="lore", description="Busca fragmentos del pasado del servidor sobre un tema.")
    @app_commands.describe(tema="Qué quieres buscar en el lore del servidor")
    async def slash_lore(self, interaction: discord.Interaction, tema: str):
        await interaction.response.defer()
        try:
            resultados = await self.bot.user_repo.search_lore(tema, interaction.channel_id, limit=20)
            if not resultados:
                return await interaction.followup.send(
                    f"ni idea de qué es '{tema}'. ese lore te lo inventaste."
                )
            lineas = []
            for r in resultados:
                ts = r['Timestamp'] if isinstance(r, dict) else r[2]
                fecha = str(ts)[:10] if ts else "??/??/????"
                usr = r['UserName'] if isinstance(r, dict) else r[0]
                cnt = r['Content'] if isinstance(r, dict) else r[1]
                lineas.append(f"[{fecha}] {usr}: {cnt}")

            prompt = (
                f"ESTÁS INVESTIGANDO EL LORE DEL SERVIDOR sobre \"{tema}\":\n"
                + "\n".join(lineas)
                + "\nResponde de forma sarcástica y directa, como quien revisó los archivos."
            )
            respuesta = await self.bot.nlp_service.generate_reply(
                prompt, "", interaction.user.display_name
            )
            await interaction.followup.send(respuesta or "me dio pereza leer los archivos. inténtalo otra vez.")
        except Exception as e:
            logger.error(f"Error en /lore: {e}")
            await interaction.followup.send("error leyendo los archivos.", ephemeral=True)

    @app_commands.command(name="resumir", description="Resume el chat reciente de este canal con IA.")
    @app_commands.describe(mensajes="Cuántos mensajes analizar (por defecto 50)")
    async def slash_resumir(self, interaction: discord.Interaction, mensajes: int = 50):
        await interaction.response.defer()
        try:
            registros = await self.bot.user_repo.get_channel_messages(
                interaction.channel_id, min(mensajes, 100)
            )
            if not registros:
                return await interaction.followup.send("no hay suficientes mensajes para resumir.")

            display_list = list(registros)
            display_list.reverse()
            historial = "\n".join([f"{r.get('username') or r.get('UserName') or 'Desconocido'}: {r.get('content') or r.get('Content') or ''}" for r in display_list])

            prompt = (
                f"Genera un resumen conciso y directo de esta conversación. "
                f"Tono casual, sin florituras:\n\n{historial}\n\nResumen:"
            )
            resumen = await self.bot.nlp_service.generate_reply(
                prompt, "Resumen", "Sistema",
                system_prompt_override="Eres un asistente analítico y neutral especializado en resumir conversaciones. No tienes personalidad, no haces chistes."
            )
            if not resumen:
                return await interaction.followup.send("no pude generar el resumen.")

            embed = discord.Embed(
                title=f"📄 Resumen de {len(registros)} mensajes",
                description=resumen,
                color=0xFF8C42
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /resumir: {e}")
            await interaction.followup.send("error generando el resumen.", ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Lock / Unlock
    # ------------------------------------------------------------------

    @app_commands.command(name="lock", description="[ADMIN] Bloquea los comandos de Dalet en este canal.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_lock(self, interaction: discord.Interaction):
        try:
            await self.bot.admin_repo.set_channel_lock(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, interaction.guild.name, True
            )
            await interaction.response.send_message(
                f"🔒 Canal **{interaction.channel.mention}** bloqueado. Los comandos de Dalet están desactivados.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /lock: {e}")
            await interaction.response.send_message("❌ error al bloquear el canal.", ephemeral=True)

    @app_commands.command(name="unlock", description="[ADMIN] Desbloquea los comandos de Dalet en este canal.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_unlock(self, interaction: discord.Interaction):
        try:
            await self.bot.admin_repo.set_channel_lock(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, interaction.guild.name, False
            )
            await interaction.response.send_message(
                f"🔓 Canal **{interaction.channel.mention}** desbloqueado.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /unlock: {e}")
            await interaction.response.send_message("❌ error al desbloquear el canal.", ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Proactive / Reactive
    # ------------------------------------------------------------------

    @app_commands.command(name="proactive", description="[ADMIN] Activa o desactiva el modo proactivo en este canal.")
    @app_commands.describe(activar="True para activar, False para desactivar")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_proactive(self, interaction: discord.Interaction, activar: bool):
        try:
            await self.bot.user_repo.set_channel_proactive(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, activar
            )
            estado = "activado ✅" if activar else "desactivado 🛑"
            await interaction.response.send_message(
                f"Modo proactivo **{estado}** en {interaction.channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /proactive: {e}")
            await interaction.response.send_message("❌ error configurando el modo proactivo.", ephemeral=True)

    @app_commands.command(name="reactive", description="[ADMIN] Activa o desactiva el modo reactivo (respuesta a menciones) en el servidor.")
    @app_commands.describe(activar="True para activar, False para desactivar")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_reactive(self, interaction: discord.Interaction, activar: bool):
        try:
            await self.bot.user_repo.set_server_reactive(
                interaction.guild_id, interaction.guild.name, activar
            )
            estado = "activado ✅" if activar else "desactivado 🛑"
            await interaction.response.send_message(
                f"Modo reactivo **{estado}** en este servidor.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /reactive: {e}")
            await interaction.response.send_message("❌ error configurando el modo reactivo.", ephemeral=True)


    # ------------------------------------------------------------------
    # Admin: Welcome Channel
    # ------------------------------------------------------------------

    @app_commands.command(name="setwelcome", description="[ADMIN] Establece el canal de bienvenida del servidor.")
    @app_commands.describe(canal="Canal donde Dalet enviará los mensajes de bienvenida")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setwelcome(self, interaction: discord.Interaction, canal: discord.TextChannel):
        try:
            await self.bot.admin_repo.set_welcome_channel(interaction.guild_id, canal.id)
            await interaction.response.send_message(
                f"✅ Canal de bienvenida establecido en {canal.mention}.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /setwelcome: {e}")
            await interaction.response.send_message("❌ error al configurar el canal de bienvenida.", ephemeral=True)

    @app_commands.command(name="removewelcome", description="[ADMIN] Elimina el canal de bienvenida del servidor.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_removewelcome(self, interaction: discord.Interaction):
        try:
            await self.bot.admin_repo.set_welcome_channel(interaction.guild_id, None)
            await interaction.response.send_message(
                "🗑️ Canal de bienvenida eliminado. Ya no se enviarán bienvenidas.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /removewelcome: {e}")
            await interaction.response.send_message("❌ error al eliminar el canal de bienvenida.", ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Nombre personalizado del bot
    # ------------------------------------------------------------------

    @app_commands.command(name="setname", description="[ADMIN] Establece un nombre personalizado para Dalet en este servidor.")
    @app_commands.describe(nombre="Nombre personalizado (máx. 32 caracteres)")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setname(self, interaction: discord.Interaction, nombre: str):
        if len(nombre) > 32:
            return await interaction.response.send_message(
                "❌ el nombre no puede superar los 32 caracteres.", ephemeral=True
            )
        try:
            await self.bot.admin_repo.set_server_custom_name(interaction.guild_id, nombre)
            await interaction.response.send_message(
                f"✅ Ahora me llamo **{nombre}** en este servidor.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /setname: {e}")
            await interaction.response.send_message("❌ error al cambiar el nombre.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))

