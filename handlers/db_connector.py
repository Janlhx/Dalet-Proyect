import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Carga la URL de la base de datos desde el archivo .env
DATABASE_URL = os.getenv("DATABASE_URL")
# ======================================================
# ▼▼▼ LÍNEAS DE DIAGNÓSTICO ▼▼▼
# ======================================================
print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
print(f"+++ [DB Connector] Intentando usar DATABASE_URL:")
if DATABASE_URL:
    # Mostramos solo una parte de la URL para no exponer la contraseña completa en los logs
    url_parts = DATABASE_URL.split('@')
    if len(url_parts) > 1:
        print(f"+++    URL encontrada (parcial): postgres://...@{url_parts[-1]}")
    else:
        print(f"+++    URL encontrada (formato desconocido): {DATABASE_URL[:30]}...")
else:
    print("+++    ¡ERROR! DATABASE_URL NO encontrada o vacía.")
print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
# ======================================================
def get_connection():
    """Crea y devuelve una nueva conexión a la base de datos."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def execute_procedure(procedure_name, params=()):
    """Ejecuta un procedimiento almacenado (para INSERT, UPDATE, DELETE)."""
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # ------------------------------------------------------------------
                # ¡AQUÍ ESTÁ EL CAMBIO!
                # Ya no usamos cur.callproc().
                # Construimos una consulta SQL con la sintaxis CALL
                # y placeholders %s para los parámetros.
                # ------------------------------------------------------------------
                
                # 1. Creamos los placeholders (ej: %s, %s, %s)
                placeholders = ', '.join(['%s'] * len(params))
                
                # 2. Creamos la consulta SQL
                sql_query = f"CALL {procedure_name}({placeholders})"
                
                # 3. Ejecutamos la consulta
                cur.execute(sql_query, params)
                
            # 4. Hacemos commit de los cambios
            conn.commit()
        except Exception as e:
            print(f"Error ejecutando el procedimiento {procedure_name}: {e}")
        finally:
            conn.close()

def fetch_all(query, params=()):
    """Ejecuta una consulta (SELECT) y devuelve todos los resultados."""
    conn = get_connection()
    results = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
        except Exception as e:
            print(f"Error en la consulta fetch_all: {e}")
        finally:
            conn.close()
    return results