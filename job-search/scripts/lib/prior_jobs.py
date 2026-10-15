#!/usr/bin/env python3
"""Read job URLs out of previous runs' job_list.md files so a new run can skip them.

Opt-in only: use when the user keeps earlier runs in a folder and wants a fresh list.
There is no database or JSON cache; the previous job_list.md files are the cache.

Usage:
  python3 prior_jobs.py --prior-dir ./job_search_runs                      # print seen URLs
  python3 prior_jobs.py --prior-dir ./job_search_runs --jobs raw.json -o fresh.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s)>\]|\"']+")
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "ref", "source", "src", "gh_src", "lever-source", "gclid", "fbclid"}


def canonical(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url.strip())
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if k.lower() not in TRACKING]
        return urllib.parse.urlunsplit(
            (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urllib.parse.urlencode(q), ""))
    except Exception:
        return url.strip()


def load_seen(prior_dir: str) -> set:
    seen = set()
    for f in Path(prior_dir).expanduser().rglob("job_list.md"):
        for u in URL_RE.findall(f.read_text(errors="ignore")):
            seen.add(canonical(u.rstrip(".,;")))
    return seen


def filter_disjoint(candidates: list, prior_dir: str) -> tuple:
    """Return (fresh, previously_seen) for a list of job dicts carrying a `url`."""
    seen = load_seen(prior_dir)
    fresh, old = [], []
    for c in candidates:
        (old if canonical(str(c.get("url", ""))) in seen else fresh).append(c)
    return fresh, old


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prior-dir", required=True)
    ap.add_argument("--jobs", help="JSON list of candidate jobs to filter")
    ap.add_argument("-o", "--output", help="Where to write the filtered list (default: stdout)")
    a = ap.parse_args()
    if not a.jobs:
        print("\n".join(sorted(load_seen(a.prior_dir))))
        return
    data = json.load(open(a.jobs))
    jobs = data if isinstance(data, list) else data.get("results", data.get("jobs_list", []))
    fresh, old = filter_disjoint(jobs, a.prior_dir)
    print(f"{len(old)} previously seen dropped, {len(fresh)} fresh", file=sys.stderr)
    out = json.dumps(fresh, indent=2)
    if a.output:
        Path(a.output).write_text(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
