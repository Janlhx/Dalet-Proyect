import psycopg2
import os
from dotenv import load_dotenv

# Carga la URL de la base de datos desde el archivo .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# (Quitamos los prints de diagnóstico de la URL, ya confirmamos que se lee)

def get_connection():
    """Crea y devuelve una nueva conexión a la base de datos."""
    # Verificar si la URL existe antes de intentar conectar
    if not DATABASE_URL:
        print("!!!!!! [DB Connector] ERROR FATAL: DATABASE_URL no está configurada.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"!!!!!! [DB Connector] Error al conectar a la base de datos: {e}")
        return None

def execute_procedure(procedure_name, params=()):
    """Ejecuta un procedimiento almacenado (usa CALL)."""
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                placeholders = ', '.join(['%s'] * len(params))
                sql_query = f"CALL {procedure_name}({placeholders})"
                # print(f"--- [DB Connector] Ejecutando CALL: {sql_query} con {params}") # DEBUG (opcional)
                cur.execute(sql_query, params)
            conn.commit()
            # print(f"--- [DB Connector] CALL {procedure_name} ejecutado.") # DEBUG (opcional)
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error ejecutando CALL {procedure_name}({params}): {e}")
        finally:
            conn.close()

# ======================================================
# ▼▼▼ ¡ESTAS FUNCIONES DEBEN ESTAR PRESENTES! ▼▼▼
# ======================================================
def fetch_one(query, params=()):
    """Ejecuta una consulta (SELECT) y devuelve UNA SOLA fila (tupla) o None."""
    conn = get_connection()
    result = None
    if conn:
        try:
            with conn.cursor() as cur:
                # print(f"--- [DB Connector] Ejecutando fetch_one: {query} con {params}") # DEBUG (opcional)
                cur.execute(query, params)
                result = cur.fetchone()
                # print(f"--- [DB Connector] Resultado fetch_one: {result!r}") # DEBUG (opcional)
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_one: {e}")
        finally:
            conn.close()
    return result

def fetch_all(query, params=()):
    """Ejecuta una consulta (SELECT) y devuelve TODAS las filas (lista de tuplas) o lista vacía."""
    conn = get_connection()
    results = []
    if conn:
        try:
            with conn.cursor() as cur:
                # print(f"--- [DB Connector] Ejecutando fetch_all: {query} con {params}") # DEBUG (opcional)
                cur.execute(query, params)
                results = cur.fetchall()
                # print(f"--- [DB Connector] Resultado fetch_all: {len(results)} filas") # DEBUG (opcional)
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_all: {e}")
        finally:
            conn.close()
    return results
# ======================================================