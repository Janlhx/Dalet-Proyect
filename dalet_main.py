import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask
from threading import Thread

#________________________________________________________________________________________
load_dotenv()  # Carga las variables desde el archivo .env

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("Token de Discord cargado:", bool(DISCORD_TOKEN))
print("Key de Gemini cargada:", bool(GEMINI_API_KEY))

# Configura la API de Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

#________________________________________________________________________________________
bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)

# --- CÓDIGO DEL SERVIDOR WEB ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# --- FIN DEL CÓDIGO DEL SERVIDOR WEB ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot conectado como {bot.user}")

#________________________________________________________________________________________
async def load_extensions():
    # ======================================================
    # ▼▼▼ AÑADE ESTA LÍNEA ▼▼▼
    # ======================================================
    print("<<<<< INICIANDO CARGA DE MÓDULOS... SI VES ESTO, ESTÁS EN EL LOG CORRECTO >>>>>")
    # ======================================================
    
    for filename in os.listdir("./handlers"):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                print(f"--- Cargado: {module_name}")
            except Exception as e:
                # También haremos el error más visible
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                print(f"!!!!!! ERROR FATAL AL CARGAR {module_name} !!!!!!")
                print(f"!!!!!! DETALLE: {e}")
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
#________________________________________________________________________________________

#________________________________________________________________________________________
async def main():
    async with bot:
        await load_extensions()
        # Se usa bot.start() en lugar de bot.run() en un entorno async
        await bot.start(DISCORD_TOKEN)

# Inicia el servidor web en un hilo secundario
keep_alive() # <--- ¡ESTA ES LA LÍNEA QUE FALTABA!

# Inicia el bot en el hilo principal
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Bot desconectado manualmente.")