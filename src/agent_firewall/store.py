from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_DIR

DB_FILE = "agent-firewall.sqlite3"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / APP_DIR / DB_FILE


class AgentFirewallStore:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.path = db_path(self.workspace)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                create table if not exists config (
                  key text primary key,
                  value text not null,
                  updated_at text not null
                );

                create table if not exists flows (
                  name text primary key,
                  value text not null,
                  updated_at text not null
                );

                create table if not exists runs (
                  run_id text primary key,
                  goal text not null,
                  flow_name text not null,
                  status text not null,
                  started_at text not null,
                  finished_at text,
                  final_summary text
                );

                create table if not exists run_events (
                  id integer primary key autoincrement,
                  run_id text not null,
                  node_id text,
                  event_type text not null,
                  payload text not null,
                  created_at text not null,
                  foreign key(run_id) references runs(run_id)
                );
                """
            )

    def get_config(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select value from config where key = ?", ("app",)).fetchone()
        return json.loads(row["value"]) if row else None

    def save_config(self, value: dict[str, Any]) -> None:
        timestamp = now_iso()
        with self._connect() as db:
            db.execute(
                """
                insert into config(key, value, updated_at)
                values('app', ?, ?)
                on conflict(key) do update set
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (json.dumps(value, ensure_ascii=False), timestamp),
            )

    def get_flow(self, name: str = "default") -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select value from flows where name = ?", (name,)).fetchone()
        return json.loads(row["value"]) if row else None

    def save_flow(self, value: dict[str, Any], name: str = "default") -> None:
        timestamp = now_iso()
        with self._connect() as db:
            db.execute(
                """
                insert into flows(name, value, updated_at)
                values(?, ?, ?)
                on conflict(name) do update set
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (name, json.dumps(value, ensure_ascii=False), timestamp),
            )

    def create_run(self, run_id: str, goal: str, flow_name: str) -> None:
        with self._connect() as db:
            db.execute(
                """
                insert into runs(run_id, goal, flow_name, status, started_at)
                values(?, ?, ?, 'running', ?)
                """,
                (run_id, goal, flow_name, now_iso()),
            )

    def log_event(self, run_id: str, event_type: str, payload: dict[str, Any], node_id: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                """
                insert into run_events(run_id, node_id, event_type, payload, created_at)
                values(?, ?, ?, ?, ?)
                """,
                (run_id, node_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
            )

    def finish_run(self, run_id: str, status: str, final_summary: str) -> None:
        with self._connect() as db:
            db.execute(
                """
                update runs
                set status = ?, finished_at = ?, final_summary = ?
                where run_id = ?
                """,
                (status, now_iso(), final_summary, run_id),
            )
