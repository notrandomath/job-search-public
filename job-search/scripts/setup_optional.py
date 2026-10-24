#!/usr/bin/env python3
"""Optional installs for reading client-rendered job pages. Nothing here runs unless the user said yes.

The skill works without any of this. These items only let it open JavaScript-rendered and bot-checked
career pages in a real browser (scripts/verify/render_page.py). Ask the user first, list every item
below with its reason, and install only the ones they pick.

Usage:
  python3 setup_optional.py --check                 # JSON: each item, why, size, command, installed?
  python3 setup_optional.py --install playwright    # install chosen items (ids from --check)
  python3 setup_optional.py --install playwright chromium
  python3 setup_optional.py --uninstall             # delete everything this script installed

Everything goes into one folder (default ~/.job-search-skill, override with JOB_SEARCH_HOME): a private
Python virtual environment, so your system Python is never modified. Chromium itself is stored in
Playwright's usual cache. Exit codes: 0 ok, 2 nothing to do, 3 this environment cannot install.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from _common import setup_stdio  # noqa: E402

setup_stdio()

HOME = os.environ.get("JOB_SEARCH_HOME") or os.path.join(os.path.expanduser("~"), ".job-search-skill")
VENV = os.path.join(HOME, "venv")


def venv_python():
    exe = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
    return exe if os.path.exists(exe) else None


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def chrome_installed():
    return any(os.path.exists(p) for p in (
        "/Applications/Google Chrome.app", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"))


def playwright_installed():
    py = venv_python()
    if py and _run([py, "-c", "import playwright"]).returncode == 0:
        return True
    return _run([sys.executable, "-c", "import playwright"]).returncode == 0


def chromium_installed():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify"))
    import render_page
    return bool(render_page.find_cached_chromium())


def can_install():
    """False in environments that cannot create a venv or reach PyPI."""
    try:
        import venv  # noqa: F401
    except ImportError:
        return False, "Python's venv module is unavailable"
    r = _run([sys.executable, "-c", "import urllib.request as u;u.urlopen('https://pypi.org/simple/',timeout=8)"])
    return (r.returncode == 0), ("" if r.returncode == 0 else "cannot reach pypi.org (no network or blocked)")


def items():
    pw, ch, gc = playwright_installed(), chromium_installed(), chrome_installed()
    return [
        {"id": "playwright", "installed": pw,
         "what": "Playwright, a Python library that drives a web browser",
         "why": "opens JavaScript-rendered and bot-checked job pages and reads the posting text, which a plain fetch cannot",
         "size": "tens of MB", "where": f"{VENV} (a private virtual environment; system Python untouched)",
         "command": f"python -m venv {VENV} && {VENV}/bin/python -m pip install playwright"},
        {"id": "chromium", "installed": ch or gc, "needed": not gc,
         "what": "Chromium, an open-source browser build that Playwright launches",
         "why": ("Google Chrome is already installed and will be used, so this is not needed" if gc
                 else "Playwright needs a browser to open pages; none was found on this machine"),
         "size": "roughly 100 to 300 MB", "where": "Playwright's browser cache (~/Library/Caches/ms-playwright, ~/.cache/ms-playwright, or %LOCALAPPDATA%\\ms-playwright)",
         "command": "python -m playwright install chromium"},
    ]


def install(ids):
    ok, why = can_install()
    if not ok:
        print(f"This environment cannot install: {why}.", file=sys.stderr)
        return 3
    os.makedirs(HOME, exist_ok=True)
    if "playwright" in ids and not playwright_installed():
        if not venv_python():
            r = _run([sys.executable, "-m", "venv", VENV])
            if r.returncode:
                print("venv creation failed:", r.stderr[-300:], file=sys.stderr)
                return 3
        py = venv_python()
        r = _run([py, "-m", "pip", "install", "--quiet", "playwright"])
        if r.returncode:
            print("pip install playwright failed:", r.stderr[-400:], file=sys.stderr)
            return 3
        print("installed: playwright")
    if "chromium" in ids:
        if chrome_installed():
            print("skipped: chromium (Google Chrome is already installed and will be used)")
        else:
            py = venv_python() or sys.executable
            r = _run([py, "-m", "playwright", "install", "chromium"])
            if r.returncode:
                print("chromium download failed:", (r.stderr or r.stdout)[-400:], file=sys.stderr)
                return 3
            print("installed: chromium")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--install", nargs="+", choices=["playwright", "chromium"])
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    if a.uninstall:
        shutil.rmtree(HOME, ignore_errors=True)
        print(f"removed {HOME}. Chromium, if downloaded, stays in Playwright's cache; delete that folder to remove it.")
        return 0
    if a.install:
        return install(a.install)
    ok, why = can_install()
    todo = [i for i in items() if not i["installed"] and i.get("needed", True)]
    print(json.dumps({"can_install": ok, "reason": why, "missing": todo, "all": items()}, indent=2))
    return 0 if todo else 2


if __name__ == "__main__":
    sys.exit(main())
