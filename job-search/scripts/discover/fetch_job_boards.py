#!/usr/bin/env python3
"""
Fetch live job postings from free/public job board APIs.

Pulls structured, current data directly from ATS APIs and aggregators, rather
than relying on generic web search (which returns stale/cached snippets).
Requires outbound network access to the relevant API hosts — will fail fast
with a clear error in network-restricted sandboxes. If that happens, use the manual fallbacks in ../../references/sources/sources_and_fallbacks.md.

Usage:
    python3 fetch_job_boards.py --keywords "<role keyword>" \
        --slugs <slug> <slug> --locations "<city>" \
        --sources greenhouse lever ashby remoteok arbeitnow hn

Sources:
    greenhouse  - Greenhouse public job board API (needs company slugs)
    lever       - Lever public postings API (needs company slugs)
    ashby       - Ashby public job board API (needs company slugs)
    remoteok    - RemoteOK aggregator API (no slugs needed, broad/remote-heavy)
    arbeitnow   - Arbeitnow aggregator API (no slugs needed)
    hn          - Hacker News "Who is Hiring" threads via Algolia API (no slugs needed)
    muse        - The Muse public jobs API, entry-level and internship listings (no key)

Company slugs for greenhouse/lever/ashby: see ../../references/sources/sources_and_fallbacks.md (section 5)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'lib'))
from _common import open_url, setup_stdio
from datetime import datetime, timezone

TIMEOUT = 15

setup_stdio()


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "job-search-skill/1.0"})
    with open_url(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    data = _get_json(url)
    out = []
    for job in data.get("jobs", []):
        out.append({
            "source": "greenhouse",
            "company": slug,
            "title": job.get("title"),
            "location": (job.get("location") or {}).get("name"),
            "url": job.get("absolute_url"),
            "updated_at": job.get("updated_at"),
        })
    return out


def fetch_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = _get_json(url)
    out = []
    for job in data:
        cats = job.get("categories", {})
        out.append({
            "source": "lever",
            "company": slug,
            "title": job.get("text"),
            "location": cats.get("location"),
            "url": job.get("hostedUrl"),
            "updated_at": datetime.fromtimestamp(
                job.get("createdAt", 0) / 1000, tz=timezone.utc
            ).isoformat() if job.get("createdAt") else None,
        })
    return out


def fetch_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    data = _get_json(url)
    out = []
    for job in data.get("jobs", []):
        out.append({
            "source": "ashby",
            "company": slug,
            "title": job.get("title"),
            "location": job.get("location"),
            "url": job.get("jobUrl") or job.get("applyUrl"),
            "updated_at": job.get("publishedAt"),
        })
    return out


def fetch_remoteok(keywords):
    url = "https://remoteok.com/api"
    data = _get_json(url)
    out = []
    for job in data:
        if not isinstance(job, dict) or "position" not in job:
            continue
        title = job.get("position", "")
        if keywords and not any(k.lower() in title.lower() for k in keywords):
            continue
        out.append({
            "source": "remoteok",
            "company": job.get("company"),
            "title": title,
            "location": job.get("location") or "Remote",
            "url": job.get("url"),
            "updated_at": job.get("date"),
        })
    return out


def fetch_arbeitnow(keywords):
    url = "https://www.arbeitnow.com/api/job-board-api"
    data = _get_json(url)
    out = []
    for job in data.get("data", []):
        title = job.get("title", "")
        if keywords and not any(k.lower() in title.lower() for k in keywords):
            continue
        out.append({
            "source": "arbeitnow",
            "company": job.get("company_name"),
            "title": title,
            "location": job.get("location"),
            "url": job.get("url"),
            "updated_at": job.get("created_at"),
        })
    return out


def fetch_hn_hiring(keywords):
    # Find the most recent "Who is hiring" story, then its comments.
    search_url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        "?query=Who%20is%20hiring&tags=story&hitsPerPage=5"
    )
    data = _get_json(search_url)
    hits = [h for h in data.get("hits", []) if "who is hiring" in (h.get("title") or "").lower()]
    if not hits:
        return []
    story_id = hits[0]["objectID"]
    thread_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
    thread = _get_json(thread_url)
    out = []
    for c in thread.get("children", []):
        text = (c.get("text") or "")
        if not text:
            continue
        if keywords and not any(k.lower() in text.lower() for k in keywords):
            continue
        snippet = text[:300].replace("<p>", " ").replace("\n", " ")
        out.append({
            "source": "hn_who_is_hiring",
            "company": None,
            "title": snippet,
            "location": None,
            "url": f"https://news.ycombinator.com/item?id={c.get('id')}",
            "updated_at": None,
        })
    return out


def fetch_muse(keywords):
    """The Muse public jobs API (no key). Pulls entry-level and internship listings, a few pages."""
    out = []
    for level in ("Entry%20Level", "Internship"):
        for page in range(1, 6):
            try:
                data = _get_json(f"https://www.themuse.com/api/public/jobs?page={page}&level={level}")
            except Exception:
                break
            items = data.get("results", [])
            if not items:
                break
            for job in items:
                title = job.get("name", "")
                if keywords and not any(k.lower() in title.lower() for k in keywords):
                    continue
                out.append({
                    "source": "themuse",
                    "company": (job.get("company") or {}).get("name"),
                    "title": title,
                    "location": "; ".join(l.get("name", "") for l in job.get("locations", [])) or None,
                    "url": (job.get("refs") or {}).get("landing_page"),
                    "updated_at": job.get("publication_date"),
                })
    return out


SOURCE_FUNCS_SLUG = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}
SOURCE_FUNCS_KEYWORD = {"remoteok": fetch_remoteok, "arbeitnow": fetch_arbeitnow, "hn": fetch_hn_hiring, "muse": fetch_muse}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keywords", nargs="*", default=[], help="Role keywords to filter titles/text on")
    p.add_argument("--output", "-o", default=None, help="Write JSON here instead of stdout")
    p.add_argument("--slugs", nargs="*", default=[], help="Company slugs for greenhouse/lever/ashby")
    p.add_argument("--locations", nargs="*", default=[], help="Location substrings to filter on (case-insensitive)")
    p.add_argument("--sources", nargs="*", default=list(SOURCE_FUNCS_SLUG) + list(SOURCE_FUNCS_KEYWORD),
                    help="Which sources to query")
    args = p.parse_args()

    results = []
    errors = []

    for src in args.sources:
        if src in SOURCE_FUNCS_SLUG:
            fn = SOURCE_FUNCS_SLUG[src]
            for slug in args.slugs:
                try:
                    results.extend(fn(slug))
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
                    errors.append(f"{src}/{slug}: {e}")
        elif src in SOURCE_FUNCS_KEYWORD:
            fn = SOURCE_FUNCS_KEYWORD[src]
            try:
                results.extend(fn(args.keywords))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
                errors.append(f"{src}: {e}")

    # Keyword filter for slug-based sources (greenhouse/lever/ashby return everything for a company)
    if args.keywords:
        results = [
            r for r in results
            if any(k.lower() in (r.get("title") or "").lower() for k in args.keywords)
        ]

    # Location filter
    if args.locations:
        results = [
            r for r in results
            if r.get("location") and any(loc.lower() in r["location"].lower() for loc in args.locations)
        ]

    payload = json.dumps({"results": results, "count": len(results), "errors": errors}, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {len(results)} results to {args.output}", file=sys.stderr)
    else:
        print(payload)

    if errors and not results:
        sys.stderr.write(
            "\nAll queries failed — likely no outbound network access in this sandbox. "
            "Use the manual fallbacks in references/sources/sources_and_fallbacks.md.\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
