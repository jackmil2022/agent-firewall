---
name: skill-creator
description: "Create or update concise project skills for Agent Firewall. Use when the user asks to add, scaffold, validate, or package reusable skills, including skills with scripts, references, assets, and agent metadata."
---

# Skill Creator

Use this skill to create project-local skills under `.agent-firewall/skills`.

## Workflow

1. Clarify the skill trigger, expected tasks, and reusable resources.
2. Run `scripts/init_skill.py <name> --path .agent-firewall/skills`.
3. Keep `SKILL.md` concise and move long references into `references/`.
4. Add deterministic scripts for repeated operations.
5. Validate by running `scripts/init_skill.py --help` and checking the generated `SKILL.md`.

## Naming

Use lowercase letters, digits, and hyphens. Prefer short verb-led names such as `control-browser` or `inspect-api`.
