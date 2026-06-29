import discord
from discord.ext import commands
from datetime import datetime, timezone
import logging

logger = logging.getLogger("dalet.handlers.smartresume")

class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    """Comandos para generar y ver resúmenes de chat."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo
        self.nlp = bot.nlp_service

    @commands.command(name="resumir", aliases=["resume"])
    async def resumir(self, ctx, cantidad_mensajes: int = 50):
        """📄 Genera un resumen de los últimos N mensajes del canal. Uso: `d.resumir [cantidad]`"""
        await ctx.typing()

        try:
            registros = await self.repo.get_channel_messages(ctx.channel.id, cantidad_mensajes)

            if not registros:
                return await ctx.send("No hay suficientes mensajes en este canal para generar un resumen.")

            display_list = list(registros)
            display_list.reverse()
            historial_texto = "\n".join([
                f"{r.get('username') or r.get('UserName') or 'Desconocido'}: {r.get('content') or r.get('Content') or ''}"
                for r in display_list
            ])

            prompt = (
                f"Analiza el siguiente historial de chat y genera un resumen conciso y neutral de los temas principales, "
                f"eventos importantes y el tono general de la conversación. Sé breve y directo.\n\n"
                f"Historial:\n{historial_texto}\n\nResumen:"
            )

            resumen_generado = await self.nlp.generate_reply(
                prompt,
                "Resumen de Chat",
                "Sistema",
                system_prompt_override=(
                    "Eres un asistente analítico y neutral especializado en resumir conversaciones. "
                    "No tienes personalidad, no haces chistes, no interactúas con los usuarios. "
                    "Tu única función es extraer la información clave de forma estructurada y objetiva."
                )
            )

            if not resumen_generado:
                return await ctx.send("La IA no pudo generar un resumen esta vez.")

            # Guardar en Postgres (no crítico — si Neon está offline, el resumen igual se muestra)
            try:
                await self.repo.call_procedure(
                    "sp_SaveSummary",
                    ctx.channel.id, resumen_generado, len(registros)
                )
            except Exception as save_err:
                logger.debug(f"No se pudo guardar resumen en Postgres (no crítico): {save_err}")

            embed = discord.Embed(
                title=f"📄 Resumen de los últimos {len(registros)} mensajes",
                description=resumen_generado,
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"#{ctx.channel.name}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in resumir: {e}")
            await ctx.send(f"❌ Ocurrió un error al generar el resumen.")

    @commands.command(name="ver_resumenes", aliases=["resumenes"])
    async def ver_resumenes(self, ctx, cantidad: int = 5):
        """📜 Muestra los últimos resúmenes guardados para este canal. Uso: `d.ver_resumenes [cantidad]`"""
        try:
            query = "SELECT generated_date, summary_text FROM fn_GetRecentSummaries($1, $2)"
            resumenes = await self.repo.fetch_all(query, ctx.channel.id, cantidad)

            if not resumenes:
                return await ctx.send("No hay resúmenes guardados para este canal todavía. Usa `d.resumir` para generar uno.")

            embed = discord.Embed(
                title=f"📜 Últimos {len(resumenes)} Resúmenes · #{ctx.channel.name}",
                color=discord.Color.dark_orange()
            )

            for i, r in enumerate(resumenes):
                fecha_str = r[0].strftime('%d/%m/%Y %H:%M UTC') if r[0] else "Fecha desconocida"
                texto = r[1] or "(vacío)"
                texto_corto = (texto[:200] + '…') if len(texto) > 200 else texto
                embed.add_field(
                    name=f"#{i+1} — {fecha_str}",
                    value=texto_corto,
                    inline=False
                )

            embed.set_footer(text=f"Mostrando {len(resumenes)} resúmenes.")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in ver_resumenes: {e}")
            await ctx.send(f"❌ Error al obtener los resúmenes.")

async def setup(bot):
    await bot.add_cog(ResumenInteligente(bot))
