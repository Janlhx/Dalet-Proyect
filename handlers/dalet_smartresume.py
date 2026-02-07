import discord
from discord.ext import commands
from datetime import datetime, timezone
import logging
import traceback

logger = logging.getLogger("dalet.handlers.smartresume")

class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    """Comandos para generar, ver y comparar resúmenes de chat de forma asíncrona."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo
        self.nlp = bot.nlp_service

    @commands.command(name="resumir_hibrido")
    async def resumir_hibrido(self, ctx, cantidad_mensajes: int = 50):
        """Genera un resumen de la conversación del canal usando la BD y la IA."""
        await ctx.typing()
        
        try:
            # 1. Obtener historial desde la base de datos asíncronamente
            registros = await self.repo.get_channel_messages(ctx.channel.id, cantidad_mensajes)
            
            if not registros:
                return await ctx.send("No hay suficientes mensajes en este canal para generar un resumen.")

            # registers are in descending order, we want chronological for display
            display_list = list(registros)
            display_list.reverse()
            historial_texto = "\n".join([f"{r[0]}: {r[1]}" for r in display_list])

            # 2. Generar resumen con NLPService
            prompt = (f"Analiza el siguiente historial de chat y genera un resumen conciso y neutral de los temas principales, "
                     f"eventos importantes y el tono general de la conversación. Sé breve y directo.\n\n"
                     f"Historial:\n{historial_texto}\n\nResumen:")
            
            resumen_generado = await self.nlp.generate_reply(prompt, "Resumen de Chat", "Sistema")

            if not resumen_generado:
                 return await ctx.send("La IA no pudo generar un resumen esta vez.")

            # 3. Guardar resumen en la base de datos
            await self.repo.call_procedure(
                "sp_SaveSummary",
                ctx.channel.id, resumen_generado, len(registros)
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
            logger.error(f"Error in resumir_hibrido: {e}")
            await ctx.send(f"❌ Ocurrió un error al generar o guardar el resumen.")

    @commands.command(name="ver_resumenes_hibrido")
    async def ver_resumenes_hibrido(self, ctx, cantidad: int = 5):
        """📜 Muestra los últimos resúmenes generados para este canal. Uso: `d.ver_resumenes_hibrido [cantidad]`"""
        try:
            query = "SELECT generated_date, summary_text FROM fn_GetRecentSummaries($1, $2)"
            resumenes = await self.repo.fetch_all(query, ctx.channel.id, cantidad)

            if not resumenes:
                return await ctx.send("No hay resúmenes guardados para este canal.")

            embed = discord.Embed(
                title=f"📜 Últimos {len(resumenes)} Resúmenes de #{ctx.channel.name}",
                color=discord.Color.dark_orange()
            )

            for i, r in enumerate(resumenes):
                fecha_str = r[0].strftime('%Y-%m-%d %H:%M UTC')
                texto = r[1]
                texto_corto = (texto[:200] + '...') if len(texto) > 200 else texto
                embed.add_field(
                    name=f"#{i+1} - {fecha_str}",
                    value=texto_corto,
                    inline=False
                )
            
            embed.set_footer(text=f"Mostrando {len(resumenes)} resúmenes.")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in ver_resumenes: {e}")
            await ctx.send(f"❌ Error al obtener los resúmenes.")

    @commands.command(name="comparar_resumenes_hibrido")
    async def comparar_resumenes_hibrido(self, ctx, index1: int, index2: int):
        """Compara dos resúmenes del historial de este canal usando la IA."""
        await ctx.typing()
        try:
            res1_row = await self.repo.fetch_one("SELECT fn_GetSummaryByIndex($1, $2)", ctx.channel.id, index1)
            res2_row = await self.repo.fetch_one("SELECT fn_GetSummaryByIndex($1, $2)", ctx.channel.id, index2)

            res1 = res1_row[0] if res1_row else None
            res2 = res2_row[0] if res2_row else None
            
            if not res1 or not res2:
                return await ctx.send("❌ Uno o ambos índices son inválidos.")

            # Llamar a NLPService para comparar
            prompt = (f"Compara los siguientes dos resúmenes del chat. Explica brevemente cómo cambiaron los temas, "
                     f"el tono o las prioridades entre el Resumen {index1} y el Resumen {index2}.\n\n"
                     f"Resumen {index1}:\n{res1}\n\nResumen {index2}:\n{res2}\n\nComparación:")
            
            comparacion = await self.nlp.generate_reply(prompt, "Comparación de Resúmenes", "Sistema")

            if not comparacion:
                return await ctx.send("La IA no pudo generar una comparación.")

            embed = discord.Embed(
                title=f"🔄 Comparación Resúmenes #{index1} vs #{index2}",
                description=comparacion,
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in comparar_resumenes: {e}")
            await ctx.send(f"❌ Error al comparar los resúmenes.")

async def setup(bot):
    await bot.add_cog(ResumenInteligente(bot))
