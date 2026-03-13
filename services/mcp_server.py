import os
import logging
import psutil
from mcp.server.fastmcp import FastMCP
from database.repositories.user_repository import UserRepository
from services.osu_service import OsuService
from database.pool import DatabasePool
from ui.atoms import DaletAtoms

logger = logging.getLogger("dalet.mcp")

# Inicializamos FastMCP
mcp = FastMCP("Dalet-Intelligence")

# Repositorios y Servicios
user_repo = UserRepository()
osu_service = OsuService(
    client_id=int(os.getenv("OSU_CLIENT_ID", 0)),
    client_secret=os.getenv("OSU_CLIENT_SECRET", "")
)

@mcp.tool()
async def save_user_memory(user_id: int, username: str, memory_content: str) -> str:
    """
    Guarda información importante o hechos sobre un usuario que Dalet debe recordar.
    Usa esto cuando el usuario te cuente algo personal o que pidió recordar explícitamente.
    """
    try:
        await DatabasePool.get_pool()
        await user_repo.add_user_memory(user_id, username, memory_content)
        logger.info(f"MCP Tool: Memory saved for {username}")
        return f"He guardado esto en mi memoria: '{memory_content}'"
    except Exception as e:
        logger.error(f"MCP Tool Error (save_user_memory): {e}")
        return f"No pude guardar el recuerdo: {str(e)}"

@mcp.tool()
async def get_osu_stats(username: str, mode: str = "osu") -> str:
    """
    Obtiene estadísticas básicas (Rank, PP, Accuracy) de un jugador de osu!.
    Modos válidos: osu, taiko, fruits, mania.
    """
    try:
        user_data = await osu_service.get_user(username, mode)
        stats = user_data.get('statistics', {})
        rank = stats.get('global_rank', 'Sin Rank')
        pp = stats.get('pp', 0)
        acc = stats.get('hit_accuracy', 0)
        return (f"Estadísticas de {username} en {mode}:\n"
                f"- Rank Global: #{rank}\n"
                f"- Performance: {pp}pp\n"
                f"- Precisión: {acc:.2f}%")
    except Exception as e:
        logger.error(f"MCP Tool Error (get_osu_stats): {e}")
        return f"No encontré nada para '{username}' en osu!. Tal vez cambió de nombre o no existe."

@mcp.tool()
async def search_chat_lore(query: str, channel_id: int) -> str:
    """
    Busca en el historial del canal mensajes antiguos que coincidan con una palabra clave.
    Sirve para cuando alguien dice '¿te acuerdas cuando hablamos de...?' o '¿quién dijo X?'.
    """
    try:
        cid = int(channel_id) if channel_id != "N/A" else None
        if not cid: return "No tengo un ID de canal válido para buscar."
        
        await DatabasePool.get_pool()
        results = await user_repo.search_lore(query, cid, limit=5)
        if not results:
            return f"He buscado '{query}' pero no hay rastro en mis registros de este canal."
        
        lore_text = "Esto es lo que he encontrado en mis archivos:\n"
        for r in results:
            ts = r['timestamp'].strftime('%d/%m/%Y')
            lore_text += f"- [{ts}] {r['username']}: {r['content']}\n"
        return lore_text
    except Exception as e:
        logger.error(f"MCP Tool Error (search_chat_lore): {e}")
        return "Mis sensores de búsqueda están fallando ahora mismo."

@mcp.tool()
async def check_user_memories(user_id: int) -> str:
    """
    Consulta todos los recuerdos guardados sobre un usuario específico. 
    Úsalo para refrescar tu memoria sobre quién es alguien.
    """
    try:
        uid = int(user_id) if user_id != "N/A" else None
        if not uid: return "No puedo buscar recuerdos sin un ID de usuario."
        
        await DatabasePool.get_pool()
        memories = await user_repo.get_all_user_memories(uid)
        if not memories:
            return "No tengo recuerdos guardados sobre este usuario aún."
        
        res = "Esto es lo que sé sobre este usuario:\n"
        for m in memories:
            res += f"- {m['content']}\n"
        return res
    except Exception as e:
        logger.error(f"MCP Tool Error (check_user_memories): {e}")
        return "Error al acceder a mis bancos de memoria."

@mcp.tool()
async def get_user_profile_summary(user_id: int) -> str:
    """
    Genera un perfil psicológico y de datos resumido del usuario basado en todas las memorias.
    Úsalo para entender quién es alguien antes de hablar con él si no lo recuerdas bien.
    """
    try:
        uid = int(user_id) if user_id != "N/A" else None
        if not uid: return "No puedo analizar a un fantasma sin ID."
        
        await DatabasePool.get_pool()
        memories = await user_repo.get_all_user_memories(uid)
        if not memories:
            return "No sé nada de este usuario aún. Es un libro en blanco."
        
        # En el futuro esto podría ser un call a Gemini para resumir, 
        # por ahora devolvemos los puntos clave.
        count = len(memories)
        last_m = memories[-1]['content']
        return f"Perfil de {uid}: Tengo {count} recuerdos. Lo último que sé: '{last_m}'."
    except Exception as e:
        return f"Error en el perfil: {e}"

@mcp.tool()
async def get_system_status() -> str:
    """
    Informa sobre el estado de salud de Dalet: Conexión a Base de Datos, uso de memoria y actividad.
    Úsalo si alguien te pregunta '¿cómo estás?' desde un punto de vista técnico.
    """
    try:
        pool = await DatabasePool.get_pool()
        pool_size = len(pool._holders) if hasattr(pool, '_holders') else "Desconocido"
        
        proc = psutil.Process(os.getpid())
        ram_usage = proc.memory_info().rss / (1024 * 1024) # MB
        
        return (f"Estado de mis sistemas:\n"
                f"- Base de Datos (Neon): ✅ Activa (Pool: {pool_size})\n"
                f"- Consumo de RAM: {ram_usage:.2f} MB\n"
                f"- Estado del modelo: {DaletAtoms.EMOJI_DALET} Operativo")
    except Exception as e:
        return f"Mis sistemas indican fatiga: {str(e)}"

@mcp.tool()
async def get_osu_recent_activity(username: str, mode: str = "osu") -> str:
    """
    Consulta las jugadas más recientes de un usuario en osu!. 
    Útil para felicitar a alguien por una nueva jugada o ver si ha estado activo.
    """
    try:
        user_data = await osu_service.get_user(username, mode)
        user_id = user_data['id']
        recent_scores = await osu_service.get_user_recent_scores(user_id, mode, limit=3)
        
        if not recent_scores:
            return f"{username} no ha jugado nada recientemente en {mode}."
            
        res = f"Últimas jugadas de {username}:\n"
        for s in recent_scores:
            bm = s.get('beatmapset', {}).get('title', 'Mapa desconocido')
            rank = s.get('rank', 'F')
            acc = s.get('accuracy', 0) * 100
            res += f"- {bm} [{rank}] ({acc:.2f}%)\n"
        return res
    except Exception as e:
        logger.error(f"MCP Tool Error (get_osu_recent): {e}")
        return f"No pude espiar las jugadas de {username}."

if __name__ == "__main__":
    mcp.run()
