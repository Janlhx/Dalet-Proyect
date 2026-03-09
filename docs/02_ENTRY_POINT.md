# 🚀 Entry Point: `dalet_main.py`

> This is the **first file to be executed**. It bootstraps everything: the database, services, Discord bot, and the web server.

---

## What does this file do?

**Execution sequence when running `python dalet_main.py`:**

1. Configures the logging system (outputs to console and `dalet.log`)
2. Loads environment variables from `.env`
3. Starts a Flask server on port 8080 (in a separate thread)
4. Enters the `main()` loop which:
   - Connects to the database (asyncpg pool)
   - Instantiates all repositories and services
   - Automatically loads all Cogs from `/handlers/`
   - Connects the bot to Discord

---

## 📋 Components Explained

### Logging (`logging.basicConfig`)

```python
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),  # Display in console
        logging.FileHandler("dalet.log")    # Save to file
    ]
)
```

- Each module has its own logger: `dalet.main`, `dalet.handlers.nlp`, etc.
- This allows for module-specific filtering if needed.
- The `dalet.log` file accumulates all messages (crucial for debugging on Render).

---

### Flask Server (Health Check)

```python
app = Flask('')

@app.route('/')
def home():
    return "The bot is alive."

def keep_alive():
    t = Thread(target=run)
    t.start()
```

**Why does this exist?**  
Render (the cloud hosting provider) requires the application to respond to HTTP requests to confirm it's healthy. If it stops responding, Render restarts it. Flask runs in a **separate thread** to avoid blocking the asynchronous bot loop.

---

### `DatabasePool.get_pool()` — Database Initialization

```python
await DatabasePool.get_pool()
```

This is called **once** at startup. It creates a "pool" of 1 to 5 PostgreSQL connections shared across all repositories. This is significantly more efficient than opening/closing a new connection for every query.

---

### Instantiating Repositories and Services

```python
bot.user_repo       = UserRepository()
bot.osu_repo        = OsuRepository()
bot.admin_repo      = AdminRepository()
bot.analytics_repo  = AnalyticsRepository()

bot.nlp_service     = NLPService(GEMINI_API_KEY, user_repo=bot.user_repo)
bot.memory_service  = MemoryService(bot.user_repo)
bot.osu_service     = OsuService(client_id=..., client_secret=...)
```

All these are stored as attributes of the `bot` object, allowing any Cog to access them via `self.bot.user_repo`, `self.bot.nlp_service`, etc.

---

### Periodic Flush Task

```python
flush_task = asyncio.get_event_loop().create_task(bot.user_repo._periodic_flush())
```

Starts a background task that empties the message buffer into the database every 60 seconds.

---

### Expired Message Purge (Privacy TTL)

```python
async def _purge_expired_messages():
    while True:
        await asyncio.sleep(3600)  # Every hour
        deleted = await conn.fetchval("SELECT fn_PurgeExpiredMessages()")
```

Every hour, it clears messages older than 48 hours. This is a core privacy policy: we don't store conversational history forever.

---

### Global Block Check (Security Middleware)

```python
@bot.check
async def global_block_check(ctx):
    is_locked = await bot.admin_repo.is_channel_locked(ctx.channel.id)
    return not is_locked
```

Before executing **any command**, the bot checks if the channel is locked. If it is, the command is silently ignored. Certain utility commands (`unlock`, `cs`, `channelstatus`) are exempt.

---

### `load_extensions(bot)` — Dynamic Cog Loading

```python
for filename in os.listdir(handlers_path):
    if filename.endswith(".py") and not filename.startswith("__"):
        await bot.load_extension(f"handlers.{filename[:-3]}")
```

Automatically loads all `.py` files in `/handlers/`. There’s no need to register Cogs manually—simply creating the file makes it loadable upon restart.

---

### Resilience Loop: `while True`

```python
while True:
    bot = commands.Bot(...)
    try:
        async with bot:
            await load_extensions(bot)
            await bot.start(DISCORD_TOKEN)
    except discord.HTTPException as e:
        if e.status == 429:
            await asyncio.sleep(60)  # Waiting out a rate limit
    except Exception as e:
        await asyncio.sleep(10)  # Retrying after any other error
```

If the bot disconnects for any reason, the loop automatically restarts it rather than crashing the service. Discord 429 errors trigger a 60-second wait; other errors wait 10 seconds.
