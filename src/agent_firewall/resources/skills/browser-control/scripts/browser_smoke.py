#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys


HTML = """
<!doctype html>
<html>
  <head><title>Agent Firewall Browser Smoke</title></head>
  <body>
    <button id="run">Run</button>
    <output id="result">idle</output>
    <script>
      document.querySelector("#run").addEventListener("click", () => {
        document.querySelector("#result").textContent = "browser-control-ok";
      });
    </script>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Playwright browser-control smoke test.")
    parser.add_argument("--headed", action="store_true", help="Open a visible browser.")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"ok": False, "error": "playwright is not installed"}))
        return 2

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page()
        page.set_content(HTML)
        title = page.title()
        page.locator("#run").click()
        result = page.locator("#result").inner_text()
        browser.close()

    ok = title == "Agent Firewall Browser Smoke" and result == "browser-control-ok"
    print(json.dumps({"ok": ok, "title": title, "result": result}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
