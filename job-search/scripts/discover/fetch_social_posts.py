#!/usr/bin/env python3
"""
Find recent hiring posts on open social sources (no API keys).

Sources:
  bluesky   - Bluesky post search via the public AppView (api.bsky.app)
  hn        - Hacker News comments via Algolia (hiring and "who wants to be hired" threads)

LinkedIn and X posts are NOT reachable this way (no public API, and web search does not
index them). For those, use the human-in-the-loop path in references/workflow/deep_search.md.

Usage:
  python3 scripts/discover/fetch_social_posts.py --query '"we\'re hiring" "research engineer"' --since 2026-09-20
  python3 scripts/discover/fetch_social_posts.py --query 'new grad machine learning' --sources hn bluesky -o posts.json

Output rows: source, author, date, text, url. These are leads, never verified postings:
check the poster, the date, and whether the role exists on the employer's ATS.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from _common import open_url, setup_stdio  # noqa: E402

setup_stdio()
UA = {"User-Agent": "job-search-skill/1.0 (open-source research; contact via repo issues)",
      "Accept": "application/json"}


def _get(url):
    with open_url(urllib.request.Request(url, headers=UA), timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def bluesky(query, since, limit):
    params = {"q": query, "limit": min(limit, 100), "sort": "latest"}
    if since:
        params["since"] = since + "T00:00:00Z"
    data = _get("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode(params))
    out = []
    for p in data.get("posts", []):
        rec = p.get("record", {})
        handle = p.get("author", {}).get("handle", "")
        rkey = p.get("uri", "").rsplit("/", 1)[-1]
        out.append({
            "source": "bluesky", "author": handle, "date": rec.get("createdAt", "")[:10],
            "text": " ".join(rec.get("text", "").split())[:600],
            "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        })
    return out


def hn(query, since, limit):
    params = {"query": query, "tags": "comment", "hitsPerPage": min(limit, 100)}
    if since:
        import calendar
        import time
        ts = calendar.timegm(time.strptime(since, "%Y-%m-%d"))
        params["numericFilters"] = f"created_at_i>{ts}"
    data = _get("https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(params))
    out = []
    for h in data.get("hits", []):
        text = " ".join(urllib.parse.unquote(h.get("comment_text") or "").replace("<p>", " ").split())
        out.append({
            "source": "hn", "author": h.get("author"), "date": (h.get("created_at") or "")[:10],
            "text": text[:600], "url": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
        })
    return out


FUNCS = {"bluesky": bluesky, "hn": hn}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", "-q", required=True)
    ap.add_argument("--sources", nargs="*", default=list(FUNCS), choices=list(FUNCS))
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; only posts on or after this date")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--output", "-o", default=None)
    a = ap.parse_args()
    rows, errors = [], []
    for s in a.sources:
        try:
            rows += FUNCS[s](a.query, a.since, a.limit)
        except Exception as e:  # network or HTTP error: report, keep going
            errors.append(f"{s}: {str(e)[:100]}")
    payload = json.dumps({"results": rows, "count": len(rows), "errors": errors}, indent=2, ensure_ascii=False)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {len(rows)} posts to {a.output}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
