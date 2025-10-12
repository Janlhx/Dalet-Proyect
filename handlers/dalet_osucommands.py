import discord
from discord.ext import commands
from handlers.modules.osu_api import OsuAPI
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai
import json, os

# --- Configuración y funciones auxiliares ---
LINKED_ACCOUNTS_FILE = "linked_accounts.json"
def load_linked_accounts():
    if not os.path.exists(LINKED_ACCOUNTS_FILE): return {}
    try:
        with open(LINKED_ACCOUNTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except json.JSONDecodeError: return {}
def save_linked_accounts(data):
    with open(LINKED_ACCOUNTS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

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
        self.osu = OsuAPI(client_id=38819, client_secret="jiy7kpqNVZKtgjZRpvY2EzPmc6VL2BT1cpeS1qmR")

    @commands.command(help="""Vincula tu cuenta de osu! a tu perfil de Discord.
    
    Uso: `d.link <usuario_osu>`
    Ejemplo: `d.link WhiteCat`
    
    Una vez vinculada, no necesitarás escribir tu nombre en otros comandos.
    """)
    async def link(self, ctx, osu_username: str):
        await ctx.typing()
        try:
            user_data = self.osu.get_user(osu_username)
            if not user_data or "id" not in user_data:
                return await ctx.send(f"❌ No se encontró `{osu_username}`.")
            accounts = load_linked_accounts()
            accounts[str(ctx.author.id)] = user_data["username"]
            save_linked_accounts(accounts)
            await ctx.send(f"✅ Vinculado correctamente a **{user_data['username']}**.")
        except Exception as e:
            await ctx.send("⚠️ Error al vincular la cuenta."); print(f"[link] Error: {e}")

    @commands.command(help="""Desvincula tu cuenta de osu!.
    
    Uso: `d.unlink`
    """)
    async def unlink(self, ctx):
        accounts = load_linked_accounts()
        author_id = str(ctx.author.id)
        if author_id in accounts:
            del accounts[author_id]
            save_linked_accounts(accounts)
            await ctx.send("🗑️ Cuenta de osu! desvinculada.")
        else:
            await ctx.send("🤔 No tienes una cuenta vinculada.")

    @commands.command(help="""Muestra un perfil detallado de osu! de un jugador.
    
    Uso: `d.osuProfile [usuario] [-modo]`
    Ejemplo: `d.osuProfile WhiteCat -mania`
    
    Si no especificas un usuario, buscará tu perfil vinculado.
    """, aliases=["op"])
    async def osuProfile(self, ctx, *, args: str = None):
        username, mode, is_linked = None, "osu", False
        if args:
            parts = args.split()
            username_parts = []
            for part in parts:
                if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                    mode = part[1:].lower()
                else:
                    username_parts.append(part)
            username = " ".join(username_parts) if username_parts else None
        if not username:
            accounts = load_linked_accounts()
            username = accounts.get(str(ctx.author.id))
            if not username: return await ctx.send("❌ No tienes cuenta vinculada ni nombre especificado.")
            is_linked = True
        await ctx.typing()
        try:
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user: return await ctx.send(f"No se pudo encontrar '{username}' en modo '{mode}'.")
            stats, grades = user.get("statistics", {}), user.get("statistics", {}).get("grade_counts", {})
            play_time_hours, country_code = round(stats.get("play_time", 0) / 3600), user.get("country_code", "xx")
            global_rank_formatted = f"#{stats.get('global_rank'):,}" if stats.get('global_rank') else "N/A"
            country_rank_formatted = f"#{stats.get('country_rank'):,}" if stats.get('country_rank') else "N/A"
            mode_colors = {"osu": 0xFF66AA, "taiko": 0xDA3B26, "fruits": 0x86BA40, "mania": 0x5885C9}
            embed = discord.Embed(title=f"Perfil de {user['username']}", url=f"https://osu.ppy.sh/users/{user['id']}/{mode}", description=f"**Mostrando estadísticas para: `{mode.capitalize()}`**", color=mode_colors.get(mode, 0x7289DA))
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            main_stats_text = (f"**País:** :flag_{country_code.lower()}: `{country_rank_formatted}`\n**Rango Global:** 🏆 `{global_rank_formatted}`\n**PP:** 🎯 `{stats.get('pp', 0):,.2f}`\n"
                               f"**Precisión:** 📈 `{stats.get('hit_accuracy', 0):.2f}%`\n**Nivel:** ✨ `{stats.get('level', {}).get('current', 0)}`\n"
                               f"**Tiempo de Juego:** 🕒 `{play_time_hours:,} horas`\n**Playcount:** 🖱️ `{stats.get('play_count', 0):,}`")
            embed.add_field(name=f"Estadísticas de {mode.capitalize()}", value=main_stats_text, inline=False)
            if grades:
                grades_text = f"**SS:** `{grades.get('ss', 0) + grades.get('ssh', 0):,}` | **S:** `{grades.get('s', 0) + grades.get('sh', 0):,}` | **A:** `{grades.get('a', 0):,}`"
                embed.add_field(name="Calificaciones", value=grades_text, inline=False)
            if is_linked: embed.set_footer(text="Mostrando perfil vinculado.")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send("⚠️ Error al obtener el perfil."); print(f"[osuProfile] Error: {e}")

    @commands.command(help="""Genera un análisis de perfil de osu! con IA.
    
    Uso: `d.osuAnalyze [usuario] [-modo]`
    Ejemplo: `d.osuAnalyze -mania`
    
    Da un análisis general de fortalezas y debilidades.
    """, aliases=["oa"])
    async def osuAnalyze(self, ctx, *, args: str = None,):
        username, mode, is_linked = None, "osu", False
        valid_modes = ["osu", "taiko", "fruits", "mania"]
        if args:
            parts = args.split()
            username_parts = []
            for part in parts:
                if part.startswith("-") and part[1:].lower() in valid_modes:
                    mode = part[1:].lower()
                else:
                    username_parts.append(part)
            username = " ".join(username_parts) if username_parts else None

        if not username:
            accounts = load_linked_accounts()
            username = accounts.get(str(ctx.author.id))
            if not username:
                return await ctx.send("❌ No tienes cuenta vinculada ni nombre especificado.")
            is_linked = True
            
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

    El flag `--focus` te permite elegir el área de entrenamiento.
    Si no lo usas, la IA determinará el foco automáticamente.
    
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
            accounts = load_linked_accounts()
            username = accounts.get(str(ctx.author.id))
            if not username: return await ctx.send("❌ No tienes cuenta vinculada ni nombre especificado.")
            is_linked = True
        await ctx.typing()
        try:
            user = self.osu.get_user(username, mode)
            if not user or 'id' not in user: return await ctx.send(f"No se pudo encontrar '{username}' en modo '{mode}'.")
            best, recent = self.osu.get_user_best_scores(user["id"], mode, 10), self.osu.get_user_recent_scores(user["id"], mode, 20)
            
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