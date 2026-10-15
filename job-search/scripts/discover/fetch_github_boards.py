#!/usr/bin/env python3
"""
fetch_github_boards.py - Dynamically discover and parse job board repositories on GitHub.

Zero hardcoding:
- Discovers repositories via the GitHub Search API based on user search queries, domain, or seniority level.
- Supports direct inspection of any user-specified GitHub repository (--repo owner/repo).
- Supports direct inspection of local filesystem repositories or markdown files (--file /path/to/README.md).
- --file also accepts a raw URL.
- Handles HTML tables and Markdown pipe tables (with or without outer pipes, <angle-bracket> links, column order read from the header row).
- Falls back from Python's HTTP client to curl, and tries main/master/dev and README name variants.
- Prints and saves a per-source report (rows parsed, rows kept, or why a source gave none) so a relevant board is never silently dropped.
- Unwraps tracking links to extract canonical ATS URLs (Greenhouse, Ashby, Lever, Workday, etc.).

Usage:
  # Dynamic search for any level or domain on GitHub:
  python3 scripts/discover/fetch_github_boards.py --search "<role> jobs" --locations "<location>"
  python3 scripts/discover/fetch_github_boards.py --search "<role> jobs" --locations "remote"
  python3 scripts/discover/fetch_github_boards.py --search "<level> <role>" --locations "<region>"

  # Target a specific repository:
  python3 scripts/discover/fetch_github_boards.py --repo <owner>/<repo>

  # Local filesystem access (e.g. cloned repo on disk):
  python3 scripts/discover/fetch_github_boards.py --file /path/to/cloned/repo/README.md

  # Save to output file:
  python3 scripts/discover/fetch_github_boards.py --search "<role> jobs" --output dynamic_github_jobs.json
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'lib'))
from _common import open_url, setup_stdio

setup_stdio()

HEADERS = {
    "User-Agent": "job-search-skill/1.0",
    "Accept": "application/vnd.github.v3+json, text/plain, */*"
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "gh_src"
}

def clean_url(url: str) -> str:
    """Strip tracking query parameters while preserving critical ATS routing parameters."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        clean_items = [(k, v) for k, v in query_items if k.lower() not in TRACKING_PARAMS]
        clean_query = urllib.parse.urlencode(clean_items)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, ""))
    except Exception:
        return url.strip()

