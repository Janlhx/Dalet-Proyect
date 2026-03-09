# 🧠 Servicios — La IA y la Memoria

> Los servicios contienen la **lógica de negocio** más compleja del bot. No saben nada de Discord directamente; reciben datos y retornan resultados.

---

## 🗂️ Archivos

| Archivo                      | Clase           | Responsabilidad                                       |
| ---------------------------- | --------------- | ----------------------------------------------------- |
| `services/nlp_service.py`    | `NLPService`    | Genera respuestas de texto con Gemini o Groq          |
| `services/memory_service.py` | `MemoryService` | Construye el contexto para la IA y gestiona recuerdos |
| `services/osu_service.py`    | `OsuService`    | Consulta la API de osu!                               |

---

## 🤖 `nlp_service.py` — Generador de Respuestas

### ¿Qué hace?

Toma el mensaje del usuario + el contexto de la conversación + la personalidad de Dalet y genera una respuesta de texto usando un modelo de IA.

### Proveedores de IA

El proveedor se configura con la variable de entorno `AI_PROVIDER`:

| Proveedor                      | Variable             | Modelo por defecto                                              |
| ------------------------------ | -------------------- | --------------------------------------------------------------- |
| **Gemini** (principal)         | `AI_PROVIDER=gemini` | `gemini-2.0-flash` (configurable con `GEMINI_MODEL`)            |
| **Groq** (alternativa)         | `AI_PROVIDER=groq`   | `llama-3.3-70b-versatile` (configurable con `GROQ_MODEL`)       |
| **Groq Fallback** (automático) | —                    | `llama-3.1-8b-instant` (configurable con `GROQ_MODEL_FALLBACK`) |

### Cadena de Fallback

```
Intento con Gemini
│
├─ Éxito → retornar respuesta
│
└─ ¿Error (cuota, red)? → Intentar Groq (70B)
              │
              ├─ Éxito → retornar respuesta
              │
              └─ ¿Error 429 de Groq? → Intentar Groq Fallback (8B)
                            │
                            ├─ Éxito → retornar respuesta
                            │
                            └─ Error → retornar mensaje de disculpa hardcodeado
```

### La Personalidad de Dalet

Se define como un string en `self.personality` que se envía como **system instruction** al modelo.

**Reglas clave de la personalidad:**

| Regla                    | Qué hace                                                               |
| ------------------------ | ---------------------------------------------------------------------- |
| IDENTIDAD                | Dalet es mujer, usa lenguaje natural y acorde a su identidad           |
| TONO "BANTER"            | Sarcástica e irónica, pero por confianza, nunca grosera                |
| BREVEDAD                 | Respuestas de 1-2 frases. Solo se alarga si el tema lo requiere        |
| SIN PREGUNTAS            | No hace preguntas de relleno innecesarias                              |
| SIN EMOJIS               | Prohibido usar emojis                                                  |
| COHERENCIA SIN REPROCHES | Mantiene coherencia con el historial pero no dice "ya te lo dije"      |
| PRIORIDAD VISUAL         | Si hay una imagen, esa es la realidad. Ignora memorias contradictorias |

### Tags Especiales en las Respuestas

La IA puede incluir tags especiales que el bot procesa antes de enviar:

| Tag                              | Propósito                           | Ejemplo                                                 |
| -------------------------------- | ----------------------------------- | ------------------------------------------------------- |
| `[SAVE_MEMORY: texto]`           | Guarda un recuerdo sobre el usuario | `[SAVE_MEMORY: su nombre es Carlos]`                    |
| `[ACTION: nombre, param: valor]` | Ejecuta un comando de Discord       | `[ACTION: ping]` o `[ACTION: osu_analyze, user: Litxe]` |

### `generate_reply(trigger, context, username, image_urls)`

Método principal. Llama a `_get_images_description()` si hay imágenes, luego delega a Gemini o Groq.

### `_generate_gemini_reply()`

Construye el prompt en formato:

```
Conversación reciente:
{context}
[IMAGEN DETECTADA: {descripción}]  ← solo si hay imagen

Nuevo mensaje de {username}: "{trigger}"
```

