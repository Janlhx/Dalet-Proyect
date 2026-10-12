import logging
import os
import re
import json
import time
import asyncio
from collections import deque

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


class MemoryService:
    """
    Servicio de memoria cognitiva para Dalet basado en Pirámide Semántica (L0 -> L1 -> L2 -> L3).
    - L3 (Persona): Identidad estable, rasgos base y relación con Dalet.
    - L2 (Scenario): Contexto activo, proyectos actuales y estado reciente.
    - L1 (Atom): Hechos puntuales y conclusiones granulares en UserMemories.
    - L0 (Conversation): Historial reciente de mensajes del canal.
    """

    def __init__(self, user_repo):
        self.repo = user_repo
        self.max_db_history = 10  # Ventana optimizada de mensajes (L0)
        self.max_atoms_per_user = 20  # Tope de átomos L1 por usuario tras consolidar en L2/L3
        self._user_memory_cooldown: dict[int, float] = {}  # {user_id: last_analysis_timestamp}

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
        1. L3 (Persona) + L2 (Escenario Actual) desde UserPersonas
        2. L1 (Átomos relevantes) desde UserMemories (máx 3 coincidencias/recientes)
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
            # 2a. Consultar L3 y L2 (UserPersonas)
            try:
                if hasattr(self.repo, "get_user_persona"):
                    persona_data = await self.repo.get_user_persona(user_id)
                    if persona_data:
                        p_l3 = (persona_data.get("persona_l3") or "").strip()
                        s_l2 = (persona_data.get("scenario_l2") or "").strip()
                        if p_l3:
                            pyramid_lines.append(f"• [L3 - Perfil Persona]: {p_l3}")
                        if s_l2:
                            pyramid_lines.append(f"• [L2 - Escenario Actual]: {s_l2}")
            except Exception as e:
                logger.error(f"Error obteniendo UserPersona (L2/L3): {e}")

            # 2b. Consultar L1 (Átomos en UserMemories)
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    msg_words = set(re.findall(r"\w{3,}", current_message.lower()))

                    def _extract(row):
                        if hasattr(row, "get"):
                            return (
                                row.get("user_message") or row.get("UserMessage") or "",
                                row.get("dalet_thought") or row.get("DaletThought") or "",
                                row.get("content") or row.get("Content") or "",
                                row.get("topic") or row.get("Topic") or "general",
                            )
                        try:
                            return (
                                row["user_message"],
                                row["dalet_thought"],
                                row["content"],
                                row.get("topic", "general"),
                            )
                        except Exception:
                            u = row[2] if len(row) > 2 else ""
                            d = row[3] if len(row) > 3 else ""
                            c = row[1] if len(row) > 1 else str(row)
                            t = row[0] if len(row) > 0 else "general"
                            return (u or "", d or "", c or "", t or "general")

                    # Filtrar por relevancia temática primero
                    matched = []
                    unmatched = []
                    for m in memories_raw:
                        u_msg, d_th, cnt, topic = _extract(m)
                        search_text = f"{u_msg} {d_th} {cnt}".lower()
                        mem_words = set(re.findall(r"\w{3,}", search_text))
                        line = ""
                        if d_th:
                            line = f"• [L1 - Átomo ({topic})]: {d_th}"
                            if u_msg:
                                line += f' (Dijo: "{u_msg[:100]}")'
                        elif cnt:
                            line = f"• [L1 - Dato ({topic})]: {cnt}"

                        if line:
                            if mem_words & msg_words:
                                matched.append(line)
                            else:
                                unmatched.append(line)

                    # Seleccionar hasta 3 átomos L1 (priorizando coincidencias temáticas)
                    selected_memories = (matched + unmatched)[:3]
                    pyramid_lines.extend(selected_memories)

            except Exception as e:
                logger.error(f"Error obteniendo recuerdos L1 de usuario: {e}")

        # Construir contexto final con instrucción de actitud natural
        final_parts = []
        if pyramid_lines:
            header = f"[PIRÁMIDE SEMÁNTICA DE {user_name.upper()} (L3 -> L1)]:\n" + "\n".join(pyramid_lines)
            instruction = (
                "[DIRECTIVA DE MEMORIA NATURAL]:\n"
                f"Esta es tu pirámide de memoria sobre {user_name} (L3 identidad estable, L2 contexto actual, L1 recuerdos puntuales). "
                "Úsala como trasfondo psicológico y contextual (incluso para desambiguar búsquedas o referencias implícitas) de forma 100% natural. "
                "NUNCA recites ni fuerces estos recuerdos de manera robótica (por ejemplo, NO digas 'según mi memoria L3 sé que X') "
                "a menos que la conversación fluya orgánicamente hacia ello."
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