def clean_name(text: str) -> str:
    """Strip markdown/HTML decoration from a company or role cell: **bold**, [text](url), emoji markers."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    return " ".join(text.split()).strip()



ATS_HINTS = ("greenhouse.io", "ashbyhq.com", "lever.co", "myworkdayjobs.com", "icims.com",
             "smartrecruiters.com", "workable.com", "jobvite.com", "careers.", "/jobs/", "/job/")
COMPANY_WORDS = ("company", "employer", "organization", "organisation", "name", "firm")
ROLE_WORDS = ("role", "title", "position", "job", "opening")
LOC_WORDS = ("location", "city", "region", "where")
APPLY_WORDS = ("apply", "application", "link", "url", "posting")


def _github_headers() -> dict:
    h = dict(HEADERS)
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def curl_fetch(url: str, timeout: int = 20) -> str:
    """Backup fetch through curl (some sandboxes allow it when Python sockets are blocked)."""
    out = subprocess.run(["curl", "-fsSL", "--max-time", str(timeout), "-A", "job-search-skill/1.0", url],
                         capture_output=True, timeout=timeout + 5)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(f"curl exit {out.returncode}")
    return out.stdout.decode("utf-8", errors="ignore")


def fetch_text(url: str, timeout: int = 20) -> tuple[str, str]:
    """Return (text, method). Tries Python HTTP first, then curl."""
    try:
        req = urllib.request.Request(url, headers=_github_headers())
        with open_url(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore"), "python"
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise
        err = e
    except Exception as e:  # network blocked, TLS, timeout
        err = e
    try:
        return curl_fetch(url, timeout), "curl"
    except Exception as e2:
        raise RuntimeError(f"python fetch failed ({err}); curl fallback failed ({e2})")


def fetch_readme(owner_repo: str, branch_hint: str | None = None) -> tuple[str, str, str]:
    """Try branch and file-name variants. Returns (text, raw_url, method)."""
    branches = [b for b in dict.fromkeys([branch_hint, "main", "master", "dev"]) if b]
    last = None
    for b in branches:
        for fname in ("README.md", "readme.md", "Readme.md", "README.markdown", "README.rst"):
            url = f"https://raw.githubusercontent.com/{owner_repo}/{b}/{fname}"
            try:
                text, method = fetch_text(url)
                return text, url, method
            except urllib.error.HTTPError as e:
                last = e
                continue
    raise RuntimeError(f"no README found on branches {branches} ({last})")


def search_github_repositories(query: str, min_stars: int = 0, limit: int = 10) -> list[dict]:
    """Search GitHub for job-board repositories; recently updated first."""
    qs = f"{query.strip()} in:name,description"
    if min_stars > 0:
        qs += f" stars:>={min_stars}"
    url = ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(qs)
           + f"&sort=updated&order=desc&per_page={min(max(limit, 1), 50)}")
    try:
        text, _ = fetch_text(url, timeout=15)
        data = json.loads(text)
    except Exception as e:
        print(f"Warning: GitHub Search API error for query '{query}': {e}. "
              f"Retry later, set GITHUB_TOKEN, or pass known boards with --repo.", file=sys.stderr)
        return []
    if data.get("message"):
        print(f"Warning: GitHub Search API: {data['message']}. Set GITHUB_TOKEN or pass --repo.", file=sys.stderr)
    return [{"name": i["full_name"], "stars": i.get("stargazers_count", 0),
             "branch": i.get("default_branch", "main"), "pushed": (i.get("pushed_at") or "")[:10]}
            for i in data.get("items", [])]


def list_owner_repos(owner: str, limit: int = 100) -> list[dict]:
    """All public repos of one owner that look like job boards (name or description mentions jobs, roles, hiring)."""
    out, page = [], 1
    kind = "users"  # /users/<owner>/repos also works for organizations
    while len(out) < limit and page <= 3:
        url = f"https://api.github.com/{kind}/{owner}/repos?per_page=100&page={page}&sort=updated"
        try:
            text, _ = fetch_text(url, timeout=15)
            items = json.loads(text)
        except Exception as e:
            print(f"Warning: could not list repos of '{owner}': {e}", file=sys.stderr)
            break
        if not isinstance(items, list) or not items:
            break
        for i in items:
            blob = f"{i.get('name','')} {i.get('description') or ''}".lower()
            if i.get("archived") or i.get("fork"):
                continue
            if re.search(r"job|intern|hiring|career|position|opening|graduate|new[- ]grad|role", blob):
                out.append({"name": i["full_name"], "stars": i.get("stargazers_count", 0),
                            "branch": i.get("default_branch", "main"), "pushed": (i.get("pushed_at") or "")[:10]})
        page += 1
    return out


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def _links(cell: str) -> list[str]:
    urls = re.findall(r'href=["\']([^"\']+)["\']', cell, re.I)
    urls += re.findall(r'\]\(\s*<?(https?://[^)>\s]+)>?[^)]*\)', cell)
    urls += re.findall(r'(?<![\("\'<])\bhttps?://[^\s|<>)"\']+', cell)
    seen, out = set(), []
    for u in urls:
        if u.startswith("http") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _pick_url(urls: list[str]) -> str:
    for u in urls:
        if any(h in u for h in ATS_HINTS):
            return u
    return urls[0] if urls else ""


def _map_header(cells: list[str]) -> dict:
    m = {}
    for i, raw in enumerate(cells):
        h = re.sub(r"[^a-z ]", " ", clean_name(raw).lower()).strip()
        if not h:
            continue
        for key, words in (("company", COMPANY_WORDS), ("role", ROLE_WORDS), ("loc", LOC_WORDS), ("apply", APPLY_WORDS)):
            if key not in m and any(w in h for w in words):
                m[key] = i
                break
    return m


def _rows_to_jobs(header: list[str] | None, rows: list[list[str]], source_name: str) -> list[dict]:
    if not rows:
        return []
    m = _map_header(header) if header else {}
    # Fall back to the conventional layout Company | Role | Location | ... | Apply
    if "role" not in m and "apply" not in m:
        if len(rows[0]) < 4:
            return []
        m = {"company": 0, "role": 1, "loc": 2}
    m.setdefault("company", 0)
    if "role" not in m:
        m["role"] = 1 if len(rows[0]) > 1 else 0
    jobs, last_company = [], ""
    for cells in rows:
        row_text = " ".join(cells)
        if "🔒" in row_text:
            continue
        def cell(k):
            i = m.get(k)
            return cells[i] if i is not None and i < len(cells) else ""
        urls = _links(cell("apply")) if "apply" in m else []
        if not urls:
            urls = _links(cell("role")) or _links(row_text)
        url = _pick_url(urls)
        if not url:
            continue
        company = clean_name(cell("company"))
        if company in ("↳", "", "-", "—") and last_company:
            company = last_company
        elif company:
            last_company = company
        title = clean_name(cell("role"))
        if not title:
            continue
        loc = " ".join(re.sub(r"<[^>]+>", " ", cell("loc")).split())
        jobs.append({"source": "github_board", "repo": source_name, "company": company,
                     "title": title, "location": loc, "url": clean_url(url)})
    return jobs


def parse_html_tables(content: str, source_name: str) -> list[dict]:
    jobs = []
    for tbl in re.findall(r"<table[^>]*>(.*?)</table>", content, re.S | re.I):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S | re.I)
        parsed = [re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S | re.I) for r in trs]
        parsed = [p for p in parsed if p]
        if not parsed:
            continue
        header = parsed[0] if re.search(r"<th", trs[0], re.I) else None
        jobs += _rows_to_jobs(header, parsed[1:] if header else parsed, source_name)
    return jobs


def parse_markdown_tables(content: str, source_name: str) -> list[dict]:
    lines = content.split("\n")
    jobs, i = [], 0
    sep = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
    while i < len(lines):
        if "|" in lines[i] and i + 1 < len(lines) and sep.match(lines[i + 1]) and "|" in lines[i + 1]:
            header = _split_row(lines[i])
            j, rows = i + 2, []
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(_split_row(lines[j]))
                j += 1
            jobs += _rows_to_jobs(header, rows, source_name)
            i = j
        else:
            i += 1
    return jobs


def parse_board(content: str, source_name: str) -> tuple[list[dict], str]:
    """Parse every table in the document (HTML and Markdown can be mixed). Returns (jobs, diagnosis)."""
    jobs = parse_html_tables(content, source_name) + parse_markdown_tables(content, source_name)
    if jobs:
        return jobs, "ok"
    n_md = len(re.findall(r"^\s*\|?[^|\n]+\|[^|\n]*\|", content, re.M))
    n_html = len(re.findall(r"<tr", content, re.I))
    if not n_md and not n_html:
        site = re.findall(r"https?://[^\s)\]>\"']+", content)
        live = [u for u in site if "github.com" not in u and "shields.io" not in u and "githubusercontent" not in u][:1]
        return [], "no tables in README (tool or site-backed board" + (f"; try {live[0]}" if live else "") + ")"
    return [], "tables present but no job rows with links (likely a company directory or a differently shaped board; read it directly)"


def filter_jobs(jobs: list[dict], keywords: list[str] = None, locations: list[str] = None, exclude_companies: list[str] = None) -> list[dict]:
    """Filter parsed listings by target technical keywords, locations, and blacklists."""
    filtered = []
    norm_excludes = [e.lower() for e in (exclude_companies or [])]
    norm_keywords = [k.lower() for k in (keywords or [])]
    norm_locations = [l.lower() for l in (locations or [])]

    for j in jobs:
        comp = j.get("company", "").lower()
        title = j.get("title", "").lower()
        loc = j.get("location", "").lower()

        # Hard company exclusion
        if any(exc in comp for exc in norm_excludes):
            continue

        # Keywords filter (if specified)
        if norm_keywords:
            if not any(k in title for k in norm_keywords):
                continue

        # Location filter (if specified)
        if norm_locations:
            if not any(l in loc for l in norm_locations):
                continue

        filtered.append(j)

    return filtered


def load_source(s: dict) -> dict:
    """Fetch and parse one source. Always returns a report entry; never raises."""
    rep = {"name": s.get("name"), "stars": s.get("stars"), "pushed": s.get("pushed"),
           "raw_rows": 0, "kept_rows": 0, "status": "", "via": "", "url": ""}
    jobs = []
    try:
        if s.get("path") and os.path.exists(s["path"]):
            with open(s["path"], "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            rep["via"], rep["url"] = "file", s["path"]
        elif s.get("url"):
            text, rep["via"] = fetch_text(s["url"])
            rep["url"] = s["url"]
        else:
            text, rep["url"], rep["via"] = fetch_readme(s["name"], s.get("branch"))
        jobs, diag = parse_board(text, s.get("name") or "custom_source")
        rep["raw_rows"], rep["status"] = len(jobs), diag
    except Exception as e:
        rep["status"] = f"fetch failed: {e}"
    return {"report": rep, "jobs": jobs}


def main():
    parser = argparse.ArgumentParser(description="Discover, fetch and parse job-board repositories on GitHub, and report every source tried.")
    parser.add_argument("--search", "-s", default=None,
                        help="Dynamic search query on GitHub (e.g. 'junior software engineer jobs', 'ai jobs')")
    parser.add_argument("--repo", "-r", nargs="+", default=None,
                        help="One or more GitHub repositories 'owner/repo' (e.g. <owner>/<repo>)")
    parser.add_argument("--owner", nargs="+", default=None,
                        help="One or more GitHub owners/orgs: every job-board-looking repo of each is fetched "
                             "Finds small boards that keyword search misses; take owner names from a board you already use.")
    parser.add_argument("--file", "-f", default=None,
                        help="Local path or raw URL of a markdown/HTML job board")
    parser.add_argument("--min-stars", type=int, default=0, help="Minimum stars for dynamic repo search")
    parser.add_argument("--max-repos", type=int, default=10,
                        help="How many repositories to fetch from a dynamic search (default: 10; all are reported)")
    parser.add_argument("--keywords", nargs="*", default=None, help="Keep roles whose title contains any of these")
    parser.add_argument("--locations", nargs="*", default=None, help="Keep roles whose location contains any of these")
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="Company substrings to drop (pass the user's exclusions and active-pipeline companies)")
    parser.add_argument("--output", "-o", default=None, help="Path to save the JSON results")
    args = parser.parse_args()

    sources = []
    if args.owner:
        for o in args.owner:
            repos = list_owner_repos(o.strip().strip("/"))
            print(f"[owner] {o}: {len(repos)} job-board-looking repositories", file=sys.stderr)
            sources.extend(repos)
    if args.file:
        if os.path.exists(args.file):
            sources.append({"name": os.path.basename(args.file), "path": args.file})
        else:
            sources.append({"name": os.path.basename(args.file), "url": args.file})
    elif args.repo:
        for r in args.repo:
            sources.append({"name": r.strip().strip("/")})
    elif args.search:
        found = search_github_repositories(args.search, min_stars=args.min_stars, limit=args.max_repos)
        print(f"[search] '{args.search}': {len(found)} repositories", file=sys.stderr)
        sources.extend(found)
    elif not args.owner:
        print("Error: provide one of --search, --repo, --owner, or --file.", file=sys.stderr)
        sys.exit(1)

    loaded = [load_source(s) for s in sources]
    all_jobs = []
    for l in loaded:
        all_jobs.extend(l["jobs"])

    seen, deduped = set(), []
    for j in all_jobs:
        u = j.get("url")
        if u and u not in seen:
            seen.add(u)
            deduped.append(j)
    filtered = filter_jobs(deduped, keywords=args.keywords, locations=args.locations, exclude_companies=args.exclude)
    kept_by_repo = {}
    for j in filtered:
        kept_by_repo[j["repo"]] = kept_by_repo.get(j["repo"], 0) + 1
    reports = []
    for l in loaded:
        r = l["report"]
        r["kept_rows"] = kept_by_repo.get(r["name"], 0)
        reports.append(r)

    print("\nSources report (every source tried; none are silently dropped):", file=sys.stderr)
    for r in reports:
        star = f" ★{r['stars']}" if r.get("stars") is not None else ""
        via = f" via {r['via']}" if r.get("via") else ""
        print(f"  - {r['name']}{star}{via}: {r['raw_rows']} rows parsed, {r['kept_rows']} kept after filters"
              f"{'' if r['status']=='ok' else ' | ' + r['status']}", file=sys.stderr)
    zero = [r["name"] for r in reports if r["raw_rows"] == 0]
    if zero:
        print(f"  ! {len(zero)} source(s) returned no rows ({', '.join(zero)}). Read them directly or use their live site; "
              f"do not report them as covered.", file=sys.stderr)
    print(f"Extracted {len(filtered)} matching roles (from {len(deduped)} unique listings)", file=sys.stderr)

    out = {"results": filtered, "sources_report": reports}
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"Saved results to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
