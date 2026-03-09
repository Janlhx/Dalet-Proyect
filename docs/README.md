# 📖 Documentación del Proyecto Dalet

Bienvenido a la documentación técnica de **Dalet**, un bot de Discord con IA conversacional, integración con osu!, y un sistema de memoria persistente.

---

## 📂 Índice de Documentos

| Archivo                                              | Descripción                                                               |
| ---------------------------------------------------- | ------------------------------------------------------------------------- |
| [01_ARQUITECTURA.md](./01_ARQUITECTURA.md)           | Visión general del proyecto, cómo funciona todo junto y el flujo de datos |
| [02_PUNTO_DE_ENTRADA.md](./02_PUNTO_DE_ENTRADA.md)   | `dalet_main.py` — El arranque del bot                                     |
| [03_HANDLERS.md](./03_HANDLERS.md)                   | Los Cogs/Handlers — cada módulo de comandos explicado                     |
| [04_SERVICIOS.md](./04_SERVICIOS.md)                 | `NLPService` y `MemoryService` — la IA y la memoria                       |
| [05_BASE_DE_DATOS.md](./05_BASE_DE_DATOS.md)         | Pool, Repositorios y Patrón Repository                                    |
| [06_ESQUEMA_SQL.md](./06_ESQUEMA_SQL.md)             | Todas las tablas, vistas, procedimientos y funciones SQL                  |
| [07_VARIABLES_ENTORNO.md](./07_VARIABLES_ENTORNO.md) | Variables `.env` necesarias para correr el bot                            |
| [NEON_MIGRATION.md](./NEON_MIGRATION.md)             | Guía de migración a Neon (PostgreSQL en la nube)                          |

---

## 🗺️ Mapa del Proyecto

```
Dalet-Proyect/
├── dalet_main.py           ← Punto de entrada principal
├── .env                    ← Variables de entorno (secretos)
├── requirements.txt        ← Dependencias Python
│
├── handlers/               ← Módulos de comandos (Cogs de discord.py)
│   ├── dalet_nlpchat.py        ← Motor de IA conversacional
│   ├── dalet_chatlogger.py     ← Logger de mensajes en BD
│   ├── dalet_admcommands_handler.py  ← Comandos admin
│   ├── dalet_geminicommand.py  ← Config de IA (proactivo/reactivo)
│   ├── dalet_commands_handlers.py    ← Comandos generales
│   ├── dalet_helpcommands_handlers.py ← Sistema de ayuda
│   ├── dalet_events_handlers.py      ← Eventos de Discord
│   ├── dalet_osucommands.py    ← Comandos de osu!
│   └── dalet_smartresume.py    ← Resúmenes de chat con IA
│
├── services/               ← Lógica de negocio (IA, memoria)
│   ├── nlp_service.py          ← Generación de respuestas con Gemini/Groq
│   ├── memory_service.py       ← Gestión del contexto y recuerdos
│   └── osu_service.py          ← Integración con la API de osu!
│
├── database/               ← Capa de acceso a datos
│   ├── pool.py                 ← Conexión/Pool de PostgreSQL
│   └── repositories/
│       ├── base_repository.py      ← Métodos SQL genéricos
│       ├── user_repository.py      ← Usuarios, mensajes, memorias
│       ├── admin_repository.py     ← Bloqueos de canales
│       ├── osu_repository.py       ← Datos de osu!
│       └── analytics_repository.py ← Métricas y errores
│
├── sql/                    ← Scripts SQL del esquema de la BD
│   ├── 01_Schema.sql           ← Tablas base
│   ├── 03_Procedures_Functions.sql ← Procedimientos y funciones
│   ├── 04_Views.sql            ← Vistas
│   ├── 08_Privacy_TTL.sql      ← Política de retención de datos
│   ├── 09_Enhancements.sql     ← Mejoras a tablas existentes
│   └── 10_New_Tables.sql       ← Tablas de analítica
│
└── docs/                   ← Esta carpeta (documentación)
```
