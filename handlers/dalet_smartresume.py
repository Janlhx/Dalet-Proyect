import discord
from discord.ext import commands
# Quitamos json y os
import google.generativeai as genai
from datetime import datetime
# Importamos el conector
import db_connector
import traceback # Para errores
from datetime import datetime, timezone
class ResumenInteligente(commands.Cog, name="Resumen Inteligente"):
    def __init__(self, bot):
        self.bot = bot
        # Configurar Gemini aquí si no está globalmente
        # genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # --- 🗑️ SECCIÓN ELIMINADA 🗑️ ---
    # Ya no necesitamos _load_json ni _save_json
    # --- FIN DE LA SECCIÓN ELIMINADA ---

    # ==========================================================
    # ▼▼▼ COMANDO resumir_hibrido MODIFICADO ▼▼▼
    # ==========================================================
    @commands.command(name="resumir_hibrido")
    async def resumir_hibrido(self, ctx, cantidad_mensajes: int = 50):
        """Genera un resumen de la conversación del canal usando la BD."""
        print(f"\n--- [Resumen DEBUG] Iniciando resumir_hibrido para canal {ctx.channel.id}...")
        await ctx.typing()
        
        historial_texto = ""
        try:
            # 1. Obtener historial desde la base de datos
            print(f"--- [Resumen DEBUG] Obteniendo {cantidad_mensajes} mensajes de la BD...")
            # REQUISITO 4: Usamos la VISTA en lugar de un JOIN
            query = """
                SELECT UserName, Content
                FROM V_ChannelMessages
                WHERE ChannelID = %s
                ORDER BY Timestamp DESC
                LIMIT %s
            """
            # Obtener mensajes y revertir para orden cronológico
            registros = db_connector.fetch_all(query, (ctx.channel.id, cantidad_mensajes))
            registros.reverse()
            historial_texto = "\n".join([f"{autor}: {contenido}" for autor, contenido in registros])
            print(f"--- [Resumen DEBUG] Historial obtenido (longitud): {len(historial_texto)} chars")

            # 2. Generar resumen con Gemini (sin cambios)
            print("--- [Resumen DEBUG] Llamando a Gemini para resumir...")
            prompt = (f"Eres Dalet, una IA asistente. Analiza el siguiente historial de chat y genera un resumen conciso y neutral de los temas principales, eventos importantes y el tono general de la conversación. Sé breve y directo.\n\nHistorial:\n{historial_texto}\n\nResumen:")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt) # Usar async
            resumen_generado = response.text.strip()
            print(f"--- [Resumen DEBUG] Resumen recibido (longitud): {len(resumen_generado)} chars")

            if not resumen_generado:
                 await ctx.send("La IA no pudo generar un resumen esta vez.")
                 return

            # 3. Guardar resumen en la base de datos
            print("--- [Resumen DEBUG] Guardando resumen en la BD...")
            db_connector.execute_procedure(
                "sp_SaveSummary",
                (ctx.channel.id, resumen_generado, len(registros)) # Pasamos canal, texto y cantidad
            )
            print("--- [Resumen DEBUG] Resumen guardado.")

            # 4. Enviar respuesta (sin cambios)
            embed = discord.Embed(
                title=f"📄 Resumen de los últimos {len(registros)} mensajes",
                description=resumen_generado,
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [Resumen DEBUG] ERROR en resumir_hibrido: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Ocurrió un error al generar o guardar el resumen: {e}")
        finally:
            print("--- [Resumen DEBUG] --- Comando resumir_hibrido finalizado.\n")


    # ==========================================================
    # ▼▼▼ COMANDO ver_resumenes_hibrido MODIFICADO ▼▼▼
    # ==========================================================
    @commands.command(name="ver_resumenes_hibrido")
    async def ver_resumenes_hibrido(self, ctx, cantidad: int = 5):
        """Muestra los últimos resúmenes generados para este canal desde la BD."""
        print(f"\n--- [Resumen DEBUG] Iniciando ver_resumenes para canal {ctx.channel.id}...")
        try:
            # Usamos la función fn_GetRecentSummaries que devuelve una tabla
            # Los parámetros van en la query directamente para funciones SETOF
            query = "SELECT generated_date, summary_text FROM fn_GetRecentSummaries(%s, %s)"
            # fetch_all devolverá una lista de tuplas: [(datetime, text), (datetime, text), ...]
            resumenes = db_connector.fetch_all(query, (ctx.channel.id, cantidad))
            print(f"--- [Resumen DEBUG] {len(resumenes)} resúmenes encontrados.")

            if not resumenes:
                return await ctx.send("No hay resúmenes guardados para este canal.")

            embed = discord.Embed(
                title=f"📜 Últimos {len(resumenes)} Resúmenes de #{ctx.channel.name}",
                color=discord.Color.dark_orange()
            )

            # Iteramos sobre los resultados (ya están ordenados por fecha DESC por la función SQL)
            for i, (fecha_dt, texto) in enumerate(resumenes):
                # Formatear fecha
                fecha_str = fecha_dt.strftime('%Y-%m-%d %H:%M UTC')
                # Acortar texto si es muy largo para el embed
                texto_corto = (texto[:200] + '...') if len(texto) > 200 else texto
                embed.add_field(
                    name=f"#{i+1} - {fecha_str}",
                    value=texto_corto,
                    inline=False
                )
            
            embed.set_footer(text=f"Mostrando {len(resumenes)} de (potencialmente más) resúmenes.")
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [Resumen DEBUG] ERROR en ver_resumenes: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Error al obtener los resúmenes: {e}")
        finally:
            print("--- [Resumen DEBUG] --- Comando ver_resumenes finalizado.\n")


    # ==========================================================
    # ▼▼▼ COMANDO comparar_resumenes_hibrido MODIFICADO ▼▼▼
    # ==========================================================
    @commands.command(name="comparar_resumenes_hibrido")
    async def comparar_resumenes_hibrido(self, ctx, index1: int, index2: int):
        """Compara dos resúmenes del historial de este canal usando la IA."""
        print(f"\n--- [Resumen DEBUG] Iniciando comparar_resumenes para canal {ctx.channel.id} ({index1} vs {index2})...")
        await ctx.typing()
        try:
            # Obtenemos los textos de los resúmenes usando la función fn_GetSummaryByIndex
            res1_result = db_connector.fetch_one("SELECT fn_GetSummaryByIndex(%s, %s)", (ctx.channel.id, index1))
            res2_result = db_connector.fetch_one("SELECT fn_GetSummaryByIndex(%s, %s)", (ctx.channel.id, index2))

            res1 = res1_result[0] if res1_result and res1_result[0] else None
            res2 = res2_result[0] if res2_result and res2_result[0] else None
            
            print(f"--- [Resumen DEBUG] Resumen 1 encontrado: {bool(res1)}, Resumen 2 encontrado: {bool(res2)}")

            if not res1 or not res2:
                return await ctx.send("❌ Uno o ambos índices son inválidos o no se encontraron resúmenes.")

            # Llamar a Gemini para comparar (sin cambios)
            print("--- [Resumen DEBUG] Llamando a Gemini para comparar...")
            prompt = (f"Compara los siguientes dos resúmenes del chat. Explica brevemente cómo cambiaron los temas, el tono o las prioridades entre el Resumen {index1} (más antiguo si index1 > index2) y el Resumen {index2} (más reciente si index2 < index1).\n\nResumen {index1}:\n{res1}\n\nResumen {index2}:\n{res2}\n\nComparación:")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            comparacion = response.text.strip()
            print(f"--- [Resumen DEBUG] Comparación recibida (longitud): {len(comparacion)} chars")

            if not comparacion:
                await ctx.send("La IA no pudo generar una comparación esta vez.")
                return

            # Enviar respuesta (sin cambios)
            embed = discord.Embed(
                title=f"🔄 Comparación Resúmenes #{index1} vs #{index2}",
                description=comparacion,
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"!!!!!! [Resumen DEBUG] ERROR en comparar_resumenes: {e}")
            traceback.print_exc()
            await ctx.send(f"❌ Error al comparar los resúmenes: {e}")
        finally:
            print("--- [Resumen DEBUG] --- Comando comparar_resumenes finalizado.\n")


async def setup(bot):
    await bot.add_cog(ResumenInteligente(bot))