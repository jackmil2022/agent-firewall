---
name: browser-control
description: "Control and verify browser workflows with Playwright. Use when the user asks to open pages, inspect local apps, click controls, capture screenshots, or run browser smoke tests on macOS or Windows."
---

# Browser Control

Use `scripts/browser_smoke.py` for a fast cross-platform smoke test before relying on browser automation.

## Workflow

1. Install the app with the browser extra: `pip install -e .[browser]`.
2. Install Chromium once if needed: `python -m playwright install chromium`.
3. Run `python .agent-firewall/skills/browser-control/scripts/browser_smoke.py`.
4. For app verification, adapt the script to navigate to the local URL, click expected controls, and assert visible output.

Keep browser checks headless by default. Use `--headed` only when a visible browser is needed.
