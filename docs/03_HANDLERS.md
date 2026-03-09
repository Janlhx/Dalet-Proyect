# 🧩 Handlers (Cogs) — Command Modules

> A **Cog** is discord.py's way of organizing commands and events into separate classes. Every file in `/handlers/` is an independent Cog.

---

## Handler Overview

| File | Class | Responsibility |
| ---- | ----- | -------------- |
| `dalet_nlpchat.py` | `DaletNLPChat` | Core conversational AI engine |
| `dalet_chatlogger.py` | `ChatLogger` | Saves messages to the database |
| `dalet_admcommands_handler.py` | `AdminCommands` | Bot administration commands |
| `dalet_geminicommand.py` | `AIConfigCommands` | Proactive/Reactive mode configuration |
| `dalet_commands_handlers.py` | `CommandsHandler` | General utility commands |
| `dalet_helpcommands_handlers.py` | `CustomHelpCommand` | Paginated interactive help system |
| `dalet_events_handlers.py` | `EventsHandler` | Discord events (on_ready, errors, welcomes) |
| `dalet_osucommands.py` | _(osu commands)_ | All osu!-related commands |
| `dalet_smartresume.py` | `ResumenInteligente` | AI-powered chat summaries |

---

## 🤖 `dalet_nlpchat.py` — The Conversational Brain

**This is the most critical file in the bot.**

### What does it do?

It listens to **all** server messages and decides when Dalet should respond using AI.

### Behavioral Constants (at the top of the file)

```python
BASE_RESPONSE_RATE = 0.25       # 25% proactive response probability
COOLDOWN_TIME = 45              # Wait 45s between proactive replies
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Minimum 10 messages before replying
MAX_MESSAGES_WINDOW = 10        # Reset counter if 10 msgs pass without reply
```

### `on_message` Flow (triggered per message)

```
1. Is it a bot or DM? → Ignore
2. Starts with a command prefix (d., /, !...)? → Ignore
3. Store in local_history (immediate RAM memory)
4. Is it on error_cooldown from a recent 429? → Ignore
5. Is it "dalet test" or "dalet on"? → Fast non-AI reply
6. Contains "remember that" or "my name is"? → Save to UserMemories
7. Is the server reactive AND mentioned/called "dalet"? → generate_response()
8. Is the channel proactive AND _should_respond() is true? → generate_response()
```

### `_should_respond()` — Proactivity logic

Decides if Dalet should respond spontaneously. Returns `True` only if:

- It is not currently responding (`is_responding = False`)
- 45s have passed since the last reply
- At least 10 messages have arrived since the last reply
- A random number between 0 and 1 falls within the 25% probability range

### `generate_response()` — The response process

1. Sets `is_responding = True` (flag to prevent concurrent replies)
2. Detects images in the message (attachments, embeds, replies)
3. Cleans message content (removes mentions and the word "dalet")
4. Calls `memory_service.get_relevant_context()` → retrieves context
5. Calls `nlp_service.generate_reply()` → generates AI response
6. If reply contains `[SAVE_MEMORY: ...]` → saves memory and strips it from text
7. If reply contains `[ACTION: ...]` → executes a Discord command
8. Sends message to Discord
9. Saves response in `local_history` (so Dalet remembers what she said)
10. Logs interaction in `analytics_repo` and `user_repo`

### `_handle_429()` — Rate Limit Management

When Discord returns a 429 error (Too Many Requests), it triggers an exponential cooldown:

- Standard Error: starts at 30s, doubles with each consecutive error
- Cloudflare 1015 Error: starts at 120s (more severe blocks)

The cooldown is stored in `self.error_cooldown` (Unix timestamp). While `time.time() < error_cooldown`, the bot won't attempt to reply.

---

## 📝 `dalet_chatlogger.py` — The Message Logger

### What does it do?

Listens to **all** messages and saves them to the database asynchronously. It works in parallel with `dalet_nlpchat.py`.

### `on_message`

