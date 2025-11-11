"""
Handler (Cog) para todos los comandos de osu!.

Este es el Cog más complejo. Integra:
1. API de osu! (a través del módulo 'osu_api').
2. Lógica de análisis de IA (a través del módulo 'dalet_osuanalyzer').
3. Lógica de Base de Datos (CRUD en 'OsuAccounts' y 'OsuScores').
4. Lógica de Vistas y Funciones (consumiendo 'V_OsuRankingGlobal' y 'fn_GetScoreHistory').
5. Lógica de Triggers (disparando 'trg_AuditPPChanges').
"""
import discord
from discord.ext import commands
from handlers.modules.osu_api import OsuAPI
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai # Necesario para osuCoach
import os
import asyncio
import db_connector
from datetime import datetime, timezone
import traceback
from discord.utils import format_dt # Para formatear la fecha

# --- Clases Paginator (UI para comandos) ---
class AnalysisPaginator(discord.ui.View):
    """Paginador para el análisis de 'osuAnalyze' (campos de Embed)."""
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self.update_buttons()
    def update_buttons(self):
        if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1
    async def update_embed(self, interaction: discord.Interaction):
        if not interaction.message.embeds: return
        embed = interaction.message.embeds[0]
        if len(embed.fields) > 3:
             embed.set_field_at(index=3, name=f"🧠 Análisis de Dalet (Página {self.index + 1}/{len(self.pages)})", value=self.pages[self.index], inline=False)
             self.update_buttons()
             await interaction.response.edit_message(embed=embed, view=self)
        else: await interaction.response.defer()
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0: self.index -= 1; await self.update_embed(interaction)
        else: await interaction.response.defer()
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_embed(interaction)
        else: await interaction.response.defer()

class DescriptionPaginator(discord.ui.View):
    """Paginador para 'osuCoach' (descripción de Embed)."""
    def __init__(self, pages, embed_shell):
        super().__init__(timeout=180)
        self.pages = pages
        self.embed_shell = embed_shell
        self.index = 0
        self.update_view()
    def update_view(self):
         if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1
            self.embed_shell.set_footer(text=f"Página {self.index + 1} de {len(self.pages)}")
    async def update_message(self, interaction: discord.Interaction):
        self.update_view()
        self.embed_shell.description = self.pages[self.index]
        await interaction.response.edit_message(embed=self.embed_shell, view=self)
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0: self.index -= 1; await self.update_message(interaction)
        else: await interaction.response.defer()
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_message(interaction)
        else: await interaction.response.defer()

