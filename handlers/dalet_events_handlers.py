from discord.ext import commands
import discord
import random
from handlers.modules.dalet_nlp import generate_contextual_reply

class EventsHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 
#________________________________________________________________________________________        
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Bot conectado como {self.bot.user}")
        
#________________________________________________________________________________________
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):  # Para comandos que no existen
            await ctx.send("No tengo esa Función")
#________________________________________________________________________________________



#________________________________________________________________________________________
@commands.Cog.listener()
async def on_member_join(self, member):
    # ID del canal donde se mandará el mensaje
    channel_id = 790644877389201439  # <-- reemplaza con el ID de tu canal
    channel = member.guild.get_channel(channel_id)

    if channel:
        await channel.send(f"¡Bienvenido {member.mention} al servidor!")

#________________________________________________________________________________________
async def setup(bot):
    await bot.add_cog(EventsHandler(bot))



