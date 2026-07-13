from __future__ import annotations

import argparse
import asyncio
import json
import runpy
import sys
from pathlib import Path

from .acp import serve_acp
from .browser import browser_smoke
from .capabilities import discover_mcp_tools, list_capabilities
from .config import APP_DIR, AgentFirewallConfig, ConfigError, load_config, load_config_mapping, normalize_config_mapping, write_default_config
from .engine import EngineError, build_agent_sync, probe_model_connection
from .flow import FlowError, load_flow, preflight_flow, save_flow
from .imports import import_local_skill
from .runner import RunnerError, resume_flow, run_flow
from .revisions import apply_revision, create_revision, review_revision, revert_revision
from .skills import install_bundled_skills, list_skill_manifests
from .store import AgentFirewallStore
from .workbench import compare_test_runs, run_test_case, save_test_case, set_test_run_baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-firewall")
    parser.add_argument("--workspace", default=".", help="Workspace root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize config and bundled skills.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite generated config and bundled skills.")

    doctor_parser = subparsers.add_parser("doctor", help="Validate config, skills, and engine imports.")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable output.")

    subparsers.add_parser("skills", help="List configured skills.")

    agent_parser = subparsers.add_parser("agent", help="Create the configured deepagents instance.")
    agent_parser.add_argument("--name", help="Agent config key. Defaults to active_agent.")

    acp_parser = subparsers.add_parser("acp", help="Serve the configured agent over ACP.")
    acp_parser.add_argument("--name", help="Agent config key. Defaults to active_agent.")
    acp_parser.add_argument("--runner", action="store_true", help="Serve the sqlite-backed flow runner over ACP.")
    acp_parser.add_argument("--goal", default="Run the configured Agent Firewall flow.")

    run_parser = subparsers.add_parser("run", help="Run the configured flow and persist logs to sqlite.")
    run_parser.add_argument("--goal", default="Run the configured Agent Firewall flow.")
    run_parser.add_argument("--flow-name", default="default")
    run_parser.add_argument("--flow-path", help="Read a flow JSON file instead of sqlite.")
    run_parser.add_argument("--run-id", help="Use a caller-provided run id for polling and cancellation.")

    resume_parser = subparsers.add_parser("resume", help="Resume a paused flow run.")
    resume_parser.add_argument("--run-id", required=True)
    resume_parser.add_argument("--correction", default="")

    flow_save_parser = subparsers.add_parser("flow-save", help="Save a flow JSON document to sqlite.")
    flow_save_parser.add_argument("--name", default="default")
    flow_save_parser.add_argument("--file", help="Read flow JSON from file. Defaults to stdin.")

    workspace_parser = subparsers.add_parser("workspace-json", help="Print desktop workspace state from sqlite.")
    workspace_parser.add_argument("--flow-name", default="default")

    config_export_parser = subparsers.add_parser("config-export", help="Print sqlite config as JSON.")
    config_export_parser.add_argument("--output", help="Write JSON to a file instead of stdout.")

    config_save_parser = subparsers.add_parser("config-save", help="Save config JSON to sqlite.")
    config_save_parser.add_argument("--file", help="Read config JSON from file. Defaults to stdin.")
    subparsers.add_parser("model-test", help="Send a minimal request to the global model.")

    test_case_save_parser = subparsers.add_parser("test-case-save", help="Save a workbench test case.")
    test_case_save_parser.add_argument("--file", help="Read test case JSON from file. Defaults to stdin.")
    test_case_run_parser = subparsers.add_parser("test-case-run", help="Run a saved workbench test case.")
    test_case_run_parser.add_argument("--id", type=int, required=True)
    test_case_run_parser.add_argument("--baseline-run-id")
    test_case_run_parser.add_argument("--revision-id", type=int)
    test_case_run_parser.add_argument("--run-id")
    test_case_run_parser.add_argument("--approved", action="store_true")
    baseline_parser = subparsers.add_parser("test-case-baseline-set", help="Set a successful run as the current baseline.")
    baseline_parser.add_argument("--id", type=int, required=True)
    baseline_parser.add_argument("--run-id", required=True)
    subparsers.add_parser("workbench-json", help="Print capability, case, run, revision, and comparison state.")
    run_json_parser = subparsers.add_parser("run-json", help="Print one run and its persisted events.")
    run_json_parser.add_argument("--run-id", required=True)
    run_cancel_parser = subparsers.add_parser("run-cancel", help="Finalize an active run as cancelled.")
    run_cancel_parser.add_argument("--run-id", required=True)
    preflight_parser = subparsers.add_parser("flow-preflight", help="Validate a flow and return structured issues.")
    preflight_parser.add_argument("--file", help="Read flow JSON from file. Defaults to stdin.")
    discover_parser = subparsers.add_parser("mcp-tools", help="Discover tools exposed by a configured MCP server.")
    discover_parser.add_argument("--agent", required=True)
    discover_parser.add_argument("--server", required=True)
    discover_parser.add_argument("--approved", action="store_true")
    import_parser = subparsers.add_parser("capability-import-local", help="Import a local Skill directory into the managed library.")
    import_parser.add_argument("--source", required=True)
    compare_parser = subparsers.add_parser("run-compare", help="Compare candidate and baseline test runs.")
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--candidate", required=True)
    revision_create_parser = subparsers.add_parser("revision-create", help="Create an auditable draft revision.")
    revision_create_parser.add_argument("--file", help="Read revision JSON from file. Defaults to stdin.")
    revision_review_parser = subparsers.add_parser("revision-review", help="Review a passing revision comparison.")
    revision_review_parser.add_argument("--id", type=int, required=True)
    revision_review_parser.add_argument("--comparison-id", type=int, required=True)
    revision_apply_parser = subparsers.add_parser("revision-apply", help="Apply a reviewed revision.")
    revision_apply_parser.add_argument("--id", type=int, required=True)
    revision_revert_parser = subparsers.add_parser("revision-revert", help="Revert an applied revision.")
    revision_revert_parser.add_argument("--id", type=int, required=True)
    internal_script_parser = subparsers.add_parser("_script-run", help=argparse.SUPPRESS)
    internal_script_parser.add_argument("--file", required=True)

    browser_parser = subparsers.add_parser("browser-smoke", help="Run the initialized browser-control skill smoke test.")
    browser_parser.add_argument("--headed", action="store_true", help="Open a visible browser window.")
    browser_parser.add_argument("--install-browser", action="store_true", help="Install Playwright Chromium first.")

    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()

    try:
        if args.command == "init":
            cfg = write_default_config(workspace, force=args.force)
            skills = install_bundled_skills(workspace, force=args.force)
            print(f"initialized sqlite database: {cfg}")
            print(f"initialized skills: {skills}")
            return 0
        if args.command == "doctor":
            return _doctor(workspace, as_json=args.json)
        if args.command == "skills":
            skills_root = workspace / ".agent-firewall" / "skills"
            for item in list_skill_manifests(skills_root):
                print(f"{item.name}\t{item.path}\t{item.description}")
            return 0
        if args.command == "agent":
            config = load_config(workspace=workspace)
            agent = build_agent_sync(config, args.name)
            print(f"created deep agent: {agent!r}")
            return 0
        if args.command == "acp":
            config = load_config(workspace=workspace)
            asyncio.run(serve_acp(config, args.name, runner=args.runner, goal=args.goal))
            return 0
        if args.command == "run":
            config = load_config(workspace=workspace)
            result = run_flow(
                config,
                goal=args.goal,
                flow_name=args.flow_name,
                flow_path=args.flow_path,
                run_id=args.run_id,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] == "success" else 1
        if args.command == "resume":
            config = load_config(workspace=workspace)
            result = resume_flow(config, args.run_id, correction=args.correction)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] == "success" else 1
        if args.command == "flow-save":
            flow = _read_flow_payload(args.file)
            preflight = preflight_flow(flow, load_config(workspace=workspace))
            if not preflight["valid"]:
                print(json.dumps(preflight, indent=2, ensure_ascii=False))
                return 1
            target = save_flow(workspace, flow, name=args.name)
            print(json.dumps({"ok": True, "database": str(target), "flow": args.name}, ensure_ascii=False))
            return 0
        if args.command == "workspace-json":
            print(json.dumps(_workspace_payload(workspace, args.flow_name), indent=2, ensure_ascii=False))
            return 0
        if args.command == "config-export":
            data = load_config_mapping(workspace)
            text = json.dumps(data, indent=2, ensure_ascii=False)
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
            else:
                print(text)
            return 0
        if args.command == "config-save":
            data = _read_config_payload(args.file)
            data = normalize_config_mapping(data)
            AgentFirewallConfig.from_mapping(data, workspace)
            AgentFirewallStore(workspace).save_config(data)
            print(json.dumps({"ok": True, "database": str(AgentFirewallStore(workspace).path)}, ensure_ascii=False))
            return 0
        if args.command == "model-test":
            print(json.dumps(probe_model_connection(load_config(workspace=workspace)), ensure_ascii=False))
            return 0
        if args.command == "test-case-save":
            value = _read_json_payload(args.file)
            print(json.dumps(save_test_case(load_config(workspace=workspace), value), indent=2, ensure_ascii=False))
            return 0
        if args.command == "test-case-run":
            config = load_config(workspace=workspace)
            result = run_test_case(
                config,
                args.id,
                baseline_run_id=args.baseline_run_id,
                revision_id=args.revision_id,
                run_id=args.run_id,
                approved=args.approved,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] == "success" else 1
        if args.command == "test-case-baseline-set":
            result = set_test_run_baseline(load_config(workspace=workspace), args.run_id)
            if result.get("test_case_id") != args.id:
                raise ValueError("baseline run belongs to a different test case")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "workbench-json":
            print(json.dumps(_workbench_payload(workspace), indent=2, ensure_ascii=False))
            return 0
        if args.command == "run-json":
            result = AgentFirewallStore(workspace).get_run_details(args.run_id)
            if result is None:
                raise RuntimeError(f"run not found: {args.run_id}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "run-cancel":
            result = AgentFirewallStore(workspace).cancel_run(args.run_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "flow-preflight":
            config = load_config(workspace=workspace)
            result = preflight_flow(_read_json_payload(args.file), config)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["valid"] else 1
        if args.command == "mcp-tools":
            config = load_config(workspace=workspace)
            print(
                json.dumps(
                    discover_mcp_tools(config, args.agent, args.server, approved=args.approved),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "capability-import-local":
            print(json.dumps(import_local_skill(workspace, args.source), ensure_ascii=False))
            return 0
        if args.command == "run-compare":
            config = load_config(workspace=workspace)
            print(json.dumps(compare_test_runs(config, args.baseline, args.candidate), indent=2, ensure_ascii=False))
            return 0
        if args.command == "revision-create":
            config = load_config(workspace=workspace)
            value = _read_json_payload(args.file)
            result = create_revision(
                config,
                target_type=str(value["target_type"]),
                target_ref=str(value["target_ref"]),
                after=dict(value["after"]),
                reason=str(value["reason"]),
                test_case_id=int(value["test_case_id"]) if value.get("test_case_id") is not None else None,
                baseline_run_id=str(value["baseline_run_id"]) if value.get("baseline_run_id") else None,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "revision-review":
            result = review_revision(load_config(workspace=workspace), args.id, args.comparison_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "revision-apply":
            print(json.dumps(apply_revision(load_config(workspace=workspace), args.id), indent=2, ensure_ascii=False))
            return 0
        if args.command == "revision-revert":
            print(json.dumps(revert_revision(load_config(workspace=workspace), args.id), indent=2, ensure_ascii=False))
            return 0
        if args.command == "_script-run":
            original_argv = sys.argv
            try:
                sys.argv = [args.file]
                runpy.run_path(args.file, run_name="__main__")
            finally:
                sys.argv = original_argv
            return 0
        if args.command == "browser-smoke":
            result = browser_smoke(headed=args.headed, install_browser=args.install_browser)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
    except (ConfigError, EngineError, FlowError, RunnerError, RuntimeError, ValueError, PermissionError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


def _doctor(workspace: Path, *, as_json: bool = False) -> int:
    report: dict[str, object] = {
        "workspace": str(workspace),
        "database": str(AgentFirewallStore(workspace).path),
        "config": False,
        "skills": [],
        "deepagents": False,
        "acp": False,
    }
    config = load_config(workspace=workspace)
    report["config"] = True
    report["active_agent"] = config.active.name
    skills_root = workspace / ".agent-firewall" / "skills"
    report["skills"] = [
        {"name": item.name, "path": str(item.path), "description": item.description}
        for item in list_skill_manifests(skills_root)
    ]
    try:
        import deepagents  # noqa: F401

        report["deepagents"] = True
    except ImportError as exc:
        report["deepagents_error"] = str(exc)
    try:
        import deepagents_acp  # noqa: F401

        report["acp"] = True
    except ImportError as exc:
        report["acp_error"] = str(exc)

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"workspace: {report['workspace']}")
        print(f"database: {report['database']}")
        print(f"config: {'ok' if report['config'] else 'missing'}")
        print(f"active agent: {report.get('active_agent', '')}")
        print(f"deepagents: {'ok' if report['deepagents'] else 'missing'}")
        print(f"acp: {'ok' if report['acp'] else 'missing'}")
        print("skills:")
        for item in report["skills"]:  # type: ignore[index]
            print(f"  - {item['name']}: {item['path']}")
    return 0 if report["config"] and report["skills"] else 1


def _read_flow_payload(file_path: str | None) -> dict[str, object]:
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _read_config_payload(file_path: str | None) -> dict[str, object]:
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _read_json_payload(file_path: str | None) -> dict[str, object]:
    return json.loads(Path(file_path).read_text(encoding="utf-8") if file_path else sys.stdin.read())


def _workspace_payload(workspace: Path, flow_name: str) -> dict[str, object]:
    config = load_config(workspace=workspace)
    config_data = load_config_mapping(workspace)
    skills_root = workspace / APP_DIR / "skills"
    agents = [
        {
            "key": key,
            "name": value.get("name") or key,
            "model": value.get("model") or "",
            "systemPrompt": value.get("system_prompt") or "",
            "tools": value.get("tools") or [],
            "skills": value.get("skills") or [],
            "subagents": value.get("subagents") or [],
            "mcpServers": value.get("mcp_servers") or {},
            "allowedMcpTools": value.get("allowed_mcp_tools") or {},
            "interruptOn": value.get("interrupt_on") or {},
            "responseFormat": value.get("response_format"),
            "checkpoint": value.get("checkpoint", True),
        }
        for key, value in (config_data.get("agents") or {}).items()
    ]
    store = AgentFirewallStore(workspace)
    return {
        "workspace": str(workspace),
        "configPath": str(AgentFirewallStore(workspace).path),
        "config": config_data,
        "activeAgent": config_data.get("active_agent") or (agents[0]["key"] if agents else ""),
        "acp": config_data.get("acp") or {},
        "agents": agents,
        "skills": [
            {"id": item.path.name, "name": item.name, "description": item.description, "path": str(item.path)}
            for item in list_skill_manifests(skills_root)
        ],
        "mcpServers": [
            {"id": f"{agent['key']}:{key}", "key": key, "agent": agent["key"], "config": value}
            for agent in agents
            for key, value in agent["mcpServers"].items()
        ],
        "flow": load_flow(workspace, config, name=flow_name).to_mapping(),
        "capabilities": list_capabilities(config),
        "testCases": store.list_test_cases(),
        "runs": store.list_runs(),
        "revisions": store.list_revisions(),
        "comparisons": store.list_comparisons(),
    }


def _workbench_payload(workspace: Path) -> dict[str, object]:
    config = load_config(workspace=workspace)
    store = AgentFirewallStore(workspace)
    return {
        "workspace": str(workspace),
        "capabilities": list_capabilities(config),
        "testCases": store.list_test_cases(),
        "runs": store.list_runs(),
        "revisions": store.list_revisions(),
        "comparisons": store.list_comparisons(),
    }
