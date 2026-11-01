import logging
import os
import re
import json
import time
import asyncio
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger("dalet.services.memory")

_MEMORY_ANALYSIS_PROMPT = """Eres el motor de Pirámide Semántica Cognitiva (L0 -> L1 -> L2 -> L3) de Dalet (un bot de Discord con personalidad humana, sarcástica pero leal y empática).
Tu tarea es observar la conversación actual (L0) de {user_name} con Dalet y destilarla en las 3 capas superiores de memoria si aporta valor real:

[ESTADO ACTUAL DE MEMORIA DEL USUARIO]:
- L3 (Perfil Persona duradero actual): "{current_persona_l3}"
- L2 (Escenario/Contexto activo actual): "{current_scenario_l2}"

[INTERACCIÓN RECIENTE (L0)]:
Usuario ({user_name}): "{user_message}"
Respuesta de Dalet: "{dalet_reply}"

Pregunta: ¿Este mensaje revela algún dato duradero, preferencia, rasgo de personalidad, anécdota, proyecto actual, estado emocional o dinámica de relación sobre {user_name} que Dalet deba recordar o evolucionar?
Descarta:
- Saludos simples ("hola", "buenas", "que tal").
- Bromas casuales efímeras sin sustancia personal.
- Consultas puntuales externas efímeras ("a cómo está el dólar", "qué hora es") a menos que revelen un interés o contexto personal del usuario.
- Respuestas triviales ("ok", "si", "no", "jaja", "xd").

Responde ÚNICAMENTE con un objeto JSON en crudo:
Si NO vale la pena recordar ni actualizar la pirámide:
{{"save": false}}

Si SÍ vale la pena recordar y evolucionar la pirámide:
{{
  "save": true,
  "topic": "gustos" | "personal" | "humor" | "emocional" | "interaccion" | "general",
  "user_message": "cita o resumen breve de lo que dijo el usuario",
  "dalet_thought": "L1 (Átomo): Hecho concreto o conclusión puntual de esta interacción en 1-2 frases concisas.",
  "scenario_l2": "L2 (Escenario Actual): Síntesis actualizada de en qué anda el usuario últimamente, sus proyectos actuales, estado de ánimo reciente o temas recurrentes (fusiona lo nuevo con el L2 anterior en máx 2 frases).",
  "persona_l3": "L3 (Perfil Persona): Retrato psicológico e identidad estable del usuario (quién es, qué estudia/trabaja, gustos base y cómo se lleva con Dalet, evolucionando el L3 anterior en máx 2-3 frases densas)."
}}
"""

_MEMORY_STOPWORDS = {
    # Español
    "que", "con", "por", "para", "una", "uno", "unos", "unas", "los", "las", "del",
    "como", "cómo", "pero", "este", "esta", "esto", "estos", "estas", "eso", "esa",
    "esos", "esas", "aquel", "mas", "más", "muy", "sin", "sobre", "entre", "hasta",
    "desde", "cuando", "cuándo", "donde", "dónde", "quien", "quién", "cual", "cuál",
    "todo", "toda", "todos", "todas", "hacer", "hace", "hizo", "tiene", "tengo",
    "tienes", "estoy", "está", "estas", "estás", "estaban", "eres", "soy", "somos",
    "fue", "fueron", "son", "era", "eran", "hay", "algo", "nada", "poco", "mucho",
    "muchos", "muchas", "tambien", "también", "solo", "sólo", "mejor", "peor",
    "creo", "dice", "dijo", "decir", "puede", "puedo", "puedes", "quiero", "quieres",
    "siento", "parece", "porque", "porqué", "pues", "entonces", "ahora", "antes",
    "despues", "después", "siempre", "nunca", "cada", "otro", "otra", "otros",
    "otras", "mismo", "misma", "tanto", "tanta", "algun", "algún", "alguna",
    "alguien", "nadie", "hola", "buenas", "buenos", "dias", "días", "noches",
    "tardes", "gracias", "favor", "dalet", "bot", "server", "servidor", "canal",
    "chat", "mensaje", "usuario", "cosa", "cosas", "vez", "veces", "bien", "mal",
    "ver", "ves", "mira", "oye", "sabes", "sabe", "mis", "tus", "sus", "nos", "les",
    # Inglés
    "the", "and", "for", "that", "this", "with", "from", "your", "have", "has",
    "had", "are", "was", "were", "been", "what", "when", "where", "which", "who",
    "whom", "whose", "why", "how", "about", "into", "over", "after", "before",
    "between", "under", "again", "further", "then", "once", "here", "there",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "than", "too", "very", "can", "will", "just", "should",
    "now", "like", "know", "think", "want", "need", "make", "made", "take",
}

