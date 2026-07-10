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
                  final_summary text,
                  flow_snapshot text,
                  state_json text,
                  parent_run_id text
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

                create table if not exists test_cases (
                  id integer primary key autoincrement,
                  name text not null,
                  target_type text not null,
                  target_ref text not null,
                  goal text not null,
                  input_json text not null,
                  assertions_json text not null,
                  created_at text not null,
                  updated_at text not null
                );

                create table if not exists revisions (
                  id integer primary key autoincrement,
                  target_type text not null,
                  target_ref text not null,
                  before_json text not null,
                  after_json text not null,
                  reason text not null,
                  status text not null check(status in ('draft', 'applied', 'reverted')),
                  created_at text not null,
                  applied_at text
                );

                create table if not exists run_comparisons (
                  id integer primary key autoincrement,
                  baseline_run_id text not null,
                  candidate_run_id text not null,
                  result_json text not null,
                  created_at text not null
                );
                """
            )
            self._ensure_column(db, "runs", "flow_snapshot", "text")
            self._ensure_column(db, "runs", "state_json", "text")
            self._ensure_column(db, "runs", "parent_run_id", "text")

    @staticmethod
    def _ensure_column(db: sqlite3.Connection, table: str, column: str, sql_type: str) -> None:
        columns = {row["name"] for row in db.execute(f"pragma table_info({table})")}
        if column not in columns:
            db.execute(f"alter table {table} add column {column} {sql_type}")

    @staticmethod
    def _decode_row(row: sqlite3.Row, *json_fields: str) -> dict[str, Any]:
        result = dict(row)
        for field in json_fields:
            result[field] = json.loads(result[field])
        return result

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

    def create_run(
        self,
        run_id: str,
        goal: str,
        flow_name: str,
        flow_snapshot: dict[str, Any],
        *,
        parent_run_id: str | None = None,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                insert into runs(run_id, goal, flow_name, status, started_at, flow_snapshot, parent_run_id)
                values(?, ?, ?, 'running', ?, ?, ?)
                """,
                (run_id, goal, flow_name, now_iso(), json.dumps(flow_snapshot, ensure_ascii=False), parent_run_id),
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

    def save_checkpoint(self, run_id: str, state: dict[str, Any], *, status: str = "running") -> None:
        with self._connect() as db:
            db.execute(
                "update runs set status = ?, state_json = ? where run_id = ?",
                (status, json.dumps(state, ensure_ascii=False), run_id),
            )

    def reopen_run(self, run_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "update runs set status = 'running', finished_at = null where run_id = ?",
                (run_id,),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
        return self._decode_run(row) if row else None

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "select * from runs order by started_at desc, rowid desc limit ?",
                (max(0, limit),),
            ).fetchall()
        return [self._decode_run(row) for row in rows]

    def get_run_details(self, run_id: str) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        return {**run, "events": self.list_events(run_id)} if run else None

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                select id, run_id, node_id, event_type, payload, created_at
                from run_events where run_id = ? order by id
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]

    @staticmethod
    def _decode_run(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in ("flow_snapshot", "state_json"):
            result[key] = json.loads(result[key]) if result.get(key) else None
        return result

    def save_test_case(self, value: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_iso()
        fields = (
            value["name"],
            value["target_type"],
            value["target_ref"],
            value["goal"],
            json.dumps(value["input_json"], ensure_ascii=False),
            json.dumps(value["assertions_json"], ensure_ascii=False),
        )
        with self._connect() as db:
            if value.get("id") is None:
                cursor = db.execute(
                    """
                    insert into test_cases(
                      name, target_type, target_ref, goal, input_json, assertions_json, created_at, updated_at
                    ) values(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*fields, timestamp, timestamp),
                )
                test_case_id = cursor.lastrowid
            else:
                test_case_id = value["id"]
                cursor = db.execute(
                    """
                    update test_cases set
                      name = ?, target_type = ?, target_ref = ?, goal = ?, input_json = ?, assertions_json = ?,
                      updated_at = ?
                    where id = ?
                    """,
                    (*fields, timestamp, test_case_id),
                )
                if not cursor.rowcount:
                    raise KeyError(f"test case not found: {test_case_id}")
        result = self.get_test_case(test_case_id)
        assert result is not None
        return result

    def list_test_cases(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("select * from test_cases order by updated_at desc, id desc").fetchall()
        return [self._decode_row(row, "input_json", "assertions_json") for row in rows]

    def get_test_case(self, test_case_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select * from test_cases where id = ?", (test_case_id,)).fetchone()
        return self._decode_row(row, "input_json", "assertions_json") if row else None

    def delete_test_case(self, test_case_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute("delete from test_cases where id = ?", (test_case_id,))
        return bool(cursor.rowcount)

    def create_revision(self, value: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                """
                insert into revisions(
                  target_type, target_ref, before_json, after_json, reason, status, created_at
                ) values(?, ?, ?, ?, ?, 'draft', ?)
                """,
                (
                    value["target_type"],
                    value["target_ref"],
                    json.dumps(value["before_json"], ensure_ascii=False),
                    json.dumps(value["after_json"], ensure_ascii=False),
                    value["reason"],
                    now_iso(),
                ),
            )
            revision_id = cursor.lastrowid
        result = self.get_revision(revision_id)
        assert result is not None
        return result

    def get_revision(self, revision_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select * from revisions where id = ?", (revision_id,)).fetchone()
        return self._decode_row(row, "before_json", "after_json") if row else None

    def list_revisions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("select * from revisions order by created_at desc, id desc").fetchall()
        return [self._decode_row(row, "before_json", "after_json") for row in rows]

    def update_revision_status(self, revision_id: int, status: str) -> dict[str, Any] | None:
        if status not in {"draft", "applied", "reverted"}:
            raise ValueError(f"invalid revision status: {status}")
        with self._connect() as db:
            db.execute(
                """
                update revisions
                set status = ?, applied_at = case
                  when ? = 'applied' then coalesce(applied_at, ?)
                  else applied_at
                end
                where id = ?
                """,
                (status, status, now_iso(), revision_id),
            )
        return self.get_revision(revision_id)

    def save_comparison(self, value: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                """
                insert into run_comparisons(baseline_run_id, candidate_run_id, result_json, created_at)
                values(?, ?, ?, ?)
                """,
                (
                    value["baseline_run_id"],
                    value["candidate_run_id"],
                    json.dumps(value["result_json"], ensure_ascii=False),
                    now_iso(),
                ),
            )
            comparison_id = cursor.lastrowid
        result = self.get_comparison(comparison_id)
        assert result is not None
        return result

    def list_comparisons(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("select * from run_comparisons order by created_at desc, id desc").fetchall()
        return [self._decode_row(row, "result_json") for row in rows]

    def get_comparison(self, comparison_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("select * from run_comparisons where id = ?", (comparison_id,)).fetchone()
        return self._decode_row(row, "result_json") if row else None
