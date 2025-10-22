import discord
from discord.ext import commands
# Asegúrate de tener los imports correctos
from handlers.modules.osu_api import OsuAPI
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai # Necesario para osuCoach
import os
import asyncio # Necesario para timeouts si los usas
# Import del conector
from . import db_connector
import datetime

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
                 f"**PP:** 🎯 `{stats.get('pp', 0):,.2f}`\n"
                 f"**Precisión:** 📈 `{stats.get('hit_accuracy', 0):.2f}%`\n"
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
    @commands.command(name="osuAnalyze", help="Analiza el perfil de osu! con IA.\nUso: `d.osuAnalyze [usuario] [-modo] [--focus <area>]`")
    async def osu_analyze(self, ctx, *, args: str = None):
        print("\n--- [osuAnalyze DEBUG v5] --- Intentando ejecutar comando...")
        if not self.osu:
             print("!!!!!! [osuAnalyze DEBUG v5] OsuAPI no inicializada. Abortando.")
             return await ctx.send("❌ Error: La conexión con la API de osu! no está configurada correctamente.")

        username, user_focus, mode, is_linked = None, None, "osu", False

        # --- Parseo de argumentos ---
        if args:
             parts = args.split()
             username_parts = []
             i = 0
             while i < len(parts):
                 part = parts[i]
                 # Ejemplo simple de parseo, ajusta según tu necesidad
                 if part.lower() == '--focus' and i + 1 < len(parts): # Usar --focus como en osuCoach
                      # Podrías validar el focus aquí si quieres
                      user_focus = parts[i+1].lower()
                      i += 2
                      continue
                 if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                      mode = part[1:].lower()
                      i += 1
                      continue
                 username_parts.append(part)
                 i += 1
             # Asignar username solo si se encontraron partes de nombre
             if username_parts:
                 username = " ".join(username_parts).strip()

        if not username:
            # Usamos la función auxiliar
            username = await self._get_linked_username(ctx)
            if not username:
                 await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <tu_usuario_osu>` o especifica un nombre.")
                 print("--- [osuAnalyze DEBUG v5] _get_linked_username devolvió None. Terminando.")
                 print("------------------------------\n")
                 return
            is_linked = True

        # --- Si llegamos aquí, TENEMOS un 'username' ---
        print(f"--- [osuAnalyze DEBUG v5] Intentando analizar: {username!r}, Modo: {mode}, Focus: {user_focus}")
        await ctx.typing()
        try:
            # Obtener datos del usuario
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user:
                 print(f"!!!!!! [osuAnalyze DEBUG v5] API osu! no encontró usuario '{username}' en modo '{mode}'.")
                 await ctx.send(f"❌ No se pudo encontrar al jugador '{username}' en el modo '{mode}'.")
                 print("------------------------------\n")
                 return

            # Obtener scores (manejar errores si la API falla)
            best_scores = []
            recent_scores = []
            try:
                 best_scores = self.osu.get_user_best_scores(user["id"], mode, 10)
                 recent_scores = self.osu.get_user_recent_scores(user["id"], mode, 20)
            except Exception as e_scores:
                 print(f"!!!!!! [osuAnalyze DEBUG v5] ERROR al obtener scores: {e_scores}")
                 # Podemos continuar sin scores o abortar, decidimos continuar
                 await ctx.send("⚠️ No se pudieron obtener los scores recientes/mejores, el análisis puede ser limitado.")
# ======================================================
            # ▼▼▼ ¡NUEVO! Guardando Scores en la Base de Datos ▼▼▼
            # ======================================================
            # Guardar best scores
            for score in best_scores:
                # El mod es una lista, lo unimos en un string
                mods_str = "".join(score.get('mods', []))
                # La API a veces no devuelve timestamp, usamos la fecha de la jugada
                timestamp = score.get('created_at', datetime.utcnow().isoformat())
                db_connector.execute_procedure(
                    "sp_SaveOrUpdateOsuScore",
                    (
                        score['id'], user['id'], score['beatmap']['id'],
                        score['score'], score['accuracy'], mods_str,
                        'best', timestamp
                    )
                )
            
            # Guardar recent scores
            for score in recent_scores:
                mods_str = "".join(score.get('mods', []))
                timestamp = score.get('created_at', datetime.utcnow().isoformat())
                db_connector.execute_procedure(
                    "sp_SaveOrUpdateOsuScore",
                    (
                        score['id'], user['id'], score['beatmap']['id'],
                        score['score'], score['accuracy'], mods_str,
                        'recent', timestamp
                    )
                )
            print(f"--- [osuAnalyze DEBUG v5] {len(best_scores) + len(recent_scores)} scores guardados/actualizados en la BD.")
            # ======================================================
            # Pasar user_focus al Analyzer si lo usa para análisis interno
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            # Verificar si el método existe y es async
            if hasattr(analyzer, 'generate_ai_analysis') and asyncio.iscoroutinefunction(analyzer.generate_ai_analysis):
                 prompt = await analyzer.generate_ai_analysis()
            else:
                 # Si no es async o no existe, intentar llamada síncrona o manejar error
                 try:
                      prompt = analyzer.generate_ai_analysis() # Asumiendo síncrono si no es async
                 except AttributeError:
                      print("!!!!!! [osuAnalyze DEBUG v5] ERROR: Método generate_ai_analysis no encontrado en OsuAnalyzer.")
                      await ctx.send("❌ Error interno: No se pudo generar el prompt de análisis.")
                      return

            # Llamar a Gemini (con timeout)
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            ai_text = None
            try:
                 response_task = model.generate_content_async(prompt)
                 response = await asyncio.wait_for(response_task, timeout=45.0) # Timeout un poco más largo para análisis
                 ai_text = response.text.strip()
            except asyncio.TimeoutError:
                 print("!!!!!! [osuAnalyze DEBUG v5] Timeout esperando respuesta de Gemini.")
                 await ctx.send("⏳ La IA está tardando mucho en generar el análisis. Intenta de nuevo.")
                 return
            except Exception as e_gemini:
                 print(f"!!!!!! [osuAnalyze DEBUG v5] ERROR al llamar a Gemini: {e_gemini}")
                 await ctx.send("❌ Error al contactar con la IA para el análisis.")
                 return

            if not ai_text:
                 print("!!!!!! [osuAnalyze DEBUG v5] Gemini devolvió respuesta vacía.")
                 await ctx.send("🤔 La IA no generó un análisis esta vez.")
                 return

            # --- Enviar Embed ---
            embed = discord.Embed(title=f"Análisis de {user['username']} (Modo: {mode.capitalize()})", color=0x9932CC)
            stats = user.get("statistics", {})
            avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name="PP", value=f"{stats.get('pp', 0):.2f}", inline=True)
            embed.add_field(name="Accuracy", value=f"{stats.get('hit_accuracy', 0):.2f}%", inline=True)
            global_rank = stats.get('global_rank')
            embed.add_field(name="Rank", value=f"#{global_rank:,}" if global_rank else "N/A", inline=True)
            if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")

            # Lógica Paginator para el campo de análisis
            PAGE_LIMIT = 1024 # Límite por campo de Embed
            if len(ai_text) <= PAGE_LIMIT:
                 embed.add_field(name="🧠 Análisis de Dalet", value=ai_text, inline=False)
                 print(f"--- [osuAnalyze DEBUG v5] Enviando embed para {username!r}")
                 await ctx.send(embed=embed)
            else:
                 pages = [ai_text[i:i + PAGE_LIMIT] for i in range(0, len(ai_text), PAGE_LIMIT)]
                 # Asegurarse que AnalysisPaginator se instancia correctamente
                 embed.add_field(name=f"🧠 Análisis de Dalet (Página 1/{len(pages)})", value=pages[0], inline=False)
                 print(f"--- [osuAnalyze DEBUG v5] Enviando embed paginado para {username!r}")
                 await ctx.send(embed=embed, view=AnalysisPaginator(pages))

        except Exception as e:
            print(f"!!!!!! [osuAnalyze DEBUG v5] ERROR INESPERADO: {e}")
            await ctx.send("⚠️ Error inesperado al generar el análisis.")
        print("------------------------------\n")


    # --- Comando osuCoach (LIMPIO y usando auxiliar) ---
    @commands.command(help="Genera un plan de coaching de osu!...", aliases=["oc"])
    async def osuCoach(self, ctx, *, args: str = None):
        print("\n--- [osuCoach DEBUG v5] --- Intentando ejecutar comando...")
        if not self.osu:
             print("!!!!!! [osuCoach DEBUG v5] OsuAPI no inicializada. Abortando.")
             return await ctx.send("❌ Error: La conexión con la API de osu! no está configurada.")

        username, mode, user_focus, is_linked = None, "osu", None, False

        # --- Parseo de argumentos ---
        if args:
             parts = args.split()
             username_parts = []
             i = 0
             while i < len(parts):
                 part = parts[i]
                 # Usamos --focus como estándar
                 if part.lower() == '--focus' and i + 1 < len(parts):
                      # Validar focus si es necesario
                      valid_focus = ["precisión", "consistencia", "velocidad", "lectura", "stamina", "aim", "tech", "dedos"] # Ejemplo ampliado
                      focus_input = parts[i+1].lower()
                      # Permitir cualquier focus o validar contra lista
                      user_focus = focus_input # Asignar directamente
                      # if focus_input in valid_focus:
                      #      user_focus = focus_input
                      # else:
                      #      await ctx.send(f"⚠️ Enfoque '{focus_input}' no reconocido (opcional). Opciones sugeridas: {', '.join(valid_focus)}")
                      i += 2
                      continue
                 # Usar -mode
                 if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                      mode = part[1:].lower()
                      i += 1
                      continue
                 username_parts.append(part)
                 i += 1
             if username_parts:
                 username = " ".join(username_parts).strip()

        if not username:
            # Usamos la función auxiliar
            username = await self._get_linked_username(ctx)
            if not username:
                 await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <tu_usuario_osu>` o especifica un nombre.")
                 print("--- [osuCoach DEBUG v5] _get_linked_username devolvió None. Terminando.")
                 print("------------------------------\n")
                 return
            is_linked = True

        # --- Si llegamos aquí, TENEMOS un 'username' ---
        print(f"--- [osuCoach DEBUG v5] Intentando generar coach: {username!r}, Modo: {mode}, Focus: {user_focus}")
        await ctx.typing()
        try:
            # Obtener datos del usuario
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user:
                 print(f"!!!!!! [osuCoach DEBUG v5] API osu! no encontró usuario '{username}' en modo '{mode}'.")
                 await ctx.send(f"❌ No se pudo encontrar al jugador '{username}' en el modo '{mode}'.")
                 print("------------------------------\n")
                 return

            # Obtener scores
            best_scores = []
            recent_scores = []
            try:
                 best_scores = self.osu.get_user_best_scores(user["id"], mode, 10)
                 recent_scores = self.osu.get_user_recent_scores(user["id"], mode, 20)
            except Exception as e_scores:
                 print(f"!!!!!! [osuCoach DEBUG v5] ERROR al obtener scores: {e_scores}")
                 await ctx.send("⚠️ No se pudieron obtener los scores recientes/mejores, el coaching puede ser limitado.")
