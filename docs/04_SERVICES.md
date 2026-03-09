# 🧠 Services — AI & Memory

> Services contain the bot's most complex **business logic**. They are largely decoupled from Discord; they receive input data and return processed results.

---

## 🗂️ Files

| File | Class | Responsibility |
| ---- | ----- | -------------- |
| `services/nlp_service.py` | `NLPService` | Generates AI text responses via Gemini or Groq |
| `services/memory_service.py` | `MemoryService` | Builds AI context and manages persistent memories |
| `services/osu_service.py` | `OsuService` | Queries the official osu! API |

---

## 🤖 `nlp_service.py` — Response Generator

### What does it do?

It takes the user's message + conversation context + Dalet's personality profile and generates a natural language response using an AI model.

### AI Providers

The provider is configured via the `AI_PROVIDER` environment variable:

| Provider | Variable | Default Model |
| -------- | -------- | ------------- |
| **Gemini** (Primary) | `AI_PROVIDER=gemini` | `gemini-2.0-flash` (configurable via `GEMINI_MODEL`) |
| **Groq** (Alternative) | `AI_PROVIDER=groq` | `llama-3.3-70b-versatile` (via `GROQ_MODEL`) |
| **Groq Fallback** (Auto) | — | `llama-3.1-8b-instant` (via `GROQ_MODEL_FALLBACK`) |

### Fallback Chain

```
Try Gemini
│
├─ Success → Return response
│
└─ Error (Quota/Network)? → Try Groq (70B)
              │
              ├─ Success → Return response
              │
              └─ Groq 429 Error? → Try Groq Fallback (8B)
                            │
                            ├─ Success → Return response
                            │
                            └─ Error → Return hardcoded apology message
```

### Dalet's Personality

Defined as a string in `self.personality` and sent as a **system instruction** to the model.

**Key Personality Rules:**

| Rule | Description |
| ---- | ----------- |
| IDENTITY | Dalet is female, uses natural language consistent with her persona. |
| BANTER TONE | Sarcastic and ironic, rooted in familiarity, but never truly rude. |
| BREVITY | Responses should be 1-2 sentences. Only longer if the topic requires it. |
| NO FILLER | Avoids unnecessary polite filler questions. |
| NO EMOJIS | Forbidden from using emojis. |
| CONSISTENCY | Maintains context without saying "I already told you." |
| VISION PRIORITY | If an image is provided, that is the ground truth. Ignore conflicting memories. |

### Special Response Tags

The AI can include special tags which the bot processes before sending the final message:

| Tag | Purpose | Example |
| --- | ------- | ------- |
| `[SAVE_MEMORY: text]` | Saves a fact about the user | `[SAVE_MEMORY: his name is Carlos]` |
| `[ACTION: name, param: val]` | Triggers a Discord command | `[ACTION: ping]` or `[ACTION: osu_analyze, user: Litxe]` |

---

## 💾 `memory_service.py` — Memory System

### What does it do?

Compiles all the context Dalet needs for a coherent response: recent chat history and personal user memories.

### `get_relevant_context(channel_id, user_id, current_message)`

**The most critical method in the system.** Returns a string containing the full context for the AI.

#### Phase 1: Chat History

```python
db_history = await self.repo.get_channel_messages(channel_id, 20)
```

Retrieves up to 20 messages by combining:

1. **Pending log buffer** (`_log_buffer` in the repository)
2. **Currently flushing logs** (`_flushing_logs`)
3. **Database logs** (already persisted messages)

It then supplements this with `local_history` (Cog-level RAM cache) to include ultra-recent messages that the `ChatLogger` might not have processed yet.

#### Phase 2: User Memories (Semantic Search)

```python
memories_raw = await self.repo.get_all_user_memories(user_id)
```

Fetches all saved memories for the user. Then:

1. Creates vector embeddings for the current message AND each memory using `gemini-embedding-001`.
2. Calculates **cosine similarity** between the message and each memory.
3. Only includes memories with similarity ≥ 0.70 (high relevance).

This prevents irrelevant memories from confusing the AI.

---

## 🎮 `osu_service.py` — osu! Integration

### What does it do?

Manages the OAuth2 authentication token for the osu! API and handles data requests for osu! commands.

### Authentication

The osu! API uses OAuth2 with Client Credentials. Tokens expire periodically, and `OsuService` automatically renews them as needed.

Required `.env` variables:

- `OSU_CLIENT_ID`
- `OSU_CLIENT_SECRET`

### Core Methods

| Method | Description |
| ------ | ----------- |
| `get_user(username, mode)` | Fetches a full player profile |
| `get_user_scores(user_id, type, mode, limit)` | Fetches top or recent scores |
| `get_beatmap(beatmap_id)` | Fetches specific beatmap metadata |
