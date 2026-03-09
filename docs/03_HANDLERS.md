# 🧩 Handlers (Cogs) — Módulos de Comandos

> Un **Cog** (Cogwheel/engranaje) es la forma que tiene discord.py de organizar comandos y eventos en clases separadas. Cada archivo en `/handlers/` es un Cog independiente.

---

## Resumen de Handlers

| Archivo                          | Clase                | Responsabilidad                                     |
| -------------------------------- | -------------------- | --------------------------------------------------- |
| `dalet_nlpchat.py`               | `DaletNLPChat`       | Motor principal de IA conversacional                |
| `dalet_chatlogger.py`            | `ChatLogger`         | Guarda mensajes en la BD                            |
| `dalet_admcommands_handler.py`   | `AdminCommands`      | Comandos de administración del bot                  |
| `dalet_geminicommand.py`         | `AIConfigCommands`   | Configuración de modos proactivo/reactivo           |
| `dalet_commands_handlers.py`     | `CommandsHandler`    | Comandos generales de utilidad                      |
| `dalet_helpcommands_handlers.py` | `CustomHelpCommand`  | Sistema de ayuda interactivo paginado               |
| `dalet_events_handlers.py`       | `EventsHandler`      | Eventos de Discord (on_ready, errores, bienvenidas) |
| `dalet_osucommands.py`           | _(osu commands)_     | Todos los comandos relacionados con osu!            |
| `dalet_smartresume.py`           | `ResumenInteligente` | Resúmenes de chat con IA                            |

---

## 🤖 `dalet_nlpchat.py` — El Cerebro Conversacional

**Este es el archivo más importante del bot.**

### ¿Qué hace?

Escucha **todos** los mensajes del servidor y decide cuándo Dalet debe responder con IA.

### Constantes de Comportamiento (al inicio del archivo)

```python
BASE_RESPONSE_RATE = 0.25       # 25% de probabilidad de respuesta proactiva
COOLDOWN_TIME = 45              # Espera 45s entre respuestas proactivas
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Mínimo 10 mensajes antes de responder
MAX_MESSAGES_WINDOW = 10        # Reset de contador si pasan 10 msgs sin responder
```

### Flujo de `on_message` (cada mensaje que llega)

```
1. ¿Es un bot o DM? → Ignorar
2. ¿Empieza con prefijo de comando (d., /, !...)? → Ignorar
3. Guardar en local_history (memoria inmediata en RAM)
4. ¿Está en error_cooldown por un 429 reciente? → Ignorar
5. ¿Es "dalet test" o "dalet on"? → Respuesta rápida sin IA
6. ¿Dice "recuerda que" o "mi nombre es"? → Guardar en UserMemories
7. ¿El servidor es reactivo Y la mencionan/dicen "dalet"? → generate_response()
8. ¿El canal es proactivo Y _should_respond() dice sí? → generate_response()
```

### `_should_respond()` — El "dado" de la proactividad

Decide si Dalet responde de forma espontánea. Devolverá `True` solo si:

- No está respondiendo ya (`is_responding = False`)
- Han pasado 45s desde la última respuesta
- Han llegado al menos 10 mensajes desde la última respuesta
- Sale un número aleatorio entre 0 y 1 que cae en el 25% de probabilidad

### `generate_response()` — El proceso de respuesta

1. Pone `is_responding = True` (flag para evitar responder dos veces a la vez)
2. Detecta imágenes en el mensaje (attachments, embeds, replies)
3. Limpia el contenido del mensaje (quita menciones y la palabra "dalet")
4. Llama a `memory_service.get_relevant_context()` → obtiene el contexto
5. Llama a `nlp_service.generate_reply()` → genera la respuesta con IA
6. Si la respuesta contiene `[SAVE_MEMORY: ...]` → guarda el recuerdo y lo elimina del texto
7. Si la respuesta contiene `[ACTION: ...]` → ejecuta un comando de Discord
8. Envía el mensaje a Discord
9. Guarda la respuesta en `local_history` (para que sepa lo que dijo ella misma)
10. Loguea la interacción en `analytics_repo` y `user_repo`

### `_handle_429()` — Manejo de Rate Limits

Cuando Discord devuelve un error 429 (demasiadas peticiones), activa un cooldown exponencial:

- Error normal: empieza en 30s, se duplica con cada error consecutivo
- Error Cloudflare 1015: empieza en 120s (son bloqueos más severos)

El cooldown se guarda en `self.error_cooldown` (timestamp Unix). Mientras `time.time() < error_cooldown`, el bot no intenta responder.

---

## 📝 `dalet_chatlogger.py` — El Registrador de Mensajes

### ¿Qué hace?

Escucha **todos** los mensajes y los guarda en la base de datos de forma asíncrona. Trabaja en paralelo con `dalet_nlpchat.py`.

### `on_message`

- Ignora bots y DMs
- Ignora mensajes que empiecen con `d.` o `D.` (son comandos, no conversación)
- Llama a `repo.log_message()` que guarda en el `_log_buffer` (no escribe en la BD inmediatamente)

### Comando `d.chatlog [cantidad]`

Muestra los últimos N mensajes del canal actual (combinando buffer + BD).

---

## 🛡️ `dalet_admcommands_handler.py` — Comandos de Administración