# --- Cog Principal de osu! ---

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis con IA."""

    def __init__(self, bot):
        self.bot = bot
        client_id = os.getenv("OSU_CLIENT_ID")
        client_secret = os.getenv("OSU_CLIENT_SECRET")
        if not client_id or not client_secret:
             print("!!!!!! [osu! Cog] ADVERTENCIA: Credenciales de osu! no encontradas.")
             self.osu = None
        else:
             try:
                  self.osu = OsuAPI(client_id=int(client_id), client_secret=client_secret)
                  print("--- [osu! Cog] OsuAPI inicializada.")
             except Exception as e:
                  print(f"!!!!!! [osu! Cog] ERROR al inicializar OsuAPI: {e}")
                  self.osu = None

    async def _get_linked_username(self, ctx):
        """
        Función auxiliar para obtener el nombre de osu! vinculado desde la BD.
        
        Intenta obtener el nombre de usuario directamente desde la tabla 'OsuAccounts'.
        Reemplaza la función 'fn_GetOsuUsername' para un rendimiento óptimo
        en este Cog.
        """
        try:
            query = "SELECT osuusername FROM osuaccounts WHERE userid = %s LIMIT 1"
            result = db_connector.fetch_one(query, (ctx.author.id,))
            
            if result and result[0]:
                return str(result[0]).strip()
            else:
                return None
        except Exception as e:
             print(f"!!!!!! [osu! Cog] ERROR en _get_linked_username: {e}")
             return None

    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
         """
         Vincula tu cuenta de Discord con tu perfil de osu! y guarda tus stats.
         
         Llama a la API de osu! para obtener los datos más recientes y luego
         llama al SP 'sp_LinkOsuAccount' (Req 3) para hacer un "Upsert"
         en la tabla 'OsuAccounts'.
         """
         if not self.osu: return await ctx.send("❌ Error: La API de osu! no está configurada.")
         async with ctx.typing():
             try:
                 user_data = self.osu.get_user(osu_username)
             except Exception as e_api:
                 print(f"!!!!!! [osu! Cog] ERROR en API (link): {e_api}")
                 await ctx.send(f"❌ Error al contactar la API de osu! para buscar a '{osu_username}'.")
                 return

             if not user_data or 'statistics' not in user_data:
                 await ctx.send(f"❌ No se encontró un jugador con el nombre '{osu_username}'.")
                 return

             stats = user_data.get('statistics', {})
             try:
                 # Llama al SP con todos los datos del perfil (Req 3)
                 db_connector.execute_procedure(
                     "sp_LinkOsuAccount",
                     (
                         ctx.author.id, user_data["username"], user_data["id"],
                         user_data.get('playmode', 'osu'), stats.get('pp', 0.0),
                         stats.get('global_rank', None), stats.get('country_rank', None),
                         stats.get('hit_accuracy', 0.0)
                     )
                 )
                 await ctx.send(f"✅ ¡Tu cuenta ha sido vinculada con **{user_data['username']}** y tus estadísticas han sido guardadas!")
             except Exception as e_db:
                 await ctx.send("❌ Hubo un error al guardar la vinculación en la base de datos.")
                 print(f"!!!!!! [osu! Cog] ERROR en DB (link): {e_db}")

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """
        Desvincula tu cuenta de osu!.
        
        Llama al SP 'sp_UnlinkOsuAccount' (Req 3) para eliminar
        el registro de 'OsuAccounts'.
        """
        try:
             db_connector.execute_procedure("sp_UnlinkOsuAccount", (ctx.author.id,))
             await ctx.send("✅ Vinculación con osu! eliminada (si existía).")
        except Exception as e:
             await ctx.send("❌ Hubo un error al intentar desvincular la cuenta.")
             print(f"!!!!!! [osu! Cog] Error en DB (unlink): {e}")

    @commands.command(help="Muestra un perfil detallado de osu!.\nUso: `d.op [usuario] [-modo]`", aliases=["op"])
    async def osuProfile(self, ctx, *, args: str = None):
        """
        Muestra un perfil detallado de osu!.
        
        Si no se da un nombre, usa la cuenta vinculada de la BD.
        Parsea los argumentos para modo (ej. -mania).
        Llama a la API de osu! para obtener datos frescos.
        """
        if not self.osu: return await ctx.send("❌ Error: La API de osu! no está configurada.")

        username, mode, is_linked = None, "osu", False

        # --- Parseo de argumentos ---
        if args:
             parts = args.split()
             username_parts = []
             temp_mode = None
             for part in parts:
                 if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                     temp_mode = part[1:].lower()
                 else:
                     username_parts.append(part)
             
             if username_parts: username = " ".join(username_parts).strip()
             if temp_mode: mode = temp_mode
        else:
            # Usamos la función auxiliar si no hay argumentos
            username = await self._get_linked_username(ctx)
            if not username:
                await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <tu_usuario_osu>` o especifica un nombre.")
                return
            is_linked = True

        await ctx.typing()
        try:
             # Llamada a la API de osu!
             user = self.osu.get_user(username, mode)
             if not user or 'id' not in user:
                 await ctx.send(f"❌ No se pudo encontrar al jugador '{username}' en el modo '{mode}'.")
                 return

             # --- Crear y enviar Embed ---
             stats = user.get("statistics", {})
             grades = stats.get("grade_counts", {})
             play_time_seconds = stats.get("play_time", 0)
             play_time_hours = round(play_time_seconds / 3600) if play_time_seconds else 0
             country_code = user.get("country_code", "xx")
             global_rank = stats.get('global_rank')
             global_rank_formatted = f"#{global_rank:,}" if global_rank else "N/A"
             country_rank = stats.get('country_rank')
             country_rank_formatted = f"#{country_rank:,}" if country_rank else "N/A"
             mode_colors = {"osu": 0xFF66AA, "taiko": 0xDA3B26, "fruits": 0x86BA40, "mania": 0x5885C9}

             embed = discord.Embed(
                 title=f"Perfil de {user['username']}",
                 url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                 description=f"**Mostrando estadísticas para: `{mode.capitalize()}`**",
                 color=mode_colors.get(mode, 0x7289DA)
             )
             avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
             embed.set_thumbnail(url=avatar_url)

             main_stats_text = (
                 f"**País:** :flag_{country_code.lower()}: `{country_rank_formatted}`\n"
                 f"**Rango Global:** 🏆 `{global_rank_formatted}`\n"
                 f"**PP:** 📈 `{stats.get('pp', 0):,.2f}`\n"
                 f"**Precisión:** 🎯`{stats.get('hit_accuracy', 0):.2f}%`\n"
                 f"**Nivel:** ✨ `{stats.get('level', {}).get('current', 0)}` (`{stats.get('level', {}).get('progress', 0)}%`)\n"
                 f"**Tiempo de Juego:** 🕒 `{play_time_hours:,} horas`\n"
                 f"**Playcount:** 🖱️ `{stats.get('play_count', 0):,}`"
            )
             embed.add_field(name=f"Estadísticas de {mode.capitalize()}", value=main_stats_text, inline=False)

             if grades:
                 ssh_count = grades.get('ssh', 0) or 0; ss_count = grades.get('ss', 0) or 0
                 sh_count = grades.get('sh', 0) or 0; s_count = grades.get('s', 0) or 0
                 a_count = grades.get('a', 0) or 0
                 grades_text = f"**SS:** `{ssh_count + ss_count:,}` | **S:** `{sh_count + s_count:,}` | **A:** `{a_count:,}`"
                 embed.add_field(name="Calificaciones", value=grades_text, inline=False)

             if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")
             await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [osu! Cog] ERROR en osuProfile: {e}")
            await ctx.send(f"⚠️ Error al obtener el perfil de '{username}'. Verifica el nombre y modo.")

    async def _run_analysis_or_coach(self, ctx, args: str, mode: str):
        """
        Función auxiliar interna que ejecuta la lógica común
        para 'osuAnalyze' y 'osuCoach'.
        
        Flujo:
        1. Parsea argumentos (usuario, modo, focus).
        2. Obtiene el usuario vinculado si no se provee nombre.
        3. Llama a la API de osu! para 'user', 'best_scores', 'recent_scores'.
        4. Llama a 'sp_LinkOsuAccount' (para disparar el Trigger de auditoría - Req 6).
        5. Llama a 'sp_SaveOrUpdateOsuScore' (para guardar scores y disparar Trigger de validación).
        6. Llama al módulo 'OsuAnalyzer' para generar el prompt de IA.
        7. Llama a Gemini para la respuesta.
        8. Envía el Embed paginado.
        """
        if not self.osu:
             print("!!!!!! [osu! Cog] OsuAPI no inicializada.")
             return await ctx.send("❌ Error: La API de osu! no está configurada."), None, None, None

        username, user_focus, is_linked = None, None, False

        try:
            if args:
                 parts = args.split(); username_parts = []; i = 0
                 while i < len(parts):
                      part = parts[i]
                      if part.lower() == '--focus' and i + 1 < len(parts):
                           user_focus = parts[i+1].lower(); i += 2; continue
                      if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                           mode = part[1:].lower(); i += 1; continue
                      username_parts.append(part); i += 1
                 if username_parts: username = " ".join(username_parts).strip()
        except Exception as e_parse:
            print(f"!!!!!! [osu! Cog] ERROR parseando args: {e_parse}")
            await ctx.send("❌ Error al procesar los argumentos.")
            return None, None, None, None

        if not username:
            username = await self._get_linked_username(ctx)
            if not username:
                 await ctx.send("❌ No tienes cuenta vinculada ni especificaste nombre.")
                 return None, None, None, None
            is_linked = True

        await ctx.typing()

        user = self.osu.get_user(username, mode)
        if not user or 'id' not in user:
             await ctx.send(f"❌ No se pudo encontrar '{username}' en modo '{mode}'.")
             return None, None, None, None

        best_scores, recent_scores = [], []
        try:
             best_scores = self.osu.get_user_best_scores(user["id"], mode, 50)
             recent_scores = self.osu.get_user_recent_scores(user["id"], mode, 50)
        except Exception as e_scores:
             print(f"!!!!!! [osu! Cog] ERROR al obtener scores: {e_scores}")
             await ctx.send("⚠️ No se pudieron obtener scores, análisis limitado.")

        # --- Actualizar BD (Triggers) ---
        # 1. Actualizar OsuAccounts (Dispara el Trigger de auditoría 'trg_AuditPPChanges')
        try:
            stats = user.get('statistics', {})
            db_connector.execute_procedure(
                "sp_LinkOsuAccount",
                (
                    ctx.author.id, user["username"], user["id"],
                    user.get('playmode', 'osu'), stats.get('pp', 0.0),
                    stats.get('global_rank', None), stats.get('country_rank', None),
                    stats.get('hit_accuracy', 0.0)
                )
            )
        except Exception as e_db:
            print(f"!!!!!! [osu! Cog] ERROR al actualizar OsuAccounts (Trigger): {e_db}")

        # 2. Guardar Scores (Dispara el Trigger de validación 'trg_ValidateScore')
        for score_type, scores in [('best', best_scores), ('recent', recent_scores)]:
            for score in scores:
                try:
                    mods_str = "".join(score.get('mods', []))
                    timestamp = datetime.fromisoformat(score.get('created_at').replace('Z', '+00:00')) if score.get('created_at') else datetime.now(timezone.utc)
                    beatmap_info = score.get('beatmap')
                    if not beatmap_info or 'id' not in beatmap_info: continue

                    db_connector.execute_procedure(
                        "sp_SaveOrUpdateOsuScore",
                        (
                            score['id'], ctx.author.id, user['id'], beatmap_info['id'], 
                            score['score'], score['accuracy'], mods_str, score_type, timestamp
                        )
                    )
                except Exception as e_proc:
                     print(f"!!!!!! [osu! Cog] ERROR en sp_SaveOrUpdateOsuScore: {e_proc}")

        # Devolver datos para el comando específico
        return user, best_scores, recent_scores, user_focus, is_linked, mode

    @commands.command(name="osuAnalyze", help="Analiza el perfil de osu! con IA.\nUso: `d.osuAnalyze [usuario] [-modo] [--focus <area>]`")
    async def osu_analyze(self, ctx, *, args: str = None):
        """
        Analiza el perfil de osu! de un usuario usando la IA.
        
        Este comando llama a la función auxiliar '_run_analysis_or_coach'
        para obtener y guardar todos los datos (lo que dispara los Triggers).
        Luego, usa 'OsuAnalyzer' para generar un prompt de ANÁLISIS.
        """
        try:
            user, best_scores, recent_scores, user_focus, is_linked, mode = await self._run_analysis_or_coach(ctx, args, "osu")
            if not user: return # El error ya se envió

            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            prompt = analyzer.generate_ai_analysis() # Usar el método síncrono

            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=45.0)
            ai_text = response.text.strip()

            if not ai_text:
                await ctx.send("❌ La IA no pudo generar un análisis esta vez.")
                return

            embed = discord.Embed(title=f"Análisis de {user['username']} (Modo: {mode.capitalize()})", color=0x9932CC)
            stats = user.get("statistics", {})
            embed.set_thumbnail(url=user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png"))
            embed.add_field(name="PP", value=f"{stats.get('pp', 0):.2f}", inline=True)
            embed.add_field(name="Accuracy", value=f"{stats.get('hit_accuracy', 0):.2f}%", inline=True)
            global_rank = stats.get('global_rank')
            embed.add_field(name="Rank", value=f"#{global_rank:,}" if global_rank else "N/A", inline=True)
            if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")

            PAGE_LIMIT = 1024
            if len(ai_text) <= PAGE_LIMIT:
                 embed.add_field(name="🧠 Análisis de Dalet", value=ai_text, inline=False)
                 await ctx.send(embed=embed)
            else:
                 pages = [ai_text[i:i + PAGE_LIMIT] for i in range(0, len(ai_text), PAGE_LIMIT)]
                 embed.add_field(name=f"🧠 Análisis de Dalet (Página 1/{len(pages)})", value=pages[0], inline=False)
                 await ctx.send(embed=embed, view=AnalysisPaginator(pages))

        except asyncio.TimeoutError:
             await ctx.send("⏳ La IA tardó mucho en responder. Intenta de nuevo.")
        except Exception as e:
            print(f"!!!!!! [osu! Cog] ERROR INESPERADO en osuAnalyze: {e}")
            traceback.print_exc()
            await ctx.send("⚠️ Error inesperado al generar el análisis.")

    @commands.command(help="Genera un plan de coaching de osu!...", aliases=["oc"])
    async def osuCoach(self, ctx, *, args: str = None):
        """
        Genera un plan de coaching de osu! usando la IA.
        
        Llama a '_run_analysis_or_coach' para obtener/guardar datos (Triggers).
        Luego, usa 'OsuAnalyzer' para generar un prompt de COACHING.
        """
        try:
            user, best_scores, recent_scores, user_focus, is_linked, mode = await self._run_analysis_or_coach(ctx, args, "osu")
            if not user: return # El error ya se envió

            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            prompt = await analyzer.generate_coaching_prompt() # Usar el método asíncrono

            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=60.0) # Timeout más largo
            ai_text = response.text.strip()

            if not ai_text:
                await ctx.send("❌ La IA no pudo generar un plan de coaching esta vez.")
                return

            embed_shell = discord.Embed(title=f"Plan de Coaching para {user['username']}", color=0xFFD700)
            embed_shell.set_thumbnail(url=user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png"))
            if is_linked: embed_shell.set_footer(text="Mostrando perfil vinculado.")
            
            PAGE_CHAR_LIMIT = 1800
            if len(ai_text) <= PAGE_CHAR_LIMIT:
                embed_shell.description = ai_text
                await ctx.send(embed=embed_shell)
            else:
                pages = [ai_text[i:i + PAGE_CHAR_LIMIT] for i in range(0, len(ai_text), PAGE_CHAR_LIMIT)]
                embed_shell.description = pages[0]
                await ctx.send(embed=embed_shell, view=DescriptionPaginator(pages, embed_shell))

        except asyncio.TimeoutError:
             await ctx.send("⏳ La IA tardó mucho en responder. Intenta de nuevo.")
        except Exception as e:
            print(f"!!!!!! [osu! Cog] ERROR INESPERADO en osuCoach: {e}")
            traceback.print_exc()
            await ctx.send("⚠️ Error inesperado al generar el plan de coaching.")

    @commands.command(name="ranking", help="Muestra el ranking de PP del bot.")
    async def osu_ranking(self, ctx, limit: int = 10):
        """
        Muestra el ranking de PP de usuarios vinculados en el bot.
        
        Consume la vista 'V_OsuRankingGlobal' (Req 4c y 5a).
        """
        if limit > 25: limit = 25 # Evitar spam

        try:
            query = "SELECT UserName, PP, Accuracy, CalculatedRank FROM V_OsuRankingGlobal LIMIT %s"
            ranking_data = db_connector.fetch_all(query, (limit,))

            if not ranking_data:
                return await ctx.send("No hay datos de ranking disponibles.")

            embed = discord.Embed(
                title="🏆 Ranking Global de PP (Usuarios de Dalet)",
                color=0xFF66AA
            )
            
            description = ""
            for row in ranking_data:
                # row[0]=UserName, row[1]=PP, row[2]=Accuracy, row[3]=CalculatedRank
                description += f"**{row[3]}. {row[0]}** - `{row[1]:,.2f} pp` (`{row[2]:.2f}%`)\n"
            
            embed.description = description
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error al obtener el ranking: {e}")
            print(f"!!!!!! [osu! Cog] ERROR en osu_ranking: {e}")

    @commands.command(name="scorehistory", help="Muestra tu historial de accuracy en 'best plays'.")
    async def osu_score_history(self, ctx):
        """
        Muestra la evolución de accuracy de tus 'best plays' guardadas.
        
        Consume la función 'fn_GetScoreHistory' (Req 4d y 5a).
        """
        try:
            query = "SELECT * FROM fn_GetScoreHistory(%s, 10)"
            history_data = db_connector.fetch_all(query, (ctx.author.id,))

            if not history_data:
                return await ctx.send("No tienes historial de scores (tipo 'best') guardado.")

            embed = discord.Embed(
                title=f"📈 Historial de 'Best Plays' de {ctx.author.name}",
                description="Muestra la ganancia/pérdida de accuracy entre tus 'best plays' guardadas.",
                color=0x5885C9
            )

            for row in history_data:
                # El guion bajo (_) ignora el ScoreID, que es la primera columna (row[0])
                _, accuracy, change, timestamp = row[0], row[1], row[2], row[3]
                change_str = "N/A"
                if change is not None:
                    change_str = f"+{change:.2f}%" if change > 0 else f"{change:.2f}%"
                
                field_name = f"{format_dt(timestamp, 'D')}" # Formato de fecha
                field_value = f"**Acc:** `{accuracy:.2f}%` (Cambio: `{change_str}`)"
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            embed.set_footer(text="El cambio se compara con el 'best play' guardado anteriormente.")
            await ctx.send(embed=embed)
        
        except Exception as e:
            await ctx.send(f"❌ Error al obtener tu historial de scores: {e}")
            print(f"!!!!!! [osu! Cog] ERROR en scorehistory: {e}")

async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    print("--- [osu! Cog] Ejecutando setup...")
    client_id = os.getenv("OSU_CLIENT_ID")
    client_secret = os.getenv("OSU_CLIENT_SECRET")
    if client_id and client_secret:
        try:
             int(client_id)
             await bot.add_cog(OsuHandler(bot))
             print("--- [osu! Cog] Cog OsuHandler añadido exitosamente.")
        except ValueError:
             print(f"!!!!!! [osu! Cog] ERROR: OSU_CLIENT_ID ('{client_id}') no es número.")
        except Exception as e:
             print(f"!!!!!! [osu! Cog] ERROR al añadir cog: {e}")
    else:
        print("!!!!!! [osu! Cog] ADVERTENCIA: Faltan credenciales osu!. Cog no cargado.")