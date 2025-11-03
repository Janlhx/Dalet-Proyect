# Proyecto Final de Bases de Datos - Bot de Discord "Dalet"

## 1. Resumen del Proyecto

Este repositorio contiene la implementación del bot de Discord "Dalet" y la arquitectura de su base de datos, desarrollado como proyecto final para el curso de Bases de Datos.

El objetivo central fue migrar la persistencia de datos del bot, que originalmente se basaba en múltiples archivos JSON, a una base de datos relacional centralizada. Se utilizó **PostgreSQL**, alojado en **Neon**, para construir un modelo de datos robusto que soporta las diversas funcionalidades del bot.

## 2. Funcionalidad del Bot

El bot "Dalet" integra varias funciones que ahora dependen de la base de datos:

* **Memoria Conversacional y de Usuario:** El bot utiliza la tabla `Messages` para obtener contexto de chat en vivo y la tabla `UserMemories` para almacenar información específica que los usuarios le solicitan recordar.
* **Integración con API de Osu!:** Los usuarios vinculan sus perfiles de `osu!` (guardados en `OsuAccounts`). El bot obtiene y almacena *scores* relevantes (`OsuScores`) y estadísticas de perfil para su análisis.
* **Análisis y Coaching de Rendimiento:** A través de comandos como `d.osuAnalyze` y `d.osuCoach`, el bot consulta los datos almacenados y las vistas (ej. `V_OsuRankingGlobal`) para generar análisis de rendimiento y planes de coaching personalizados usando IA.
* **Resúmenes de Chat:** El bot puede leer el historial de un canal (`V_ChannelMessages`), generar un resumen del mismo y almacenarlo en la tabla `Summaries`.
* **Gestión de Configuración:** Los administradores del servidor pueden configurar el comportamiento del bot (ej. canales proactivos, modo reactivo) a través de comandos que modifican las tablas `Channels` y `Servers`.

## 3. Stack Técnico

* **Aplicación (Bot):** Python (usando `discord.py`, `psycopg2`, `google-generativeai`, `Flask`)
* **Base de Datos:** PostgreSQL (alojada en Neon)
* **Alojamiento (Bot):** Render

## 4. Arquitectura de Alojamiento (Render)

El bot está desplegado en **Render** utilizando la modalidad "Web Service".

[cite_start]Para asegurar la alta disponibilidad, el script principal (`dalet_main.py` [cite: 50-56]) inicia un servidor web **Flask** en un hilo secundario. Este servidor expone un *endpoint* de *health check* (`/`). Render monitorea este *endpoint*: si el proceso principal del bot falla, el servidor Flask también lo hace. Render detecta la falta de respuesta y reinicia automáticamente el servicio.

## 5. Configuración de la Base de Datos

La carpeta `/sql` en este repositorio contiene los 5 scripts necesarios para crear la base de datos desde cero. Es crucial ejecutarlos en el orden numérico establecido para respetar las dependencias (ej. tablas deben existir antes que los procedimientos, procedimientos antes que las vistas, etc.).

1.  **`01_Schema.sql`**:
    * Contiene todas las sentencias `CREATE TABLE` para el esquema, así como `CREATE TYPE` y `CREATE INDEX`.
2.  **`02_Data.sql`**:
    * Contiene las sentencias `INSERT INTO` para poblar la base de datos con datos de muestra.
3.  **`03_Procedures_Functions.sql`**:
    * Contiene toda la lógica de negocio de la base de datos (`CREATE PROCEDURE` y `CREATE FUNCTION`). Aquí se define el CRUD (`sp_LogMessage`, `sp_LinkOsuAccount`, `fn_GetUserStats`, etc.).
4.  **`04_Views.sql`**:
    * Contiene las `CREATE VIEW` utilizadas para el análisis y la abstracción de consultas complejas (`V_ChannelMessages`, `V_OsuRankingGlobal`).
5.  **`05_Triggers.sql`**:
    * Contiene las funciones de trigger y las sentencias `CREATE TRIGGER` (`trg_AuditPPChanges`, `trg_ValidateScore`) para auditoría y validación.

## 6. Instalación Local

Para ejecutar el bot en un entorno local:

1.  Clonar este repositorio.
2.  Crear un archivo `.env` en la raíz del proyecto.
3.  Añadir las siguientes variables de entorno al archivo `.env`:

    ```
    DISCORD_TOKEN=...
    GEMINI_API_KEY=...
    DATABASE_URL=...
    OSU_CLIENT_ID=...
    OSU_CLIENT_SECRET=...
    ```
4.  Instalar las dependencias (se asume un archivo `requirements.txt`):
    ```bash
    pip install -r requirements.txt
    ```
5.  Ejecutar el bot:
    ```bash
    python dalet_main.py
    ```

## 7. Documentación del Proyecto

La justificación técnica detallada, el Diagrama Entidad-Relación (DER) y el análisis de cumplimiento de los requisitos del proyecto se encuentran en el archivo `Proyecto Final Bases De Datos.docx`.
