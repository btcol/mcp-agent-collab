#!/usr/bin/env python3
"""
Test Suite for MCP Multi-Agent Collaboration Tool
Valida las 8 tools del servidor MCP mediante llamadas directas y protocolo JSON-RPC.
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = BASE_DIR / "server.py"
TEST_CHANNELS_DIR = BASE_DIR / "tests" / "sandbox_channels"

# Importar CollabManager directamente para pruebas unitarias rápidas
sys.path.insert(0, str(BASE_DIR))
from server import CollabManager, TOOLS_MANIFEST


class TestMCPCollabManager(unittest.TestCase):
    def setUp(self):
        if TEST_CHANNELS_DIR.exists():
            shutil.rmtree(TEST_CHANNELS_DIR)
        TEST_CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
        self.manager = CollabManager(TEST_CHANNELS_DIR)

    def tearDown(self):
        if TEST_CHANNELS_DIR.exists():
            shutil.rmtree(TEST_CHANNELS_DIR)

    def test_tools_manifest_has_all_tools(self):
        tool_names = [t["name"] for t in TOOLS_MANIFEST]
        expected = [
            "collab_register",
            "collab_unregister",
            "collab_leave_note",
            "collab_read_inbox",
            "collab_acquire_lock",
            "collab_release_lock",
            "collab_get_status",
            "collab_publish_contract",
            "collab_inspect_contracts"
        ]
        for name in expected:
            self.assertIn(name, tool_names, f"Falta la tool: {name}")

    def test_multi_agent_registration_with_repos(self):
        res1 = self.manager.register_agent("Antigravity", role="Frontend", repo_name="TecnoFlash-Web")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["agent_id"], "agente1")
        self.assertTrue((TEST_CHANNELS_DIR / "agente1.md").exists())

        res2 = self.manager.register_agent("btcol", role="Backend DB", repo_name="core-api")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["agent_id"], "agente2")
        self.assertTrue((TEST_CHANNELS_DIR / "agente2.md").exists())

        status = self.manager.get_status()
        self.assertIn("agente1", status["active_agents"])
        self.assertIn("agente2", status["active_agents"])
        self.assertEqual(status["active_agents"]["agente1"]["repoName"], "TecnoFlash-Web")
        self.assertEqual(status["active_agents"]["agente2"]["repoName"], "core-api")

    def test_cross_repo_contract_publish_and_inspect(self):
        self.manager.register_agent("btcol", role="Backend DB", repo_name="core-api")
        contract_body = "export interface CreateProductPayload { aliaddo: { code: string }; }"
        
        pub_res = self.manager.publish_contract(
            contract_name="CreateProductPayload",
            contract_type="typescript",
            content=contract_body,
            published_by="agente2",
            repo_name="core-api"
        )
        self.assertTrue(pub_res["success"])

        # Agente 1 en TecnoFlash-Web inspecciona contratos
        inspect_res = self.manager.inspect_contracts(filter_type="typescript")
        self.assertEqual(inspect_res["total_contracts"], 1)
        self.assertIn("CreateProductPayload", inspect_res["contracts"])
        self.assertEqual(inspect_res["contracts"]["CreateProductPayload"]["content"], contract_body)

    def test_atomic_locks_and_conflicts(self):
        self.manager.register_agent("Antigravity", preferred_id="agente1")
        self.manager.register_agent("btcol", preferred_id="agente2")

        # Agente 2 adquiere lock
        lock_res = self.manager.acquire_lock("agente2", "migration_0017", reason="Aplicando DDL en Postgres")
        self.assertTrue(lock_res["success"])

        # Agente 1 intenta adquirir el mismo lock y es rechazado
        lock_fail = self.manager.acquire_lock("agente1", "migration_0017", reason="Modificando schema")
        self.assertFalse(lock_fail["success"])
        self.assertEqual(lock_fail["locked_by"], "agente2")

        # Agente 2 libera el lock
        release_res = self.manager.release_lock("agente2", "migration_0017")
        self.assertTrue(release_res["success"])

        # Ahora Agente 1 puede adquirirlo
        lock_ok = self.manager.acquire_lock("agente1", "migration_0017", reason="Schema actualizado")
        self.assertTrue(lock_ok["success"])

    def test_forced_lock_release(self):
        self.manager.register_agent("Antigravity", preferred_id="agente1")
        self.manager.register_agent("btcol", preferred_id="agente2")

        # Agente 2 bloquea un recurso
        self.manager.acquire_lock("agente2", "CartStore.ts", reason="Refactor")

        # Agente 1 intenta liberarlo sin force -> falla
        rel_fail = self.manager.release_lock("agente1", "CartStore.ts", force=False)
        self.assertFalse(rel_fail["success"])

        # Agente 1 libera forzadamente -> éxito
        rel_ok = self.manager.release_lock("agente1", "CartStore.ts", force=True, reason="Agente 2 no responde")
        self.assertTrue(rel_ok["success"])
        self.assertTrue(rel_ok.get("forced"))

    def test_lock_ttl_expiration(self):
        self.manager.register_agent("Antigravity", preferred_id="agente1")
        self.manager.register_agent("btcol", preferred_id="agente2")

        # Simular un lock que expiró hace 5 minutos
        from datetime import datetime, timezone, timedelta
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%MZ")
        
        board = self.manager._load_board()
        board.setdefault("locks", {})["expired_resource"] = {
            "owner": "agente2",
            "acquiredAt": past_time,
            "expiresAt": past_time,
            "reason": "Lock viejo abandonado"
        }
        self.manager._save_board(board)

        # Agente 1 intenta adquirirlo: debe concederse automáticamente porque expiró
        res = self.manager.acquire_lock("agente1", "expired_resource", reason="Tomando control")
        self.assertTrue(res["success"])
        self.assertEqual(res["owner"], "agente1")

    def test_unregister_agent_and_auto_release_locks(self):
        self.manager.register_agent("Antigravity", preferred_id="agente1")
        self.manager.acquire_lock("agente1", "file_a.ts", reason="Edit A")
        self.manager.acquire_lock("agente1", "file_b.ts", reason="Edit B")

        # Desregistrar agente1
        unreg = self.manager.unregister_agent("agente1", reason="Sprint terminado")
        self.assertTrue(unreg["success"])
        self.assertIn("file_a.ts", unreg["released_locks"])
        self.assertIn("file_b.ts", unreg["released_locks"])

        status = self.manager.get_status()
        self.assertNotIn("agente1", status["active_agents"])
        self.assertNotIn("file_a.ts", status["current_locks"])
        self.assertNotIn("file_b.ts", status["current_locks"])

        # Verificar que el canal tiene la traza de sesión finalizada
        with open(TEST_CHANNELS_DIR / "agente1.md", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ST:DONE", content)
            self.assertIn("MOD:SESSION", content)
            self.assertIn("Sprint terminado", content)

    def test_cross_channel_leave_note_and_inbox(self):
        self.manager.register_agent("Antigravity", preferred_id="agente1")
        self.manager.register_agent("btcol", preferred_id="agente2")

        # Agente 1 escribe nota directa en el canal de Agente 2
        note_res = self.manager.leave_note(
            from_agent="agente1",
            to_agent="agente2",
            status="REQ",
            module="SHOP/CART",
            files="src/components/ShopApp.tsx",
            locks="NONE",
            message="¿Terminaste la Etapa 5 del carrito?",
            requirement="Confirmar para hacer build de storefront"
        )
        self.assertTrue(note_res["success"])

        # Verificar que se escribió en agente2.md
        with open(TEST_CHANNELS_DIR / "agente2.md", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ST:REQ", content)
            self.assertIn("FROM:agente1", content)
            self.assertIn("TO:agente2", content)
            self.assertIn("¿Terminaste la Etapa 5 del carrito?", content)

        # Agente 2 consulta su buzón
        inbox = self.manager.read_inbox("agente2")
        self.assertGreaterEqual(len(inbox["pending_messages"]), 1)
        self.assertEqual(inbox["pending_messages"][0]["from"], "agente1")


class TestMCPServerStdio(unittest.TestCase):
    """Prueba el servidor JSON-RPC 2.0 real vía subprocess stdio"""

    def test_stdio_jsonrpc_execution(self):
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "collab_get_status",
                "arguments": {}
            }}
        ]
        input_data = "\n".join(json.dumps(r) for r in reqs) + "\n"

        proc = subprocess.run(
            [sys.executable, str(SERVER_SCRIPT)],
            input=input_data,
            text=True,
            capture_output=True,
            check=True
        )

        lines = [line.strip() for line in proc.stdout.split("\n") if line.strip()]
        self.assertEqual(len(lines), 3)

        res1 = json.loads(lines[0])
        self.assertEqual(res1["result"]["serverInfo"]["name"], "mcp-agent-collab")

        res2 = json.loads(lines[1])
        self.assertEqual(len(res2["result"]["tools"]), 9)

        res3 = json.loads(lines[2])
        content_text = json.loads(res3["result"]["content"][0]["text"])
        self.assertIn("active_agents", content_text)


if __name__ == "__main__":
    unittest.main()
