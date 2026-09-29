#!/usr/bin/env python3
"""
MCP Multi-Agent Collaboration Watcher Daemon
--------------------------------------------
Monitorea en tiempo real los canales Markdown (agente1.md, agente2.md, ... agenteN.md)
en el directorio de canales configurado.
Detecta nuevas líneas insertadas o recados cruzados y los sincroniza en el tablero compartido.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_CHANNELS_DIR = Path(__file__).resolve().parent / "channels"

TOKEN_LOG_REGEX = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+"
    r"ST:(?P<status>[A-Z_]+)\s*\|\s*"
    r"(?:FROM:(?P<from_agent>[^|]+)\|\s*)?"
    r"(?:TO:(?P<to_agent>[^|]+)\|\s*)?"
    r"(?:MOD:(?P<mod>[^|]+)\|\s*)?"
    r"(?:RW:(?P<rw>[^|]+)\|\s*)?"
    r"(?:F(?:ILES)?:(?P<files>[^|]+)\|\s*)?"
    r"(?:DB:(?P<db>[^|]+)\|\s*)?"
    r"(?:(?:I|MSG):(?P<msg>[^|]+)\|\s*)?"
    r"(?:LOCKS?:(?P<locks>[^|]+)\|\s*)?"
    r"(?:REQ(?:_RESP)?:(?P<req>[^|\n]+))?",
    re.IGNORECASE,
)


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MultiAgentWatcher:
    def __init__(self, channels_dir: Path, interval: float = 2.0, notify_desktop: bool = True):
        self.channels_dir = Path(channels_dir)
        self.interval = interval
        self.notify_desktop = notify_desktop
        self.state_file = self.channels_dir / ".watcher_state.json"
        self.state: Dict[str, dict] = {}
        self.load_state()

    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}

    def save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def scan_channels(self) -> List[dict]:
        if not self.channels_dir.exists():
            return []

        all_events = []
        md_files = sorted(self.channels_dir.glob("*.md"))

        for fpath in md_files:
            key = fpath.name
            mtime = os.stat(fpath).st_mtime
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            content = "".join(lines)
            file_hash = compute_sha256(content)

            prev_info = self.state.get(key)
            if not prev_info:
                seen = [compute_sha256(l.strip()) for l in lines if l.strip()]
                self.state[key] = {
                    "mtime": mtime,
                    "hash": file_hash,
                    "seen_hashes": seen,
                    "last_seen_iso": datetime.now().isoformat(),
                }
                continue

            if prev_info.get("hash") == file_hash:
                continue

            seen_hashes = set(prev_info.get("seen_hashes", []))
            new_seen = list(seen_hashes)

            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("#") or line_str.startswith(">"):
                    continue

                h = compute_sha256(line_str)
                if h in seen_hashes:
                    continue

                new_seen.append(h)
                match = TOKEN_LOG_REGEX.match(line_str)
                data = match.groupdict() if match else {}

                event = {
                    "timestamp": data.get("timestamp") or datetime.now().isoformat(),
                    "file": key,
                    "raw_line": line_str,
                    "from_agent": data.get("from_agent") or key.replace(".md", ""),
                    "to_agent": data.get("to_agent") or "all",
                    "status": data.get("status") or "MSG",
                    "locks": data.get("locks") or "NONE",
                    "req": data.get("req") or "",
                    "msg": data.get("msg") or line_str,
                    "files": data.get("files") or "",
                }
                all_events.append(event)

            self.state[key] = {
                "mtime": mtime,
                "hash": file_hash,
                "seen_hashes": new_seen,
                "last_seen_iso": datetime.now().isoformat(),
            }

        self.save_state()
        return all_events

    def notify(self, event: dict):
        banner = "=" * 80
        print(f"\n{banner}", flush=True)
        print(f"🚨 [MCP COLLAB ALERT] {event['from_agent']} -> {event['to_agent']}", flush=True)
        print(f"📄 Canal: {event['file']} | ⏱️  {event['timestamp']}", flush=True)
        print(f"🚦 Estado: ST:{event['status']} | LOCKS: {event['locks']}", flush=True)
        if event.get("files"):
            print(f"📁 Afecta: {event['files']}", flush=True)
        print(f"💬 Mensaje: {event['msg']}", flush=True)
        if event.get("req"):
            print(f"👉 Requerimiento: {event['req']}", flush=True)
        print(f"{banner}\n", flush=True)

        if self.notify_desktop and shutil.which("notify-send"):
            try:
                subprocess.run(
                    ["notify-send", "-a", "MCP-Agent-Collab", f"Recado de {event['from_agent']}", event['msg'][:100]],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

    def run_loop(self):
        print(f"👁️  MCP Collab Watcher iniciado sobre: {self.channels_dir}")
        print(f"   Monitoreando cada {self.interval}s. Presiona Ctrl+C para salir.\n", flush=True)
        try:
            while True:
                events = self.scan_channels()
                for ev in events:
                    self.notify(ev)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n🛑 Watcher detenido.")


def main():
    parser = argparse.ArgumentParser(description="Demonio de monitoreo multi-agente MCP")
    parser.add_argument("--channels-dir", type=str, default=str(DEFAULT_CHANNELS_DIR), help="Directorio de canales .md")
    parser.add_argument("--interval", type=float, default=2.0, help="Intervalo en segundos")
    parser.add_argument("--no-desktop", action="store_true", help="Deshabilitar notify-send")
    parser.add_argument("--once", action="store_true", help="Escanear una sola vez y salir")

    args = parser.parse_args()
    watcher = MultiAgentWatcher(
        channels_dir=Path(args.channels_dir),
        interval=args.interval,
        notify_desktop=not args.no_desktop
    )

    if args.once:
        events = watcher.scan_channels()
        print(f"Escaneo finalizado. {len(events)} eventos nuevos.")
        for ev in events:
            watcher.notify(ev)
    else:
        watcher.run_loop()


if __name__ == "__main__":
    main()
