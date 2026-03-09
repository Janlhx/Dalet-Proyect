# 🏗️ Arquitectura General de Dalet

> Este documento explica el "big picture": cómo están conectadas todas las piezas del bot y cuál es el flujo de datos cuando alguien le habla a Dalet.

---

## 🧠 ¿Qué es Dalet?

Dalet es un bot de Discord asíncrono construido sobre **discord.py**. Tiene tres grandes capacidades:

1. **IA Conversacional**: Responde mensajes usando Google Gemini (o Groq como fallback).
2. **Memoria Persistente**: Recuerda cosas sobre los usuarios y el historial del chat gracias a una base de datos PostgreSQL en Neon.
3. **Integración con osu!**: Puede consultar estadísticas del juego osu! usando su API oficial.

---

## ⚙️ Tecnologías Usadas

| Tecnología            | Para qué se usa                                                            |
| --------------------- | -------------------------------------------------------------------------- |
| **Python 3.x**        | Lenguaje principal                                                         |
| **discord.py**        | Librería para interactuar con la API de Discord                            |
| **asyncpg**           | Driver asíncrono para PostgreSQL (mucho más rápido que psycopg2 para bots) |
| **PostgreSQL (Neon)** | Base de datos en la nube. Neon tiene un plan gratis con "pausa" automática |
| **Google Gemini API** | Modelo de IA principal (Gemini 2.0 Flash)                                  |
| **Groq API**          | Modelo de IA de respaldo (Llama 3.3 70B)                                   |
| **Flask**             | Servidor HTTP mínimo para el Health Check de Render                        |
| **Render**            | Plataforma donde se despliega el bot en la nube                            |

---

## 🔄 Flujo Principal: "¿Qué pasa cuando alguien menciona a Dalet?"

```
Usuario escribe "@Dalet hola"
          │
          ▼
[Discord API] ─── evento on_message ──► [dalet_nlpchat.py]
                                              │
                                    ┌─────────┴────────────┐
                                    │  ¿Está en cooldown?   │
                                    │  ¿La mencionan?       │
                                    └─────────┬────────────┘
                                              │ Sí → Generar respuesta
                                              ▼
                                    [memory_service.py]
                                    get_relevant_context()
                                    ┌────────────────────────────────┐
                                    │ 1. Buffer logs en memoria        │
                                    │ 2. Logs en proceso de flush      │
                                    │ 3. BD (V_ChannelMessages)        │
                                    │ 4. local_history del Cog         │
                                    │ 5. Memorias del usuario          │
                                    └──────────────┬─────────────────┘
                                                   │ context string
                                                   ▼
                                         [nlp_service.py]
                                         generate_reply()
                                         ┌──────────────────────────┐
                                         │  ¿Gemini disponible?      │
                                         │  → Llama Gemini 2.0 Flash │
                                         │  ¿Error de cuota?         │
                                         │  → Fallback a Groq        │
                                         └──────────┬───────────────┘
                                                    │ texto de respuesta
                                                    ▼
                                         [dalet_nlpchat.py]
                                         ┌───────────────────────────┐
                                         │ ¿Contiene [SAVE_MEMORY:]?  │
                                         │ → Guardar en UserMemories  │
                                         │ ¿Contiene [ACTION:]?       │
                                         │ → Ejecutar comando         │
                                         └──────────┬────────────────┘
                                                    │
                                                    ▼
                                         message.channel.send(reply)
                                         [Discord API] → Usuario
```

---

## 🗄️ Flujo de Guardado de Mensajes (Batch Logging)

Para no sobrecargar la base de datos de Neon con una consulta por cada mensaje, se usa un sistema de **buffer + flush**:

```
Usuario envía mensaje
        │
        ▼
[dalet_chatlogger.py] on_message
        │
        ▼
user_repo.log_message()
        │
        ▼
[_log_buffer] ← El mensaje se guarda en RAM primero
        │
        ├── ¿Buffer lleno (≥20 msgs)? → flush_logs() inmediato
        │
        └── [_periodic_flush] (cada 60s) → flush_logs() programado
                │
                ▼
        sp_LogMessage() × N llamadas en UNA transacción → Neon DB
```

> **¿Por qué esto importa para la IA?**  
> Mientras los mensajes están en el buffer (antes del flush), NO están en la BD. Por eso `get_channel_messages()` combina el buffer, el estado de flushing Y la BD para dar siempre el contexto completo.

---

## 🧩 Patrón de Diseño: Cogs

discord.py usa el concepto de **Cog** (engranaje). Un Cog es simplemente una clase Python que agrupa comandos y eventos relacionados. Dalet carga todos los Cogs automáticamente desde la carpeta `/handlers/` al arrancar.

Ventajas:

- Se puede **recargar un Cog solo** (`d.reload handlers.dalet_nlpchat`) sin reiniciar el bot completo.
- El código está organizado por responsabilidad.

---

## 🗺️ Patrón de Diseño: Repository

La capa de base de datos sigue el **patrón Repository**:

```
Handlers/Services              Repository               Base de Datos
─────────────────             ────────────             ──────────────
bot.user_repo           →    UserRepository      →    asyncpg + Neon
bot.admin_repo          →    AdminRepository     →    asyncpg + Neon
bot.osu_repo            →    OsuRepository       →    asyncpg + Neon
bot.analytics_repo      →    AnalyticsRepository →    asyncpg + Neon
                              ↑ todos heredan de ↑
                              BaseRepository
```

Ventajas:

- El código de los handlers **no sabe nada de SQL**. Solo llama métodos como `repo.get_channel_messages()`.
- Si cambias la base de datos, solo cambias el repositorio.

---

## 🔁 Resiliencia y Fallbacks

| Problema                       | Solución implementada                                      |
| ------------------------------ | ---------------------------------------------------------- |
| Gemini sin cuota               | Groq como fallback automático                              |
| Groq sin cuota                 | Groq Fallback (modelo más pequeño: llama-3.1-8b)           |
| Neon BD dormida/lenta          | `local_history` en RAM como fallback de contexto           |
| Discord Rate Limit 429         | Cooldown exponencial (`error_cooldown`) en `dalet_nlpchat` |
| Bot crashea en Render          | Bucle infinito `while True` en `main()` que lo reinicia    |
| Mensajes no guardados (buffer) | `_flushing_logs` para no perder mensajes durante el flush  |
