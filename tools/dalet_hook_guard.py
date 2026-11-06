"""
Dalet PreToolUse Security & Style Hook Guard
Se ejecuta automáticamente antes de `run_command` (configurado en `.agents/hooks.json`).
Bloquea comandos destructivos accidentales (`git push --force`, borrado de `.env` o `dalet_memory.db`, `git reset --hard`)
y permite el flujo normal de desarrollo seguro.
"""

import json
import re
import sys

DANGEROUS_PATTERNS = [
    (r"git\s+push\s+.*(--force|-f\b)", "Bloqueado por Dalet Safety Hook: 'git push --force' está prohibido en main."),
    (r"git\s+reset\s+--hard", "Bloqueado por Dalet Safety Hook: 'git reset --hard' puede destruir cambios no guardados."),
    (r"(rm|del|Remove-Item)\s+.*(\.env|dalet_memory\.db)", "Bloqueado por Dalet Safety Hook: prohibido eliminar .env o la base de datos local dalet_memory.db."),
]


def main():
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        return

    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or {}
    cmd = str(args.get("CommandLine") or "")

    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, flags=re.IGNORECASE):
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
            return

    sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")


if __name__ == "__main__":
    main()
