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
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer

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

    @app_commands.command(name="info", description="Tarjeta de presentación e información de Dalet.")
    async def slash_info(self, interaction: discord.Interaction):
        from ui.molecules import DaletMolecules
        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Dalet {DaletAtoms.VERSION}",
            description=(
                f'> *"searching who asked"*\n\n'
                f"{DaletAtoms.GLYPH_POINTER} **Creador**: Litxe\n"
                f"{DaletAtoms.GLYPH_POINTER} **Estado**: En línea y juzgando tus jugadas\n"
                f"{DaletAtoms.GLYPH_POINTER} **Prefijo**: `d.` o mención `@Dalet`\n\n"
                f"{DaletAtoms.GLYPH_SUB} Escribe `d.changelog` para ver las novedades de la versión.\n"
                f"{DaletAtoms.GLYPH_SUB} Escribe `d.help` para consultar el menú de comandos."
            ),
            color=DaletAtoms.COLOR_PRIMARY
        )
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        DaletMolecules.add_standard_footer(embed, context_text=f"{DaletAtoms.VERSION} │ Litxe")
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
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(username, modo)
            embed = OsuPresenter.build_profile_card(user, modo, lang=server_lang)
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
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(username, modo)
            recent = await self.bot.osu_service.get_user_recent_scores(
                user["id"], modo, limit=1, include_fails=1
            )
            if not recent:
                return await interaction.followup.send(
                    f"**{username}** no tiene jugadas recientes."
                )

            embed = OsuPresenter.build_recent_card(user.get("username", username), modo, recent[0], user_data=user, lang=server_lang)
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
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(username, modo)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=modo, limit=5)
            embed = OsuPresenter.build_top_card(user.get("username", username), modo, best, user_data=user, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /top: {e}")
            await interaction.followup.send("⚠️ error obteniendo top plays.", ephemeral=True)

    @app_commands.command(name="skills", description="Desglose de habilidades osu! (Aim, Speed, Acc, Stamina, Reading) con veredicto de Dalet.")
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
    async def slash_skills(
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
                    "❌ no tienes cuenta vinculada. usa `/link` primero o especifica un usuario.",
                    ephemeral=True
                )

            user = await self.bot.osu_service.get_user(username, modo)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=modo, limit=50)
            if not best:
                return await interaction.followup.send(f"**{username}** no tiene mejores jugadas registradas en {modo}.")

            skills_data = OsuAnalyzer.calculate_skills(best)

            dominant = skills_data.get("dominant_skill", "Aim")
            weakest = skills_data.get("weakest_skill", "Stamina")
            overall = skills_data.get("overall_skill_stars", 0.0)
            stats = user.get("statistics", {})
            gr = stats.get("global_rank") or "N/A"

            server_lang = "en"
            if interaction.guild_id:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
                except Exception:
                    server_lang = "en"

            is_es = server_lang == "es"
            if is_es:
                micro_prompt = (
                    f"ROL: Eres Dalet, una bot cínica, técnica y experta en osu!.\n"
                    f"TAREA: Haz un roast o veredicto técnico contundente (MÁXIMO 2 ORACIONES, 30-40 palabras) sobre el perfil de {username}:\n"
                    f"- Habilidad dominante: {dominant} ({skills_data[dominant]['stars']}★)\n"
                    f"- Habilidad más débil: {weakest} ({skills_data[weakest]['stars']}★)\n"
                    f"- Promedio de estrellas: {overall}★\n"
                    f"- Rank global: #{gr}\n"
                    f"REGLAS: Búrlate con sarcasmo de su debilidad en {weakest} comparado con su {dominant}. Máximo 1 emoji. Cero rodeos. IDIOMA: Español."
                )
                fallback_roasts = {
                    "Speed": "Mucho DT farmeado en mapas cortos, pero ponle una stream rápida y se te traba el cerebro.",
                    "Stamina": "Aguantas maratones eternos de relleno, lástima que ante una ráfaga de velocidad te derritas.",
                    "Aim": "Metes buen acc en ritmos planos, pero te mueven los círculos dos milímetros y ya estás tirando miss.",
                    "Accuracy": "Mucho combo y estrellitas infladas, pero ese acc parece que tocas el teclado con guantes de boxeo.",
                    "Reading": "Buen reading en mapas lentos, pero te suben el AR a 10.3 y ni te enteras de qué nota fallaste."
                }
            else:
                micro_prompt = (
                    f"ROLE: You are Dalet, a cynical, witty, and sharp osu! expert.\n"
                    f"TASK: Write a biting technical roast (MAX 2 SHORT SENTENCES, 30-40 words) about {username}'s profile in English:\n"
                    f"- Dominant skill: {dominant} ({skills_data[dominant]['stars']}★)\n"
                    f"- Weakest skill: {weakest} ({skills_data[weakest]['stars']}★)\n"
                    f"- Overall stars: {overall}★\n"
                    f"- Global rank: #{gr}\n"
                    f"RULES: Mock their weak {weakest} compared to their {dominant} with dry sarcasm. Max 1 emoji. No filler. LANGUAGE: English."
                )
                fallback_roasts = {
                    "Speed": "Lots of DT farmed on short maps, but throw you a fast stream and your hands fall apart.",
                    "Stamina": "You can endure endless marathon filler, too bad you melt the second any speed burst hits.",
                    "Aim": "Decent accuracy on flat rhythms, but move the circles two millimeters and you're already dropping misses.",
                    "Accuracy": "Inflated star rating and combo, but with that accuracy you might as well be tapping with boxing gloves.",
                    "Reading": "Decent reading on slow maps, but bump the AR to 10.3 and you won't even know which note you choked."
                }

            roast_text = None
            try:
                roast_text = await self.bot.nlp_service.generate_reply(
                    micro_prompt, "Skill Roast", username,
                    max_tokens_override=120,
                    language=server_lang
                )
            except Exception as nlp_err:
                logger.warning(f"No se pudo generar roast para slash skills ({username}): {nlp_err}")

            if not roast_text:
                fallback_default = f"Mucho número inflado en {dominant}, pero en {weakest} das pena ajena." if is_es else f"Over-inflated numbers in {dominant}, but your {weakest} is embarrassing."
                roast_text = fallback_roasts.get(weakest, fallback_default)

            embed = OsuPresenter.build_skills_card(user, skills_data, roast_text=roast_text, mode=modo, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /skills: {e}")
            await interaction.followup.send("⚠️ error calculando las habilidades.", ephemeral=True)

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
            medals = ["✦", "◈", "◇"]
            lines = []
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`{i+1}.`"
                name = row.get("UserName") or row.get("username") or row.get("osuusername") or "??"
                pp = float(row.get("PP") or row.get("pp") or 0)
                acc = float(row.get("Accuracy") or row.get("accuracy") or 0)
                lines.append(f"{medal} **{name}** — {pp:,.0f}pp • {acc:.2f}%")
            embed = discord.Embed(
                title=f"{DaletAtoms.EMOJI_DALET} Ranking osu! del Servidor",
                description="\n".join(lines),
                color=DaletAtoms.COLOR_PRIMARY
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
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            embed = OsuPresenter.build_compare_card(u1, u2, lang=server_lang)
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

    # ------------------------------------------------------------------
    # Admin: Idioma del servidor (English / Español)
    # ------------------------------------------------------------------

    @app_commands.command(name="language", description="[ADMIN] Changes or displays the server language / Cambia el idioma del servidor.")
    @app_commands.describe(idioma="Elige el idioma del servidor (en: English, es: Español)")
    @app_commands.choices(idioma=[
        app_commands.Choice(name="English (Default)", value="en"),
        app_commands.Choice(name="Español", value="es"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_language(self, interaction: discord.Interaction, idioma: str = None):
        if not interaction.guild_id:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

        if not idioma:
            current = await self.bot.admin_repo.get_server_language(interaction.guild_id)
            lang_name = "English" if current == "en" else "Español"
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_POINTER} Current server language is **{lang_name}** (`{current}`).\n"
                f"{DaletAtoms.GLYPH_SUB} Use `/language [idioma]` to change it.",
                ephemeral=True
            )

        await self.bot.admin_repo.set_server_language(interaction.guild_id, idioma)
        if idioma == "es":
            await interaction.response.send_message(
                f"{DaletAtoms.EMOJI_DALET} Idioma del servidor actualizado a **Español**. Dalet responderá y mostrará estadísticas en español.",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                f"{DaletAtoms.EMOJI_DALET} Server language updated to **English**. Dalet will now chat and format statistics in English.",
                ephemeral=False
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))

