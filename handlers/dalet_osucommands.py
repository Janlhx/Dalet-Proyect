import discord
from discord.ext import commands
from handlers.modules.osu_api import OsuAPI
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai
import json, os
from handlers import db_connector
# --- Configuración y funciones auxiliares ---

class AnalysisPaginator(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self.update_buttons()
    def update_buttons(self):
        self.children[0].disabled = self.index == 0
        self.children[1].disabled = self.index == len(self.pages) - 1
    async def update_embed(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.set_field_at(index=3, name=f"🧠 Análisis de Dalet (Página {self.index + 1}/{len(self.pages)})", value=self.pages[self.index], inline=False)
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction, button):
        if self.index > 0: self.index -= 1; await self.update_embed(interaction)
        else: await interaction.response.defer()
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction, button):
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_embed(interaction)
        else: await interaction.response.defer()

class DescriptionPaginator(discord.ui.View):
    def __init__(self, pages, embed_shell):
        super().__init__(timeout=180)
        self.pages = pages
        self.embed_shell = embed_shell
        self.index = 0
        self.update_view()
    def update_view(self):
        self.children[0].disabled = self.index == 0
        self.children[1].disabled = self.index == len(self.pages) - 1
        self.embed_shell.set_footer(text=f"Página {self.index + 1} de {len(self.pages)}")
    async def update_message(self, interaction: discord.Interaction):
        self.update_view()
        self.embed_shell.description = self.pages[self.index]
        await interaction.response.edit_message(embed=self.embed_shell, view=self)
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction, button):
        if self.index > 0: self.index -= 1; await self.update_message(interaction)
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction, button):
        if self.index < len(self.pages) - 1: self.index += 1; await self.update_message(interaction)

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis con IA."""

    def __init__(self, bot):
            self.bot = bot
            # Es mejor cargar las credenciales desde variables de entorno
            self.osu = OsuAPI(
                client_id=os.getenv("OSU_CLIENT_ID"), 
                client_secret=os.getenv("OSU_CLIENT_SECRET")
            )

    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
        """Vincula tu cuenta de Discord con tu perfil de osu! y guarda tus stats."""
        async with ctx.typing():
            # 1. Obtener datos del usuario (incluyendo stats)
            #    Asumimos que self.osu.get_user() ya devuelve las stats
            #    Si no, necesitarías modificar osu_api.py o hacer otra llamada
            user_data = self.osu.get_user(osu_username) # Obtiene los datos del modo por defecto ('osu')
            
            if not user_data or 'statistics' not in user_data:
                await ctx.send("❌ No se encontró un jugador con ese nombre o faltan estadísticas.")
                return

            # Extraer estadísticas (con valores por defecto si no existen)
            stats = user_data.get('statistics', {})
            play_mode = user_data.get('playmode', 'osu') # Obtener el modo (por si acaso)
            pp = stats.get('pp', 0.0)
            global_rank = stats.get('global_rank') # Puede ser None si no tiene rank
            country_rank = stats.get('country_rank') # Puede ser None
            accuracy = stats.get('hit_accuracy', 0.0)

            try:
                # 2. Llamar al procedimiento actualizado con todos los datos
                db_connector.execute_procedure(
                    "sp_LinkOsuAccount",
                    (
                        ctx.author.id, 
                        user_data["username"], 
                        user_data["id"],
                        play_mode,          # Nuevo
                        pp,                 # Nuevo
                        global_rank,        # Nuevo (puede ser None)
                        country_rank,       # Nuevo (puede ser None)
                        accuracy            # Nuevo
                    )
                )
                await ctx.send(f"✅ ¡Tu cuenta de osu! ha sido vinculada con **{user_data['username']}** y tus estadísticas han sido guardadas!")
            except Exception as e:
                await ctx.send("❌ Hubo un error al conectar con la base de datos.")
                print(f"Error en el comando link: {e}")
    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Desvincula tu cuenta de osu!."""
        try:
            # Llamamos a nuestro nuevo procedimiento para eliminar el registro
            db_connector.execute_procedure(
                "sp_UnlinkOsuAccount", 
                (ctx.author.id,)  # Pasamos el ID del autor como parámetro
            )
            # Enviamos un mensaje genérico que funciona si tenías o no una cuenta vinculada.
            await ctx.send("✅ Si tenías una cuenta de osu! vinculada, ha sido eliminada.")
        except Exception as e:
            await ctx.send("❌ Hubo un error al conectar con la base de datos.")
            print(f"Error en el comando unlink: {e}")
    @commands.command(help="Muestra un perfil detallado de osu! de un jugador...", aliases=["op"])
    async def osuProfile(self, ctx, *, args: str = None):
        print("\n--- [osuProfile DEBUG v4] --- Intentando ejecutar comando...") # NUEVO PRINT INICIAL
        username, mode, is_linked = None, "osu", False
        
        # --- Parseo de argumentos (simplificado para prueba) ---
        if args:
             # Asumimos que args es solo el nombre de usuario por ahora
             username = args.strip() 
             # (Ignoramos el modo por ahora para simplificar)
        
        # --- Lógica SIN nombre de usuario ---
        if not username:
            print(f"--- [osuProfile DEBUG v4] No se proporcionó nombre. Consultando BD para UserID: {ctx.author.id}")
            try:
                # Directamente intentamos la consulta
                result = db_connector.fetch_one("SELECT fn_GetOsuUsername(%s)", (ctx.author.id,))
                print(f"--- [osuProfile DEBUG v4] Resultado DB: {result!r}") # Ver qué devuelve exactamente

                nombre_db = None
                if result and result[0] is not None:
                    nombre_db = str(result[0]).strip()
                
                if nombre_db:
                    username = nombre_db
                    is_linked = True
                    print(f"--- [osuProfile DEBUG v4] Nombre encontrado en BD: {username!r}")
                else:
                    print("--- [osuProfile DEBUG v4] No se encontró nombre en BD o resultado vacío.")
                    await ctx.send("❌ No tienes cuenta vinculada.")
                    print("------------------------------\n")
                    return # Terminar aquí si no hay nombre vinculado

            except Exception as e:
                 print(f"!!!!!! [osuProfile DEBUG v4] ERROR al consultar DB: {e}")
                 await ctx.send("❌ Error al consultar tu cuenta vinculada.")
                 print("------------------------------\n")
                 return
        
        # --- Si llegamos aquí, TENEMOS un 'username' (sea de args o de la BD) ---
        print(f"--- [osuProfile DEBUG v4] Intentando obtener perfil para: {username!r}, Modo: {mode}")
        await ctx.typing()
        try:
             user = self.osu.get_user(username, mode)
             if not user or 'id' not in user:
                 print(f"!!!!!! [osuProfile DEBUG v4] API osu! no encontró usuario.")
                 await ctx.send(f"No se pudo encontrar '{username}' en modo '{mode}'.")
                 print("------------------------------\n")
                 return

             # --- Crear y enviar Embed (código simplificado) ---
             stats = user.get("statistics", {})
             embed = discord.Embed(title=f"Perfil de {user['username']} (Modo: {mode})", color=discord.Color.blue())
             embed.add_field(name="PP", value=f"{stats.get('pp', 0):.2f}")
             embed.add_field(name="Rank", value=f"#{stats.get('global_rank', 'N/A')}")
             if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")
             
             print(f"--- [osuProfile DEBUG v4] Enviando embed para {username!r}")
             await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [osuProfile DEBUG v4] ERROR al obtener/enviar perfil: {e}")
            await ctx.send("⚠️ Error al obtener el perfil.")
        
        print("------------------------------\n")

    @commands.command(name="osuAnalyze")
    async def osu_analyze(self, ctx, *, args: str = None):
        """Analiza el perfil de un jugador y da un plan de coaching.
        
        Uso: d.osuAnalyze [usuario] [-focus <área>] [-mode <modo>]
        Ejemplo: d.osuAnalyze "Litxe" -focus velocidad -mode taiko
        """
        username, user_focus, mode = None, None, "osu"
        # ... (el código para parsear los argumentos no cambia)

        if not username:
            is_linked = True
            result = db_connector.fetch_one("SELECT fn_GetOsuUsername(%s)", (ctx.author.id,))
            if result and result[0]:
                username = result[0]
            else:
                return await ctx.send("Especifica un jugador o vincula tu cuenta con `d.link`.")
            
        await ctx.typing()
        try:
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user: return await ctx.send(f"No se pudo encontrar '{username}' en modo '{mode}'.")
            best, recent = self.osu.get_user_best_scores(user["id"], mode, 10), self.osu.get_user_recent_scores(user["id"], mode, 20)
            
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent, best_plays=best)
            prompt = analyzer.generate_ai_analysis()
            
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            ai_text = response.text.strip()
            
            embed = discord.Embed(title=f"Análisis de {user['username']} (Modo: {mode.capitalize()})", color=0x9932CC)
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            stats = user.get("statistics", {})
            embed.add_field(name="PP", value=f"{stats.get('pp', 0):.2f}", inline=True)
            embed.add_field(name="Accuracy", value=f"{stats.get('hit_accuracy', 0):.2f}%", inline=True)
            embed.add_field(name="Rank", value=f"#{stats.get('global_rank', 'N/A')}", inline=True)
            if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")
            
            if len(ai_text) <= 1024:
                embed.add_field(name="🧠 Análisis de Dalet", value=ai_text, inline=False)
                await ctx.send(embed=embed)
            else:
                pages = [ai_text[i:i + 1020] for i in range(0, len(ai_text), 1020)]
                embed.add_field(name=f"🧠 Análisis de Dalet (Página 1/{len(pages)})", value=pages[0], inline=False)
                await ctx.send(embed=embed, view=AnalysisPaginator(pages))
        except Exception as e:
            await ctx.send("⚠️ Error al generar el análisis."); print(f"[osuAnalyze] Error: {e}")

    @commands.command(help="""Genera un plan de coaching de osu! completo con IA.

    Uso: `d.osuCoach [usuario] [-modo] [--focus <enfoque>]`

    Ejemplos:
    `d.osuCoach` - Analiza tu perfil vinculado con foco automático.
    `d.osuCoach -mania` - Analiza tu perfil en modo mania.
    `d.osuCoach Litxe --focus velocidad` - Analiza a Litxe enfocándose en 'velocidad'.

    Enfoques válidos: `precisión`, `consistencia`, `velocidad`, `lectura`, `stamina`.
    """, aliases=["oc"])
    async def osuCoach(self, ctx, *, args: str = None):
        username, mode, user_focus, is_linked = None, "osu", None, False
        if args:
            parts, username_parts, i = args.split(), [], 0
            while i < len(parts):
                part = parts[i]
                if part.lower() == '--focus' and i + 1 < len(parts):
                    user_focus, i = parts[i+1].lower(), i + 2; continue
                if part.startswith('-') and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                    mode, i = part[1:].lower(), i + 1; continue
                username_parts.append(part); i += 1
            if username_parts: username = " ".join(username_parts)

        if not username:
            result = db_connector.fetch_one("SELECT fn_GetOsuUsername(%s)", (ctx.author.id,))
            if result and result[0]:
                username = result[0]
                is_linked = True
            else:
                return await ctx.send("❌ No tienes cuenta vinculada ni has especificado un nombre.")

        await ctx.typing()
        try:
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user: return await ctx.send(f"No se pudo encontrar '{username}' en modo '{mode}'.")
            
            best = self.osu.get_user_best_scores(user["id"], mode, 10)
            recent = self.osu.get_user_recent_scores(user["id"], mode, 20)
            
            analyzer = OsuAnalyzer(self.osu, user, recent_plays=recent, best_plays=best, user_focus=user_focus)
            prompt = await analyzer.generate_coaching_prompt()
            
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            ai_text = response.text.strip()
            
            embed_shell = discord.Embed(title=f"Plan de Coaching para {user['username']}", color=0xFFD700)
            embed_shell.set_thumbnail(url=user.get("avatar_url", ""))
            if is_linked: embed_shell.set_footer(text="Mostrando perfil vinculado.")
            PAGE_CHAR_LIMIT = 1800
            
            if len(ai_text) <= PAGE_CHAR_LIMIT:
                embed_shell.description = ai_text
                await ctx.send(embed=embed_shell)
            else:
                pages = [ai_text[i:i + PAGE_CHAR_LIMIT] for i in range(0, len(ai_text), PAGE_CHAR_LIMIT)]
                embed_shell.description = pages[0]
                await ctx.send(embed=embed_shell, view=DescriptionPaginator(pages, embed_shell))
        except Exception as e:
            await ctx.send("⚠️ Error al generar el plan de coaching."); print(f"[osuCoach] Error: {e}")

async def setup(bot):
    await bot.add_cog(OsuHandler(bot))

