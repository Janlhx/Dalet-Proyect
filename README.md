# Proyecto Final de Bases de Datos - Bot de Discord "Dalet"

## 1. Resumen del Proyecto

Este repositorio contiene la implementación del bot de Discord "Dalet" y la arquitectura de su base de datos, desarrollado como proyecto final para el curso de Bases de Datos.

El objetivo central fue migrar la persistencia de datos del bot, que originalmente se basaba en múltiples archivos JSON, a una base de datos relacional centralizada. Se utilizó **PostgreSQL**, alojado en **Neon**, para construir un modelo de datos robusto que soporta las diversas funcionalidades del bot.

## 2. Funcionalidad del Bot

El bot "Dalet" integra varias funciones que ahora dependen de la base de datos:

* **Memoria Conversacional y de Usuario:** El bot utiliza la tabla `Messages` para obtener contexto de chat en vivo y la tabla `UserMemories` para almacenar información específica que los usuarios le solicitan recordar.
* **Integración con API de Osu!:** Los usuarios vinculan sus perfiles de `osu!` (guardados en `OsuAccounts`). El bot obtiene y almacena *scores* relevantes (`OsuScores`) y estadísticas de perfil para su análisis.
* **Análisis y Coaching de Rendimiento:** A través de comandos como `d.osuAnalyze` y `d.osuCoach`, el bot consulta los datos almacenados y las vistas para generar planes de coaching personalizados usando IA.
* **Resúmenes de Chat:** El bot puede leer el historial de un canal (`V_ChannelMessages`), generar un resumen del mismo y almacenarlo en la tabla `Summaries`.
* **Gestión de Configuración:** Los administradores del servidor pueden configurar el comportamiento del bot (ej. canales proactivos, modo reactivo) a través de comandos que modifican las tablas `Channels` y `Servers`.

## 3. Stack Técnico y Arquitectura de Despliegue

Este proyecto se apoya en tres servicios en la nube principales:

1.  **Neon (La Base de Datos):**
    * **Rol:** Aloja nuestra base de datos PostgreSQL.
    * **Implementación:** Neon provee una URL de conexión (`DATABASE_URL`) que el bot usa para conectarse y ejecutar todas las consultas, funciones y procedimientos almacenados.

2.  **Render (El Bot):**
    * **Rol:** Aloja y ejecuta el código de Python (`dalet_main.py`).
    * **Implementación:** Está configurado como un "Web Service". [cite_start]Para asegurar la alta disponibilidad, el script principal (`dalet_main.py` [cite: 50-56]) inicia un servidor web **Flask** en un hilo secundario. Render monitorea el *endpoint* (`/`) de este servidor. Si el bot falla, el servidor Flask también lo hace, y Render reinicia automáticamente todo el servicio.

3.  **UptimeRobot (El "Despertador"):**
    * **Rol:** Evita que el servicio de Render (en su plan gratuito) se "duerma" por inactividad.
    * **Implementación:** UptimeRobot es un servicio externo configurado para hacer una petición HTTP a la URL de Render (`https://tu-bot.onrender.com`) cada 20-30 minutos. Esto simula tráfico constante y mantiene el bot despierto.

## 4. Guía de Replicación (Paso a Paso)

Para replicar este bot desde cero, sigue estos pasos en orden.

### Paso 1: Configuración de Servicios Externos (Obtener API Keys)

Antes de tocar el código, necesitas las 5 claves de tus servicios:

1.  **Discord (DISCORD_TOKEN):**
    * Ve al [Portal de Desarrolladores de Discord](https://discord.com/developers/applications).
    * Crea una "New Application".
    * Ve a la pestaña "Bot".
    * Activa los **"Privileged Gateway Intents"** (especialmente `MESSAGE CONTENT INTENT`). Esto es crucial para que el bot pueda leer mensajes.
    * Haz clic en "Reset Token" para obtener tu `DISCORD_TOKEN`.
    * Invita a tu bot a tu servidor usando la pestaña "OAuth2" > "URL Generator" (selecciona los permisos `bot` y `applications.commands`).

2.  **Neon (DATABASE_URL):**
    * Crea una cuenta en [Neon](https://neon.tech).
    * Crea un nuevo proyecto.
    * En el dashboard de tu proyecto, busca la cadena de conexión (Connection String) que empieza por `postgres://...`. Esa es tu `DATABASE_URL`.

3.  **Google Gemini (GEMINI_API_KEY):**
    * Ve a [Google AI Studio](https://aistudio.google.com/).
    * Crea una "API Key" para tu proyecto. Esa es tu `GEMINI_API_KEY`.

4.  **Osu! (OSU_CLIENT_ID y OSU_CLIENT_SECRET):**
    * Inicia sesión en [osu!](https://osu.ppy.sh/home).
    * Ve a tu Configuración (Settings) > "OAuth" (al final).
    * Registra una "new OAuth application".
    * Esto te dará un `Client ID` y un `Client Secret`.

### Paso 2: Configuración de la Base de Datos (SQL)

Ahora que tienes tu `DATABASE_URL`, necesitas construir las tablas.

1.  Conéctate a tu base de datos de Neon. Puedes usar su editor SQL web o un cliente de escritorio como DBeaver o PgAdmin.
2.  Abre la carpeta `/sql` de este repositorio.
3.  Ejecuta los scripts en tu base de datos en **estricto orden numérico**:
    * `01_Schema.sql` (Crea las tablas)
    * `02_Data.sql` (Inserta datos de muestra)
    * `03_Procedures_Functions.sql` (Crea la lógica)
    * `04_Views.sql` (Crea las vistas)
    * `05_Triggers.sql` (Crea los triggers)

### Paso 3: Instalación Local (Python)

1.  Clona este repositorio: `git clone ...`
2.  Crea un archivo llamado `.env` en la raíz del proyecto.
3.  Copia y pega lo siguiente en ese archivo `.env`, llenando con las claves del Paso 1:

    ```
    DISCORD_TOKEN=...
    GEMINI_API_KEY=...
    DATABASE_URL=...
    OSU_CLIENT_ID=...
    OSU_CLIENT_SECRET=...
    ```
4.  Crea un entorno virtual (recomendado) e instala las dependencias (asegúrate de tener `requirements.txt`):
    ```bash
    pip install -r requirements.txt
    ```
5.  Ejecuta el bot localmente para probar:
    ```bash
    python dalet_main.py
    ```

### Paso 4: Despliegue en Producción (Render)

1.  Sube tu repositorio a GitHub.
2.  En [Render](https://render.com/), crea un "New Web Service".
3.  Conecta tu repositorio de GitHub.
4.  Configura los siguientes ajustes:
    * **Build Command:** `pip install -r requirements.txt`
    * **Start Command:** `python dalet_main.py`
5.  Ve a la pestaña "Environment" de tu servicio en Render.
6.  Añade todas las variables de entorno del Paso 3 ( `DISCORD_TOKEN`, `GEMINI_API_KEY`, etc.) una por una.
7.  Haz clic en "Create Web Service". Render hará el deploy.
8.  Copia la URL de tu servicio (ej. `https://dalet-bot.onrender.com`).
9.  (Opcional pero recomendado) Ve a [UptimeRobot](https://uptimerobot.com/), crea un monitor HTTP(s) y pégale la URL de Render para que la "despierte" cada 20 minutos.

## 7. Documentación del Proyecto

La justificación técnica detallada, el Diagrama Entidad-Relación (DER) y el análisis de cumplimiento de los requisitos del proyecto se encuentran en el archivo `Proyecto Final Bases De Datos.docx`.
