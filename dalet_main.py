import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
import google.generativeai as genai

#________________________________________________________________________________________
load_dotenv()  # Carga las variables desde el archivo .env

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("Token de Discord cargado:", bool(DISCORD_TOKEN))
print("Key de Gemini cargada:", bool(GEMINI_API_KEY))

# Configura la API de Gemini
genai.configure(api_key=GEMINI_API_KEY)

#________________________________________________________________________________________
bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot conectado como {bot.user}")

#________________________________________________________________________________________
async def load_extensions():
    for filename in os.listdir("./handlers"):
        # Ahora ignora archivos que empiezan con '__'
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                print(f" Cargado: {module_name}")
            except Exception as e:
                print(f" Error al cargar {module_name}: {e}")
#________________________________________________________________________________________

#________________________________________________________________________________________
async def main():
    async with bot:
        await load_extensions()

        await bot.start(DISCORD_TOKEN)
    
asyncio.run(main())
 