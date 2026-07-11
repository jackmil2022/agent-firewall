from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_DIR

DB_FILE = "agent-firewall.sqlite3"


def snapshot_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma busy_timeout = 5000")
        connection.execute("pragma foreign_keys = on")
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.execute("pragma journal_mode = wal")
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

                create table if not exists discovered_mcp_tools (
                  agent_key text not null,
                  server_key text not null,
                  tool_name text not null,
                  input_schema text not null,
                  description text not null,
                  server_config_hash text,
                  discovered_at text not null,
                  primary key(agent_key, server_key, tool_name)
                );
                """
            )
            self._ensure_column(db, "runs", "flow_snapshot", "text")
            self._ensure_column(db, "runs", "state_json", "text")
            self._ensure_column(db, "runs", "parent_run_id", "text")
            self._ensure_column(db, "runs", "run_kind", "text not null default 'flow'")
            self._ensure_column(db, "runs", "test_case_id", "integer")
            self._ensure_column(db, "runs", "snapshot_hash", "text")
            self._ensure_column(db, "runs", "target_snapshot", "text")
            self._ensure_column(db, "runs", "target_snapshot_hash", "text")
            self._ensure_column(db, "runs", "execution_snapshot", "text")
            self._ensure_column(db, "runs", "execution_snapshot_hash", "text")
            self._ensure_column(db, "runs", "revision_id", "integer")
            self._ensure_column(db, "runs", "is_baseline", "integer not null default 0")
            self._ensure_column(db, "runs", "baseline_at", "text")
            self._ensure_column(db, "test_cases", "snapshot_hash", "text")
            self._ensure_column(db, "test_cases", "baseline_run_id", "text")
            self._ensure_column(db, "revisions", "test_case_id", "integer")
            self._ensure_column(db, "revisions", "snapshot_hash", "text")
            self._ensure_column(db, "revisions", "baseline_run_id", "text")
            self._ensure_column(db, "revisions", "candidate_run_id", "text")
            self._ensure_column(db, "revisions", "comparison_id", "integer")
            self._ensure_column(db, "revisions", "reviewed_at", "text")
            self._ensure_column(db, "revisions", "before_hash", "text")
            self._ensure_column(db, "revisions", "after_hash", "text")
            self._ensure_column(db, "run_comparisons", "snapshot_hash", "text")
            self._ensure_column(db, "run_comparisons", "revision_id", "integer")
            self._ensure_column(db, "discovered_mcp_tools", "server_config_hash", "text")
            self._backfill_test_case_hashes(db)

    @staticmethod
    def _ensure_column(db: sqlite3.Connection, table: str, column: str, sql_type: str) -> None:
        columns = {row["name"] for row in db.execute(f"pragma table_info({table})")}
        if column not in columns:
            db.execute(f"alter table {table} add column {column} {sql_type}")

    @staticmethod
    def _backfill_test_case_hashes(db: sqlite3.Connection) -> None:
        rows = db.execute("select * from test_cases where snapshot_hash is null").fetchall()
        for row in rows:
            value = dict(row)
            case_snapshot = {
                "name": value["name"],
                "target_type": value["target_type"],
                "target_ref": value["target_ref"],
                "goal": value["goal"],
                "input_json": json.loads(value["input_json"]),
                "assertions_json": json.loads(value["assertions_json"]),
            }
            db.execute(
                "update test_cases set snapshot_hash = ? where id = ?",
                (snapshot_hash(case_snapshot), value["id"]),
            )

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
        run_kind: str = "flow",
        test_case_id: int | None = None,
        snapshot_hash_value: str | None = None,
        target_snapshot: dict[str, Any] | None = None,
        target_snapshot_hash: str | None = None,
        execution_snapshot: dict[str, Any] | None = None,
        execution_snapshot_hash: str | None = None,
        revision_id: int | None = None,
    ) -> None:
        if run_kind not in {"flow", "test_case"}:
            raise ValueError(f"invalid run kind: {run_kind}")
        with self._connect() as db:
            db.execute(
                """
                insert into runs(
                  run_id, goal, flow_name, status, started_at, flow_snapshot, parent_run_id,
                  run_kind, test_case_id, snapshot_hash, target_snapshot, target_snapshot_hash, revision_id,
                  execution_snapshot, execution_snapshot_hash
                ) values(?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    goal,
                    flow_name,
                    now_iso(),
                    json.dumps(flow_snapshot, ensure_ascii=False),
                    parent_run_id,
                    run_kind,
                    test_case_id,
                    snapshot_hash_value,
                    json.dumps(target_snapshot, ensure_ascii=False) if target_snapshot is not None else None,
                    target_snapshot_hash,
                    revision_id,
                    json.dumps(execution_snapshot, ensure_ascii=False) if execution_snapshot is not None else None,
                    execution_snapshot_hash,
                ),
            )

    def log_event(self, run_id: str, event_type: str, payload: dict[str, Any], node_id: str | None = None) -> None:
        with self._connect() as db:
            run = db.execute("select status from runs where run_id = ?", (run_id,)).fetchone()
            if run and run["status"] == "cancelled" and not (
                event_type == "run_cancelled"
                or (event_type == "run_finished" and payload.get("status") == "cancelled")
            ):
                return
            db.execute(
                """
                insert into run_events(run_id, node_id, event_type, payload, created_at)
                values(?, ?, ?, ?, ?)
                """,
                (run_id, node_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
            )

    def finish_run(self, run_id: str, status: str, final_summary: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """
                update runs
                set status = ?, finished_at = ?, final_summary = ?
                where run_id = ? and status != 'cancelled'
                """,
                (status, now_iso(), final_summary, run_id),
            )
        return bool(cursor.rowcount)

    def cancel_run(self, run_id: str, reason: str = "cancelled by operator") -> dict[str, Any]:
        timestamp = now_iso()
        with self._connect() as db:
            cursor = db.execute(
                """
                update runs set status = 'cancelled', finished_at = ?, final_summary = ?
                where run_id = ? and status in ('running', 'needs_input', 'blocked')
                """,
                (timestamp, reason, run_id),
            )
            if cursor.rowcount:
                for event_type, payload in (
                    ("run_cancelled", {"reason": reason}),
                    ("run_finished", {"status": "cancelled", "summary": reason}),
                ):
                    db.execute(
                        """
                        insert into run_events(run_id, node_id, event_type, payload, created_at)
                        values(?, null, ?, ?, ?)
                        """,
                        (run_id, event_type, json.dumps(payload, ensure_ascii=False), timestamp),
                    )
        if not cursor.rowcount:
            run = self.get_run(run_id)
            if not run:
                raise ValueError(f"run not found: {run_id}")
            raise ValueError(f"run is not cancellable: {run_id} ({run['status']})")
        result = self.get_run_details(run_id)
        assert result is not None
        return result

    def save_checkpoint(self, run_id: str, state: dict[str, Any], *, status: str = "running") -> None:
        with self._connect() as db:
            db.execute(
                "update runs set status = ?, state_json = ? where run_id = ? and status != 'cancelled'",
                (status, json.dumps(state, ensure_ascii=False), run_id),
            )

    def reopen_run(self, run_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute(
                """
                update runs set status = 'running', finished_at = null
                where run_id = ? and status in ('needs_input', 'blocked', 'failed')
                """,
                (run_id,),
            )
        if not cursor.rowcount:
            raise ValueError(f"run is no longer resumable: {run_id}")

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
        for key in ("flow_snapshot", "state_json", "target_snapshot", "execution_snapshot"):
            result[key] = json.loads(result[key]) if result.get(key) else None
        result["is_baseline"] = bool(result.get("is_baseline", 0))
        return result

    def mark_run_baseline(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"run not found: {run_id}")
        if run.get("test_case_id") is None:
            raise ValueError("baseline must be a test case run")
        return self.set_test_case_baseline(int(run["test_case_id"]), run_id)

    def set_test_case_baseline(self, test_case_id: int, run_id: str) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("begin immediate")
            case = db.execute("select * from test_cases where id = ?", (test_case_id,)).fetchone()
            if not case:
                raise ValueError(f"test case not found: {test_case_id}")
            run = db.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
            if not run:
                raise ValueError(f"run not found: {run_id}")
            if (
                run["run_kind"] != "test_case"
                or run["status"] != "success"
                or run["test_case_id"] != test_case_id
                or not run["snapshot_hash"]
                or run["snapshot_hash"] != case["snapshot_hash"]
            ):
                raise ValueError("baseline must be a successful run of the current test case snapshot")
            timestamp = now_iso()
            db.execute(
                """
                update runs set is_baseline = 1, baseline_at = coalesce(baseline_at, ?)
                where run_id = ?
                """,
                (timestamp, run_id),
            )
            db.execute(
                "update test_cases set baseline_run_id = ? where id = ?",
                (run_id, test_case_id),
            )
        result = self.get_run(run_id)
        assert result is not None
        return result

    def save_test_case(self, value: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_iso()
        case_snapshot = {
            "name": value["name"],
            "target_type": value["target_type"],
            "target_ref": value["target_ref"],
            "goal": value["goal"],
            "input_json": value["input_json"],
            "assertions_json": value["assertions_json"],
        }
        case_hash = snapshot_hash(case_snapshot)
        fields = (
            value["name"],
            value["target_type"],
            value["target_ref"],
            value["goal"],
            json.dumps(value["input_json"], ensure_ascii=False),
            json.dumps(value["assertions_json"], ensure_ascii=False),
            case_hash,
        )
        with self._connect() as db:
            if value.get("id") is None:
                cursor = db.execute(
                    """
                    insert into test_cases(
                      name, target_type, target_ref, goal, input_json, assertions_json, snapshot_hash,
                      created_at, updated_at
                    ) values(?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                      snapshot_hash = ?, baseline_run_id = case
                        when snapshot_hash = ? then baseline_run_id else null
                      end, updated_at = ?
                    where id = ?
                    """,
                    (*fields, case_hash, timestamp, test_case_id),
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
                  target_type, target_ref, before_json, after_json, reason, status, created_at,
                  test_case_id, snapshot_hash, baseline_run_id, before_hash, after_hash
                ) values(?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)
                """,
                (
                    value["target_type"],
                    value["target_ref"],
                    json.dumps(value["before_json"], ensure_ascii=False),
                    json.dumps(value["after_json"], ensure_ascii=False),
                    value["reason"],
                    now_iso(),
                    value.get("test_case_id"),
                    value.get("snapshot_hash"),
                    value.get("baseline_run_id"),
                    value.get("before_hash"),
                    value.get("after_hash"),
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

    def transition_revision_status(self, revision_id: int, expected: str, status: str) -> dict[str, Any]:
        if status not in {"draft", "applied", "reverted"}:
            raise ValueError(f"invalid revision status: {status}")
        with self._connect() as db:
            cursor = db.execute(
                """
                update revisions
                set status = ?, applied_at = case
                  when ? = 'applied' then coalesce(applied_at, ?)
                  else applied_at
                end
                where id = ? and status = ?
                  and (? != 'applied' or reviewed_at is not null)
                """,
                (status, status, now_iso(), revision_id, expected, status),
            )
        if not cursor.rowcount:
            revision = self.get_revision(revision_id)
            if not revision:
                raise ValueError(f"revision not found: {revision_id}")
            raise ValueError(f"revision status changed: {revision_id} ({revision['status']})")
        result = self.get_revision(revision_id)
        assert result is not None
        return result

    def bind_revision_candidate(self, revision_id: int, run_id: str) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                """
                update revisions set candidate_run_id = ?, comparison_id = null, reviewed_at = null
                where id = ? and status = 'draft'
                """,
                (run_id, revision_id),
            )
        if not cursor.rowcount:
            raise ValueError(f"draft revision not found: {revision_id}")
        result = self.get_revision(revision_id)
        assert result is not None
        return result

    def mark_revision_reviewed(
        self, revision_id: int, comparison_id: int, candidate_run_id: str | None = None
    ) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                """
                update revisions set comparison_id = ?, reviewed_at = ?
                where id = ? and status = 'draft'
                  and (? is null or candidate_run_id = ?)
                """,
                (comparison_id, now_iso(), revision_id, candidate_run_id, candidate_run_id),
            )
        if not cursor.rowcount:
            raise ValueError(f"draft revision not found: {revision_id}")
        result = self.get_revision(revision_id)
        assert result is not None
        return result

    def save_comparison(self, value: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                """
                insert into run_comparisons(
                  baseline_run_id, candidate_run_id, result_json, created_at, snapshot_hash, revision_id
                ) values(?, ?, ?, ?, ?, ?)
                """,
                (
                    value["baseline_run_id"],
                    value["candidate_run_id"],
                    json.dumps(value["result_json"], ensure_ascii=False),
                    now_iso(),
                    value.get("snapshot_hash"),
                    value.get("revision_id"),
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

    def replace_discovered_mcp_tools(
        self,
        agent_key: str,
        server_key: str,
        tools: list[dict[str, Any]],
        *,
        server_config_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        discovered_at = now_iso()
        if server_config_hash is None:
            config = self.get_config() or {}
            server_config = (
                ((config.get("agents") or {}).get(agent_key) or {}).get("mcp_servers") or {}
            ).get(server_key)
            server_config_hash = snapshot_hash(server_config) if isinstance(server_config, dict) else None
        with self._connect() as db:
            db.execute(
                "delete from discovered_mcp_tools where agent_key = ? and server_key = ?",
                (agent_key, server_key),
            )
            db.executemany(
                """
                insert into discovered_mcp_tools(
                  agent_key, server_key, tool_name, input_schema, description, server_config_hash, discovered_at
                ) values(?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        agent_key,
                        server_key,
                        str(tool.get("tool_name") or tool["name"]),
                        json.dumps(tool.get("input_schema") or {}, ensure_ascii=False),
                        str(tool.get("description") or ""),
                        server_config_hash,
                        discovered_at,
                    )
                    for tool in tools
                ],
            )
        return self.list_discovered_mcp_tools(agent_key=agent_key, server_key=server_key)

    def list_discovered_mcp_tools(
        self,
        *,
        agent_key: str | None = None,
        server_key: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[str] = []
        if agent_key is not None:
            clauses.append("agent_key = ?")
            params.append(agent_key)
        if server_key is not None:
            clauses.append("server_key = ?")
            params.append(server_key)
        where = f" where {' and '.join(clauses)}" if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                f"select * from discovered_mcp_tools{where} order by agent_key, server_key, tool_name",
                params,
            ).fetchall()
        return [self._decode_row(row, "input_schema") for row in rows]

    def get_discovered_mcp_tool(
        self, agent_key: str, server_key: str, tool_name: str
    ) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """
                select * from discovered_mcp_tools
                where agent_key = ? and server_key = ? and tool_name = ?
                """,
                (agent_key, server_key, tool_name),
            ).fetchone()
        return self._decode_row(row, "input_schema") if row else None
