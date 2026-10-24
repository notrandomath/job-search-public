#!/usr/bin/env python3
"""
fetch_job_text.py - Universal script to fetch and inspect the complete, raw job description text from any URL or ATS endpoint.

Usage:
  python3 scripts/verify/fetch_job_text.py <job_url>
  python3 scripts/verify/fetch_job_text.py <job_url> --output <output_path>

Supported Platforms:
  - Greenhouse (web boards & API)
  - Ashby (web boards, __appData, and GraphQL API)
  - Lever (web boards & API)
  - Workday
  - Direct career portals / static HTML pages
"""

import sys
import os
import re
import json
import html
import urllib.request
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'lib'))
from _common import open_url, setup_stdio

setup_stdio()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-skill/1.0)",
    "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def clean_html_to_markdown(raw_html):
    """Converts raw HTML into clean, readable markdown-like text preserving structure."""
    if not raw_html:
        return ""
    
    text = html.unescape(raw_html)
    
    # Remove script and style tags
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<noscript.*?</noscript>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace headers with markdown headers
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n\n# \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n\n### \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n\n#### \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace list items with markdown bullet points
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'\n* \1', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace paragraphs and breaks with newlines
    text = re.sub(r'<p[^>]*>', r'\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', r'', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', r'\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*>', r'\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', r'', text, flags=re.IGNORECASE)
    
    # Replace bold and italic
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Clean up whitespace
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split('\n')]
    
    # Reconstruct paragraphs
    cleaned_lines = []
    prev_empty = False
    for l in lines:
        if not l:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(l)
            prev_empty = False
            
    return "\n".join(cleaned_lines).strip()

def fetch_greenhouse_api(board, job_id):
    """Fetches full job text from Greenhouse API."""
    url = f"https://api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    req = urllib.request.Request(url, headers=HEADERS)
    with open_url(req, timeout=12) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        title = data.get("title", "")
        loc = (data.get("location", {}) or {}).get("name", "")
        updated_at = data.get("updated_at", "")
        content = data.get("content", "")
        
        md_text = f"# {title}\n"
        md_text += f"**Company**: {board.capitalize()}\n"
        md_text += f"**Location**: {loc}\n"
        md_text += f"**Last Updated**: {updated_at}\n\n"
        md_text += "---\n\n"
        md_text += clean_html_to_markdown(content)
        return md_text

