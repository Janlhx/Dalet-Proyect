import discord
from discord.ext import commands
# Asegúrate de tener los imports correctos
from handlers.modules.osu_api import OsuAPI
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai # Necesario para osuCoach
import os
import asyncio # Necesario para timeouts si los usas
# Import del conector
import db_connector
from datetime import datetime, timezone # Necesitamos importar timezone
# Import para traceback
import traceback
from discord.utils import format_dt # Para formatear la fecha
# --- Clases Paginator (sin cambios) ---
class AnalysisPaginator(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self.update_buttons()
    def update_buttons(self):
        # Asegurarse de que los botones existen antes de deshabilitarlos
        if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1
    async def update_embed(self, interaction: discord.Interaction):
        # Verificar si hay embed antes de intentar modificarlo
        if not interaction.message.embeds: return
        embed = interaction.message.embeds[0]
        # Asegurarse de que el campo existe
        if len(embed.fields) > 3:
             embed.set_field_at(index=3, name=f"🧠 Análisis de Dalet (Página {self.index + 1}/{len(self.pages)})", value=self.pages[self.index], inline=False)
             self.update_buttons()
             await interaction.response.edit_message(embed=embed, view=self)
        else:
             await interaction.response.defer() # No hacer nada si la estructura no es la esperada
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button): # Añadir tipos
        if self.index > 0: self.index -= 1; await self.update_embed(interaction)
        else: await interaction.response.defer() # Importante deferir si no hay acción
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button): # Añadir tipos
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_embed(interaction)
        else: await interaction.response.defer() # Importante deferir si no hay acción

class DescriptionPaginator(discord.ui.View):
    def __init__(self, pages, embed_shell):
        super().__init__(timeout=180)
        self.pages = pages
        self.embed_shell = embed_shell # Guardamos el embed base
        self.index = 0
        self.update_view() # Actualizar estado inicial
    def update_view(self):
        # Asegurarse de que los botones existen
         if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1
            # Actualizar el footer del embed base
            self.embed_shell.set_footer(text=f"Página {self.index + 1} de {len(self.pages)}")
    async def update_message(self, interaction: discord.Interaction):
        self.update_view()
        # Modificar la descripción del embed base
        self.embed_shell.description = self.pages[self.index]
        await interaction.response.edit_message(embed=self.embed_shell, view=self)
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button): # Añadir tipos
        if self.index > 0: self.index -= 1; await self.update_message(interaction)
        else: await interaction.response.defer() # Deferir si no hay acción
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button): # Añadir tipos
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_message(interaction)
        else: await interaction.response.defer() # Deferir si no hay acción

