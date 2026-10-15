#!/usr/bin/env python3
"""Report what works in this environment so the run can pick fallbacks up front.

Usage: python doctor.py            (use `py -3 doctor.py` on Windows if `python` is absent)

Prints one line per capability: OK / MISSING / BLOCKED, and the fallback to use.
Exit code is always 0; this is advisory.
"""
import os
import platform
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
from _common import open_url, setup_stdio  # noqa: E402

setup_stdio()

CHECKS = [
    ("Greenhouse API", "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs", "company ATS sweep"),
    ("Lever API", "https://api.lever.co/v0/postings/palantir?limit=1", "company ATS sweep"),
    ("Ashby API", "https://api.ashbyhq.com/posting-api/job-board/notion", "company ATS sweep"),
    ("GitHub raw", "https://raw.githubusercontent.com/git/git/master/README.md", "GitHub trackers"),
    ("GitHub API", "https://api.github.com/rate_limit", "dynamic repo search"),
    ("HN Algolia", "https://hn.algolia.com/api/v1/search?query=who%20is%20hiring&hitsPerPage=1", "HN threads"),
]


def probe(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "job-search-skill/1.0"})
        with open_url(req, timeout=10) as r:
            return r.status
    except Exception as e:
        return str(e)[:80]


def main():
    print(f"Python {platform.python_version()} on {platform.system()} ({platform.machine()})")
    if sys.version_info < (3, 8):
        print("MISSING  Python >= 3.8 required. Use the manual fallbacks.")
    try:
        import jobspy  # noqa: F401
        print("OK       python-jobspy installed (optional; LinkedIn/Indeed are low-signal, see sources_and_fallbacks.md)")
    except ImportError:
        print("MISSING  python-jobspy (optional): skip fetch_jobspy.py; nothing else depends on it")
    try:
        import certifi  # noqa: F401
        print("OK       certifi present")
    except ImportError:
        print("NOTE     certifi absent: system certificates are used, with an unverified retry on cert errors")
    for name, url, use in CHECKS:
        r = probe(url)
        if r == 200:
            print(f"OK       {name} ({use})")
        else:
            print(f"BLOCKED  {name} ({use}): {r}; use manual fallback in references/sources/sources_and_fallbacks.md")


if __name__ == "__main__":
    main()
