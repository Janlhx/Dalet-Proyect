# 🚀 Punto de Entrada: `dalet_main.py`

> Es el **primer archivo que se ejecuta**. Arranca todo: la base de datos, los servicios, el bot de Discord y el servidor web.

---

## ¿Qué hace este archivo?

**Orden de ejecución al correr `python dalet_main.py`:**

1. Configura el sistema de logging (para ver mensajes en consola y en `dalet.log`)
2. Carga las variables del archivo `.env`
3. Inicia un servidor Flask en el puerto 8080 (en un hilo separado)
4. Entra al bucle `main()` que:
   - Conecta la base de datos (pool asyncpg)
   - Crea instancias de todos los repositorios y servicios
   - Carga todos los Cogs desde `/handlers/`
   - Conecta el bot a Discord

---

## 📋 Componentes Explicados

### Logging (`logging.basicConfig`)

```python
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),  # Muestra en consola
        logging.FileHandler("dalet.log")    # Guarda en archivo
    ]
)
```

- Cada módulo tiene su propio logger: `dalet.main`, `dalet.handlers.nlp`, etc.
- Esto permite filtrar logs por módulo si fuera necesario.
- El archivo `dalet.log` acumula todos los mensajes (útil para debuggear en Render).

---

### Servidor Flask (Health Check)

```python
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo."

def keep_alive():
    t = Thread(target=run)
    t.start()
```

**¿Por qué existe esto?**  
Render (el servidor en la nube) necesita que la aplicación responda a peticiones HTTP para saber que sigue viva. Si no responde, Render la reinicia. Flask corre en un **hilo separado** para no bloquear el bot asíncrono.

---

### `DatabasePool.get_pool()` — Primera conexión a la BD

```python
await DatabasePool.get_pool()
```

Se llama **una sola vez** al inicio. Crea un "pool" de 1 a 5 conexiones a PostgreSQL que todos los repositorios comparten. Esto es más eficiente que abrir/cerrar una conexión nueva en cada consulta.

---

### Instanciación de Repositorios y Servicios

```python
bot.user_repo       = UserRepository()
bot.osu_repo        = OsuRepository()
bot.admin_repo      = AdminRepository()
bot.analytics_repo  = AnalyticsRepository()

bot.nlp_service     = NLPService(GEMINI_API_KEY, user_repo=bot.user_repo)
bot.memory_service  = MemoryService(bot.user_repo)
bot.osu_service     = OsuService(client_id=..., client_secret=...)
```

Todos se guardan como atributos del objeto `bot` para que cualquier Cog pueda acceder a ellos con `self.bot.user_repo`, `self.bot.nlp_service`, etc.

---

### Flush Task Periódico

```python
flush_task = asyncio.get_event_loop().create_task(bot.user_repo._periodic_flush())
```

Inicia en segundo plano la tarea que cada 60 segundos vacía el buffer de mensajes hacia la base de datos.

---

### Purga de Mensajes Expirados (Privacy TTL)

```python
async def _purge_expired_messages():
    while True:
        await asyncio.sleep(3600)  # Cada hora
        deleted = await conn.fetchval("SELECT fn_PurgeExpiredMessages()")
```

Cada hora elimina mensajes con más de 48 horas de antigüedad. Esto es una política de privacidad: no guardamos el historial de conversaciones para siempre.

---

### Global Block Check (Middleware de Seguridad)

```python
@bot.check
async def global_block_check(ctx):
    is_locked = await bot.admin_repo.is_channel_locked(ctx.channel.id)
    return not is_locked
```

Antes de ejecutar **cualquier comando**, se verifica si el canal está bloqueado. Si lo está, el comando se ignora silenciosamente. Algunos comandos están exentos (`unlock`, `cs`, `channelstatus`).

---

### `load_extensions(bot)` — Carga Dinámica de Cogs

```python
for filename in os.listdir(handlers_path):
    if filename.endswith(".py") and not filename.startswith("__"):
        await bot.load_extension(f"handlers.{filename[:-3]}")
```

Carga automáticamente todos los archivos `.py` en `/handlers/`. No hay que registrar los Cogs manualmente; solo crear el archivo y ya se carga al reiniciar.

---

### Bucle de Resiliencia `while True`

```python
while True:
    bot = commands.Bot(...)
    try:
        async with bot:
            await load_extensions(bot)
            await bot.start(DISCORD_TOKEN)
    except discord.HTTPException as e:
        if e.status == 429:
            await asyncio.sleep(60)  # Rate limit al inicio
    except Exception as e:
        await asyncio.sleep(10)  # Cualquier otro error
```

Si el bot se desconecta por cualquier razón, el bucle lo reinicia automáticamente en vez de caerse. Los errores 429 de Discord esperan 60 segundos; cualquier otro error espera 10 segundos.
