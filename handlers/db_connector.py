import psycopg2
import os
from dotenv import load_dotenv

# Carga la URL de la base de datos desde el archivo .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# (Quitamos los prints de diagnóstico anteriores, ya confirmamos que la URL se lee)

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
                cur.execute(sql_query, params)
            conn.commit()
        except Exception as e:
            # Imprimir error más detallado
            print(f"!!!!!! [DB Connector] Error ejecutando CALL {procedure_name}({params}): {e}")
            # Considerar re-lanzar la excepción si quieres que el comando falle explícitamente
            # raise e
        finally:
            conn.close()

# ======================================================
# ▼▼▼ ¡ASEGÚRATE DE QUE ESTAS FUNCIONES ESTÉN PRESENTES! ▼▼▼
# ======================================================
def fetch_one(query, params=()):
    """Ejecuta una consulta (SELECT) y devuelve UNA SOLA fila (tupla) o None."""
    conn = get_connection()
    result = None # Inicializar resultado como None
    if conn:
        try:
            with conn.cursor() as cur:
                print(f"--- [DB Connector] Ejecutando fetch_one: {query} con {params}") # DEBUG
                cur.execute(query, params)
                result = cur.fetchone() # fetchone() devuelve una tupla o None
                print(f"--- [DB Connector] Resultado fetch_one: {result!r}") # DEBUG
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_one: {e}")
            # No re-lanzar aquí para que la función devuelva None en caso de error
        finally:
            conn.close()
    # Devolver el resultado (que será None si no se encontró nada o si hubo error)
    return result

def fetch_all(query, params=()):
    """Ejecuta una consulta (SELECT) y devuelve TODAS las filas (lista de tuplas) o lista vacía."""
    conn = get_connection()
    results = [] # Inicializar como lista vacía
    if conn:
        try:
            with conn.cursor() as cur:
                print(f"--- [DB Connector] Ejecutando fetch_all: {query} con {params}") # DEBUG
                cur.execute(query, params)
                results = cur.fetchall() # fetchall() devuelve lista de tuplas o lista vacía
                print(f"--- [DB Connector] Resultado fetch_all: {len(results)} filas") # DEBUG
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_all: {e}")
            # No re-lanzar, devolver lista vacía en caso de error
        finally:
            conn.close()
    # Devolver la lista de resultados (vacía si no hubo o si hubo error)
    return results
# ======================================================