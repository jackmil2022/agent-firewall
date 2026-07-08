from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .acp import serve_acp
from .browser import browser_smoke
from .config import ConfigError, load_config, write_default_config
from .engine import EngineError, build_agent_sync
from .skills import install_bundled_skills, list_skill_manifests


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

    browser_parser = subparsers.add_parser("browser-smoke", help="Run the initialized browser-control skill smoke test.")
    browser_parser.add_argument("--headed", action="store_true", help="Open a visible browser window.")
    browser_parser.add_argument("--install-browser", action="store_true", help="Install Playwright Chromium first.")

    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()

    try:
        if args.command == "init":
            cfg = write_default_config(workspace, force=args.force)
            skills = install_bundled_skills(workspace, force=args.force)
            print(f"initialized config: {cfg}")
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
            asyncio.run(serve_acp(config, args.name))
            return 0
        if args.command == "browser-smoke":
            result = browser_smoke(headed=args.headed, install_browser=args.install_browser)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
    except (ConfigError, EngineError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


def _doctor(workspace: Path, *, as_json: bool = False) -> int:
    report: dict[str, object] = {
        "workspace": str(workspace),
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
        print(f"config: {'ok' if report['config'] else 'missing'}")
        print(f"active agent: {report.get('active_agent', '')}")
        print(f"deepagents: {'ok' if report['deepagents'] else 'missing'}")
        print(f"acp: {'ok' if report['acp'] else 'missing'}")
        print("skills:")
        for item in report["skills"]:  # type: ignore[index]
            print(f"  - {item['name']}: {item['path']}")
    return 0 if report["config"] and report["skills"] else 1
