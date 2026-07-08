#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
from pathlib import Path


def normalize_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not name:
        raise ValueError("skill name must contain at least one letter or digit")
    return name[:63]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an Agent Firewall skill folder.")
    parser.add_argument("name", nargs="+", help="Skill name. It will be normalized to kebab-case.")
    parser.add_argument("--path", default=".agent-firewall/skills", help="Skill root directory.")
    parser.add_argument("--force", action="store_true", help="Overwrite SKILL.md if it already exists.")
    args = parser.parse_args()

    name = normalize_name(" ".join(args.name))
    target = Path(args.path) / name
    target.mkdir(parents=True, exist_ok=True)
    skill_md = target / "SKILL.md"
    if skill_md.exists() and not args.force:
        print(f"exists: {skill_md}")
        return 0
    skill_md.write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f'description: "Use when creating or executing the {name} workflow."',
                "---",
                "",
                f"# {name}",
                "",
                "Describe the workflow, required tools, and validation steps.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"created: {skill_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