print("--- [osu! Cog] Archivo dalet_osucommands.py leído por Python ---") # DEBUG INICIAL

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis con IA."""

    def __init__(self, bot):
        print("--- [osu! Cog] Iniciando __init__ de OsuHandler...") # DEBUG INIT
        self.bot = bot
        # Usamos getenv con valores por defecto por si no están definidas
        client_id = os.getenv("OSU_CLIENT_ID")
        client_secret = os.getenv("OSU_CLIENT_SECRET")
        if not client_id or not client_secret:
             print("!!!!!! [osu! Cog] ADVERTENCIA: OSU_CLIENT_ID o OSU_CLIENT_SECRET no encontradas en variables de entorno.")
             self.osu = None # Indicar que la API no está disponible
        else:
             print("--- [osu! Cog] Credenciales osu! encontradas. Inicializando OsuAPI...")
             try:
                  # Asegúrate de pasar los IDs como enteros si OsuAPI los espera así
                  self.osu = OsuAPI(client_id=int(client_id), client_secret=client_secret)
                  print("--- [osu! Cog] OsuAPI inicializada.")
             except ValueError:
                  print("!!!!!! [osu! Cog] ERROR: OSU_CLIENT_ID debe ser un número.")
                  self.osu = None
             except Exception as e:
                  print(f"!!!!!! [osu! Cog] ERROR al inicializar OsuAPI: {e}")
                  self.osu = None
        print("--- [osu! Cog] __init__ completado.") # DEBUG INIT FIN

    # --- Función auxiliar para obtener nombre vinculado (con debug v6 - Consulta Directa) ---
    async def _get_linked_username(self, ctx):
        """Intenta obtener el nombre de usuario vinculado DIRECTAMENTE desde la tabla."""
        print(f"\n--- [_get_linked_username DEBUG v6] Consultando BD para UserID: {ctx.author.id}")
        try:
            # ======================================================
            # ▼▼▼ ¡CAMBIO PRINCIPAL! ▼▼▼
            # Hacemos la consulta SELECT directamente a la tabla
            # ======================================================
            query = "SELECT osuusername FROM osuaccounts WHERE userid = %s LIMIT 1"
            # ======================================================

            result = db_connector.fetch_one(query, (ctx.author.id,)) # Pasar el ID como tupla
            print(f"--- [_get_linked_username DEBUG v6] Resultado DB (consulta directa): {result!r}")

            nombre_db = None
            if result and result[0] is not None:
                # Forzar conversión a string y quitar espacios extra
                nombre_db = str(result[0]).strip()

            if nombre_db: # Comprobar si la cadena no está vacía después de strip()
                print(f"--- [_get_linked_username DEBUG v6] Nombre encontrado: {nombre_db!r}")
                print("-------------------------------------------\n")
                return nombre_db
            else:
                print("--- [_get_linked_username DEBUG v6] No se encontró nombre en BD o resultado vacío/None.")
                print("-------------------------------------------\n")
                return None
        except Exception as e:
             # Imprimir el error pero no enviar mensaje a Discord, devolver None
             print(f"!!!!!! [_get_linked_username DEBUG v6] ERROR al consultar DB directamente: {e}")
             print("-------------------------------------------\n")
             # await ctx.send("❌ Error al consultar tu cuenta vinculada.") # Quitar mensaje de aquí
             return None

    # --- Comandos link y unlink ---
    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
         """Vincula tu cuenta de Discord con tu perfil de osu! y guarda tus stats."""
         if not self.osu: return await ctx.send("❌ Error: La API de osu! no está configurada correctamente en el bot.") # Verificar API
         async with ctx.typing():
             # Intentar obtener datos del usuario
             try:
                 user_data = self.osu.get_user(osu_username)
             except Exception as e_api:
                 print(f"!!!!!! [link DEBUG] ERROR al llamar a self.osu.get_user: {e_api}")
                 await ctx.send(f"❌ Error al contactar la API de osu! para buscar a '{osu_username}'. Intenta de nuevo más tarde.")
                 return

             if not user_data or 'statistics' not in user_data:
                 await ctx.send(f"❌ No se encontró un jugador con el nombre '{osu_username}' o faltan estadísticas en la respuesta de la API.")
                 return

             # Extraer estadísticas
             stats = user_data.get('statistics', {})
             # Asegurarse que playmode venga de user_data si es posible, si no, default 'osu'
             play_mode = user_data.get('playmode', 'osu')
             pp = stats.get('pp', 0.0)
             # Usar None como default si no existen, la BD acepta NULL
             global_rank = stats.get('global_rank', None)
             country_rank = stats.get('country_rank', None)
             accuracy = stats.get('hit_accuracy', 0.0)

             try:
                 # Llamar al procedimiento almacenado
                 db_connector.execute_procedure(
                     "sp_LinkOsuAccount",
                     (
                         ctx.author.id, user_data["username"], user_data["id"],
                         play_mode, pp, global_rank, country_rank, accuracy
                     )
                 )
                 await ctx.send(f"✅ ¡Tu cuenta de osu! ha sido vinculada con **{user_data['username']}** y tus estadísticas han sido guardadas!")
             except Exception as e_db:
                 await ctx.send("❌ Hubo un error al guardar la vinculación en la base de datos.")
                 print(f"Error en el comando link al llamar a sp_LinkOsuAccount: {e_db}")


    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Desvincula tu cuenta de osu!."""
         # No necesita API osu!
        try:
             db_connector.execute_procedure("sp_UnlinkOsuAccount", (ctx.author.id,))
             # Mensaje más informativo
             await ctx.send("✅ Vinculación con osu! eliminada (si existía).")
        except Exception as e:
             await ctx.send("❌ Hubo un error al intentar desvincular la cuenta en la base de datos.")
             print(f"Error en el comando unlink: {e}")


    # --- Comando osuProfile (LIMPIO y usando auxiliar) ---
    @commands.command(help="Muestra un perfil detallado de osu!.\nUso: `d.op [usuario] [-modo]`", aliases=["op"])
    async def osuProfile(self, ctx, *, args: str = None):
        print("\n--- [osuProfile DEBUG v5] --- Intentando ejecutar comando...")
        # Verificar si la API está disponible ANTES de hacer nada
        if not self.osu:
             print("!!!!!! [osuProfile DEBUG v5] OsuAPI no inicializada. Abortando.")
             return await ctx.send("❌ Error: La conexión con la API de osu! no está configurada correctamente en el bot.")

        username, mode, is_linked = None, "osu", False

        # --- Parseo de argumentos ---
        if args:
             parts = args.split()
             username_parts = []
             temp_mode = None # Variable temporal para el modo
             for part in parts:
                 # Verificar si es un flag de modo
                 if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                     temp_mode = part[1:].lower()
                 else: # Si no es flag de modo, es parte del nombre
                     username_parts.append(part)
             
             # Asignar nombre y modo si se encontraron
             if username_parts:
                 username = " ".join(username_parts).strip()
             if temp_mode:
                 mode = temp_mode
        else:
            # Usamos la función auxiliar si no hay argumentos
            username = await self._get_linked_username(ctx)
            if not username:
                # La función auxiliar ya imprimió logs, solo enviamos mensaje a Discord
                await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <tu_usuario_osu>` o especifica un nombre.")
                print("--- [osuProfile DEBUG v5] _get_linked_username devolvió None. Terminando.")
                print("------------------------------\n")
                return # Terminar si no hay nombre vinculado
            is_linked = True
            # Si está vinculado, podríamos querer obtener el modo guardado en DB también? (Futura mejora)

        # --- Si llegamos aquí, TENEMOS un 'username' ---
        print(f"--- [osuProfile DEBUG v5] Intentando obtener perfil para: {username!r}, Modo: {mode}")
        await ctx.typing()
        try:
             # Llamada a la API de osu!
             user = self.osu.get_user(username, mode)
             if not user or 'id' not in user:
                 print(f"!!!!!! [osuProfile DEBUG v5] API osu! no encontró usuario '{username}' en modo '{mode}'.")
                 await ctx.send(f"❌ No se pudo encontrar al jugador '{username}' en el modo '{mode}'.")
                 print("------------------------------\n")
                 return

             # --- Crear y enviar Embed ---
             stats = user.get("statistics", {})
             grades = stats.get("grade_counts", {})
             play_time_seconds = stats.get("play_time", 0)
             play_time_hours = round(play_time_seconds / 3600) if play_time_seconds else 0
             country_code = user.get("country_code", "xx")
             # Manejar rangos None de forma segura
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
             # Usar avatar por defecto si no existe
             avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
             embed.set_thumbnail(url=avatar_url)

             main_stats_text = (
                 f"**País:** :flag_{country_code.lower()}: `{country_rank_formatted}`\n"
                 f"**Rango Global:** 🏆 `{global_rank_formatted}`\n"
                 f"**PP:** 📈 `{stats.get('pp', 0):,.2f}`\n"
                 f"**Precisión:** 🎯`{stats.get('hit_accuracy', 0):.2f}%`\n"
                 f"**Nivel:** ✨ `{stats.get('level', {}).get('current', 0)}` (`{stats.get('level', {}).get('progress', 0)}%`)\n" # Añadir progreso
                 f"**Tiempo de Juego:** 🕒 `{play_time_hours:,} horas`\n"
                 f"**Playcount:** 🖱️ `{stats.get('play_count', 0):,}`"
            )
             embed.add_field(name=f"Estadísticas de {mode.capitalize()}", value=main_stats_text, inline=False)

             if grades: # Asegurarse que grades no sea None o vacío
                 ssh_count = grades.get('ssh', 0) or 0
                 ss_count = grades.get('ss', 0) or 0
                 sh_count = grades.get('sh', 0) or 0
                 s_count = grades.get('s', 0) or 0
                 a_count = grades.get('a', 0) or 0
                 grades_text = f"**SS:** `{ssh_count + ss_count:,}` | **S:** `{sh_count + s_count:,}` | **A:** `{a_count:,}`"
                 embed.add_field(name="Calificaciones", value=grades_text, inline=False)

             if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")

             print(f"--- [osuProfile DEBUG v5] Enviando embed para {username!r}")
             await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [osuProfile DEBUG v5] ERROR al obtener/enviar perfil: {e}")
            # Dar un error más específico si es posible
            await ctx.send(f"⚠️ Error al obtener el perfil de '{username}'. Verifica el nombre y modo, o inténtalo más tarde.")
        print("------------------------------\n")


    # --- Comando osuAnalyze (LIMPIO y usando auxiliar) ---
    # --- Comando osuAnalyze (CON DIAGNÓSTICO REFORZADO) ---
# --- Comando osuAnalyze (CON DIAGNÓSTICO REFORZADO y FIX DATETIME/ORDER) ---
    @commands.command(name="osuAnalyze", help="Analiza el perfil de osu! con IA.\nUso: `d.osuAnalyze [usuario] [-modo] [--focus <area>]`")
    async def osu_analyze(self, ctx, *, args: str = None):
        print("\n--- [osuAnalyze DEBUG v6] --- Iniciando comando...")
        try:
            if not self.osu:
                 print("!!!!!! [osuAnalyze DEBUG v6] OsuAPI no inicializada.")
                 return await ctx.send("❌ Error: La API de osu! no está configurada.")

            username, user_focus, mode, is_linked = None, None, "osu", False

            print("--- [osuAnalyze DEBUG v6] Parseando argumentos...")
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
                print(f"--- [osuAnalyze DEBUG v6] Args parseados: user='{username}', mode='{mode}', focus='{user_focus}'")
            except Exception as e_parse:
                print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR parseando args: {e_parse}")
                traceback.print_exc()
                await ctx.send("❌ Error al procesar los argumentos.")
                return

            if not username:
                print("--- [osuAnalyze DEBUG v6] No hay nombre, buscando vinculado...")
                username = await self._get_linked_username(ctx)
                if not username:
                     await ctx.send("❌ No tienes cuenta vinculada ni especificaste nombre.")
                     print("--- [osuAnalyze DEBUG v6] Terminando: No hay nombre.")
                     return
                is_linked = True

            print(f"--- [osuAnalyze DEBUG v6] Obteniendo datos para: {username!r}, Modo: {mode}")
            await ctx.typing()

            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user:
                 print(f"!!!!!! [osuAnalyze DEBUG v6] API osu! no encontró usuario.")
                 await ctx.send(f"❌ No se pudo encontrar '{username}' en modo '{mode}'.")
                 return

            print("--- [osuAnalyze DEBUG v6] Obteniendo scores...")
            best_scores, recent_scores = [], []
            try:
                 best_scores = self.osu.get_user_best_scores(user["id"], mode, 10)
                 recent_scores = self.osu.get_user_recent_scores(user["id"], mode, 20)
                 print(f"--- [osuAnalyze DEBUG v6] Scores obtenidos: {len(best_scores)} best, {len(recent_scores)} recent.")
            except Exception as e_scores:
                 print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR al obtener scores: {e_scores}")
                 traceback.print_exc()
                 await ctx.send("⚠️ No se pudieron obtener scores, análisis limitado.")

            # --- Guardar scores en DB (CON FIX DATETIME y FIX USERID/OSU_ID ORDER) ---
            print(f"--- [osuAnalyze DEBUG v6] Guardando scores en BD...")
            saved_count = 0
            score_type = 'best'
            for score in best_scores:
                try:
                    mods_str = "".join(score.get('mods', []))
                    timestamp_str = score.get('created_at')
                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            print(f"WARN: Could not parse timestamp '{timestamp_str}', using current time.")
                            timestamp = datetime.now(timezone.utc)
                    else:
                        timestamp = datetime.now(timezone.utc)

                    score_id = score['id']
                    user_id_discord = ctx.author.id # ID Discord (BIGINT) - Segundo parámetro
                    user_id_osu = user['id']        # ID Osu! (INT) - Tercer parámetro
                    beatmap_info = score.get('beatmap')
                    if not beatmap_info or 'id' not in beatmap_info:
                         print(f"WARN: Score (best) {score_id} no tiene beatmap ID. Saltando.")
                         continue
                    beatmap_id = beatmap_info['id'] # INT - Cuarto parámetro
                    score_value = score['score']    # INT - Quinto parámetro
                    accuracy_value = score['accuracy'] # FLOAT/NUMERIC - Sexto parámetro

                    db_connector.execute_procedure(
                        "sp_SaveOrUpdateOsuScore",
                        ( # Orden SQL: ScoreID, UserID(Discord), OsuUserID, BeatmapID, Score, Accuracy, Mods, Type, Timestamp
                            score_id, user_id_discord, user_id_osu, beatmap_id, score_value,
                            accuracy_value, mods_str, score_type, timestamp
                        )
                    )
                    saved_count += 1
                except KeyError as e_key:
                     print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR Key (best): Dato faltante: {e_key} - Score ID: {score.get('id', 'N/A')}")
                except Exception as e_proc:
                     print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR Proc (best): {e_proc}")
                     traceback.print_exc()

            score_type = 'recent'
            for score in recent_scores:
                 try:
                    mods_str = "".join(score.get('mods', []))
                    timestamp_str = score.get('created_at')
                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            print(f"WARN: Could not parse timestamp '{timestamp_str}', using current time.")
                            timestamp = datetime.now(timezone.utc)
                    else:
                        timestamp = datetime.now(timezone.utc)

                    score_id = score['id']
                    user_id_discord = ctx.author.id # ID Discord (BIGINT)
                    user_id_osu = user['id']        # ID Osu! (INT)
                    beatmap_info = score.get('beatmap')
                    if not beatmap_info or 'id' not in beatmap_info:
                         print(f"WARN: Score (recent) {score_id} no tiene beatmap ID. Saltando.")
                         continue
                    beatmap_id = beatmap_info['id'] # INT
                    score_value = score['score']    # INT
                    accuracy_value = score['accuracy'] # FLOAT/NUMERIC

                    db_connector.execute_procedure(
                        "sp_SaveOrUpdateOsuScore",
                        ( # Orden SQL: ScoreID, UserID(Discord), OsuUserID, BeatmapID, Score, Accuracy, Mods, Type, Timestamp
                            score_id, user_id_discord, user_id_osu, beatmap_id, score_value,
                            accuracy_value, mods_str, score_type, timestamp
                        )
                    )
                    saved_count += 1
                 except KeyError as e_key:
                    print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR Key (recent): Dato faltante: {e_key} - Score ID: {score.get('id', 'N/A')}")
                 except Exception as e_proc:
                    print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR Proc (recent): {e_proc}")
                    traceback.print_exc()

            print(f"--- [osuAnalyze DEBUG v6] {saved_count} scores procesados para BD.")
            # No enviamos mensaje de error aquí, solo logueamos

            print("--- [osuAnalyze DEBUG v6] Generando prompt con OsuAnalyzer...")
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            prompt = ""
            try:
                 method_to_call = getattr(analyzer, 'generate_ai_analysis', None)
                 if method_to_call:
                      if asyncio.iscoroutinefunction(method_to_call):
                           prompt = await method_to_call()
                      else:
                           prompt = method_to_call()
                 else: raise AttributeError("Método generate_ai_analysis no encontrado")
                 print(f"--- [osuAnalyze DEBUG v6] Prompt generado (longitud): {len(prompt)}")
                 if not prompt: raise ValueError("Prompt vacío generado por Analyzer")
            except Exception as e_analyzer:
                 print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR en OsuAnalyzer: {e_analyzer}")
                 traceback.print_exc()
                 await ctx.send("❌ Error interno al generar el análisis.")
                 return

            print("--- [osuAnalyze DEBUG v6] Llamando a Gemini...")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            ai_text = None
            try:
                 response_task = model.generate_content_async(prompt)
                 response = await asyncio.wait_for(response_task, timeout=45.0)
                 ai_text = response.text.strip()
                 print(f"--- [osuAnalyze DEBUG v6] Respuesta Gemini (longitud): {len(ai_text)}")
                 if not ai_text: raise ValueError("Respuesta vacía de Gemini")
            except asyncio.TimeoutError:
                 print("!!!!!! [osuAnalyze DEBUG v6] Timeout Gemini.")
                 await ctx.send("⏳ La IA tardó mucho. Intenta de nuevo.")
                 return
            except Exception as e_gemini:
                 print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR Gemini: {e_gemini}")
                 traceback.print_exc()
                 error_details = getattr(e_gemini, 'message', str(e_gemini))
                 await ctx.send(f"❌ Error contactando la IA: {error_details}")
                 return

            print("--- [osuAnalyze DEBUG v6] Creando y enviando Embed...")
            embed = discord.Embed(title=f"Análisis de {user['username']} (Modo: {mode.capitalize()})", color=0x9932CC)
            stats = user.get("statistics", {})
            avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name="PP", value=f"{stats.get('pp', 0):.2f}", inline=True)
            embed.add_field(name="Accuracy", value=f"{stats.get('hit_accuracy', 0):.2f}%", inline=True)
            global_rank = stats.get('global_rank')
            embed.add_field(name="Rank", value=f"#{global_rank:,}" if global_rank else "N/A", inline=True)
            if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")

            PAGE_LIMIT = 1024
            if len(ai_text) <= PAGE_LIMIT:
                 embed.add_field(name="🧠 Análisis de Dalet", value=ai_text, inline=False)
                 print(f"--- [osuAnalyze DEBUG v6] Enviando embed para {username!r}")
                 await ctx.send(embed=embed)
            else:
                 pages = [ai_text[i:i + PAGE_LIMIT] for i in range(0, len(ai_text), PAGE_LIMIT)]
                 embed.add_field(name=f"🧠 Análisis de Dalet (Página 1/{len(pages)})", value=pages[0], inline=False)
                 print(f"--- [osuAnalyze DEBUG v6] Enviando embed paginado para {username!r}")
                 await ctx.send(embed=embed, view=AnalysisPaginator(pages))

        except Exception as e:
            print(f"!!!!!! [osuAnalyze DEBUG v6] ERROR INESPERADO (captura general): {e}")
            traceback.print_exc()
            await ctx.send("⚠️ Error inesperado al generar el análisis.")
        finally:
            print("--- [osuAnalyze DEBUG v6] --- Comando finalizado.")
            print("------------------------------\n")

    # --- Comando osuCoach (LIMPIO y usando auxiliar) ---
   # --- Comando osuCoach (CON DIAGNÓSTICO REFORZADO) ---
# --- Comando osuCoach (CON DIAGNÓSTICO REFORZADO y FIX DATETIME/ORDER) ---
    @commands.command(help="Genera un plan de coaching de osu!...", aliases=["oc"])
    async def osuCoach(self, ctx, *, args: str = None):
        print("\n--- [osuCoach DEBUG v6] --- Iniciando comando...")
        try:
            if not self.osu:
                 print("!!!!!! [osuCoach DEBUG v6] OsuAPI no inicializada.")
                 return await ctx.send("❌ Error: La conexión con la API de osu! no está configurada.")

            username, mode, user_focus, is_linked = None, "osu", None, False

            print("--- [osuCoach DEBUG v6] Parseando argumentos...")
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
                print(f"--- [osuCoach DEBUG v6] Args parseados: user='{username}', mode='{mode}', focus='{user_focus}'")
            except Exception as e_parse:
                 print(f"!!!!!! [osuCoach DEBUG v6] ERROR parseando args: {e_parse}")
                 traceback.print_exc()
                 await ctx.send("❌ Error al procesar los argumentos.")
                 return

            if not username:
                print("--- [osuCoach DEBUG v6] No hay nombre, buscando vinculado...")
                username = await self._get_linked_username(ctx)
                if not username:
                     await ctx.send("❌ No tienes cuenta vinculada ni especificaste nombre.")
                     print("--- [osuCoach DEBUG v6] Terminando: No hay nombre.")
                     return
                is_linked = True

            print(f"--- [osuCoach DEBUG v6] Obteniendo datos para: {username!r}, Modo: {mode}, Focus: {user_focus}")
            await ctx.typing()

            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user:
                 print(f"!!!!!! [osuCoach DEBUG v6] API osu! no encontró usuario.")
                 await ctx.send(f"❌ No se pudo encontrar '{username}' en modo '{mode}'.")
                 return

            print("--- [osuCoach DEBUG v6] Obteniendo scores...")
            best_scores, recent_scores = [], []
            try:
                 best_scores = self.osu.get_user_best_scores(user["id"], mode, 10)
                 recent_scores = self.osu.get_user_recent_scores(user["id"], mode, 20)
                 print(f"--- [osuCoach DEBUG v6] Scores obtenidos: {len(best_scores)} best, {len(recent_scores)} recent.")
            except Exception as e_scores:
                 print(f"!!!!!! [osuCoach DEBUG v6] ERROR al obtener scores: {e_scores}")
                 traceback.print_exc()
                 await ctx.send("⚠️ No se pudieron obtener scores, coaching limitado.")

            # --- Guardar scores en DB (CON FIX DATETIME y FIX USERID/OSU_ID ORDER) ---
            print(f"--- [osuCoach DEBUG v6] Guardando scores en BD...")
            saved_count = 0
            score_type = 'best'
            for score in best_scores:
                try:
                    mods_str = "".join(score.get('mods', []))
                    timestamp_str = score.get('created_at')
                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            print(f"WARN: Could not parse timestamp '{timestamp_str}', using current time.")
                            timestamp = datetime.now(timezone.utc)
                    else:
                        timestamp = datetime.now(timezone.utc)

                    score_id = score['id']
                    user_id_discord = ctx.author.id # ID Discord (BIGINT)
                    user_id_osu = user['id']        # ID Osu! (INT)
                    beatmap_info = score.get('beatmap')
                    if not beatmap_info or 'id' not in beatmap_info:
                         print(f"WARN: Score (best) {score_id} no tiene beatmap ID. Saltando.")
                         continue
                    beatmap_id = beatmap_info['id'] # INT
                    score_value = score['score']    # INT
                    accuracy_value = score['accuracy'] # FLOAT/NUMERIC

                    db_connector.execute_procedure(
                        "sp_SaveOrUpdateOsuScore",
                        ( # Orden SQL: ScoreID, UserID(Discord), OsuUserID, BeatmapID, Score, Accuracy, Mods, Type, Timestamp
                            score_id, user_id_discord, user_id_osu, beatmap_id, score_value,
                            accuracy_value, mods_str, score_type, timestamp
                        )
                    )
                    saved_count += 1
                except KeyError as e_key:
                     print(f"!!!!!! [osuCoach DEBUG v6] ERROR Key (best): Dato faltante: {e_key} - Score ID: {score.get('id', 'N/A')}")
                except Exception as e_proc:
                     print(f"!!!!!! [osuCoach DEBUG v6] ERROR Proc (best): {e_proc}")
                     traceback.print_exc()

            score_type = 'recent'
            for score in recent_scores:
                 try:
                    mods_str = "".join(score.get('mods', []))
                    timestamp_str = score.get('created_at')
                    timestamp = None
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            print(f"WARN: Could not parse timestamp '{timestamp_str}', using current time.")
                            timestamp = datetime.now(timezone.utc)
                    else:
                        timestamp = datetime.now(timezone.utc)

                    score_id = score['id']
                    user_id_discord = ctx.author.id # ID Discord (BIGINT)
                    user_id_osu = user['id']        # ID Osu! (INT)
                    beatmap_info = score.get('beatmap')
                    if not beatmap_info or 'id' not in beatmap_info:
                         print(f"WARN: Score (recent) {score_id} no tiene beatmap ID. Saltando.")
                         continue
                    beatmap_id = beatmap_info['id'] # INT
                    score_value = score['score']    # INT
                    accuracy_value = score['accuracy'] # FLOAT/NUMERIC

                    db_connector.execute_procedure(
                        "sp_SaveOrUpdateOsuScore",
                        ( # Orden SQL: ScoreID, UserID(Discord), OsuUserID, BeatmapID, Score, Accuracy, Mods, Type, Timestamp
                            score_id, user_id_discord, user_id_osu, beatmap_id, score_value,
                            accuracy_value, mods_str, score_type, timestamp
                        )
                    )
                    saved_count += 1
                 except KeyError as e_key:
                    print(f"!!!!!! [osuCoach DEBUG v6] ERROR Key (recent): Dato faltante: {e_key} - Score ID: {score.get('id', 'N/A')}")
                 except Exception as e_proc:
                    print(f"!!!!!! [osuCoach DEBUG v6] ERROR Proc (recent): {e_proc}")
                    traceback.print_exc()

            print(f"--- [osuCoach DEBUG v6] {saved_count} scores procesados para BD.")
            # No enviamos mensaje de error aquí, solo logueamos


            print("--- [osuCoach DEBUG v6] Generando prompt con OsuAnalyzer...")
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            prompt = ""
            try:
                 method_to_call = getattr(analyzer, 'generate_coaching_prompt', None)
                 if method_to_call:
                      if asyncio.iscoroutinefunction(method_to_call):
                           prompt = await method_to_call()
                      else:
                           prompt = method_to_call()
                 else: raise AttributeError("Método generate_coaching_prompt no encontrado")
                 print(f"--- [osuCoach DEBUG v6] Prompt generado (longitud): {len(prompt)}")
                 if not prompt: raise ValueError("Prompt vacío generado por Analyzer")
            except Exception as e_analyzer:
                 print(f"!!!!!! [osuCoach DEBUG v6] ERROR en OsuAnalyzer: {e_analyzer}")
                 traceback.print_exc()
                 await ctx.send("❌ Error interno al generar el coaching.")
                 return

            print("--- [osuCoach DEBUG v6] Llamando a Gemini...")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            ai_text = None
            try:
                 response_task = model.generate_content_async(prompt)
                 response = await asyncio.wait_for(response_task, timeout=60.0) # Timeout más largo
                 ai_text = response.text.strip()
                 print(f"--- [osuCoach DEBUG v6] Respuesta Gemini (longitud): {len(ai_text)}")
                 if not ai_text: raise ValueError("Respuesta vacía de Gemini")
            except asyncio.TimeoutError:
                 print("!!!!!! [osuCoach DEBUG v6] Timeout Gemini.")
                 await ctx.send("⏳ La IA tardó mucho. Intenta de nuevo.")
                 return
            except Exception as e_gemini:
                 print(f"!!!!!! [osuCoach DEBUG v6] ERROR Gemini: {e_gemini}")
                 traceback.print_exc()
                 error_details = getattr(e_gemini, 'message', str(e_gemini))
                 await ctx.send(f"❌ Error contactando la IA: {error_details}")
                 return

            print("--- [osuCoach DEBUG v6] Creando y enviando Embed...")
            embed_shell = discord.Embed(title=f"Plan de Coaching para {user['username']}", color=0xFFD700)
            avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
            embed_shell.set_thumbnail(url=avatar_url)
            if is_linked: embed_shell.set_footer(text="Mostrando perfil vinculado.")
            PAGE_CHAR_LIMIT = 1800

            if len(ai_text) <= PAGE_CHAR_LIMIT:
                embed_shell.description = ai_text
                print(f"--- [osuCoach DEBUG v6] Enviando embed para {username!r}")
                await ctx.send(embed=embed_shell)
            else:
                pages = [ai_text[i:i + PAGE_CHAR_LIMIT] for i in range(0, len(ai_text), PAGE_CHAR_LIMIT)]
                embed_shell.description = pages[0]
                print(f"--- [osuCoach DEBUG v6] Enviando embed paginado para {username!r}")
                await ctx.send(embed=embed_shell, view=DescriptionPaginator(pages, embed_shell))

        except Exception as e:
            print(f"!!!!!! [osuCoach DEBUG v6] ERROR INESPERADO (captura general): {e}")
            traceback.print_exc()
            await ctx.send("⚠️ Error inesperado al generar el plan de coaching.")
        finally:
            print("--- [osuCoach DEBUG v6] --- Comando finalizado.")
            print("------------------------------\n")
    @commands.command(name="ranking", help="Muestra el ranking de PP del bot.")
    async def osu_ranking(self, ctx, limit: int = 10):
        """Muestra el ranking de PP de usuarios vinculados."""
        if limit > 25: limit = 25 # Evitar spam

        try:
            # REQUISITO 4c/5a: Llamamos a la VISTA con RANK()
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
                rank = row[3]
                username = row[0]
                pp = row[1]
                acc = row[2]
                description += f"**{rank}. {username}** - `{pp:,.2f} pp` (`{acc:.2f}%`)\n"
            
            embed.description = description
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error al obtener el ranking: {e}")

    @commands.command(name="scorehistory", help="Muestra tu historial de accuracy en 'best plays'.")
    async def osu_score_history(self, ctx):
        """Muestra la evolución de accuracy de tus 'best plays'."""
        try:
            # REQUISITO 4d/5a: Llamamos a la función con CTE y LAG()
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
                # row[0]=timestamp, row[1]=accuracy, row[2]=accuracy_change
                timestamp = row[0]
                accuracy = row[1]
                change = row[2]

                change_str = "N/A"
                if change is not None:
                    # Formateamos el cambio para que muestre el signo
                    change_str = f"+{change:.2f}%" if change > 0 else f"{change:.2f}%"
                
                field_name = f"{format_dt(timestamp, 'D')}" # 'D' = 22 de octubre de 2025
                field_value = f"**Acc:** `{accuracy:.2f}%` (Cambio: `{change_str}`)"
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            embed.set_footer(text="El cambio se compara con el 'best play' guardado anteriormente.")
            await ctx.send(embed=embed)
        
        except Exception as e:
            await ctx.send(f"❌ Error al obtener tu historial de scores: {e}")

async def setup(bot):
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
             traceback.print_exc() # Ver error al añadir cog
    else:
        print("!!!!!! [osu! Cog] ADVERTENCIA: Faltan credenciales osu!. Cog no cargado.")