_EXPLICIT_SELF_MEMORY_TRIGGERS = (
    "recuerdas", "te acuerdas", "qué sabes de mí", "que sabes de mi",
    "me conoces", "quién soy", "quien soy", "mi memoria", "sobre mí", "sobre mi",
    "remember me", "what do you know about me", "who am i",
)


def _extract_meaningful_words(text: str) -> set[str]:
    """Extrae palabras con carga semántica real filtrando stopwords y términos cortos."""
    if not text:
        return set()
    raw_words = re.findall(r"[a-záéíóúüñ]{3,}", text.lower())
    return {w for w in raw_words if w not in _MEMORY_STOPWORDS and len(w) >= 3}


def _parse_timestamp_age(ts_str: str) -> tuple[float | None, str]:
    """
    Calcula la antigüedad en días y una etiqueta legible (ej. 'hace 3 días', 'hace 2 meses')
    a partir de un timestamp ISO o SQLite ('YYYY-MM-DD HH:MM:SS').
    """
    if not ts_str or not str(ts_str).strip():
        return None, ""
    try:
        clean = str(ts_str).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_days = max(0.0, (now - dt).total_seconds() / 86400.0)
        if delta_days < 1.0:
            return delta_days, "hoy"
        if delta_days < 2.0:
            return delta_days, "ayer"
        if delta_days < 14.0:
            return delta_days, f"hace {int(delta_days)} días"
        if delta_days < 60.0:
            weeks = max(2, int(delta_days // 7))
            return delta_days, f"hace {weeks} semanas"
        months = max(2, int(delta_days // 30))
        return delta_days, f"hace {months} meses"
    except Exception:
        return None, ""


class MemoryService:
    """
    Servicio de memoria cognitiva para Dalet basado en Pirámide Semántica (L0 -> L1 -> L2 -> L3).
    - L3 (Persona): Identidad estable, rasgos base y relación con Dalet.
    - L2 (Scenario): Contexto activo, proyectos actuales y estado reciente (caduca tras 14 días).
    - L1 (Atom): Hechos puntuales y conclusiones granulares en UserMemories (solo por relevancia estricta).
    - L0 (Conversation): Historial reciente de mensajes del canal.
    """

    SCENARIO_L2_MAX_AGE_DAYS = 14.0  # L2 deja de inyectarse como 'actual' si lleva >14 días sin cambios
    ATOM_L1_MAX_AGE_DAYS = 60.0      # Átomos L1 >60 días requieren coincidencia fuerte (>=2 palabras clave)
    MEMORY_INJECTION_COOLDOWN_SEC = 600.0  # 10 min entre inyecciones pasivas de L3/L2 al mismo usuario

    def __init__(self, user_repo):
        self.repo = user_repo
        self.max_db_history = 10  # Ventana optimizada de mensajes (L0)
        self.max_atoms_per_user = 20  # Tope de átomos L1 por usuario tras consolidar en L2/L3
        self._user_memory_cooldown: dict[int, float] = {}  # {user_id: last_analysis_timestamp}
        self._memory_injection_cooldown: dict[int, float] = {}  # {user_id: last_context_injection_ts}

    async def get_relevant_context(
        self,
        channel_id: int,
        user_id: int,
        current_message: str,
        check_user_memory: bool = True,
        bot_id: int = None,
        bot_name: str = "Dalet",
        user_name: str = "Usuario",
    ) -> str:
        """
        Construye el contexto de conversación Top-Down usando la Pirámide Semántica:
        1. L3 (Persona) + L2 (Escenario Actual vigente) desde UserPersonas, sujeto a cooldown anti-repetición
        2. L1 (Átomos relevantes) desde UserMemories (SOLO si hay coincidencia semántica real con el mensaje actual)
        3. L0 (Chat reciente del canal)
        """
        history_section = []

        # Ajustar límite de mensajes según longitud del mensaje actual (mínimo 6 para no perder contexto)
        msg_len = len(current_message.split())
        history_limit = 6 if msg_len <= 3 else self.max_db_history

        # 1. Capa L0: Historial Unificado del Canal
        try:
            db_history = await self.repo.get_channel_messages(channel_id, history_limit)
            if db_history:
                for record in reversed(db_history):
                    rec_uid = record.get('user_id') or record.get('UserID')
                    usr = record.get('username') or record.get('UserName') or 'Desconocido'
                    cnt = record.get('content') or record.get('Content') or ''
                    if not cnt.strip():
                        continue

                    is_bot = False
                    if bot_id and rec_uid == bot_id:
                        is_bot = True
                    elif usr.lower() in ("dalet", (bot_name or "").lower()):
                        is_bot = True

                    author_tag = f"Tú ({bot_name})" if is_bot else usr
                    history_section.append(f"{author_tag}: {cnt}")
        except Exception as e:
            logger.error(f"Error obteniendo historial L0: {e}")

        # 2. Capas L3 (Persona), L2 (Escenario) y L1 (Átomos) sobre el usuario
        pyramid_lines = []
        if check_user_memory:
            now = time.time()
            lower_current = (current_message or "").lower()
            explicit_self_query = any(trig in lower_current for trig in _EXPLICIT_SELF_MEMORY_TRIGGERS)
            last_injected = self._memory_injection_cooldown.get(user_id, 0.0)
            in_cooldown = (now - last_injected) < self.MEMORY_INJECTION_COOLDOWN_SEC and not explicit_self_query

            # 2a. Consultar L1 primero para saber si el usuario tocó un tema específico de su memoria
            matched_l1 = []
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    msg_words = _extract_meaningful_words(current_message)

                    def _extract(row):
                        if hasattr(row, "get"):
                            return (
                                row.get("user_message") or row.get("UserMessage") or "",
                                row.get("dalet_thought") or row.get("DaletThought") or "",
                                row.get("content") or row.get("Content") or "",
                                row.get("topic") or row.get("Topic") or "general",
                                row.get("timestamp") or row.get("Timestamp") or "",
                            )
                        try:
                            return (
                                row["user_message"],
                                row["dalet_thought"],
                                row["content"],
                                row.get("topic", "general"),
                                row.get("timestamp", ""),
                            )
                        except Exception:
                            u = row[2] if len(row) > 2 else ""
                            d = row[3] if len(row) > 3 else ""
                            c = row[1] if len(row) > 1 else str(row)
                            t = row[0] if len(row) > 0 else "general"
                            ts = row[4] if len(row) > 4 else ""
                            return (u or "", d or "", c or "", t or "general", ts or "")

                    for m in memories_raw:
                        u_msg, d_th, cnt, topic, ts_val = _extract(m)
                        search_text = f"{u_msg} {d_th} {cnt}"
                        mem_words = _extract_meaningful_words(search_text)
                        overlap = mem_words & msg_words

                        # Si no hay overlap semántico real (y no pidió explícitamente su memoria), NO inyectar
                        if not overlap and not explicit_self_query:
                            continue

                        age_days, age_label = _parse_timestamp_age(ts_val)
                        # Si el recuerdo tiene más de 60 días, exigir al menos 2 palabras clave en común
                        if age_days is not None and age_days > self.ATOM_L1_MAX_AGE_DAYS and len(overlap) < 2 and not explicit_self_query:
                            continue

                        age_tag = f" [{age_label}]" if age_label else ""
                        line = ""
                        if d_th:
                            line = f"• [L1 - Átomo ({topic}){age_tag}]: {d_th}"
                            if u_msg:
                                line += f' (Dijo: "{u_msg[:100]}")'
                        elif cnt:
                            line = f"• [L1 - Dato ({topic}){age_tag}]: {cnt}"

                        if line:
                            matched_l1.append((len(overlap), line))

                    # Ordenar por mayor número de palabras clave en común y tomar máx 2
                    matched_l1.sort(key=lambda item: item[0], reverse=True)
            except Exception as e:
                logger.error(f"Error obteniendo recuerdos L1 de usuario: {e}")

            # 2b. Consultar L3 y L2 (UserPersonas) solo si no está en cooldown o si hay match temático L1 / consulta explícita
            if not in_cooldown or matched_l1 or explicit_self_query:
                try:
                    if hasattr(self.repo, "get_user_persona"):
                        persona_data = await self.repo.get_user_persona(user_id)
                        if persona_data:
                            p_l3 = (persona_data.get("persona_l3") or "").strip()
                            s_l2 = (persona_data.get("scenario_l2") or "").strip()
                            updated_at = persona_data.get("updated_at") or ""
                            age_days, age_label = _parse_timestamp_age(updated_at)

                            if p_l3:
                                pyramid_lines.append(f"• [L3 - Perfil Persona]: {p_l3}")
                            # Solo inyectar L2 si sigue vigente (<= 14 días) o no tiene timestamp antiguo
                            if s_l2 and (age_days is None or age_days <= self.SCENARIO_L2_MAX_AGE_DAYS):
                                l2_tag = f" ({age_label})" if age_label else ""
                                pyramid_lines.append(f"• [L2 - Escenario Actual{l2_tag}]: {s_l2}")
                except Exception as e:
                    logger.error(f"Error obteniendo UserPersona (L2/L3): {e}")

                for _, l1_line in matched_l1[:2]:
                    pyramid_lines.append(l1_line)

                if pyramid_lines:
                    self._memory_injection_cooldown[user_id] = now

        # Construir contexto final con directiva estricta anti-repetición
        final_parts = []
        if pyramid_lines:
            header = f"[PIRÁMIDE SEMÁNTICA DE {user_name.upper()} (L3 -> L1)]:\n" + "\n".join(pyramid_lines)
            instruction = (
                "[DIRECTIVA DE MEMORIA PASIVA — ANTI-REPETICIÓN]:\n"
                f"Esta es tu memoria interna sobre {user_name}. Es SOLO contexto silencioso de fondo.\n"
                "- PROHIBIDO sacar a colación gustos, estudios, proyectos o anécdotas de esta lista si el usuario está hablando de otra cosa.\n"
                "- NO repitas chistes ni referencias a recuerdos viejos que no vengan al caso con el mensaje actual.\n"
                "- Enfócate en responder directamente a lo que dice AHORA y al CHAT RECIENTE (L0)."
            )
            final_parts.append(f"{header}\n\n{instruction}")

        if history_section:
            final_parts.append("CHAT RECIENTE (L0):\n" + "\n".join(history_section))

        return "\n\n".join(final_parts) if final_parts else "Sin historial previo."

    async def add_memory(
        self,
        user_id: int,
        user_name: str,
        content: str,
        topic: str = "general",
        user_message: str | None = None,
        dalet_thought: str | None = None,
    ):
        """Guarda un recuerdo atómico (L1) sobre el usuario en la BD."""
        return await self.repo.add_user_memory(
            user_id=user_id,
            user_name=user_name,
            content=content,
            topic=topic,
            user_message=user_message,
            dalet_thought=dalet_thought,
        )

    async def analyze_and_record_memory(
        self,
        user_id: int,
        user_name: str,
        user_message: str,
        dalet_reply: str,
        nlp_service,
    ):
        """
        Destilación Single-Pass en background (L0 -> L1 + L2 + L3):
        1. Recupera L3 (Persona) y L2 (Escenario) actuales del usuario.
        2. Analiza con Gemini si el mensaje aporta información significativa.
        3. Guarda el nuevo átomo L1, evoluciona L2 y L3 en UserPersonas y poda átomos L1 antiguos (>20).
        """
        if not user_message or not dalet_reply or not nlp_service:
            return

        clean_msg = user_message.strip()
        # Filtros rápidos heurísticos (0 costo de tokens para mensajes triviales)
        words = clean_msg.split()
        if len(words) < 4 or len(clean_msg) < 15:
            return

        lower_msg = clean_msg.lower()
        trivial_phrases = (
            "hola", "buenos dias", "buenas noches", "buenas tardes", "adios", "chao",
            "jaja", "jajaja", "xd", "ok", "vale", "dale", "que tal", "como estas",
            "dalet on", "estoy on", "gracias"
        )
        if any(lower_msg == t for t in trivial_phrases):
            return

        # Cooldown por usuario: máx 1 análisis de memoria cada 30 segundos por usuario
        now = time.time()
        last_time = self._user_memory_cooldown.get(user_id, 0.0)
        if (now - last_time) < 30.0:
            return

        self._user_memory_cooldown[user_id] = now

        # Ejecutar análisis cognitivo con Gemini
        try:
            api_key = (getattr(nlp_service, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY") or "").strip()
            if not api_key:
                return

            # Obtener L3 y L2 actuales para que evolucionen incrementalmente
            current_l3 = "Sin perfil previo registrado."
            current_l2 = "Sin escenario activo registrado."
            if hasattr(self.repo, "get_user_persona"):
                existing_persona = await self.repo.get_user_persona(user_id)
                if existing_persona:
                    current_l3 = existing_persona.get("persona_l3") or current_l3
                    current_l2 = existing_persona.get("scenario_l2") or current_l2

            raw_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
            model_name = "gemini-3.8-flash" if "flash" in raw_model else raw_model

            prompt = _MEMORY_ANALYSIS_PROMPT.format(
                user_name=user_name,
                current_persona_l3=current_l3[:500],
                current_scenario_l2=current_l2[:400],
                user_message=clean_msg[:300],
                dalet_reply=dalet_reply[:300],
            )

            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            }

            http_client = getattr(nlp_service, "_http_client", None)
            close_client = False
            if not http_client:
                import httpx
                http_client = httpx.AsyncClient(timeout=10.0)
                close_client = True

            try:
                resp = await http_client.post(gemini_url, json=payload, timeout=8.0)
                if resp.status_code != 200:
                    logger.debug(f"[MEMORY] API status {resp.status_code} en análisis de recuerdos")
                    return

                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                result = json.loads(text)

                thought = (
                    result.get("dalet_thought")
                    or result.get("atom_l1")
                    or result.get("thought")
                    or ""
                ).strip()

                if result.get("save") and thought:
                    usr_quote = result.get("user_message", clean_msg[:120])
                    topic = result.get("topic", "general")
                    new_l2 = (result.get("scenario_l2") or "").strip()
                    new_l3 = (result.get("persona_l3") or "").strip()

                    # 1. Guardar nuevo Átomo L1
                    await self.add_memory(
                        user_id=user_id,
                        user_name=user_name,
                        content=thought,
                        topic=topic,
                        user_message=usr_quote,
                        dalet_thought=thought,
                    )

                    # 2. Evolucionar L2 (Escenario) y L3 (Persona) si el modelo los sintetizó
                    if (new_l2 or new_l3) and hasattr(self.repo, "upsert_user_persona"):
                        await self.repo.upsert_user_persona(
                            user_id=user_id,
                            user_name=user_name,
                            persona_l3=new_l3 or (current_l3 if current_l3 != "Sin perfil previo registrado." else thought),
                            scenario_l2=new_l2 or (current_l2 if current_l2 != "Sin escenario activo registrado." else thought),
                        )

                    # 3. Podar átomos L1 antiguos más allá del límite (ej. 20)
                    if hasattr(self.repo, "prune_old_user_memories"):
                        await self.repo.prune_old_user_memories(user_id, max_atoms=self.max_atoms_per_user)

                    logger.info(f"🧠 [MEMORY PYRAMID] L1/L2/L3 actualizado para {user_name} ({topic}): '{thought}'")
            finally:
                if close_client:
                    await http_client.aclose()

        except Exception as e:
            logger.debug(f"[MEMORY] No se pudo analizar recuerdo: {e}")