Todos requieren permiso de administrador en el servidor, excepto `d.cs` y `d.status`.

| Comando             | Descripción                                                                 |
| ------------------- | --------------------------------------------------------------------------- |
| `d.restart`         | Cierra el bot (Render lo reinicia automáticamente)                          |
| `d.reload <modulo>` | Recarga un Cog sin reiniciar el bot. Ej: `d.reload handlers.dalet_nlpchat`  |
| `d.sql <query>`     | Ejecuta una consulta SELECT en la BD directamente desde Discord             |
| `d.lock`            | Bloquea todos los comandos en el canal actual                               |
| `d.unlock`          | Desbloquea los comandos en el canal actual                                  |
| `d.cs`              | Muestra el estado del canal: ¿bloqueado? ¿proactivo? ¿reactivo?             |
| `d.status`          | Estado técnico del bot: BD, buffer de logs, caché, proveedor IA, throttling |
| `d.dbstats`         | Panel de analíticas: top comandos, respuestas IA, errores recientes         |

---

## ⚙️ `dalet_geminicommand.py` — Configuración de IA

### Modo Proactivo (`d.proactive`)

La IA "entra sola" en conversaciones sin que la mencionen. Solo funciona en canales que el admin haya configurado.

| Subcomando                  | Descripción                                                              |
| --------------------------- | ------------------------------------------------------------------------ |
| `d.proactive add #canal`    | Activa la IA proactiva en ese canal                                      |
| `d.proactive remove #canal` | Desactiva la IA proactiva en ese canal                                   |
| `d.proactive list`          | Lista los canales con IA proactiva                                       |
| `d.proactive clear`         | Desactiva la IA proactiva en todos los canales                           |
| `d.proactive debug`         | Muestra el estado interno del sistema (contador, cooldown, probabilidad) |

### Modo Reactivo (`d.reactive`)

La IA responde cuando la mencionan o dicen "dalet". Está activo por defecto en todos los servidores.

| Subcomando          | Descripción                             |
| ------------------- | --------------------------------------- |
| `d.reactive on`     | Activa respuestas a menciones/nombre    |
| `d.reactive off`    | Desactiva respuestas a menciones/nombre |
| `d.reactive status` | Muestra si está activo o no             |

---

## 🔧 `dalet_commands_handlers.py` — Comandos Generales

| Comando                 | Descripción                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `d.ms`                  | Muestra la latencia del bot en ms (ping)                                    |
| `d.userinfo [@usuario]` | Info de un usuario: ID, fecha de creación, cuándo se unió                   |
| `d.serverinfo`          | Info del servidor: miembros, dueño, fecha de creación                       |
| `d.say <texto>`         | Dalet repite el mensaje                                                     |
| `d.lore <término>`      | Busca mensajes pasados sobre ese tema y genera un resumen sarcástico con IA |

> **`d.lore`** es uno de los comandos más creativos: busca en la BD mensajes que contengan el término (ILIKE), los manda a la IA con instrucciones de ser "cotilla y sarcástica", y genera una respuesta personalizada.

---

## ❓ `dalet_helpcommands_handlers.py` — Sistema de Ayuda

Reemplaza el `d.help` por defecto de discord.py con un sistema interactivo y paginado.

### Componentes

- **`CustomHelpCommand`**: Genera automáticamente una portada y una página por cada Cog
- **`HelpPaginator`**: Vista con 4 botones (Anterior, Inicio, Ir a..., Siguiente). Se desactiva tras 3 minutos de inactividad
- **`PageInputModal`**: Ventana emergente (Modal) que aparece al pulsar "Ir a..." y permite escribir el número de categoría

### Cómo funciona la paginación

1. `d.help` llama a `send_bot_help()`
2. Se itera sobre todos los Cogs registrados
3. Se crea un Embed por Cog con sus comandos
4. Se añade una portada al inicio
5. Se envía la portada con los botones de navegación

---

## 📡 `dalet_events_handlers.py` — Eventos Globales

| Evento             | Descripción                                                                     |
| ------------------ | ------------------------------------------------------------------------------- |
| `on_ready`         | Se ejecuta al conectar. Sincroniza los comandos de barra `/` con Discord        |
| `on_command_error` | Maneja errores globales de comandos (comando no encontrado, sin permisos, etc.) |
| `on_member_join`   | Envía bienvenida a un canal hardcodeado (ID: 790644877389201439)                |
| `on_member_remove` | Envía despedida a un canal hardcodeado (ID: 790645132121604126)                 |

> ⚠️ **Nota**: Los IDs de canales de bienvenida/despedida están hardcodeados. Si el bot se mueve a otro servidor principal, habría que cambiarlos.

---

## 📊 `dalet_smartresume.py` — Resúmenes con IA

| Comando                                  | Descripción                                                     |
| ---------------------------------------- | --------------------------------------------------------------- |
| `d.resumir_hibrido [N]`                  | Genera un resumen de los últimos N mensajes del canal usando IA |
| `d.ver_resumenes_hibrido [N]`            | Muestra los últimos N resúmenes generados para este canal       |
| `d.comparar_resumenes_hibrido <i1> <i2>` | Compara dos resúmenes usando IA                                 |

El resumen se guarda en la tabla `Summaries` de la BD para que puedas ver la evolución de las conversaciones del canal a lo largo del tiempo.
