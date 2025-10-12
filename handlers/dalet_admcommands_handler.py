import discord
import os
import sys
from discord.ext import commands

class AdminCommands(commands.Cog, name="Comandos para el Administrador del bot"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        """[ADMIN] Reinicia el bot completamente.
        
        Uso: d.restart
        
        Este comando detiene el proceso actual del bot y lo
        inicia de nuevo. Es útil para aplicar cambios en el código
        sin tener que acceder a la consola.
        """
        await ctx.send("Reiniciando...")
        os.execv(sys.executable, ['python'] + sys.argv)

    @commands.command()    
    @commands.is_owner()
    async def shutdown(self, ctx):
        """[ADMIN] Apaga el bot.
        
        Uso: d.shutdown
        
        Detiene el bot por completo. No se volverá a encender
        hasta que lo inicies manualmente desde la consola.
        """
        await ctx.send("Apagando...")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))