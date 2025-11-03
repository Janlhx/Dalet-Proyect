"""
Módulo de Conexión a la Base de Datos.

Este archivo centraliza la conexión con la base de datos PostgreSQL en Neon.
Proporciona funciones auxiliares para ejecutar consultas (SELECT) y
procedimientos almacenados (CALL) de forma segura y consistente
a través de toda la aplicación.
"""
import psycopg2
import os
from dotenv import load_dotenv

# Carga la URL de la base de datos desde el archivo .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """
    Crea y devuelve una nueva conexión a la base de datos.

    Utiliza la variable de entorno DATABASE_URL para conectar con PostgreSQL.

    Returns:
        psycopg2.connection: Un objeto de conexión de Psycopg2 o None si falla.
    """
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
    """
    Ejecuta un procedimiento almacenado (usa CALL) y confirma la transacción.

    Esta función es para operaciones que modifican datos (INSERT, UPDATE, DELETE)
    y no devuelven resultados.

    Args:
        procedure_name (str): El nombre del procedimiento almacenado a llamar.
        params (tuple, optional): Una tupla de parámetros para el procedimiento.
    """
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                placeholders = ', '.join(['%s'] * len(params))
                sql_query = f"CALL {procedure_name}({placeholders})"
                cur.execute(sql_query, params)
            conn.commit() # Confirma la transacción
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error ejecutando CALL {procedure_name}({params}): {e}")
            conn.rollback() # Revierte en caso de error
        finally:
            conn.close()

def fetch_one(query, params=()):
    """
    Ejecuta una consulta (SELECT) y devuelve UNA SOLA fila.

    Args:
        query (str): La consulta SQL (ej. "SELECT * FROM Users WHERE UserID = %s").
        params (tuple, optional): Una tupla de parámetros para la consulta.

    Returns:
        tuple: Una tupla que representa la fila encontrada, o None si no hay resultados.
    """
    conn = get_connection()
    result = None
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_one: {e}")
        finally:
            conn.close()
    return result

def fetch_all(query, params=()):
    """
    Ejecuta una consulta (SELECT) y devuelve TODAS las filas.

    Args:
        query (str): La consulta SQL (ej. "SELECT * FROM V_OsuRankingGlobal").
        params (tuple, optional): Una tupla de parámetros para la consulta.

    Returns:
        list: Una lista de tuplas, donde cada tupla es una fila. Lista vacía si no hay resultados.
    """
    conn = get_connection()
    results = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
        except Exception as e:
            print(f"!!!!!! [DB Connector] Error en la consulta fetch_all: {e}")
        finally:
            conn.close()
    return results