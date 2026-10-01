import logging
import os
import re
import json
import time
import asyncio
from collections import deque

logger = logging.getLogger("dalet.services.memory")

_MEMORY_ANALYSIS_PROMPT = """Eres el subconsciente reflexivo de Dalet (un bot de Discord con personalidad humana, sarcástica pero leal y empática).
Tu tarea es observar lo que el usuario habla con Dalet y extraer recuerdos y conclusiones internas sobre quién es este usuario.

Usuario: "{user_name}"
Mensaje del usuario: "{user_message}"
Respuesta de Dalet: "{dalet_reply}"

Pregunta: ¿Este mensaje revela algún dato duradero, preferencia, rasgo de personalidad, anécdota, proyecto, estado emocional o dinámica de relación sobre {user_name} que Dalet deba recordar para entenderlo mejor en el futuro?
Descarta:
- Saludos simples ("hola", "buenas", "que tal").
- Bromas casuales efímeras sin sustancia personal.
- Preguntas genéricas o comandos.
- Respuestas triviales ("ok", "si", "no", "jaja", "xd").

Responde ÚNICAMENTE con un objeto JSON en crudo:
Si NO vale la pena recordar:
{{"save": false}}

Si SÍ vale la pena recordar:
{{
  "save": true,
  "topic": "gustos" | "personal" | "humor" | "emocional" | "interaccion" | "general",
  "user_message": "cita o resumen breve de lo que dijo el usuario",
  "dalet_thought": "Tu conclusión o pensamiento interno sobre el usuario en 1-2 frases concisas (ej: 'Estudia programación y se frustra con los algoritmos. Agradece cuando soy sarcástica pero comprensiva.')"
}}
"""


class MemoryService:
    """
    Servicio de memoria cognitiva para Dalet.
    Almacena el mensaje del usuario y las conclusiones/pensamientos internos que Dalet sacó de él.
    Inyecta los recuerdos de forma natural en el contexto para que Dalet no los recite robóticamente.
    """

    def __init__(self, user_repo):
        self.repo = user_repo
        self.max_db_history = 10  # Ventana optimizada de mensajes (permite mantener el hilo completo de conversaciones)
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
        Construye el contexto de conversación optimizado combinando:
        1. Historial reciente del canal (BD + local RAM, ventana adaptativa)
        2. Recuerdos y conclusiones internas de Dalet sobre el usuario (máx 3 datos clave)
        """
        history_section = []

        # Ajustar límite de mensajes según longitud del mensaje actual (mínimo 6 para no perder contexto)
        msg_len = len(current_message.split())
        history_limit = 6 if msg_len <= 3 else self.max_db_history

        # 1. Historial Unificado
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
            logger.error(f"Error obteniendo historial: {e}")

        # 2. Recuerdos y conclusiones sobre el usuario
        memory_lines = []
        if check_user_memory:
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
                            line = f"• Conclusión tuya: {d_th}"
                            if u_msg:
                                line += f' (Dijo: "{u_msg[:100]}")'
                        elif cnt:
                            line = f"• Dato previo: {cnt}"

                        if line:
                            if mem_words & msg_words:
                                matched.append(line)
                            else:
                                unmatched.append(line)

                    # Seleccionar hasta 3 recuerdos (priorizando coincidencias temáticas)
                    selected_memories = (matched + unmatched)[:3]
                    memory_lines.extend(selected_memories)

            except Exception as e:
                logger.error(f"Error obteniendo recuerdos de usuario: {e}")

        # Construir contexto final con instrucción de actitud natural
        final_parts = []
        if memory_lines:
            header = f"[LO QUE SABES Y PIENSAS DE {user_name.upper()}]:\n" + "\n".join(memory_lines)
            instruction = (
                "[DIRECTIVA DE MEMORIA NATURAL]:\n"
                f"Estos son tus recuerdos y opiniones previas sobre {user_name}. "
                "Úsalos como trasfondo psicológico para entender su personalidad, confianza y tono de forma 100% natural. "
                "NUNCA recites ni fuerces estos recuerdos de manera robótica (por ejemplo, NO digas 'recuerdo que me dijiste X') "
                "a menos que la conversación fluya orgánicamente hacia ello."
            )
            final_parts.append(f"{header}\n\n{instruction}")

        if history_section:
            final_parts.append("CHAT RECIENTE:\n" + "\n".join(history_section))

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
        """Guarda un recuerdo sobre el usuario en la BD."""
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
        Analiza asíncronamente en background si la interacción contiene datos personales,
        gustos o dinámicas de relación que Dalet deba recordar, extrayendo su conclusión interna.
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

            raw_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
            model_name = "gemini-3.8-flash" if "flash" in raw_model else raw_model

            prompt = _MEMORY_ANALYSIS_PROMPT.format(
                user_name=user_name,
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

                if result.get("save") and result.get("dalet_thought"):
                    thought = result["thought"] if "thought" in result else result.get("dalet_thought", "")
                    usr_quote = result.get("user_message", clean_msg[:120])
                    topic = result.get("topic", "general")

                    await self.add_memory(
                        user_id=user_id,
                        user_name=user_name,
                        content=thought,
                        topic=topic,
                        user_message=usr_quote,
                        dalet_thought=thought,
                    )
                    logger.info(f"🧠 [MEMORY] Recuerdo guardado para {user_name} ({topic}): '{thought}'")
            finally:
                if close_client:
                    await http_client.aclose()

        except Exception as e:
            logger.debug(f"[MEMORY] No se pudo analizar recuerdo: {e}")

