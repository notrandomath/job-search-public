#!/usr/bin/env python3
"""
Verify job postings by live fetch: existence and non-empty page (Check 1), level fit against a
caller-supplied band (Check 2), plus hints for hiring channel (input to Check 3).

Nothing here assumes a candidate type: pass the band with --max-yoe (required), and
--allow-titles / --include-title-regex / --exclude-title-regex to shape the title gate.
Text patterns are English-only; for other languages read the page and decide by hand.
"""

import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'lib'))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import open_url, setup_stdio

USER_AGENT = "Mozilla/5.0 (compatible; job-search-skill/1.0)"

setup_stdio()


SENIOR_TITLE_RE = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|lead|manager|director|vp|head of)\b", re.IGNORECASE)
BLOCKED_STATUSES = (401, 403, 406, 429, 451, 503, 999)  # the site refused the fetch; not evidence of closure
KNOWN_SHELL_HOSTS: list[str] = []  # set with --shell-hosts; shell pages are also detected generically below
COHORT_RE = re.compile(
    r"new\s+(?:college\s+)?grad|university\s+grad|early\s+career|campus|graduate\s+program|"
    r"emerging\s+talent|class\s+of\s+20\d\d|20\d\d\s+(?:start|cohort|graduat)|recent\s+grad", re.IGNORECASE)
# "5+ years ... experience", "3-5 years of professional experience", "experience: 4+ years"
YOE_FWD_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus|[-–]\s*\d{1,2}|to\s*\d{1,2}|or\s+more)?\s*(?:years?|yrs?)\b[^.\n]{0,60}?experience",
    re.IGNORECASE)
YOE_REV_RE = re.compile(
    r"experience[^.\n]{0,40}?(\d{1,2})\s*(?:\+|plus|[-–]\s*\d{1,2}|to\s*\d{1,2})?\s*(?:years?|yrs?)\b",
    re.IGNORECASE)


ALLOWED_TITLE_WORDS = set()


def title_is_senior(title):
    """Seniority words by whole word, minus any the caller allows (--allow-titles).
    'Member of Technical Staff' is a role name, not a level."""
    t = re.sub(r"technical\s+staff", " ", title or "", flags=re.IGNORECASE)
    return any(m.group(0).lower().rstrip(".") not in ALLOWED_TITLE_WORDS
               for m in SENIOR_TITLE_RE.finditer(t))


SOFT_YOE_RE = re.compile(
    r"or\s+equivalent|equivalent\s+(?:practical\s+|work\s+|professional\s+)?experience|internships?|co-?ops?|"
    r"academic|research|coursework|school\s+projects?|personal\s+projects?|open[- ]source|advanced\s+degree|"
    r"master'?s|ph\.?d|bootcamp|including", re.IGNORECASE)


def yoe_qualifier(text, phrase):
    """Words near the stated-years phrase that make it soft (equivalent experience, internships, research...)."""
    if not phrase:
        return ""
    i = text.find(phrase[:40])
    if i < 0:
        return ""
    ctx = text[max(0, i - 160): i + len(phrase) + 200]
    m = SOFT_YOE_RE.search(ctx)
    return m.group(0).lower() if m else ""


# Hard requirements: facts about the person that no framing changes. Years of experience are NOT here (soft).
HARD_PATTERNS = {
    "no_sponsorship": re.compile(
        r"(?:unable|not able|will not|won'?t|cannot|can'?t|do(?:es)? not|not)\s+(?:to\s+)?(?:offer\s+|provide\s+)?(?:visa\s+)?sponsor|"
        r"no\s+(?:visa\s+)?sponsorship|without\s+(?:the\s+need\s+for\s+)?(?:visa\s+)?sponsorship|"
        r"sponsorship\s+(?:is\s+)?not\s+(?:available|offered|provided)", re.IGNORECASE),
    "citizenship": re.compile(
        r"must\s+be\s+(?:a\s+)?(?:u\.?s\.?\s+)?citizen|(?:u\.?s\.?\s+)?citizenship\s+(?:is\s+)?required|"
        r"u\.?s\.?\s+citizens?\s+only|green\s+card\s+holders?\s+(?:or|and)\s+u\.?s\.?\s+citizens", re.IGNORECASE),
    "clearance": re.compile(
        r"security\s+clearance|ts\s*/\s*sci|top\s+secret|secret\s+clearance|public\s+trust|active\s+clearance", re.IGNORECASE),
    "graduation_window": re.compile(
        r"graduat(?:ing|ed|ion)\s+(?:between|in|by|before|after|on)\s+[^.]{0,40}20\d\d|class\s+of\s+20\d\d|"
        r"currently\s+enrolled|must\s+be\s+(?:a\s+)?(?:current\s+)?(?:student|enrolled)|returning\s+to\s+(?:school|a\s+degree)", re.IGNORECASE),
    "degree_required": re.compile(
        r"(?:ph\.?d\.?|doctorate|master'?s|bachelor'?s)\b[^.]{0,30}\b(?:is\s+)?required", re.IGNORECASE),
}
NEEDS_SPONSORSHIP = [False]  # set with --needs-sponsorship


EQUIVALENT_RE = re.compile(r"or\s+(?:equivalent|related|relevant|comparable)|equivalent\s+(?:practical\s+|work\s+)?experience|in\s+lieu\s+of", re.IGNORECASE)


NEGATED_BEFORE_RE = re.compile(r"\b(?:no|not|without|never|neither|nor)\b[^.]{0,25}$", re.IGNORECASE)
NEGATED_AFTER_RE = re.compile(
    r"^[^.]{0,30}?(?:not\s+(?:required|needed|necessary)|isn'?t\s+required|is\s+a\s+plus|preferred|optional|a\s+bonus)",
    re.IGNORECASE)


