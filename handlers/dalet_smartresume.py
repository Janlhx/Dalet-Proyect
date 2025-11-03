"""
Handler (Cog) para Resúmenes Inteligentes de Chat.

Este Cog permite a los usuarios generar resúmenes de la conversación
reciente usando la IA y la base de datos.
"""
import discord
from discord.ext import commands
import google.generativeai as genai
from datetime import datetime, timezone
import db_connector
import traceback # Para errores

class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    """Comandos para generar, ver y comparar resúmenes de chat."""
    def __init__(self, bot):
        self.bot = bot
        # (Opcional) Configurar Gemini aquí si no está globalmente
        # genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    @commands.command(name="resumir_hibrido")
    async def resumir_hibrido(self, ctx, cantidad_mensajes: int = 50):
        """
        Genera un resumen de la conversación del canal usando la BD y la IA.
        
        Pasos:
        1. Obtiene los últimos 'N' mensajes de 'V_ChannelMessages' (Req 4).
        2. Envía el historial a la IA de Gemini para generar un resumen.
        3. Guarda el resumen en la BD usando 'sp_SaveSummary' (Req 3).
        """
        await ctx.typing()
        
        historial_texto = ""
        try:
            # 1. Obtener historial desde la base de datos (Usando la Vista)
            query = """
                SELECT UserName, Content
                FROM V_ChannelMessages
                WHERE ChannelID = %s
                ORDER BY Timestamp DESC
                LIMIT %s
            """
            registros = db_connector.fetch_all(query, (ctx.channel.id, cantidad_mensajes))
            registros.reverse() # Poner en orden cronológico
            historial_texto = "\n".join([f"{autor}: {contenido}" for autor, contenido in registros])

            if not historial_texto:
                await ctx.send("No hay suficientes mensajes en este canal para generar un resumen.")
                return

            # 2. Generar resumen con Gemini
            prompt = (f"Eres Dalet, una IA asistente. Analiza el siguiente historial de chat y genera un resumen conciso y neutral de los temas principales, eventos importantes y el tono general de la conversación. Sé breve y directo.\n\nHistorial:\n{historial_texto}\n\nResumen:")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            resumen_generado = response.text.strip()

            if not resumen_generado:
                 await ctx.send("La IA no pudo generar un resumen esta vez.")
                 return

            # 3. Guardar resumen en la base de datos (Usando SP)
            db_connector.execute_procedure(
                "sp_SaveSummary",
                (ctx.channel.id, resumen_generado, len(registros))
            )

            # 4. Enviar respuesta
            embed = discord.Embed(
                title=f"📄 Resumen de los últimos {len(registros)} mensajes",
                description=resumen_generado,
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [SmartResume] ERROR en resumir_hibrido: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Ocurrió un error al generar o guardar el resumen: {e}")

    @commands.command(name="ver_resumenes_hibrido")
    async def ver_resumenes_hibrido(self, ctx, cantidad: int = 5):
        """
        Muestra los últimos resúmenes generados para este canal desde la BD.
        
        Llama a la función 'fn_GetRecentSummaries' (Req 5).
        """
        try:
            # Usamos la función de la BD que devuelve una tabla
            query = "SELECT generated_date, summary_text FROM fn_GetRecentSummaries(%s, %s)"
            resumenes = db_connector.fetch_all(query, (ctx.channel.id, cantidad))

            if not resumenes:
                return await ctx.send("No hay resúmenes guardados para este canal.")

            embed = discord.Embed(
                title=f"📜 Últimos {len(resumenes)} Resúmenes de #{ctx.channel.name}",
                color=discord.Color.dark_orange()
            )

            for i, (fecha_dt, texto) in enumerate(resumenes):
                fecha_str = fecha_dt.strftime('%Y-%m-%d %H:%M UTC')
                texto_corto = (texto[:200] + '...') if len(texto) > 200 else texto
                embed.add_field(
                    name=f"#{i+1} - {fecha_str}",
                    value=texto_corto,
                    inline=False
                )
            
            embed.set_footer(text=f"Mostrando {len(resumenes)} de (potencialmente más) resúmenes.")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [SmartResume] ERROR en ver_resumenes: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Error al obtener los resúmenes: {e}")

    @commands.command(name="comparar_resumenes_hibrido")
    async def comparar_resumenes_hibrido(self, ctx, index1: int, index2: int):
        """
        Compara dos resúmenes del historial de este canal usando la IA.
        
        Llama a la función 'fn_GetSummaryByIndex' (Req 5).
        """
        await ctx.typing()
        try:
            # Obtenemos los textos de los resúmenes usando la función de la BD
            res1_result = db_connector.fetch_one("SELECT fn_GetSummaryByIndex(%s, %s)", (ctx.channel.id, index1))
            res2_result = db_connector.fetch_one("SELECT fn_GetSummaryByIndex(%s, %s)", (ctx.channel.id, index2))

            res1 = res1_result[0] if res1_result and res1_result[0] else None
            res2 = res2_result[0] if res2_result and res2_result[0] else None
            
            if not res1 or not res2:
                return await ctx.send("❌ Uno o ambos índices son inválidos o no se encontraron resúmenes.")

            # Llamar a Gemini para comparar
            prompt = (f"Compara los siguientes dos resúmenes del chat. Explica brevemente cómo cambiaron los temas, el tono o las prioridades entre el Resumen {index1} (más antiguo si index1 > index2) y el Resumen {index2} (más reciente si index2 < index1).\n\nResumen {index1}:\n{res1}\n\nResumen {index2}:\n{res2}\n\nComparación:")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            comparacion = response.text.strip()

            if not comparacion:
                await ctx.send("La IA no pudo generar una comparación esta vez.")
                return

            embed = discord.Embed(
                title=f"🔄 Comparación Resúmenes #{index1} vs #{index2}",
                description=comparacion,
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [SmartResume] ERROR en comparar_resumenes: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Error al comparar los resúmenes: {e}")


async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(ResumenInteligente(bot))