Usa el **Google Search tool** activado en la config de Gemini para que pueda buscar información actualizada.

### `_generate_groq_reply()`

Usa la API de Groq con el formato de mensajes `[system, user]` estándar de OpenAI. Hace una petición HTTP pura con `httpx`.

### `_get_images_description(image_urls)`

Para cada imagen (máximo 2), descarga el contenido binario y lo manda a Gemini Vision para obtener una descripción concisa. La descripción se inyecta en el prompt principal.

---

## 💾 `memory_service.py` — El Sistema de Memoria

### ¿Qué hace?

Recopila todo el contexto que Dalet necesita para dar una respuesta coherente: el historial reciente del chat y los recuerdos personales del usuario.

### `get_relevant_context(channel_id, user_id, current_message)`

**El método más crítico del sistema.** Retorna un string con todo el contexto para la IA.

#### Parte 1: Historial del Chat

```python
db_history = await self.repo.get_channel_messages(channel_id, 20)
```

Obtiene hasta 20 mensajes combinando:

1. **Buffer de logs pendientes** (`_log_buffer` del repositorio)
2. **Logs en proceso de flush** (`_flushing_logs`)
3. **Base de datos** (mensajes ya persistidos)

Luego complementa con `local_history` (caché en RAM del Cog de NLP) para incluir mensajes ultra-recientes que quizás el `ChatLogger` no haya procesado aún.

El resultado final se limita a los últimos 20 mensajes en orden cronológico.

#### Parte 2: Memorias del Usuario (Embeddings)

```python
memories_raw = await self.repo.get_all_user_memories(user_id)
```

Obtiene todos los recuerdos guardados del usuario. Luego:

1. Crea embeddings vectoriales del mensaje actual Y de cada recuerdo usando `gemini-embedding-001`
2. Calcula la **similitud coseno** entre el mensaje actual y cada recuerdo
3. Solo incluye recuerdos con similitud ≥ 0.70 (muy relevantes)

Esto evita incluir recuerdos irrelevantes que confundirían a la IA.

#### Contexto Final

```
DATOS RELEVANTES (MEMORIA):
- su nombre es Carlos
- juega osu! en modo Standard

HISTORIAL RECIENTE DEL CHAT:
Carlos: hola cómo estás
usuario2: bien y tú
Carlos: bien jugando osu!
...
```

### `_calculate_similarity(vec_a, vec_b)`

Calcula la **similitud coseno** entre dos vectores. Valores:

- `1.0` = idénticos
- `0.70+` = muy relacionados (umbral usado)
- `0.0` = sin relación

### `add_memory(user_id, user_name, content, topic)`

Guarda un recuerdo en la tabla `UserMemories`. Se activa de dos formas:

1. El usuario escribe "recuerda que..." o "mi nombre es..."
2. La IA incluye `[SAVE_MEMORY: ...]` en su respuesta

### `add_to_local_history(channel_id, username, content)`

Guarda el mensaje en un `deque` en RAM (máximo 20 mensajes). Es el "caché caliente" de contexto.

**¿Por qué existe aparte de la BD?**  
Porque el `ChatLogger` guarda los mensajes en un buffer de 60 segundos antes de ir a la BD. Sin `local_history`, esos mensajes recientes no existirían para la IA.

---

## 🎮 `osu_service.py` — Integración con osu!

### ¿Qué hace?

Gestiona el token de autenticación OAuth2 con la API de osu! y hace las consultas necesarias para los comandos de osu!.

### Autenticación

La API de osu! usa OAuth2 con Client Credentials (sin usuario, solo app-to-app). El token expira cada cierto tiempo, y `OsuService` lo renueva automáticamente cuando es necesario.

Variables requeridas en `.env`:

- `OSU_CLIENT_ID`
- `OSU_CLIENT_SECRET`

### Métodos Principales

| Método                                        | Descripción                                   |
| --------------------------------------------- | --------------------------------------------- |
| `get_user(username, mode)`                    | Obtiene el perfil completo de un jugador      |
| `get_user_scores(user_id, type, mode, limit)` | Obtiene los mejores scores o scores recientes |
| `get_beatmap(beatmap_id)`                     | Obtiene info de un mapa específico            |