def fetch_workday_text(url):
    """Workday pages are client-rendered shells; read the public cxs detail JSON instead."""
    import urllib.parse
    p = urllib.parse.urlsplit(url)
    m = re.match(r"^/(?:[a-z]{2}-[A-Za-z]{2}/)?([^/]+)/(?:details|job)/(.+)$", p.path)
    if not m or "myworkdayjobs.com" not in p.netloc:
        return None
    tenant, site, rest = p.netloc.split(".")[0], m.group(1), m.group(2)
    req = urllib.request.Request(f"https://{p.netloc}/wday/cxs/{tenant}/{site}/job/{rest}",
                                 headers=dict(HEADERS, Accept="application/json"))
    with open_url(req, timeout=15) as resp:
        info = (json.loads(resp.read().decode("utf-8")).get("jobPostingInfo")) or {}
    if not info:
        return None
    md = f"# {info.get('title', '')}\n**Location**: {info.get('location', '')}\n"
    md += f"**Posted**: {info.get('startDate', '')}\n**Can apply**: {info.get('canApply')}\n\n---\n\n"
    return md + clean_html_to_markdown(info.get("jobDescription", ""))


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj
        for v in obj.values():
            r = _find_key(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r:
                return r
    return None


def apple_text(raw_html):
    """Apple's careers pages embed the posting in window.__staticRouterHydrationData."""
    m = re.search(r'__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);', raw_html, re.DOTALL)
    if not m:
        return None
    try:
        job = _find_key(json.loads(json.loads('"' + m.group(1) + '"')), "jobSummary")
    except Exception:
        return None
    if not job:
        return None
    md = f"# {job.get('postingTitle', '')}\n**Posted**: {job.get('postingDate', '')}\n\n---\n\n"
    for label, key in (("Summary", "jobSummary"), ("Description", "description"),
                       ("Minimum qualifications", "minimumQualifications"),
                       ("Preferred qualifications", "preferredQualifications")):
        if job.get(key):
            md += f"## {label}\n{job[key]}\n\n"
    return md.strip()


def fetch_job_text(url):
    """Fetches job description text directly from URL or ATS API."""
    url = url.strip()

    # 0. Workday (client-rendered shell; use the public cxs JSON)
    if "myworkdayjobs.com" in url:
        try:
            text = fetch_workday_text(url)
            if text:
                return text
        except Exception:
            pass

    # 1. Check for Greenhouse URLs
    gh_match = re.search(r'(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)', url)
    if gh_match:
        board, job_id = gh_match.group(1), gh_match.group(2)
        try:
            return fetch_greenhouse_api(board, job_id)
        except Exception:
            pass

    # 2. Check for gh_jid parameter (used by several Greenhouse-hosted career sites)
    gh_jid_match = re.search(r'[?&]gh_jid=(\d+)', url)
    if gh_jid_match:
        job_id = gh_jid_match.group(1)
        domain_match = re.search(r'https?://(?:www\.)?([^/.]+)', url)
        if domain_match:
            board = domain_match.group(1)
            try:
                return fetch_greenhouse_api(board, job_id)
            except Exception:
                pass

    # 3. Direct HTML fetch (handles Ashby __appData, Lever, Workday, and static career pages)
    req = urllib.request.Request(url, headers=HEADERS)
    with open_url(req, timeout=15) as resp:
        raw_html = resp.read().decode('utf-8', errors='ignore')
        
        apple = apple_text(raw_html)
        if apple:
            return apple

        # Check if Ashby window.__appData embedded
        ashby_match = re.search(r'window\.__appData\s*=\s*(\{.*?\});', raw_html, flags=re.DOTALL)
        if ashby_match:
            try:
                data = json.loads(ashby_match.group(1))
                posting = data.get("posting", {})
                if posting:
                    title = posting.get("title", "")
                    dept = posting.get("departmentName", "")
                    loc = posting.get("locationName", "")
                    desc_html = posting.get("descriptionHtml", "")
                    org_name = data.get("organization", {}).get("name", "")
                    
                    md_text = f"# {title}\n"
                    md_text += f"**Company**: {org_name}\n"
                    md_text += f"**Department**: {dept}\n"
                    md_text += f"**Location**: {loc}\n\n"
                    md_text += "---\n\n"
                    md_text += clean_html_to_markdown(desc_html)
                    return md_text
            except Exception:
                pass

        # Check if JSON-LD JobPosting is embedded
        jsonld_matches = re.findall(r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE)
        for j in jsonld_matches:
            try:
                data = json.loads(j.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        title = item.get("title", "")
                        org = (item.get("hiringOrganization") or {}).get("name", "") if isinstance(item.get("hiringOrganization"), dict) else ""
                        loc = item.get("jobLocation", {}).get("address", {}) if isinstance(item.get("jobLocation"), dict) else ""
                        desc = item.get("description", "")
                        date_posted = item.get("datePosted", "")
                        
                        md_text = f"# {title}\n"
                        if org:
                            md_text += f"**Company**: {org}\n"
                        if date_posted:
                            md_text += f"**Posted Date**: {date_posted}\n"
                        md_text += "---\n\n"
                        md_text += clean_html_to_markdown(desc)
                        return md_text
            except Exception:
                pass

        # Check if Next.js __NEXT_DATA__ is embedded
        next_match = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE)
        if next_match:
            try:
                data = json.loads(next_match.group(1).strip())
                props = data.get("props", {}).get("pageProps", {})
                job = props.get("job") or props.get("jobPosting") or props.get("posting")
                if isinstance(job, dict):
                    title = job.get("title") or job.get("name") or ""
                    desc = job.get("description") or job.get("descriptionHtml") or job.get("body") or ""
                    md_text = f"# {title}\n---\n\n" + clean_html_to_markdown(desc)
                    return md_text
            except Exception:
                pass

        # Fallback to general HTML cleaning
        return clean_html_to_markdown(raw_html)

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/verify/fetch_job_text.py <job_url> [--output <file_path>]")
        sys.exit(1)
        
    target_url = sys.argv[1]
    output_file = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--output":
        output_file = sys.argv[3]
        
    try:
        full_text = fetch_job_text(target_url)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_text)
            print(f"Saved job text to {output_file} ({len(full_text)} characters)")
        else:
            print(full_text)
    except Exception as e:
        print(f"Error fetching job text: {e}", file=sys.stderr)
        sys.exit(1)