# ======================================================
            # ▼▼▼ ¡NUEVO! Guardando Scores en la Base de Datos ▼▼▼
            # ======================================================
            # Guardar best scores
            for score in best_scores:
                # El mod es una lista, lo unimos en un string
                mods_str = "".join(score.get('mods', []))
                # La API a veces no devuelve timestamp, usamos la fecha de la jugada
                timestamp = score.get('created_at', datetime.utcnow().isoformat())
                db_connector.execute_procedure(
                    "sp_SaveOrUpdateOsuScore",
                    (
                        score['id'], user['id'], score['beatmap']['id'],
                        score['score'], score['accuracy'], mods_str,
                        'best', timestamp
                    )
                )
            
            # Guardar recent scores
            for score in recent_scores:
                mods_str = "".join(score.get('mods', []))
                timestamp = score.get('created_at', datetime.utcnow().isoformat())
                db_connector.execute_procedure(
                    "sp_SaveOrUpdateOsuScore",
                    (
                        score['id'], user['id'], score['beatmap']['id'],
                        score['score'], score['accuracy'], mods_str,
                        'recent', timestamp
                    )
                )
            print(f"--- [osuAnalyze DEBUG v5] {len(best_scores) + len(recent_scores)} scores guardados/actualizados en la BD.")
            # ======================================================
            # Pasamos el user_focus aquí a OsuAnalyzer
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent_scores, best_plays=best_scores, user_focus=user_focus)
            # Asegurarse que el método se llama así y es async
            prompt = ""
            try:
                if hasattr(analyzer, 'generate_coaching_prompt') and asyncio.iscoroutinefunction(analyzer.generate_coaching_prompt):
                     prompt = await analyzer.generate_coaching_prompt()
                elif hasattr(analyzer, 'generate_coaching_prompt'):
                     prompt = analyzer.generate_coaching_prompt() # Intentar síncrono
                else:
                    raise AttributeError("Método generate_coaching_prompt no encontrado")

                if not prompt: # Si el analyzer devuelve prompt vacío
                    print("!!!!!! [osuCoach DEBUG v5] OsuAnalyzer devolvió un prompt vacío.")
                    await ctx.send("🤔 No se pudo generar un prompt para el coaching con los datos actuales.")
                    return

            except AttributeError as e_analyzer_method:
                 print(f"!!!!!! [osuCoach DEBUG v5] ERROR: {e_analyzer_method}")
                 await ctx.send("❌ Error interno: No se pudo generar el prompt de coaching.")
                 return
            except Exception as e_analyzer:
                 print(f"!!!!!! [osuCoach DEBUG v5] ERROR en OsuAnalyzer: {e_analyzer}")
                 await ctx.send("❌ Error interno al analizar los datos para el coaching.")
                 return


            # Llamar a Gemini (con timeout)
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            ai_text = None
            try:
                 response_task = model.generate_content_async(prompt)
                 response = await asyncio.wait_for(response_task, timeout=60.0) # Timeout más largo para coaching
                 ai_text = response.text.strip()
            except asyncio.TimeoutError:
                 print("!!!!!! [osuCoach DEBUG v5] Timeout esperando respuesta de Gemini.")
                 await ctx.send("⏳ La IA está tardando mucho en generar el plan de coaching. Intenta de nuevo.")
                 return
            except Exception as e_gemini:
                 print(f"!!!!!! [osuCoach DEBUG v5] ERROR al llamar a Gemini: {e_gemini}")
                 await ctx.send("❌ Error al contactar con la IA para el coaching.")
                 return

            if not ai_text:
                 print("!!!!!! [osuCoach DEBUG v5] Gemini devolvió respuesta vacía.")
                 await ctx.send("🤔 La IA no generó un plan de coaching esta vez.")
                 return


            # --- Enviar Embed con Paginator ---
            embed_shell = discord.Embed(title=f"Plan de Coaching para {user['username']}", color=0xFFD700)
            avatar_url = user.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png")
            embed_shell.set_thumbnail(url=avatar_url)
            if is_linked: embed_shell.set_footer(text="Mostrando perfil vinculado.")
            PAGE_CHAR_LIMIT = 1800 # Límite para descripción

            if len(ai_text) <= PAGE_CHAR_LIMIT:
                embed_shell.description = ai_text
                print(f"--- [osuCoach DEBUG v5] Enviando embed para {username!r}")
                await ctx.send(embed=embed_shell)
            else:
                pages = [ai_text[i:i + PAGE_CHAR_LIMIT] for i in range(0, len(ai_text), PAGE_CHAR_LIMIT)]
                embed_shell.description = pages[0]
                print(f"--- [osuCoach DEBUG v5] Enviando embed paginado para {username!r}")
                # Asegurarse que DescriptionPaginator existe y se usa correctamente
                await ctx.send(embed=embed_shell, view=DescriptionPaginator(pages, embed_shell))

        except Exception as e:
            print(f"!!!!!! [osuCoach DEBUG v5] ERROR INESPERADO: {e}")
            # Considerar imprimir traceback para errores inesperados:
            # import traceback; traceback.print_exc()
            await ctx.send("⚠️ Error inesperado al generar el plan de coaching.")
        print("------------------------------\n")


async def setup(bot):
    print("--- [osu! Cog] Ejecutando setup...") # DEBUG SETUP
    # Asegúrate de tener las variables de entorno para la API de osu!
    client_id = os.getenv("OSU_CLIENT_ID")
    client_secret = os.getenv("OSU_CLIENT_SECRET")

    if client_id and client_secret:
        # Validar que client_id sea un número antes de añadir el cog
        try:
             int(client_id) # Intentar convertir a entero
             await bot.add_cog(OsuHandler(bot))
             print("--- [osu! Cog] Cog OsuHandler añadido exitosamente.") # DEBUG SETUP OK
        except ValueError:
             print(f"!!!!!! [osu! Cog] ERROR: OSU_CLIENT_ID ('{client_id}') no es un número válido. El cog no se cargará.")
        except Exception as e:
             print(f"!!!!!! [osu! Cog] ERROR al añadir cog OsuHandler: {e}") # DEBUG SETUP FAIL
    else:
        print("!!!!!! [osu! Cog] ADVERTENCIA: Faltan OSU_CLIENT_ID o OSU_CLIENT_SECRET. El cog OsuHandler no se cargará.")