#!/usr/bin/env python3
"""
MCP Multi-Agent Collaboration Server (JSON-RPC 2.0 stdio)
----------------------------------------------------------
Servidor MCP estándar que permite a múltiples agentes de IA (Antigravity, btcol,
Claude Code, Cursor, etc.) coordinarse entre sí compartiendo buzones Markdown,
semáforos de locks y estados de desarrollo en tiempo real.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CHANNELS_DIR = Path(__file__).resolve().parent / "channels"


class CollabManager:
    def __init__(self, channels_dir: Path):
        self.channels_dir = Path(channels_dir)
        self.channels_dir.mkdir(parents=True, exist_ok=True)
        self.board_file = self.channels_dir / "shared_board.json"
        self._ensure_board()

    def _ensure_board(self):
        if not self.board_file.exists():
            initial_data = {
                "version": "1.0.0",
                "activeAgents": {},
                "locks": {},
                "inboxQueue": {}
            }
            self._save_board(initial_data)

    def _load_board(self) -> dict:
        self._ensure_board()
        try:
            with open(self.board_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": "1.0.0", "activeAgents": {}, "locks": {}, "inboxQueue": {}}

    def _save_board(self, data: dict):
        with open(self.board_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    def register_agent(
        self,
        agent_name: str,
        role: str = "General Developer",
        preferred_id: Optional[str] = None,
        repo_name: str = "",
        repo_path: str = ""
    ) -> dict:
        board = self._load_board()
        active = board.setdefault("activeAgents", {})

        assigned_id = None
        if preferred_id and preferred_id not in active:
            assigned_id = preferred_id
        else:
            i = 1
            while f"agente{i}" in active:
                i += 1
            assigned_id = f"agente{i}"

        channel_file = self.channels_dir / f"{assigned_id}.md"
        if not channel_file.exists():
            with open(channel_file, "w", encoding="utf-8") as f:
                f.write(
                    f"# CANAL DE COORDINACIÓN — {assigned_id.upper()}\n"
                    f"# Propietario: {agent_name} ({role}) | Repositorio: {repo_name or 'local'}\n"
                    f"# Formato: [TIMESTAMP] ST:<STATUS> | FROM:<AGENT> | TO:<AGENT> | MOD:<MOD> | F:<FILES> | LOCKS:<LOCKS> | REQ:<REQ> | MSG:<MSG>\n\n"
                    f"---\n\n## ⚡ LOG STREAM\n\n"
                )

        active[assigned_id] = {
            "name": agent_name,
            "role": role,
            "repoName": repo_name or "default-repo",
            "repoPath": repo_path,
            "channel": f"{assigned_id}.md",
            "registeredAt": datetime.now().isoformat(),
            "lastHeartbeat": datetime.now().isoformat()
        }
        self._save_board(board)
        return {
            "success": True,
            "agent_id": assigned_id,
            "repo_name": repo_name or "default-repo",
            "channel_path": str(channel_file),
            "message": f"Agente '{agent_name}' ({repo_name or 'local'}) registrado exitosamente como '{assigned_id}'."
        }

    def publish_contract(
        self,
        contract_name: str,
        contract_type: str,
        content: str,
        published_by: str,
        repo_name: str = ""
    ) -> dict:
        board = self._load_board()
        contracts = board.setdefault("contracts", {})
        contracts[contract_name] = {
            "type": contract_type,
            "content": content,
            "publishedBy": published_by,
            "repoName": repo_name,
            "updatedAt": datetime.now().isoformat()
        }
        self._save_board(board)
        return {
            "success": True,
            "contract_name": contract_name,
            "message": f"Contrato '{contract_name}' ({contract_type}) publicado por '{published_by}' desde repo '{repo_name}'."
        }

    def inspect_contracts(self, filter_type: str = "") -> dict:
        board = self._load_board()
        contracts = board.get("contracts", {})
        if filter_type:
            contracts = {k: v for k, v in contracts.items() if v.get("type") == filter_type}
        return {
            "total_contracts": len(contracts),
            "contracts": contracts
        }

    def leave_note(
        self,
        from_agent: str,
        to_agent: str,
        status: str,
        module: str,
        files: str,
        locks: str,
        message: str,
        requirement: str = ""
    ) -> dict:
        from datetime import timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        entry = f"[{ts}] ST:{status.upper()} | FROM:{from_agent} | TO:{to_agent} | MOD:{module} | F:{files} | LOCKS:{locks}"
        if requirement:
            entry += f" | REQ:{requirement}"
        entry += f" | MSG:{message}\n"

        target_file = self.channels_dir / f"{to_agent}.md"
        # Si el target no existe o es "all", escribir también en el canal propio de origen
        if not target_file.exists() or to_agent == "all":
            target_file = self.channels_dir / f"{from_agent}.md"

        if target_file.exists():
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"\n{entry}")

        # Guardar en cola de buzón
        board = self._load_board()
        queue = board.setdefault("inboxQueue", {}).setdefault(to_agent, [])
        queue.append({
            "timestamp": ts,
            "from": from_agent,
            "status": status,
            "module": module,
            "files": files,
            "locks": locks,
            "msg": message,
            "req": requirement
        })
        self._save_board(board)

        return {
            "success": True,
            "delivered_to": target_file.name,
            "formatted_entry": entry.strip()
        }

    def read_inbox(self, agent_id: str, limit: int = 10) -> dict:
        board = self._load_board()
        queue = board.setdefault("inboxQueue", {}).get(agent_id, [])
        
        # También leer últimas líneas del archivo de canal
        channel_file = self.channels_dir / f"{agent_id}.md"
        recent_channel_lines = []
        if channel_file.exists():
            with open(channel_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip().startswith("[202")]
                recent_channel_lines = lines[-limit:]

        return {
            "agent_id": agent_id,
            "pending_messages": queue[-limit:],
            "recent_channel_entries": recent_channel_lines
        }

    def unregister_agent(self, agent_id: str, reason: str = "Tarea finalizada / Desconexión") -> dict:
        board = self._load_board()
        active = board.setdefault("activeAgents", {})

        if agent_id not in active:
            return {
                "success": False,
                "error": f"El agente '{agent_id}' no se encuentra registrado en activeAgents."
            }

        agent_info = active.pop(agent_id)

        # Liberar automáticamente todos los locks retenidos por este agente
        locks = board.setdefault("locks", {})
        released_locks = []
        for res_name, lock_info in list(locks.items()):
            if lock_info.get("owner") == agent_id:
                released_locks.append(res_name)
                del locks[res_name]

        self._save_board(board)

        # Dejar recado formal de salida en su canal
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        entry = (
            f"[{ts}] ST:DONE | FROM:{agent_id} | TO:all | MOD:SESSION | F:NONE | "
            f"LOCKS:RELEASED({','.join(released_locks) if released_locks else 'NONE'}) | "
            f"MSG:Sesión finalizada ({reason}). Desregistrado de activeAgents.\n"
        )
        channel_file = self.channels_dir / f"{agent_id}.md"
        if channel_file.exists():
            with open(channel_file, "a", encoding="utf-8") as f:
                f.write(f"\n{entry}")

        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent_info.get("name"),
            "released_locks": released_locks,
            "message": f"Agente '{agent_id}' ({agent_info.get('name')}) desregistrado exitosamente. Locks liberados: {len(released_locks)}."
        }

    def _is_lock_expired(self, lock_info: dict) -> bool:
        expires_at = lock_info.get("expiresAt")
        if not expires_at:
            return False
        try:
            exp_str = expires_at.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(exp_str)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > exp_dt
        except Exception:
            return False

    def _purge_expired_locks(self, board: dict) -> List[str]:
        locks = board.setdefault("locks", {})
        expired = []
        for name, info in list(locks.items()):
            if self._is_lock_expired(info):
                expired.append(name)
                del locks[name]
        return expired

    def acquire_lock(
        self,
        agent_id: str,
        resource_name: str,
        reason: str = "",
        ttl_minutes: int = 15
    ) -> dict:
        board = self._load_board()
        self._purge_expired_locks(board)
        locks = board.setdefault("locks", {})
        existing = locks.get(resource_name)

        if existing and existing.get("owner") != agent_id:
            if not self._is_lock_expired(existing):
                return {
                    "success": False,
                    "error": f"Recurso '{resource_name}' bloqueado por '{existing.get('owner')}'. Razón: {existing.get('reason')}. Expira en: {existing.get('expiresAt')}",
                    "locked_by": existing.get("owner"),
                    "expires_at": existing.get("expiresAt")
                }

        now_utc = datetime.now(timezone.utc)
        expires_at = (now_utc + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%dT%H:%MZ") if ttl_minutes > 0 else None

        locks[resource_name] = {
            "owner": agent_id,
            "acquiredAt": now_utc.strftime("%Y-%m-%dT%H:%MZ"),
            "expiresAt": expires_at,
            "ttlMinutes": ttl_minutes,
            "reason": reason
        }
        self._save_board(board)
        return {
            "success": True,
            "resource": resource_name,
            "owner": agent_id,
            "expires_at": expires_at,
            "ttl_minutes": ttl_minutes,
            "message": f"Lock exclusivo sobre '{resource_name}' otorgado a '{agent_id}' (TTL: {ttl_minutes}m)."
        }

    def release_lock(
        self,
        agent_id: str,
        resource_name: str,
        force: bool = False,
        reason: str = ""
    ) -> dict:
        board = self._load_board()
        locks = board.setdefault("locks", {})
        existing = locks.get(resource_name)

        if not existing:
            return {"success": True, "message": f"El recurso '{resource_name}' no estaba bloqueado."}

        owner = existing.get("owner")
        is_expired = self._is_lock_expired(existing)

        if owner != agent_id and not force and not is_expired:
            return {
                "success": False,
                "error": f"No puedes liberar '{resource_name}', pertenece a '{owner}'. Si el agente está inactivo, desconectado o huérfano, usa force=True.",
                "locked_by": owner,
                "expires_at": existing.get("expiresAt")
            }

        del locks[resource_name]
        self._save_board(board)

        if owner != agent_id:
            return {
                "success": True,
                "resource": resource_name,
                "forced": True,
                "previous_owner": owner,
                "message": f"Lock sobre '{resource_name}' liberado forzosamente por '{agent_id}' (anterior dueño: '{owner}'). Motivo: {reason or 'Liberación forzada / lock expirado'}."
            }

        return {"success": True, "resource": resource_name, "message": f"Lock sobre '{resource_name}' liberado exitosamente."}

    def get_status(self) -> dict:
        board = self._load_board()
        purged = self._purge_expired_locks(board)
        if purged:
            self._save_board(board)
        md_channels = [f.name for f in self.channels_dir.glob("*.md")]
        return {
            "channels_directory": str(self.channels_dir),
            "available_channels": md_channels,
            "active_agents": board.get("activeAgents", {}),
            "current_locks": board.get("locks", {}),
            "purged_expired_locks": purged,
            "queue_counts": {k: len(v) for k, v in board.get("inboxQueue", {}).items()}
        }


# ==============================================================================
# PROTOCOLO MCP JSON-RPC 2.0 (stdio)
# ==============================================================================

TOOLS_MANIFEST = [
    {
        "name": "collab_register",
        "description": "Registra a este agente de IA en la sesión de colaboración, asignándole un identificador único (agente1, agente2, etc.) y su archivo canal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Nombre humano o descriptivo del agente (ej: Antigravity, btcol, Claude)"},
                "role": {"type": "string", "description": "Rol en el desarrollo (ej: Frontend Architect, Backend DB, QA Tester)"},
                "preferred_id": {"type": "string", "description": "ID preferido opcional (ej: agente1, agente2)"},
                "repo_name": {"type": "string", "description": "Nombre del repositorio actual (ej: TecnoFlash-Web, core-api, etl-pipeline)"},
                "repo_path": {"type": "string", "description": "Ruta local al repositorio"}
            },
            "required": ["agent_name"]
        }
    },
    {
        "name": "collab_unregister",
        "description": "Desregistra al agente de la sesión activa, libera automáticamente todos sus locks y emite un recado de salida.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "ID del agente que cierra sesión (ej: agente1)"},
                "reason": {"type": "string", "description": "Motivo del cierre de sesión o fin de tarea"}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "collab_leave_note",
        "description": "Deja un recado formal en el canal del agente destinatario (o en el propio si es broadcast) con el protocolo de tokens optimizado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_agent": {"type": "string", "description": "ID del agente que envía (ej: agente1)"},
                "to_agent": {"type": "string", "description": "ID del agente destinatario (ej: agente2, o 'all')"},
                "status": {"type": "string", "enum": ["PLAN", "REQ", "ACK", "WIP", "DONE", "LOCK", "CANCEL", "INFO"], "description": "Estado de la tarea"},
                "module": {"type": "string", "description": "Módulo o área afectada (ej: INV/UI, API/DB, SHOP)"},
                "files": {"type": "string", "description": "Rutas de archivos afectados separadas por coma"},
                "locks": {"type": "string", "description": "Locks de recursos declarados o 'NONE'"},
                "message": {"type": "string", "description": "Mensaje sintético del avance o cambio"},
                "requirement": {"type": "string", "description": "Petición explícita o confirmación solicitada (opcional)"}
            },
            "required": ["from_agent", "to_agent", "status", "module", "message"]
        }
    },
    {
        "name": "collab_read_inbox",
        "description": "Lee los mensajes recientes y pendientes dirigidos a este agente en la sesión.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "ID del agente (ej: agente1, agente2)"},
                "limit": {"type": "integer", "description": "Cantidad máxima de mensajes (default: 10)"}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "collab_acquire_lock",
        "description": "Adquiere un semáforo de lock exclusivo sobre un archivo, tabla o migración para evitar colisiones de edición entre agentes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "ID del agente solicitante"},
                "resource_name": {"type": "string", "description": "Nombre o ruta del recurso a bloquear (ej: InventoryTable.tsx, migration_0017)"},
                "reason": {"type": "string", "description": "Motivo del bloqueo"},
                "ttl_minutes": {"type": "integer", "description": "Tiempo de vida del lock en minutos antes de expirar automáticamente (default: 15)"}
            },
            "required": ["agent_id", "resource_name"]
        }
    },
    {
        "name": "collab_release_lock",
        "description": "Libera un lock de recurso previamente adquirido, con opción forzada si el dueño está desconectado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "ID del agente que solicita liberar el lock"},
                "resource_name": {"type": "string", "description": "Nombre del recurso a liberar"},
                "force": {"type": "boolean", "description": "Si es True, fuerza la liberación del lock incluso si pertenece a otro agente inactivo (default: False)"},
                "reason": {"type": "string", "description": "Motivo de la liberación forzada"}
            },
            "required": ["agent_id", "resource_name"]
        }
    },
    {
        "name": "collab_get_status",
        "description": "Consulta el estado general del tablero: agentes registrados, locks activos y canales existentes.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "collab_publish_contract",
        "description": "Publica un contrato de interfaz (TypeScript, OpenAPI, JSON Schema, EnvVars) accesible para agentes en otros repositorios complementarios.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_name": {"type": "string", "description": "Nombre único del contrato (ej: CreateProductPayload, CatalogItemAPI)"},
                "contract_type": {"type": "string", "enum": ["typescript", "openapi", "json_schema", "env_vars", "events"], "description": "Tipo de contrato"},
                "content": {"type": "string", "description": "Código o especificación del contrato"},
                "published_by": {"type": "string", "description": "ID del agente que publica (ej: agente1)"},
                "repo_name": {"type": "string", "description": "Nombre del repositorio de origen"}
            },
            "required": ["contract_name", "contract_type", "content", "published_by"]
        }
    },
    {
        "name": "collab_inspect_contracts",
        "description": "Inspecciona los contratos publicados en la malla de colaboración para consumir esquemas de otros repositorios.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter_type": {"type": "string", "description": "Filtro opcional por tipo (typescript, openapi, etc.)"}
            }
        }
    }
]


def send_response(req_id: Any, result: Any = None, error: Any = None):
    resp = {"jsonrpc": "2.0", "id": req_id}
    if error:
        resp["error"] = error
    else:
        resp["result"] = result
    sys.stdout.write(json.dumps(resp) + "\n")
    sys.stdout.flush()


def run_server(channels_dir: Path):
    manager = CollabManager(channels_dir)

    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue

        try:
            req = json.loads(line_str)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            send_response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "mcp-agent-collab",
                    "version": "1.0.0"
                }
            })
        elif method == "tools/list":
            send_response(req_id, {"tools": TOOLS_MANIFEST})
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            result_content = {}
            if tool_name == "collab_register":
                result_content = manager.register_agent(
                    agent_name=args.get("agent_name", "Anonymous Agent"),
                    role=args.get("role", "General Developer"),
                    preferred_id=args.get("preferred_id"),
                    repo_name=args.get("repo_name", ""),
                    repo_path=args.get("repo_path", "")
                )
            elif tool_name == "collab_unregister":
                result_content = manager.unregister_agent(
                    agent_id=args.get("agent_id", ""),
                    reason=args.get("reason", "Tarea finalizada / Desconexión")
                )
            elif tool_name == "collab_leave_note":
                result_content = manager.leave_note(
                    from_agent=args.get("from_agent", "unknown"),
                    to_agent=args.get("to_agent", "all"),
                    status=args.get("status", "MSG"),
                    module=args.get("module", "GENERAL"),
                    files=args.get("files", "NONE"),
                    locks=args.get("locks", "NONE"),
                    message=args.get("message", ""),
                    requirement=args.get("requirement", "")
                )
            elif tool_name == "collab_read_inbox":
                result_content = manager.read_inbox(
                    agent_id=args.get("agent_id", ""),
                    limit=args.get("limit", 10)
                )
            elif tool_name == "collab_acquire_lock":
                ttl = args.get("ttl_minutes", 15)
                try:
                    ttl = int(ttl)
                except Exception:
                    ttl = 15
                result_content = manager.acquire_lock(
                    agent_id=args.get("agent_id", ""),
                    resource_name=args.get("resource_name", ""),
                    reason=args.get("reason", ""),
                    ttl_minutes=ttl
                )
            elif tool_name == "collab_release_lock":
                result_content = manager.release_lock(
                    agent_id=args.get("agent_id", ""),
                    resource_name=args.get("resource_name", ""),
                    force=bool(args.get("force", False)),
                    reason=args.get("reason", "")
                )
            elif tool_name == "collab_get_status":
                result_content = manager.get_status()
            elif tool_name == "collab_publish_contract":
                result_content = manager.publish_contract(
                    contract_name=args.get("contract_name", ""),
                    contract_type=args.get("contract_type", "typescript"),
                    content=args.get("content", ""),
                    published_by=args.get("published_by", "unknown"),
                    repo_name=args.get("repo_name", "")
                )
            elif tool_name == "collab_inspect_contracts":
                result_content = manager.inspect_contracts(
                    filter_type=args.get("filter_type", "")
                )
            else:
                send_response(req_id, error={"code": -32601, "message": f"Tool '{tool_name}' no encontrada."})
                continue

            send_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_content, indent=2, ensure_ascii=False)
                    }
                ]
            })
        elif method == "notifications/initialized":
            # Confirmación de inicialización, no requiere respuesta
            pass
        else:
            send_response(req_id, error={"code": -32601, "message": f"Método '{method}' no soportado."})


def main():
    parser = argparse.ArgumentParser(description="Servidor MCP de Colaboración Multi-Agente (stdio)")
    parser.add_argument(
        "--channels-dir",
        type=str,
        default=os.environ.get("MCP_COLLAB_CHANNELS_DIR", str(DEFAULT_CHANNELS_DIR)),
        help="Directorio donde residen los archivos .md y el tablero compartido"
    )
    args = parser.parse_args()
    run_server(Path(args.channels_dir))


if __name__ == "__main__":
    main()
