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

## 🚀 Cómo Configurar en Clientes MCP

### 1. En Antigravity IDE / Gemini Agent (`mcp_config.json`):
```json
{
  "mcpServers": {
    "agent-collab": {
      "command": "python3",
      "args": [
        "/home/btcol/Projects/technoplash/mcp-agent-collab/server.py",
        "--channels-dir",
        "/home/btcol/Projects/technoplash/mcp-agent-collab/channels"
      ]
    }
  }
}
```

### 2. En Claude Code / Cursor / Cline:
Añade la misma definición a tu archivo de configuración de MCP habitual.

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
