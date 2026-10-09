import discord
from discord.ext import commands
import logging
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules

logger = logging.getLogger("dalet.handlers.smartresume")


class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    """Comandos para generar resúmenes dinámicos de chat con IA."""

    def __init__(self, bot):
        self.bot = bot
        self.nlp = bot.nlp_service

    @commands.command(name="resumir", aliases=["resume"])
    async def resumir(self, ctx, cantidad_mensajes: int = 25, estilo: str = "dalet"):
        """📄 Genera un resumen inteligente de los últimos N mensajes del canal. Uso: `d.resumir [cantidad] [dalet|neutral]`"""
        await ctx.typing()

        try:
            clamped_limit = min(max(10, cantidad_mensajes), 50)
            channel = ctx.channel

            raw_messages = []
            async for msg in channel.history(limit=clamped_limit + 5):
                # Omitir el comando de invocación actual
                if msg.id == ctx.message.id:
                    continue
                raw_messages.append(msg)
                if len(raw_messages) >= clamped_limit:
                    break

            if len(raw_messages) < 3:
                return await ctx.send("⚠️ No hay suficientes mensajes recientes en este canal para generar un resumen.")

            # Invertir para leer en orden cronológico (antiguo -> reciente)
            raw_messages.reverse()

            lineas = []
            for m in raw_messages:
                author_name = m.author.display_name or m.author.name
                content = (m.clean_content or "").strip()
                if not content and m.attachments:
                    content = f"[Adjuntó {len(m.attachments)} archivo(s)/imagen(es)]"
                elif not content and m.embeds:
                    content = "[Envió un embed/enlace]"
                elif m.attachments:
                    content += f" (+{len(m.attachments)} adjunto(s))"

                if len(content) > 300:
                    content = content[:300] + "…"

                lineas.append(f"{author_name}: {content}")

            historial_texto = "\n".join(lineas)
            estilo_clean = estilo.lower().strip()

            if estilo_clean == "neutral":
                system_prompt = (
                    "Eres un asistente analítico y neutral especializado en síntesis de conversaciones. "
                    "Tu tarea es resumir objetivamente la conversación reciente de este canal. "
                    "Sigue ESTRICTAMENTE esta estructura en Markdown:\n"
                    "### 📌 En pocas palabras (TL;DR)\n"
                    "(1 o 2 oraciones con el resumen ejecutivo central)\n\n"
                    "### 💬 Temas clave\n"
                    "• (Punto 1 objetivo)\n"
                    "• (Punto 2 objetivo)\n"
                    "• (Punto 3 objetivo si aplica)\n\n"
                    "### 📋 Conclusión\n"
                    "(Cierre analítico y neutral del estado de la conversación)"
                )
            else:
                system_prompt = (
                    "Eres Dalet, una chica aguda, observadora, ligeramente sarcástica y muy carismática de Discord. "
                    "Tu tarea es resumir la conversación reciente de este canal sin rodeos innecesarios. "
                    "Sigue ESTRICTAMENTE esta estructura en Markdown:\n"
                    "### 📌 En pocas palabras (TL;DR)\n"
                    "(1 o 2 oraciones resumiendo el punto central de lo que pasó)\n\n"
                    "### 💬 Temas clave\n"
                    "• (Punto 1 claro)\n"
                    "• (Punto 2 claro)\n"
                    "• (Punto 3 claro si aplica)\n\n"
                    "### 🎭 El veredicto de Dalet\n"
                    "(Un comentario ingenioso, con tu humor seco y personalidad sobre de qué estaban hablando)"
                )

            user_prompt = f"Analiza esta conversación reciente ({len(raw_messages)} mensajes):\n\n{historial_texto}\n\nGenera el resumen estructurado:"

            resumen_generado = await self.nlp.generate_reply(
                user_prompt,
                "Resumen de Chat",
                ctx.author.display_name or ctx.author.name,
                system_prompt_override=system_prompt,
                max_tokens=550
            )

            if not resumen_generado:
                return await ctx.send("❌ La IA no pudo generar un resumen esta vez.")

            color = DaletAtoms.COLOR_PRIMARY if estilo_clean != "neutral" else DaletAtoms.COLOR_INFO
            estilo_label = "Modo Neutral" if estilo_clean == "neutral" else "Modo Dalet"

            embed = discord.Embed(
                title=f"📄 Resumen del Canal · {estilo_label}",
                description=resumen_generado,
                color=color
            )
            embed.set_author(
                name=f"#{getattr(channel, 'name', 'chat')} • {len(raw_messages)} mensajes analizados",
                icon_url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
            )
            DaletMolecules.add_standard_footer(embed, context_text="Resumen Inteligente con IA")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in resumir: {e}")
            await ctx.send("❌ Ocurrió un error al generar el resumen.")

    @commands.command(name="ver_resumenes", aliases=["resumenes"])
    async def ver_resumenes(self, ctx):
        """📜 Información sobre la generación de resúmenes en el canal."""
        embed = discord.Embed(
            title="📄 Resumen en Tiempo Real",
            description=(
                "Los resúmenes de Dalet ahora se generan dinámicamente en tiempo real leyendo directamente "
                "el historial fresco del canal.\n\n"
                "**Uso recomendado:**\n"
                "• `/resumir` (Comando de barra con selector de estilo `dalet` o `neutral`)\n"
                "• `d.resumir [cantidad=25] [dalet|neutral]` (Comando clásico de texto)"
            ),
            color=DaletAtoms.COLOR_INFO
        )
        DaletMolecules.add_standard_footer(embed, context_text="Dalet AI • Tiempo Real")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ResumenInteligente(bot))