def _soft_mention(text, m):
    """'No security clearance required', 'clearance preferred': mentioned, but not a requirement."""
    return bool(NEGATED_BEFORE_RE.search(text[max(0, m.start() - 40): m.start()])
                or NEGATED_AFTER_RE.search(text[m.end(): m.end() + 45]))


def hard_requirements(text):
    out = {}
    for cat, rx in HARD_PATTERNS.items():
        m = rx.search(text or "")
        if not m:
            continue
        if cat == "clearance" and _soft_mention(text, m):
            others = [x for x in rx.finditer(text) if not _soft_mention(text, x)]
            if not others:
                continue
            m = others[0]
        if cat == "degree_required":  # "or equivalent experience" makes a degree line soft: no knockout is expected
            ctx = text[max(0, m.start() - 120): m.end() + 120]
            if EQUIVALENT_RE.search(ctx):
                continue
        out[cat] = " ".join(m.group(0).split())[:80]
    return out


NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10}
NUMBER_WORD_RE = re.compile(
    r"\b(" + "|".join(NUMBER_WORDS) + r")\b(?=\s*(?:\+|plus|[-–]\s*\w+|to\s*\w+|or\s+more)?\s*(?:years?|yrs?)\b)", re.IGNORECASE)
HISTORY_BEFORE_RE = re.compile(r"(?:past|last|in business for|founded|established|for the)\s*$", re.IGNORECASE)


def _overlapping(rx, text):
    """Matches that may overlap, so a skipped history phrase cannot swallow the real requirement after it."""
    pos = 0
    while True:
        m = rx.search(text, pos)
        if not m:
            return
        yield m
        pos = m.start() + 1


def stated_min_yoe(text):
    """Return (lowest-bound years, matched phrase) for the highest stated requirement, or (None, '')."""
    best, phrase = None, ""
    text = NUMBER_WORD_RE.sub(lambda mm: str(NUMBER_WORDS[mm.group(1).lower()]), text or "")
    for rx in (YOE_FWD_RE, YOE_REV_RE):
        for m in _overlapping(rx, text):
            n = int(m.group(1))
            if n >= 15:  # "20 years of experience" in company-history copy; ignore implausible requirement
                continue
            # The upper bound of a range ("0-2 years") is not a separate requirement.
            if re.search(r"\d\s*(?:-|\u2013|to)\s*$", text[max(0, m.start() - 8): m.start()]):
                continue
            # Company-history copy is not a requirement: "over the past 12 years, we have grown; ... experience"
            if HISTORY_BEFORE_RE.search(text[max(0, m.start() - 30): m.start()]):
                continue
            if re.search(r"[;]|\b(?:we|our|us)\b", m.group(0), re.IGNORECASE):
                continue
            if best is None or n > best:
                best, phrase = n, " ".join(m.group(0).split())[:90]
    return best, phrase


