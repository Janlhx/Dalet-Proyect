# Guía de Migración SQL para Neon (Dalet Restructuring)

Para que el bot funcione correctamente con el nuevo código, debes ejecutar estas consultas en el **SQL Editor** de tu consola de Neon.

### 1. Limpieza de fragmentos universitarios (Opcional pero recomendado)

Ejecuta esto para quitar la tabla de auditoría que ya no usamos:

```sql
DROP TRIGGER IF EXISTS trg_AuditPPChanges ON OsuAccounts;
DROP FUNCTION IF EXISTS fn_LogPPChange();
DROP TABLE IF EXISTS Log_PPAudits;
```

### 2. Actualización de Vistas

Copia y pega el contenido de [04_Views.sql](file:///c:/Users/juans/OneDrive/Documentos/Dalet-Proyect/sql/04_Views.sql) en el editor de Neon. Todas las vistas usan `CREATE OR REPLACE`, por lo que se actualizarán sin borrar datos.

### 3. Actualización de Procedimientos y Funciones (CRÍTICO)

Copia y pega el contenido de [03_Procedures_Functions.sql](file:///c:/Users/juans/OneDrive/Documentos/Dalet-Proyect/sql/03_Procedures_Functions.sql) en el editor de Neon.

> [!IMPORTANT]
> Es vital actualizar esto porque comandos como `d.link` y los de análisis asíncrono dependen de las nuevas firmas de estos procedimientos.

### 4. Actualización de Triggers

Copia y pega el contenido de [05_Triggers.sql](file:///c:/Users/juans/OneDrive/Documentos/Dalet-Proyect/sql/05_Triggers.sql) para asegurar que solo queden las validaciones de puntajes activas.
