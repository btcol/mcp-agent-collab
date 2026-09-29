# 🤝 MCP Multi-Agent Collaboration Tool (`mcp-agent-collab`)

Servidor MCP universal (Model Context Protocol) sobre `stdio` en Python para habilitar la **cooperación autónoma, resolución de conflictos y asignación dinámica de tareas** entre múltiples agentes de IA (Antigravity, btcol, Claude Code, Cursor, Cline, etc.).

---

## 🌟 Características Principales

1. **Canales Desacoplados y Dinámicos (`agente1.md`, `agente2.md`, ... `agenteN.md`)**:
   - Cada agente que se conecta reclama un canal por orden de llegada o según el rol acordado (`collab_register`).
   - Los agentes pueden leer y escribir directamente en los canales de sus compañeros (`collab_leave_note`), permitiendo dejar recados explícitos sin supervisión humana.
2. **Tablero Atómico de Presencia y Locks (`channels/shared_board.json`)**:
   - Mecanismo de semáforo (`collab_acquire_lock` / `collab_release_lock`) para evitar colisiones concurrentes sobre archivos, esquemas de BD o migraciones.
3. **Protocolo de Tokens Compacto**:
   - Sintaxis estandarizada `[TIMESTAMP] ST:... | FROM:... | TO:... | MOD:... | LOCKS:... | MSG:...` que optimiza el consumo de contexto.
4. **Demonio Watcher en Background (`watcher.py`)**:
   - Detecta al instante recados cruzados y emite alertas para reactivar a los modelos.
5. **Portabilidad Total**:
   - Se puede ejecutar en cualquier proyecto o ruta del sistema pasando `--channels-dir` o mediante la variable de entorno `MCP_COLLAB_CHANNELS_DIR`.

---

## 🛠️ Herramientas MCP Disponibles

| Tool | Descripción | Parámetros Clave |
| :--- | :--- | :--- |
| `collab_register` | Registra al agente, su repo y le asigna su canal. | `agent_name`, `role`, `preferred_id`, `repo_name`, `repo_path` |
| `collab_unregister` | Cierra sesión limpiamente y libera en bloque todos sus locks. | `agent_id`, `reason` |
| `collab_leave_note` | Deja un recado en el canal de otro agente. | `from_agent`, `to_agent`, `status`, `module`, `files`, `locks`, `message`, `requirement` |
| `collab_read_inbox` | Consulta los mensajes pendientes para este agente. | `agent_id`, `limit` |
| `collab_acquire_lock` | Adquiere un lock exclusivo con TTL de expiración automática. | `agent_id`, `resource_name`, `reason`, `ttl_minutes` (def: 15) |
| `collab_release_lock` | Libera un lock (con opción de liberación forzada si el dueño crasheó). | `agent_id`, `resource_name`, `force` (def: false), `reason` |
| `collab_get_status` | Devuelve el estado general del tablero, agentes activos y purga locks expirados. | *(sin parámetros)* |
| `collab_publish_contract` | Publica interfaces (TypeScript, OpenAPI, etc.) cross-repo. | `contract_name`, `contract_type`, `content`, `published_by`, `repo_name` |
| `collab_inspect_contracts` | Consulta contratos publicados por otros repositorios. | `filter_type` |

---

## 📜 Protocolo de Colaboración Multi-Agente (Instrucciones para Agentes)

Puedes copiar y pegar este bloque en el prompt de sistema del agente o en su archivo `AGENT.md` / `CLAUDE.md`:

```markdown
Protocolo de Colaboración Multi-Agente: Tienes a tu disposición las herramientas MCP de agent-collab para coordinarte con los otros agentes que trabajan en este u otros repositorios:

1- Al iniciar una tarea: Ejecuta collab_register(agent_name="<TuNombre>", role="<TuRol>", repo_name="<NombreDelRepo>"). El servidor te asignará un ID (ej: agente2).
2- Para ver quién está conectado y qué recursos están tomados: Ejecuta collab_get_status().
3- Antes de modificar un archivo o migración crítica: Ejecuta collab_acquire_lock(agent_id="<TuID>", resource_name="<archivo_o_tabla>", reason="...", ttl_minutes=15) para evitar que otro agente lo modifique al mismo tiempo.
4- Para revisar mensajes pendientes o avances de tus compañeros: Ejecuta collab_read_inbox(agent_id="<TuID>").
5- Para notificar avances o pedir confirmaciones: Ejecuta collab_leave_note(from_agent="<TuID>", to_agent="<agenteReceptor_o_all>", status="WIP|DONE|REQ", module="...", message="...").
6- Si necesitas interfaces de otro repo: Consulta con collab_inspect_contracts() o publica las tuyas con collab_publish_contract().
7- Al terminar tu trabajo o cerrar la sesión: Ejecuta siempre collab_unregister(agent_id="<TuID>", reason="Tarea finalizada") para liberar automáticamente todos tus locks.
```

---

## 🚀 Cómo Configurar en Clientes MCP

### 1. En Antigravity IDE / Gemini Agent (`mcp_config.json`):
```json
{
  "mcpServers": {
    "agent-collab": {
      "command": "/home/btcol/.local/bin/mcp-agent-collab",
      "args": [
        "--channels-dir",
        "/home/btcol/Projects/technoplash/mcp-agent-collab/channels"
      ]
    }
  }
}
```

### 2. En Codex CLI:
```bash
codex mcp add agent-collab -- /home/btcol/.local/bin/mcp-agent-collab --channels-dir /home/btcol/Projects/technoplash/mcp-agent-collab/channels
```

### 3. En Zed Editor (`~/.config/zed/settings.json`):
```json
{
  "context_servers": {
    "agent-collab": {
      "command": "/home/btcol/.local/bin/mcp-agent-collab",
      "args": [
        "--channels-dir",
        "/home/btcol/Projects/technoplash/mcp-agent-collab/channels"
      ]
    }
  }
}
```

### 4. En Claude Code (CLI):
```bash
claude mcp add -s user agent-collab -- /home/btcol/.local/bin/mcp-agent-collab --channels-dir /home/btcol/Projects/technoplash/mcp-agent-collab/channels
```

### 5. En Cursor (`~/.cursor/mcp.json` o Settings -> MCP):
```json
{
  "mcpServers": {
    "agent-collab": {
      "command": "/home/btcol/.local/bin/mcp-agent-collab",
      "args": [
        "--channels-dir",
        "/home/btcol/Projects/technoplash/mcp-agent-collab/channels"
      ]
    }
  }
}
```

---

## 📁 Estructura del Paquete

```text
mcp-agent-collab/
├── README.md               # Esta documentación
├── server.py               # Servidor MCP JSON-RPC 2.0 stdio
├── watcher.py              # Demonio de monitoreo de canales
├── pyproject.toml          # Configuración de paquete Python
├── examples/               # Ejemplos de configuración
│   └── mcp_config.json
└── channels/               # Directorio de canales y tablero
    ├── agente1.md          # Historial y canal de Agente 1
    ├── agente2.md          # Historial y canal de Agente 2
    └── shared_board.json   # Registro atómico de presencia y locks
```