def fetch_workday(url, timeout=10):
    """Workday pages are client-rendered shells; read the public cxs detail JSON instead."""
    p = urllib.parse.urlsplit(url)
    m = re.match(r"^/(?:[a-z]{2}-[A-Za-z]{2}/)?([^/]+)/(?:details|job)/(.+)$", p.path)
    if not m:
        return None
    tenant, site, rest = p.netloc.split(".")[0], m.group(1), m.group(2)
    api = f"https://{p.netloc}/wday/cxs/{tenant}/{site}/job/{rest}"
    req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with open_url(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        return e.code, "", url, None
    except Exception:
        return None
    info = data.get("jobPostingInfo") or {}
    body = f"{info.get('title', '')} {info.get('jobDescription', '')} {info.get('jobRequisitionLocation', '')}"
    can_apply = info.get("canApply")
    # Synthesize an apply signal from the API flag so the generic check does not read a shell.
    html_doc = f"<html><body><h1>{info.get('title','')}</h1>{info.get('jobDescription','')}"
    html_doc += "<button>Apply</button>" if can_apply else "<p>This job is not open for applications</p>"
    html_doc += "</body></html>"
    return 200 if info else 404, html_doc, url, info.get("startDate") or info.get("posted")

def _json_get(url, timeout=10, data=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with open_url(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _synth(title, location, body, can_apply=True, posted=""):
    """A plain document built from an ATS record, so the generic checks read the real posting text."""
    import html as _h
    doc = f"<html><body><h1>{_h.escape(title or '')}</h1><p>{_h.escape(str(location or ''))}</p>"
    doc += f"<p>Posted {_h.escape(str(posted or ''))}</p>" if posted else ""
    doc += f"{body or ''}"
    doc += "<button>Apply</button>" if can_apply else "<p>This job is not open for applications</p>"
    return doc + "</body></html>"


def fetch_ats_json(url, timeout=10):
    """Read the posting from its ATS's public JSON instead of the (often client-rendered) page.

    Returns (status, document, final_url, posted) or None when the URL is not a supported platform.
    A 404 or an id missing from the employer's own board is real evidence of closure: status 404."""
    import html as _h
    p = urllib.parse.urlsplit(url)
    host, path = p.netloc.lower(), p.path
    try:
        m = re.match(r"^/([^/]+)/([0-9a-f]{8}-[0-9a-f-]{27})", path) if host == "jobs.lever.co" else None
        if m:  # Lever
            d = _json_get(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}", timeout)
            body = d.get("description", "") + "".join(f"<h3>{x.get('text','')}</h3>{x.get('content','')}" for x in d.get("lists", []))
            return 200, _synth(d.get("text"), (d.get("categories") or {}).get("location"), body + d.get("additional", ""), True), url, d.get("createdAt")
        m = re.match(r"^/([^/]+)/([0-9a-f]{8}-[0-9a-f-]{27})", path) if host == "jobs.ashbyhq.com" else None
        if m:  # Ashby: the board API lists every live posting with its description
            for j in _json_get(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}", timeout).get("jobs", []):
                if j.get("id") == m.group(2):
                    return 200, _synth(j.get("title"), j.get("location"), j.get("descriptionHtml", ""), j.get("isListed", True), j.get("publishedAt")), j.get("jobUrl") or url, j.get("publishedAt")
            return 404, "", url, None
        m = re.match(r"^/([^/]+)/(\d+)", path) if host == "jobs.smartrecruiters.com" else None
        if m:  # SmartRecruiters
            d = _json_get(f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}", timeout)
            secs = (d.get("jobAd") or {}).get("sections") or {}
            body = "".join(f"<h3>{v.get('title','')}</h3>{v.get('text','')}" for v in secs.values() if isinstance(v, dict))
            loc = (d.get("location") or {}).get("fullLocation") or (d.get("location") or {}).get("city")
            return 200, _synth(d.get("name"), loc, body, d.get("active", True), d.get("releasedDate")), url, d.get("releasedDate")
        m = re.match(r"^/([^/]+)/j/([0-9A-Za-z]+)", path) if host == "apply.workable.com" else None
        if m:  # Workable
            d = _json_get(f"https://apply.workable.com/api/v2/accounts/{m.group(1)}/jobs/{m.group(2)}", timeout)
            body = "".join(d.get(k) or "" for k in ("description", "requirements", "benefits"))
            loc = d.get("location") or {}
            return 200, _synth(d.get("title"), ", ".join(x for x in (loc.get("city"), loc.get("country")) if x), body, True, d.get("published")), url, d.get("published")
        m = re.match(r"^/hcmUI/CandidateExperience/[^/]+/sites/([^/]+)/job/(\d+)", path)
        if m and "oraclecloud.com" in host:  # Oracle HCM
            d = _json_get(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?onlyData=true"
                          f"&finder=ById;Id=%22{m.group(2)}%22,siteNumber={m.group(1)}", timeout)
            it = (d.get("items") or [None])[0]
            if not it:
                return 404, "", url, None
            body = "".join(f"<h3>{k}</h3>{it.get(k) or ''}" for k in ("ExternalDescriptionStr", "ExternalQualificationsStr", "ExternalResponsibilitiesStr") if it.get(k))
            return 200, _synth(it.get("Title"), it.get("PrimaryLocation"), body, True, it.get("ExternalPostedStartDate")), url, it.get("ExternalPostedStartDate")
        m = re.match(r"^/careers/job/(\d+)", path) if host == "apply.careers.microsoft.com" else None
        if m:  # Microsoft careers (Eightfold)
            d = (_json_get(f"https://apply.careers.microsoft.com/api/pcsx/position_details?position_id={m.group(1)}&domain=microsoft.com&hl=en", timeout).get("data") or {})
            if not d:
                return 404, "", url, None
            return 200, _synth(d.get("name"), ", ".join(d.get("locations") or []), d.get("jobDescription", ""), True, d.get("postedTs")), url, d.get("postedTs")
    except urllib.error.HTTPError as e:
        return e.code, "", url, None
    except Exception:
        return None
    return None


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_url(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            final_url = resp.geturl()
            return resp.status, content, final_url
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception:
        return 0, "", url

def extract_deep_content(raw_html):
    """Extract embedded JSON-LD, Next.js hydration state, Ashby appData, and meta tags."""
    if not raw_html:
        return "", ""
    
    extracted_parts = []

    # 1. JSON-LD Schema (JobPosting)
    jsonld_matches = re.findall(r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE)
    for j in jsonld_matches:
        try:
            data = json.loads(j.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    desc = item.get("description", "")
                    title = item.get("title", "")
                    exp = str(item.get("experienceRequirements", ""))
                    extracted_parts.append(f"{title} {desc} {exp}")
        except Exception:
            pass

    # 2. Next.js hydration payload
    next_match = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE)
    if next_match:
        try:
            data = json.loads(next_match.group(1).strip())
            props = data.get("props", {}).get("pageProps", {})
            job_obj = props.get("job") or props.get("jobPosting") or props.get("posting") or props
            extracted_parts.append(json.dumps(job_obj))
        except Exception:
            pass

    # 3. Ashby window.__appData
    ashby_match = re.search(r'window\.__appData\s*=\s*(\{.*?\});', raw_html, re.DOTALL)
    if ashby_match:
        try:
            data = json.loads(ashby_match.group(1))
            posting = data.get("posting", {})
            extracted_parts.append(posting.get("title", "") + " " + posting.get("descriptionHtml", ""))
        except Exception:
            pass

    # 3b. Apple-style hydration state (window.__staticRouterHydrationData = JSON.parse("..."))
    hyd = re.search(r'__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);', raw_html, re.DOTALL)
    if hyd:
        try:
            state = json.loads(json.loads('"' + hyd.group(1) + '"'))
            stack = [state]
            while stack:
                o = stack.pop()
                if isinstance(o, dict):
                    if "jobSummary" in o:
                        extracted_parts.append(" ".join(str(o.get(k, "")) for k in (
                            "postingTitle", "jobSummary", "description", "minimumQualifications", "preferredQualifications")))
                        break
                    stack.extend(o.values())
                elif isinstance(o, list):
                    stack.extend(o)
        except Exception:
            pass

    # 4. OpenGraph and meta description
    meta_matches = re.findall(r'<meta\s+(?:name|property)=["\'](?:og:description|description)["\']\s+content=["\'](.*?)["\']', raw_html, re.IGNORECASE)
    for m in meta_matches:
        extracted_parts.append(m)

    # 5. Visible rendered text (stripping scripts and styles so i18n bundle error strings don't cause false positives)
    no_scripts = re.sub(r'<script.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    no_styles = re.sub(r'<style.*?</style>', '', no_scripts, flags=re.DOTALL | re.IGNORECASE)
    visible_text = re.sub(r"<[^>]+>", " ", no_styles)
    visible_text = " ".join(visible_text.split())

    combined = " ".join(extracted_parts + [visible_text])
    clean_combined = re.sub(r"<[^>]+>", " ", combined)
    return visible_text, " ".join(clean_combined.split())

def is_dead_redirect(orig_url, final_url):
    """Detect if the ATS redirected away from a specific requisition slug to generic careers root."""
    if not orig_url or not final_url or orig_url == final_url:
        return False
    # If original had a specific ID/slug (e.g. /12345 or /details/ or gh_jid=)
    orig_has_id = bool(re.search(r'(?:/\d+|/details/|/jobs/|/job/|gh_jid=|jobId=)', orig_url))
    # Final URL drops the ID and ends at /careers, /jobs, /home, or domain root
    final_is_root = bool(re.search(r'/(?:careers|jobs|home|en-us/?|search/?)?$', final_url.rstrip("/")))
    if orig_has_id and final_is_root and (orig_url.rstrip("/") != final_url.rstrip("/")):
        return True
    # ATS error redirect (e.g. Greenhouse '?error=true') or same-host redirect that drops the requisition segment
    o, f = urllib.parse.urlsplit(orig_url), urllib.parse.urlsplit(final_url)
    if re.search(r"(?:^|&)error(?:=|&|$)", f.query):
        return True
    last = o.path.rstrip("/").rsplit("/", 1)[-1]
    if o.netloc.lower() == f.netloc.lower() and last and last not in f.path and last not in f.query:
        return True
    return False


ATS_HOST_RE = re.compile(
    r"(?:greenhouse\.io|ashbyhq\.com|lever\.co|myworkdayjobs\.com|smartrecruiters\.com|workable\.com|"
    r"jobvite\.com|icims\.com|bamboohr\.com|recruitee\.com|teamtailor\.com|breezy\.hr|rippling\.com|"
    r"oraclecloud\.com|eightfold\.ai|taleo\.net|successfactors\.(?:com|eu)|paylocity\.com|dayforcehcm\.com|ultipro\.com)$")
EMPLOYER_HOSTS: list[str] = []  # extra hosts to treat as the employer's own (--employer-hosts)
GH_ID_RE = re.compile(r"gh_jid=(\d+)")


def _host(url):
    return urllib.parse.urlsplit(url or "").netloc.lower().split(":")[0]


def is_ats_host(host):
    return bool(ATS_HOST_RE.search(host))


def company_tokens(company):
    words = [w for w in re.split(r"[^a-z0-9]+", (company or "").lower()) if len(w) >= 3]
    joined = "".join(re.findall(r"[a-z0-9]+", (company or "").lower()))
    return words, joined


def host_is_employer(host, company):
    """True when the host is an ATS, an explicitly trusted host, or visibly the company's own domain."""
    if is_ats_host(host) or any(host.endswith(h.lower()) for h in EMPLOYER_HOSTS):
        return True
    squashed = re.sub(r"[^a-z0-9]", "", host)
    words, joined = company_tokens(company)
    return bool((joined and joined in squashed) or any(w in squashed for w in words))


def find_employer_link(raw, page_host, company):
    """Return ('ats', url) for an ATS posting link, ('gh', url, id) for a gh_jid link, or None."""
    if not raw:
        return None
    urls = re.findall(r'https?://[^\s"\'<>)\\]+', raw.replace("\\/", "/"))
    words, joined = company_tokens(company)
    ats, gh = [], []
    for u in urls:
        u = u.rstrip(".,;")
        h = _host(u)
        if h == page_host:
            continue
        if is_ats_host(h) and re.search(r"/(?:[0-9a-f]{8}-[0-9a-f-]{27,}|\d{5,})", u):
            ats.append(u)
        elif GH_ID_RE.search(u):
            gh.append(u)
    def score(u):
        sq = re.sub(r"[^a-z0-9]", "", u.lower())
        return -int(bool(joined and joined in sq) or any(w in sq for w in words))
    if ats:
        return ("ats", sorted(ats, key=score)[0])
    if gh:
        u = sorted(gh, key=score)[0]
        return ("gh", u, GH_ID_RE.search(u).group(1))
    return None


def check_greenhouse(slugs, job_id, timeout=10):
    """Return ('live', slug, html) | ('missing', slug, None) | ('unknown', None, None)."""
    import html as _html
    for slug in slugs:
        base = f"https://boards-api.greenhouse.io/v1/boards/{slug}"
        try:
            req = urllib.request.Request(f"{base}/jobs/{job_id}", headers={"User-Agent": USER_AGENT})
            with open_url(req, timeout=timeout) as resp:
                d = json.loads(resp.read().decode("utf-8", errors="ignore"))
            body = _html.unescape(d.get("content", ""))
            doc = (f"<html><body><!-- {job_id} --><h1>{d.get('title','')}</h1>"
                   f"<p>{(d.get('location') or {}).get('name','')}</p>{body}<button>Apply</button></body></html>")
            return "live", slug, doc, d.get("absolute_url")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                continue
        except Exception:
            continue
        try:  # job id absent; is the board itself real?
            req = urllib.request.Request(f"{base}/jobs", headers={"User-Agent": USER_AGENT})
            with open_url(req, timeout=timeout) as resp:
                json.loads(resp.read().decode("utf-8", errors="ignore"))
            return "missing", slug, None, None
        except Exception:
            continue
    return "unknown", None, None, None


def greenhouse_slug_guesses(raw, link_host, company):
    found = re.findall(r"greenhouse\.io/(?:embed/job_board\?for=|v1/boards/)?([a-z0-9_-]{2,})", raw or "", re.I)
    found += re.findall(r"[?&]for=([a-z0-9_-]{2,})", raw or "", re.I)
    words, joined = company_tokens(company)
    stem = link_host.split(".")[-2] if link_host.count(".") >= 1 else ""
    guesses = found + [joined, "-".join(words), stem, "".join(re.findall(r"[a-z0-9]+", stem))]
    out, seen = [], set()
    for g in guesses:
        g = (g or "").lower()
        if g and g not in seen and g not in ("embed", "boards", "jobs", "job_board", "v1"):
            seen.add(g)
            out.append(g)
    return out


def _unconfirmed(job, url, status, reasons, extra=None):
    res = dict(job)
    res.update({"url": url, "final_url": url, "status": status, "exists_and_non_empty": False,
                "level_matched": False, "is_proper": False, "failure_reasons": reasons,
                "stated_min_yoe": None, "below_band": False, "senior_yoe_found": [],
                "early_signals": [], "channel_hint": "unknown", "content_hash": "",
                "manual_verify_hint": "Open the employer's own careers page and confirm the posting there",
                "text_snippet": "", "verification_method": "none", "verification_tier": "unconfirmed",
                "client_rendered": False})
    if extra:
        res.update(extra)
    return res


def analyze_job(job, max_yoe, band_min_yoe=None, _override=None, _aggregator_url=None, _browser=False):
    url = job.get("url")
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    updated_at = job.get("updated_at", "")

    # Exclude title keywords for level match
    is_senior_title = title_is_senior(title)

    host = urllib.parse.urlsplit(url or "").netloc.lower()
    employer_check = None
    # Greenhouse requisitions are verified through the public board API, not the page: many employers
    # redirect board URLs to a client-rendered careers page that never contains the posting text.
    if not _override and url:
        gm = re.match(r"^/([^/]+)/jobs/(\d+)", urllib.parse.urlsplit(url).path) if "greenhouse.io" in host else None
        gq = GH_ID_RE.search(url)
        gh_id = gm.group(2) if gm else (gq.group(1) if gq else None)
        if gh_id:
            slugs = [gm.group(1)] if gm else greenhouse_slug_guesses("", host, company)
            state, slug, doc, abs_url = check_greenhouse(slugs, gh_id)
            if state == "live":
                _override = (200, doc, abs_url or url)
                employer_check = f"greenhouse board '{slug}' lists requisition {gh_id}"
            elif state == "missing":
                return _unconfirmed(job, url, 404, [
                    f"Employer board '{slug}' does not list requisition {gh_id} (closed or removed)"],
                    {"aggregator_url": _aggregator_url} if _aggregator_url else None)
    wd = fetch_workday(url) if "myworkdayjobs.com" in host and not _override else None
    ats = fetch_ats_json(url) if not _override and not wd else None
    method = "page"
    if _override:
        status, raw_content, final_url = _override
        method = "browser" if _browser else "employer-api"
    elif wd:
        status, raw_content, final_url = wd[0], wd[1], wd[2]
        method = "ats-api"
    elif ats:
        status, raw_content, final_url = ats[0], ats[1], ats[2]
        method = "ats-api"
    else:
        status, raw_content, final_url = fetch_url(url)

    # Employer-side verification: a page on a third-party host (aggregator, tracker mirror, wrapper)
    # is never verification by itself, because it can outlive the posting. Follow it to the employer.
    if not _override and not host_is_employer(host.split(":")[0], company):
        link = find_employer_link(raw_content, host.split(":")[0], company)
        agg = {"aggregator_url": url}
        if link and link[0] == "ats":
            res = analyze_job(dict(job, url=link[1]), max_yoe, band_min_yoe, _aggregator_url=url)
            res["aggregator_url"] = url
            return res
        if link and link[0] == "gh":
            lh = _host(link[1])
            state, slug, doc, abs_url = check_greenhouse(greenhouse_slug_guesses(raw_content, lh, company), link[2])
            if state == "live":
                res = analyze_job(dict(job, url=abs_url or link[1]), max_yoe, band_min_yoe,
                                  _override=(200, doc, abs_url or link[1]), _aggregator_url=url)
                res["aggregator_url"] = url
                res["employer_check"] = f"greenhouse board '{slug}' lists requisition {link[2]}"
                return res
            if state == "missing":
                return _unconfirmed(job, link[1], status, [
                    f"Employer board '{slug}' does not list requisition {link[2]}; the third-party page is stale or the role was removed"], agg)
            return _unconfirmed(job, link[1], status, [
                f"Could not confirm requisition {link[2]} on the employer's board; third-party page is not verification"], agg)
        return _unconfirmed(job, url, status, [
            "Third-party page with no resolvable employer posting link; find this role on the employer's own careers page"], agg)
    is_shell_host = any(host.endswith(h) for h in KNOWN_SHELL_HOSTS)
    visible_text, clean_text = extract_deep_content(raw_content)

    # Check 1: Existence & Non-Empty Content
    expired_phrases = [
        "this job is no longer available", "position has been closed",
        "job has expired", "posting is no longer active",
        "no longer accepting applications",
        "role does not exist or is no longer available", "position is closed"
    ]
    # Generic error-page wording also shows up in footers and help text of live pages: count it only
    # when the page is short or the phrase leads the page.
    error_page_phrases = ["404 not found", "page not found"]
    waf_challenge_phrases = [
        "cf-browser-verification", "just a moment...", "enable javascript to view",
        "performing security verification", "verify you are human", "verifying you are human",
        "checking your browser before accessing", "attention required! | cloudflare",
        "protect against malicious bots", "please complete the security check"
    ]

    # Check phrases on visible text only (scripts stripped, to avoid i18n dictionary false positives)
    vis = visible_text.lower()
    is_expired = (any(p in vis for p in expired_phrases)
                  or (any(p in vis for p in error_page_phrases)
                      and (len(vis) < 1500 or any(p in vis[:600] for p in error_page_phrases))))
    # A challenge page is short; a long live posting that merely mentions a captcha vendor is not blocked.
    is_waf_block = len(vis) < 1500 and any(p in vis for p in waf_challenge_phrases)
    dead_redirect = is_dead_redirect(url, final_url)
    has_substance = len(clean_text) >= 300

    # If the URL carries a requisition number, the page should show it, or at least the posting's title.
    # (Client-rendered pages often keep the id only in the URL, so a missing id alone is not evidence.)
    req_match = re.search(r'/details/(\d+)', url) or re.search(r'/jobs/(\d+)', url) or re.search(r'gh_jid=(\d+)', url)
    req_id_missing = False
    if req_match and raw_content:
        req_id = req_match.group(1)
        title_words = [w for w in re.split(r"\W+", title.lower()) if len(w) > 2]
        found = sum(w in clean_text.lower() for w in title_words)
        title_present = bool(title_words) and found * 2 >= len(title_words)
        if req_id not in raw_content and not title_present:
            req_id_missing = True

    # Application channel: apply wording in the visible and structured text, or an apply field/label in the
    # page payload (client-rendered pages keep it there). Calls such as fn.apply(...) are not a channel:
    # every script bundle contains them.
    has_apply_channel = bool(
        re.search(r"\b(?:apply|submit (?:your |an )?application|job application|application form|submit (?:your )?resume)\b",
                  clean_text, re.IGNORECASE)
        or re.search(r"(?<![.\w])apply(?![\w(])|applyurl|applicationurl|apply_url|directapply|\"applylink\"",
                     raw_content or "", re.IGNORECASE))

    exists_and_non_empty = (
        (status == 200) and
        (not is_shell_host) and
        has_substance and 
        (not is_expired) and 
        (not is_waf_block) and 
        (not dead_redirect) and 
        (not req_id_missing) and
        has_apply_channel
    )

    # Check 2: Calibrated Level Match (parameterized to max_yoe), scanned over the FULL cleaned text
    yoe_threshold = max_yoe + 1
    stated_min, yoe_phrase = stated_min_yoe(clean_text)
    soft_qualifier = yoe_qualifier(clean_text, yoe_phrase)
    hard_reqs = hard_requirements(clean_text)
    hard_blockers = [c for c in ("no_sponsorship", "citizenship", "clearance") if c in hard_reqs] if NEEDS_SPONSORSHIP[0] else []
    senior_matches = [yoe_phrase] if (stated_min is not None and stated_min >= yoe_threshold) else []
    below_band = bool(band_min_yoe is not None and stated_min is not None and stated_min < band_min_yoe)

    level_matched = (not is_senior_title) and (len(senior_matches) == 0)

    # Level/channel signals found in the posting, for the agent's judgment (not gates)
    early_signals = []
    for term in ["fellow", "residency", "returnship", "apprentice", "internship", "early career", "new grad",
                 "graduate program", "entry level", "junior", "associate", "mid-level", "senior", "principal",
                 "director", "contract", "part-time"]:
        if term in title.lower() or term in clean_text.lower()[:2000]:
            early_signals.append(term)

    failure_reasons = []
    manual_hint = ""
    if not exists_and_non_empty:
        if is_shell_host:
            failure_reasons.append("Aggregator shell page (not the employer posting); follow it to the employer ATS")
        elif status in BLOCKED_STATUSES:
            failure_reasons.append(f"Blocked by the site (HTTP {status}); this is not evidence the role is closed")
            manual_hint = "The site refused an automated fetch; check it through the employer's JSON endpoint, a browser tool, or by opening it"
        elif status == 0:
            failure_reasons.append("Could not reach the page (network error or timeout); not evidence the role is closed")
        elif status == 404 and method == "ats-api":
            failure_reasons.append("The employer's own job data no longer lists this posting (closed or removed)")
        elif status != 200:
            failure_reasons.append(f"HTTP Status {status} (Dead/Unreachable URL)")
        elif dead_redirect:
            failure_reasons.append(f"Dead Redirect (Redirected to generic portal: {final_url})")
        elif is_waf_block:
            failure_reasons.append("WAF / Bot challenge detected; not evidence the role is closed")
            manual_hint = "The site served a bot-verification page; use a real browser tool or the employer's JSON endpoint"
        elif is_expired:
            failure_reasons.append("Page indicates job is expired / no longer available")
        elif not has_substance:
            failure_reasons.append("Empty page body (<300 characters)")
            if raw_content and "<script" in raw_content.lower():
                manual_hint = "Client-rendered page; open it in a browser or find its JSON endpoint to verify manually"
        elif req_id_missing:
            failure_reasons.append("Requisition ID not found in page payload (expired/invalid requisition)")
        elif not has_apply_channel:
            failure_reasons.append("No active apply button or submission form detected")
    if not level_matched:
        if is_senior_title:
            failure_reasons.append(f"Title indicates senior scope ({title})")
        if senior_matches:
            failure_reasons.append(f"Stated YOE requires >={yoe_threshold} years ({senior_matches[0]})")

    for c in hard_blockers:
        failure_reasons.append(f"Hard requirement the candidate cannot meet ({c}): \"{hard_reqs[c]}\"")
    is_proper = exists_and_non_empty and level_matched and not hard_blockers
    # A page we could not read is not a closed posting: blocked, bot-walled, unreachable, or a client-rendered shell.
    renderable = bool(not exists_and_non_empty and not is_shell_host and (
        status in (0, *BLOCKED_STATUSES) or is_waf_block
        or (status == 200 and not has_substance and raw_content and "<script" in raw_content.lower())))
    # Near miss: live posting, no senior title, stated minimum only 1 to 2 years above the band.
    # Not verified for the main list, but worth a labeled "stretch" entry for the agent to judge.
    # A years requirement that mentions equivalent experience, internships, research or an advanced degree
    # is soft: school work can count, so allow a wider gap (up to 3 years) before it stops being a stretch.
    # A stated number is a recruiter's discretion, not a wall: report the gap and rough odds, never a flat reject.
    gap = (stated_min - max_yoe) if stated_min is not None else None
    reach = 4 if soft_qualifier else 3
    stretch_candidate = bool(exists_and_non_empty and not level_matched and not is_senior_title and not hard_blockers
                             and gap is not None and 0 < gap <= reach)
    stretch_odds = ""
    if stretch_candidate:
        stretch_odds = "reasonable" if (gap <= 1 or (soft_qualifier and gap <= 2)) else "long_shot"

    res = dict(job)
    if employer_check:
        res["employer_check"] = employer_check
    res.update({
        "url": url,
        "final_url": final_url,
        "status": status,
        "exists_and_non_empty": exists_and_non_empty,
        "level_matched": level_matched,
        "is_proper": is_proper,
        "stretch_candidate": stretch_candidate,
        "yoe_soft_qualifier": soft_qualifier,
        "yoe_gap": gap,
        "stretch_odds": stretch_odds,
        "hard_requirements": hard_reqs,
        "failure_reasons": failure_reasons,
        "stated_min_yoe": stated_min,
        "below_band": below_band,
        "senior_yoe_found": senior_matches[:2],
        "early_signals": early_signals[:5],
        "channel_hint": ("internship" if re.search(r"\bintern(ship)?\b|co-?op", title, re.I)
                         else "university/cohort" if COHORT_RE.search(title + " " + clean_text[:3000])
                         else "industry/open"),
        "content_hash": hashlib.sha1(clean_text[:3000].encode("utf-8", "ignore")).hexdigest() if clean_text else "",
        "manual_verify_hint": manual_hint,
        "text_snippet": clean_text[:400],
        "verification_method": method,
        "verification_tier": ("verified" if is_proper else "could_not_machine_check" if renderable else "rejected"),
        "client_rendered": renderable,
    })
    return res

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify and filter job postings for level calibration.")
    parser.add_argument("jobs_json_file", help="Path to the JSON file with raw job results")
    parser.add_argument("--output", "-o", default="verified_roles.json",
                        help="Path to write verified results JSON (default: verified_roles.json)")
    parser.add_argument("--prior-dir", default=None,
                        help="Optional folder of earlier runs (job_list.md files); roles already listed there are dropped.")
    parser.add_argument("--max-yoe", type=int, required=True,
                        help="Highest stated minimum years of experience that still fits the candidate's calibrated band (derive from intake; no default)")
    parser.add_argument("--min-yoe", type=int, default=None,
                        help="Optional: flag (not fail) postings whose stated minimum is below this, as below-band")
    parser.add_argument("--allow-titles", nargs="*", default=[],
                        help="Seniority words to permit in titles (e.g. senior staff lead); default none are allowed")
    parser.add_argument("--include-title-regex", default=None,
                        help="Keep only titles matching this regex (from the role family chosen at intake); default: no title filter")
    parser.add_argument("--exclude-title-regex", default=None,
                        help="Drop titles matching this regex")
    parser.add_argument("--shell-hosts", nargs="*", default=None,
                        help="Hosts known to serve landing/shell pages instead of postings (none by default; identical page text across URLs on one host is detected automatically)")
    parser.add_argument("--employer-hosts", nargs="*", default=[],
                        help="Extra hosts to treat as the employer's own careers site (a posting on any other non-ATS host that does not "
                             "visibly belong to the company is followed to the employer, and rejected if it cannot be confirmed there)")
    parser.add_argument("--needs-sponsorship", action="store_true",
                        help="Candidate needs visa sponsorship or has no clearance/citizenship: fail postings that state no sponsorship, "
                             "citizenship-only, or a security clearance (they are always reported under hard_requirements)")
    parser.add_argument("--exclude-companies", nargs="*", default=[],
                        help="Company name substrings to drop before verification (hard exclusions and active-pipeline companies incl. parents/subsidiaries)")
    parser.add_argument("--render", choices=["off", "headless", "headed"], default="headless",
                        help="For pages that are client-rendered or bot-walled: render them in a browser (needs Playwright; "
                             "see render_page.py). 'headless' uses a hidden browser; 'headed' may also open a visible Chrome "
                             "window for bot walls. Silently skipped when Playwright is not installed. Default: headless")
    parser.add_argument("--render-max", type=int, default=30, help="Most pages to render in one run (default 30)")
    args = parser.parse_args()

    json_path = args.jobs_json_file
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    results = data if isinstance(data, list) else data.get("results", [])
    print(f"Loaded {len(results)} total raw results", flush=True)

    ALLOWED_TITLE_WORDS.update(w.lower().rstrip(".") for w in args.allow_titles)
    EMPLOYER_HOSTS[:] = args.employer_hosts
    NEEDS_SPONSORSHIP[0] = args.needs_sponsorship
    if args.shell_hosts is not None:
        KNOWN_SHELL_HOSTS[:] = args.shell_hosts
    include_re = re.compile(args.include_title_regex, re.IGNORECASE) if args.include_title_regex else None
    exclude_re = re.compile(args.exclude_title_regex, re.IGNORECASE) if args.exclude_title_regex else None

    candidates = []
    for r in results:
        title = r.get("title", "") or ""
        if include_re and not include_re.search(title):
            continue
        if exclude_re and exclude_re.search(title):
            continue
        candidates.append(r)  # seniority is judged in Check 2 against --allow-titles

    if args.exclude_companies:
        excl = [e.lower() for e in args.exclude_companies]
        before = len(candidates)
        candidates = [c for c in candidates if not any(e in str(c.get("company", "")).lower() for e in excl)]
        print(f"Company Exclusion Filter: dropped {before - len(candidates)} roles (ERR_EXCLUDED_COMPANY).", flush=True)

    if args.prior_dir:
        try:
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
            from prior_jobs import filter_disjoint
            candidates, excluded = filter_disjoint(candidates, args.prior_dir)
            print(f"Prior-run filter [{args.prior_dir}]: dropped {len(excluded)} previously listed roles. {len(candidates)} remain for verification.", flush=True)
        except Exception as e:
            print(f"Warning: Disjoint set filter error: {e}", flush=True)

    print(f"Title filter kept {len(candidates)} roles. Verifying URLs concurrently (max YOE: {args.max_yoe})...", flush=True)

    verified = []
    unverified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(analyze_job, c, args.max_yoe, args.min_yoe): c for c in candidates}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res.get("is_proper"):
                verified.append(res)
            elif res:
                unverified.append(res)

    # Ladder rung 3: render the pages a plain fetch could not read, in one browser session.
    if args.render != "off":
        todo = [r for r in unverified if r.get("client_rendered")][:args.render_max]
        if todo:
            try:
                import render_page
                av = render_page.availability()
                if av["playwright"] and (av["cached_chromium"] or av["installed_chrome"]):
                    print(f"Rendering {len(todo)} client-rendered or blocked pages in a browser...", flush=True)
                    pages = {r["url"]: r for r in render_page.render_any([r["url"] for r in todo], allow_headed=(args.render == "headed"))}
                    import html as _h
                    for old_res in todo:
                        pg = pages.get(old_res["url"])
                        if not pg or pg.get("blocked") or pg.get("error") or len(pg.get("text", "")) < 300:
                            old_res["failure_reasons"].append("Browser render did not return a readable posting")
                            continue
                        doc = f"<html><body>{_h.escape(pg['text'])}</body></html>"
                        job = {k: v for k, v in old_res.items() if k in ("company", "title", "location", "updated_at", "source")}
                        job["url"] = old_res["url"]
                        new_res = analyze_job(job, args.max_yoe, args.min_yoe, _override=(200, doc, pg.get("final_url") or old_res["url"]), _browser=True)
                        old_res.clear()
                        old_res.update(new_res)
                    verified.extend(r for r in unverified if r.get("is_proper"))
                    unverified[:] = [r for r in unverified if not r.get("is_proper")]
                else:
                    print("Render skipped: Playwright or a browser is not available (optional).", flush=True)
            except ImportError:
                pass

    # Identical page text served for different URLs on one host means a shell/landing page, not postings.
    groups = {}
    for v in verified:
        h = v.get("content_hash")
        if h:
            groups.setdefault((urllib.parse.urlsplit(v["url"]).netloc, h), []).append(v)
    for grp in groups.values():
        if len(grp) >= 2 and len({g["url"] for g in grp}) >= 2:
            for v in grp:
                v["is_proper"] = False
                v["failure_reasons"].append(f"Identical page text across {len(grp)} URLs on this host (shell page)")
    unverified.extend(v for v in verified if not v["is_proper"])
    verified = [v for v in verified if v["is_proper"]]

    print(f"\nVerification Complete: {len(verified)} VERIFIED (PROPER) roles, {len(unverified)} NOT VERIFIED (NOT PROPER) roles rejected.\n", flush=True)
    for v in verified:
        print(f"✅ [PROPER] [{v.get('company', '').upper()}] {v.get('title', '')}")
        print(f"   Location: {v.get('location', '')}")
        print(f"   URL: {v.get('url', '')}")
        print(f"   Updated: {v.get('updated_at', 'N/A')}")
        print(f"   Early Signals: {v.get('early_signals', [])}")
        print("-" * 60, flush=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(verified, f, indent=2)

    out_root, out_ext = _os.path.splitext(args.output)
    rejected_path = f"{out_root}_rejected{out_ext or '.json'}"
    with open(rejected_path, "w", encoding="utf-8") as f:
        json.dump(unverified, f, indent=2)
    print(f"Saved {len(verified)} verified roles to {args.output}")
    print(f"Saved {len(unverified)} rejected roles with diagnostics to {rejected_path}")

if __name__ == "__main__":
    main()
