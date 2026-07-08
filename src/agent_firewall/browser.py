import os
import platform
import subprocess
import sys
from pathlib import Path


def browser_smoke(*, headed: bool = False, install_browser: bool = False) -> dict[str, object]:
    if getattr(sys, "frozen", False):
        cache = _playwright_browser_cache()
        if cache is not None:
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(cache))
    if install_browser:
        if getattr(sys, "frozen", False):
            return {
                "ok": False,
                "error": "install-browser is only supported from a Python environment; run `python -m playwright install chromium` before using the packaged app.",
            }
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright is not installed"}

    html = """
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
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=not headed)
            page = browser.new_page()
            page.set_content(html)
            title = page.title()
            page.locator("#run").click()
            result = page.locator("#result").inner_text()
            browser.close()
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "guidance": "Install Chromium with `python -m playwright install chromium`, then run this command again.",
            }

    ok = title == "Agent Firewall Browser Smoke" and result == "browser-control-ok"
    return {"ok": ok, "title": title, "result": result}


def _playwright_browser_cache() -> Path | None:
    system = platform.system()
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        return Path(local_app_data) / "ms-playwright" if local_app_data else None
    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"
