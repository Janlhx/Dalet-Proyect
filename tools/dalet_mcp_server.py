"""
Dalet Brain MCP Server (Stdio JSON-RPC 2.0)
Servidor MCP nativo de Dalet que expone herramientas en tiempo real a los agentes:
- dalet_db_health: Resumen de filas y motor activo (Turso Cloud vs SQLite local).
- dalet_inspect_persona_insights: Lista las reglas de auto-calibración aprendidas por Dalet.
- dalet_inspect_user_pyramid: Consulta las capas L3, L2 y L1 de un usuario en la Pirámide Semántica.
- dalet_graph_stats: Resumen rápido de nodos, aristas y comunidades del grafo de conocimiento Graphify.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def _query_local_or_turso(sql: str, params: tuple = ()) -> list[dict]:
    """Ejecuta una consulta de solo lectura usando DashboardService o SQLite local como fallback."""
    try:
        from services.dashboard_service import DashboardService
        return DashboardService._execute_query(sql, params)
    except Exception:
        db_path = ROOT_DIR / "dalet_memory.db"
        if not db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []


TOOLS = [
    {
        "name": "dalet_db_health",
        "description": "Inspect Dalet's database health, active engine (Turso Cloud vs Local SQLite), and row counts across all cognitive and moderation tables.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "dalet_inspect_persona_insights",
        "description": "Retrieve the latest self-training personality rules (PersonaInsights) that Dalet has distilled from real Discord conversations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of insights to return (default 10).",
                }
            },
        },
    },
    {
        "name": "dalet_inspect_user_pyramid",
        "description": "Inspect a Discord user's L3 Persona, L2 Scenario, and L1 cognitive memory atoms by username or user_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Username substring or Discord UserID to search for.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "dalet_graph_stats",
        "description": "Read statistics from Dalet's Graphify AST knowledge graph (graphify-out/graph.json).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _handle_tool_call(name: str, args: dict) -> dict:
    if name == "dalet_db_health":
        try:
            from services.dashboard_service import DashboardService
            data = DashboardService.get_database_overview()
        except Exception as e:
            data = {"error": str(e)}
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

    if name == "dalet_inspect_persona_insights":
        limit = int(args.get("limit", 10))
        rows = _query_local_or_turso(
            """
            SELECT InsightID, UserID, UserName, UserMessage, DaletReply, Critique, StyleRule, CreatedAt
            FROM PersonaInsights
            ORDER BY CreatedAt DESC, InsightID DESC
            LIMIT ?
            """,
            (limit,),
        )
        return {"content": [{"type": "text", "text": json.dumps({"count": len(rows), "insights": rows}, ensure_ascii=False, indent=2)}]}

    if name == "dalet_inspect_user_pyramid":
        q = str(args.get("query", "")).strip()
        like_q = f"%{q}%"
        personas = _query_local_or_turso(
            """
            SELECT UserID, UserName, PersonaL3, ScenarioL2, MemoryCount, UpdatedAt
            FROM UserPersonas
            WHERE UserName LIKE ? OR CAST(UserID AS TEXT) LIKE ? OR PersonaL3 LIKE ?
            ORDER BY UpdatedAt DESC LIMIT 5
            """,
            (like_q, like_q, like_q),
        )
        atoms = _query_local_or_turso(
            """
            SELECT MemoryID, UserID, Topic, Content, UserMessage, DaletThought, Timestamp
            FROM UserMemories
            WHERE Content LIKE ? OR DaletThought LIKE ? OR CAST(UserID AS TEXT) LIKE ?
            ORDER BY Timestamp DESC LIMIT 10
            """,
            (like_q, like_q, like_q),
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"query": q, "personas_l3_l2": personas, "atoms_l1": atoms}, ensure_ascii=False, indent=2),
                }
            ]
        }

    if name == "dalet_graph_stats":
        graph_path = ROOT_DIR / "graphify-out" / "graph.json"
        if not graph_path.exists():
            return {"content": [{"type": "text", "text": json.dumps({"exists": False})}]}
        try:
            raw = json.loads(graph_path.read_text(encoding="utf-8"))
            nodes = raw.get("nodes", [])
            links = raw.get("links", raw.get("edges", []))
            communities = {n.get("community") for n in nodes if isinstance(n, dict) and "community" in n}
            summary = {
                "exists": True,
                "nodes_count": len(nodes),
                "edges_count": len(links),
                "communities_count": len(communities),
            }
            return {"content": [{"type": "text", "text": json.dumps(summary, ensure_ascii=False, indent=2)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}

    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "dalet-brain-mcp", "version": "4.0.4"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            params = req.get("params") or {}
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            result = _handle_tool_call(tool_name, tool_args)
            resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif req_id is not None:
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
