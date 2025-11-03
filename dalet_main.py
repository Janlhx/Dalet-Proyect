"""
Punto de Entrada Principal del Bot Dalet.

Este archivo es responsable de:
1. Cargar las variables de entorno (API keys).
2. Configurar el bot de Discord (Intents, Prefijo).
3. Iniciar el servidor web Flask (para el health check de Render).
4. Cargar dinámicamente todas las extensiones (Cogs) desde la carpeta /handlers.
5. Iniciar la conexión del bot con Discord.
"""
import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask
from threading import Thread
import sys

# --- 1. Carga de Configuración ---
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("Token de Discord cargado:", bool(DISCORD_TOKEN))
print("Key de Gemini cargada:", bool(GEMINI_API_KEY))

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. Configuración del Bot ---
bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)

# --- 3. Servidor Web (Health Check para Render) ---
app = Flask('')

@app.route('/')
def home():
    """Punto de 'health check' que Render usa para saber si el bot está vivo."""
    return "El bot está vivo."

def run():
    """Inicia el servidor Flask."""
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Crea e inicia el hilo del servidor Flask."""
    t = Thread(target=run)
    t.start()

# --- 4. Carga de Extensiones (Cogs) ---
async def load_extensions():
    """
    Carga dinámicamente todas las extensiones (archivos .py)
    de la carpeta /handlers.
    """
    print("<<<<< INICIANDO CARGA DE MÓDULOS... >>>>>")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    handlers_path = os.path.join(script_dir, "handlers")

    try:
        lista_archivos = os.listdir(handlers_path)
    except FileNotFoundError:
        print("!!!!!! ERROR GRAVE: La carpeta 'handlers' no se encontró.", file=sys.stderr)
        return

    for filename in lista_archivos:
        # Ignoramos el conector de BD, ya que no es un Cog.
        if filename == "db_connector.py":
            continue

        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                print(f"--- ✅ Cargado: {module_name}")
            except Exception as e:
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
                print(f"!!!!!! ❌ ERROR FATAL AL CARGAR {module_name} !!!!!!", file=sys.stderr)
                print(f"!!!!!! DETALLE: {e}", file=sys.stderr)
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)

# --- 5. Punto de Entrada Principal ---
async def main():
    """Función asíncrona principal para iniciar el bot."""
    async with bot:
        await load_extensions()
        await bot.start(DISCORD_TOKEN)

# Inicia el servidor web en un hilo secundario
keep_alive()

# Inicia el bot en el hilo principal
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Bot desconectado manualmente.")