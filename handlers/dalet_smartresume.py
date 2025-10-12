import discord
from discord.ext import commands
import json
import os
import google.generativeai as genai
from datetime import datetime

class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    def __init__(self, bot):
        self.bot = bot
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        for file in ["chat_history.json", "memoria.json", "resumenes.json"]:
            if not os.path.exists(file):
                with open(file, "w", encoding="utf-8") as f: json.dump({}, f, indent=4)
    def _load_json(self, path, default):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return default
    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

    @commands.command(name="resumir_hibrido")
    async def resumir_hibrido(self, ctx, cantidad: int = 50):
        """Genera un resumen de la conversación del canal.
        
        Uso: d.resumir_hibrido [cantidad_mensajes]
        Ejemplo: d.resumir_hibrido 100
        
        Combina los mensajes del chat general y la memoria de la IA
        para crear y guardar un resumen de los temas hablados.
        Por defecto usa los últimos 50 mensajes.
        """
        # ... (El código del comando no cambia)
        await ctx.typing()
        chat_data = self._load_json("chat_history.json", [])
        memoria_data = self._load_json("memoria.json", {})
        canal_key = f"{ctx.guild.id}-{ctx.channel.id}" if ctx.guild else f"DM-{ctx.author.id}"
        mensajes_chat = [f"{r.get('author_name', r.get('author', '???'))}: {r.get('content', '')}" for r in chat_data if str(r.get("channel", "")) == str(ctx.channel) or str(r.get("channel_id", "")) == str(ctx.channel.id)]
        mensajes_memoria = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in memoria_data.get(canal_key, [])]
        combinados = (mensajes_chat + mensajes_memoria)[-cantidad:]
        total_combinado = len(combinados)
        await ctx.send(f"**Resumiendo el canal...**\n- Usando últimos `{total_combinado}` mensajes para el resumen.")
        if total_combinado < 3: return await ctx.send(f"⚠️ Solo hay {total_combinado} mensajes, necesito al menos 3.")
        texto_final = "\n".join(combinados)[-8000:]
        prompt = (f"Eres Dalet, un asistente claro y directo. Resume brevemente el contenido de los mensajes siguientes. Enfócate en los temas principales, evita frases largas y no repitas ideas.\n\n{texto_final}")
        try:
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = model.generate_content(prompt)
            resumen = response.text.strip() if hasattr(response, "text") else response.candidates[0].content.parts[0].text.strip()
            resumen_data = self._load_json("resumenes.json", {})
            if canal_key not in resumen_data: resumen_data[canal_key] = []
            resumen_data[canal_key].append({"fecha": datetime.utcnow().isoformat(), "mensajes_resumidos": total_combinado, "resumen": resumen, "fuente": ["memoria", "chat_history"]})
            self._save_json("resumenes.json", resumen_data)
            if len(resumen) > 2000: resumen = resumen[:1990] + "…"
            await ctx.send(f"**🗒️ Resumen del canal:**\n{resumen}")
        except Exception as e:
            await ctx.send(f"⚠️ Error al generar el resumen: `{e}`")

    @commands.command(name="ver_resumenes_hibrido")
    async def ver_resumenes(self, ctx):
        """Muestra el historial de resúmenes del canal.
        
        Uso: d.ver_resumenes_hibrido
        
        Muestra una lista de los últimos 5 resúmenes guardados
        con su fecha y número de mensajes que analizó.
        """
        # ... (El código del comando no cambia)
        resumen_data = self._load_json("resumenes.json", {})
        canal_key = f"{ctx.guild.id}-{ctx.channel.id}" if ctx.guild else f"DM-{ctx.author.id}"
        if canal_key not in resumen_data or not resumen_data[canal_key]:
            return await ctx.send("📄 Este canal no tiene resúmenes guardados.")
        embed_text = ""
        for i, r in enumerate(resumen_data[canal_key][-5:], 1):
            fecha = datetime.fromisoformat(r["fecha"]).strftime("%Y-%m-%d %H:%M")
            embed_text += f"**{i}.** {fecha} - {r['mensajes_resumidos']} msgs\n"
        await ctx.send(f"**Historial de resúmenes híbridos:**\n{embed_text}")

    @commands.command(name="comparar_resumenes_hibrido")
    async def comparar_resumenes(self, ctx, index1: int, index2: int):
        """Compara dos resúmenes del historial usando IA.
        
        Uso: d.comparar_resumenes_hibrido <índice1> <índice2>
        Ejemplo: d.comparar_resumenes_hibrido 1 2
        
        Usa los números de la lista de `d.ver_resumenes_hibrido`.
        La IA analizará cómo ha cambiado la conversación entre ambos puntos.
        """
        # ... (El código del comando no cambia)
        resumen_data = self._load_json("resumenes.json", {})
        canal_key = f"{ctx.guild.id}-{ctx.channel.id}" if ctx.guild else f"DM-{ctx.author.id}"
        if canal_key not in resumen_data or len(resumen_data[canal_key]) < max(index1, index2):
            return await ctx.send("Índices inválidos o insuficientes resúmenes.")
        res1 = resumen_data[canal_key][index1 - 1]["resumen"]
        res2 = resumen_data[canal_key][index2 - 1]["resumen"]
        prompt = (f"Compara los siguientes dos resúmenes del chat. Explica brevemente cómo cambiaron los temas, el tono o las prioridades.\n\nResumen 1:\n{res1}\n\nResumen 2:\n{res2}")
        try:
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            resp = model.generate_content(prompt)
            comparacion = resp.text.strip() if hasattr(resp, "text") else resp.candidates[0].content.parts[0].text.strip()
            if len(comparacion) > 2000: comparacion = comparacion[:1990] + "…"
            await ctx.send(f"**Comparación:**\n{comparacion}")
        except Exception as e:
            await ctx.send(f"Error al comparar resúmenes: `{e}`")


async def setup(bot):
    await bot.add_cog(ResumenInteligente(bot))