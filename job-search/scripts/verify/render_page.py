#!/usr/bin/env python3
"""
Render a client-rendered job page in a real browser and print its visible text.

Optional. Needs Playwright (`pip install playwright`) and any Chromium it can find: the one Playwright
installed, any cached Chromium, or an installed Google Chrome. Nothing is installed or downloaded here.
When Playwright or a browser is missing, this prints a clear message and exits 2, and the caller falls
back to the next rung (see references/workflow/verification.md, "Client-rendered pages").

Escalation, stopping at the first that yields a real page:
  1. headless browser
  2. installed Chrome with a visible window (only if the headless page is a bot-verification wall; a
     window opens briefly on this machine)

Usage:
  python3 render_page.py <url> [<url> ...]
  python3 render_page.py <list_url> --links "/jobs/\\d+"     # print posting links found on a rendered list page
  python3 render_page.py <url> --json                         # machine-readable output
  python3 render_page.py --check                              # report what is available and exit
"""
import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from _common import setup_stdio  # noqa: E402

setup_stdio()

WALL_PHRASES = (
    "performing security verification", "verify you are human", "verifying you are human",
    "checking your browser before accessing", "just a moment...", "attention required! | cloudflare",
    "protect against malicious bots", "please complete the security check", "enable javascript to view",
)
CACHE_GLOBS = (
    "~/Library/Caches/ms-playwright/chromium*/*/chrome-headless-shell",
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "~/.cache/ms-playwright/chromium*/chrome-linux*/headless_shell",
    "~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
    "~/AppData/Local/ms-playwright/chromium*/chrome-win*/*.exe",
)


def _venv_python():
    """The private environment created by scripts/setup_optional.py, if the user opted in."""
    home = os.environ.get("JOB_SEARCH_HOME") or os.path.join(os.path.expanduser("~"), ".job-search-skill")
    exe = os.path.join(home, "venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(home, "venv", "bin", "python")
    return exe if os.path.exists(exe) else None


def _importable():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


def find_playwright():
    """True when Playwright can be used, here or in the private environment."""
    if _importable():
        return True
    py = _venv_python()
    if not py:
        return False
    import subprocess
    return subprocess.run([py, "-c", "import playwright"], capture_output=True).returncode == 0


def render_any(urls, link_pattern=None, budget=25, allow_headed=True):
    """Render in this process when Playwright is importable, else through the private environment."""
    if _importable():
        return render(urls, link_pattern, budget, allow_headed)
    py = _venv_python()
    if not py:
        raise RuntimeError("Playwright is not installed")
    import subprocess
    cmd = [py, os.path.abspath(__file__), *urls, "--json", "--budget", str(budget)]
    if link_pattern:
        cmd += ["--links", link_pattern]
    if not allow_headed:
        cmd.append("--no-headed")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def find_cached_chromium():
    for pattern in CACHE_GLOBS:
        hits = sorted(glob.glob(os.path.expanduser(pattern)))
        if hits:
            return hits[-1]
    return None


def has_installed_chrome():
    for p in ("/Applications/Google Chrome.app", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(p):
            return True
    return False


def availability():
    return {"playwright": find_playwright(), "cached_chromium": find_cached_chromium(),
            "installed_chrome": has_installed_chrome()}


def is_wall(text):
    t = (text or "").lower()
    return len(t) < 1500 and any(p in t for p in WALL_PHRASES)


def _launch(p, headed):
    """Try, in order: installed Chrome, Playwright's own browser, a cached Chromium."""
    errors = []
    attempts = []
    if has_installed_chrome():
        attempts.append(("chrome", dict(channel="chrome", headless=not headed)))
    if not headed:
        attempts.append(("playwright-chromium", dict(headless=True)))
    cached = find_cached_chromium()
    if cached and not headed:
        attempts.append(("cached-chromium", dict(executable_path=cached, headless=True)))
    for name, kw in attempts:
        try:
            return p.chromium.launch(**kw), name
        except Exception as e:  # missing browser build, sandbox limits...
            errors.append(f"{name}: {str(e).splitlines()[0][:100]}")
    raise RuntimeError("; ".join(errors) or "no browser available")


def _settle(page, budget):
    """Wait until the visible text stops changing; career sites with analytics never go network-idle."""
    last, stable, t0 = -1, 0, time.time()
    while time.time() - t0 < budget:
        try:
            n = len(page.inner_text("body"))
        except Exception:
            n = 0
        stable = stable + 1 if (n == last and n > 200) else 0
        if stable >= 2:
            break
        last = n
        time.sleep(1.2)


def render(urls, link_pattern=None, budget=25, allow_headed=True):
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        for headed in (False, True):
            pending = [u for u in urls if not any(r["url"] == u and not r["blocked"] for r in out)]
            if not pending:
                break
            if headed and not (allow_headed and has_installed_chrome()):
                break
            try:
                browser, used = _launch(p, headed)
            except Exception as e:
                if not headed:
                    for u in pending:
                        out.append({"url": u, "text": "", "links": [], "blocked": False, "browser": None,
                                    "error": f"no usable browser ({e})"})
                break
            page = browser.new_page()
            for u in pending:
                out[:] = [r for r in out if r["url"] != u]
                rec = {"url": u, "text": "", "links": [], "blocked": False, "browser": used + (" (headed)" if headed else ""), "error": ""}
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=30000)
                    _settle(page, budget)
                    rec["text"] = page.inner_text("body")
                    rec["final_url"] = page.url
                    if link_pattern:
                        hrefs = page.eval_on_selector_all("a", "e => e.map(x => x.href)")
                        rec["links"] = sorted({h for h in hrefs if re.search(link_pattern, h)})
                    rec["blocked"] = is_wall(rec["text"])
                except Exception as e:
                    rec["error"] = str(e).splitlines()[0][:160]
                out.append(rec)
            browser.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--links", help="regex; also print anchors on the rendered page whose href matches")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="report what is available and exit")
    ap.add_argument("--no-headed", action="store_true", help="never open a visible Chrome window")
    ap.add_argument("--budget", type=int, default=25, help="max seconds to wait for a page to settle")
    a = ap.parse_args()

    av = availability()
    if a.check or not a.urls:
        print(json.dumps(av, indent=2))
        sys.exit(0 if av["playwright"] and (av["cached_chromium"] or av["installed_chrome"]) else 2)
    if not av["playwright"]:
        print("render_page: Playwright is not installed (optional). Ask the user before installing anything: "
              "scripts/setup_optional.py --check lists what it would add and why. Otherwise use the employer's JSON "
              "endpoint, the host's browser tool, or list the role as 'could not machine-check'.", file=sys.stderr)
        sys.exit(2)

    results = render_any(a.urls, a.links, a.budget, allow_headed=not a.no_headed)
    if a.json:
        print(json.dumps(results, indent=2))
        return
    for r in results:
        status = "BLOCKED (bot wall)" if r["blocked"] else ("ERROR " + r["error"] if r["error"] else "ok")
        print(f"=== {r['url']} [{status}; {r['browser']}; {len(r['text'])} chars]")
        print(r["text"][:6000])
        for l in r["links"]:
            print("LINK", l)


if __name__ == "__main__":
    main()
