import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask
from threading import Thread
import sys # Asegúrate de tener 'import sys' al principio del archiv
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



#________________________________________________________________________________________
async def load_extensions():
    print("<<<<< INICIANDO CARGA DE MÓDULOS... >>>>>")

    # Obtenemos la ruta absoluta para que funcione siempre en Render
    script_dir = os.path.dirname(os.path.abspath(__file__))
    handlers_path = os.path.join(script_dir, "handlers")

    try:
        lista_archivos = os.listdir(handlers_path)
    except FileNotFoundError:
        print("!!!!!! ERROR GRAVE: La carpeta 'handlers' no se encontró.", file=sys.stderr)
        return

    for filename in lista_archivos:
        # ======================================================
        # ▼▼▼ ESTA ES LA LÍNEA CLAVE DE LA SOLUCIÓN ▼▼▼
        # ======================================================
        # Si el archivo es nuestro conector, lo saltamos y continuamos con el siguiente.
        if filename == "db_connector.py":
            continue
        # ======================================================

        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                print(f"--- ✅ Cargado: {module_name}")
            except Exception as e:
                # Imprimimos el error en el stream de errores para que sea más visible
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
                print(f"!!!!!! ❌ ERROR FATAL AL CARGAR {module_name} !!!!!!", file=sys.stderr)
                print(f"!!!!!! DETALLE: {e}", file=sys.stderr)
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
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