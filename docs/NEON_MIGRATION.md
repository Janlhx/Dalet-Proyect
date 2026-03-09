# SQL Migration Guide for Neon (Dalet Restructuring)

To ensure the bot functions correctly with the new structure, you must execute these queries in the **SQL Editor** of your Neon console.

---

### 1. Cleanup of Obsolete Audit Fragments (Optional but recommended)

Run this to remove the audit table no longer in use:

```sql
DROP TRIGGER IF EXISTS trg_AuditPPChanges ON OsuAccounts;
DROP FUNCTION IF EXISTS fn_LogPPChange();
DROP TABLE IF EXISTS Log_PPAudits;
```

---

### 2. View Updates

Copy and paste the content of [04_Views.sql](../sql/04_Views.sql) into the Neon editor. All views use `CREATE OR REPLACE`, allowing them to be updated without data loss.

---

### 3. Procedure and Function Update (CRITICAL)

Copy and paste the content of [03_Procedures_Functions.sql](../sql/03_Procedures_Functions.sql) into the Neon editor.

> [!IMPORTANT]
> Updating these is vital, as commands like `d.link` and asynchronous analysis functions depend on the new signatures of these procedures.

---

### 4. Trigger Update

Copy and paste the contents of [05_Triggers.sql](../sql/05_Triggers.sql) to ensure only the latest score validation logic remains active.