- Ignores bots and DMs
- Ignores messages starting with `d.` or `D.` (commands, not conversation)
- Calls `repo.log_message()` which stores in `_log_buffer` (it doesn't write to DB immediately)

### Command `d.chatlog [count]`

Shows the last N messages from the current channel (combining buffer + DB).

---

## 🛡️ `dalet_admcommands_handler.py` — Admin Commands

All require administrator permissions on the server, except `d.cs` and `d.status`.

| Command | Description |
| ------- | ----------- |
| `d.restart` | Shuts down the bot (Render auto-restarts it) |
| `d.reload <module>` | Reloads a Cog without restarting. E.g.: `d.reload handlers.dalet_nlpchat` |
| `d.sql <query>` | Executes a SELECT query in the DB directly from Discord |
| `d.lock` | Locks all commands in the current channel |
| `d.unlock` | Unlocks commands in the current channel |
| `d.cs` | Shows channel status: Locked? Proactive? Reactive? |
| `d.status` | Technical status: DB, log buffer, cache, AI provider, throttling |
| `d.dbstats` | Analytics dashboard: top commands, AI replies, recent errors |

---

## ⚙️ `dalet_geminicommand.py` — AI Configuration

### Proactive Mode (`d.proactive`)

The AI joins conversations spontaneously without being mentioned. Only works in channels specifically configured by an admin.

| Subcommand | Description |
| ---------- | ----------- |
| `d.proactive add #channel` | Enables proactive AI in that channel |
| `d.proactive remove #channel` | Disables proactive AI in that channel |
| `d.proactive list` | Lists channels with proactive AI |
| `d.proactive clear` | Disables proactive AI across all channels |
| `d.proactive debug` | Shows internal system state (counters, cooldown, probability) |

### Reactive Mode (`d.reactive`)

The AI only responds when mentioned or called "dalet". This is active by default in all servers.

| Subcommand | Description |
| ---------- | ----------- |
| `d.reactive on` | Enables replies to mentions/name |
| `d.reactive off` | Disables replies to mentions/name |
| `d.reactive status` | Shows if it's currently enabled |

---

## 🔧 `dalet_commands_handlers.py` — General Commands

| Command | Description |
| ------- | ----------- |
| `d.ms` | Displays bot latency in ms (ping) |
| `d.userinfo [@user]` | User info: ID, creation date, joindate |
| `d.serverinfo` | Server info: members, owner, creation date |
| `d.say <text>` | Dalet repeats the message |
| `d.lore <term>` | Searches past messages and generates a sarcastic AI summary |

> **`d.lore`** is one of the most creative commands: it searches the DB for messages containing the term (ILIKE), sends them to the AI with "gossipy and sarcastic" instructions, and generates a personalized summary.

---

## ❓ `dalet_helpcommands_handlers.py` — Help System

Replaces the default `d.help` with an interactive, paginated system.

### Components

- **`CustomHelpCommand`**: Automatically generates a cover page and one page per Cog
- **`HelpPaginator`**: View with 4 buttons (Back, Home, Go to..., Next). Deactivates after 3 minutes of inactivity
- **`PageInputModal`**: Popup window (Modal) that appears when clicking "Go to..." to enter a category number

### How Paging Works

1. `d.help` calls `send_bot_help()`
2. Iterates over all registered Cogs
3. Creates an Embed per Cog with its commands
4. Adds a cover page at the beginning
5. Sends the cover page with navigation buttons

---

## 📡 `dalet_events_handlers.py` — Global Events

| Event | Description |
| ----- | ----------- |
| `on_ready` | Triggers on connection. Syncs Slash commands with Discord |
| `on_command_error` | Handles global command errors (command not found, missing permissions, etc.) |
| `on_member_join` | Sends a welcome message to a hardcoded channel (ID: 790644877389201439) |
| `on_member_remove` | Sends a goodbye message to a hardcoded channel (ID: 790645132121604126) |

> ⚠️ **Note**: Welcome/Goodbye channel IDs are currently hardcoded. They should be updated if the bot is moved to a different main server.

---

## 📊 `dalet_smartresume.py` — AI Summaries

| Command | Description |
| ------- | ----------- |
| `d.resumir_hibrido [N]` | Generates an AI summary of the last N messages in the channel |
| `d.ver_resumenes_hibrido [N]` | Shows the last N generated summaries for this channel |
| `d.comparar_resumenes_hibrido <i1> <i2>` | Compares two summaries using AI |

Summaries are stored in the `Summaries` database table, allowing you to track the evolution of channel conversations over time.
