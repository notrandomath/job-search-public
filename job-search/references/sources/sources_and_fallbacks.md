# Sources, Source Quality, and Fallbacks

Two questions this file answers: **which sources deserve the user's attention**, and **what to do when a script cannot run** (no Python, no network, a different OS, a chat-only host). Run `python scripts/doctor.py` first; it prints what works here.

## 1. Source quality ladder (a counselor's priorities)

Rank by how close the source is to the hiring team and how well it is filtered for the person's level. Spend effort top-down.

| Rank | Source | Why | Caveat |
|---|---|---|---|
| 1 | **Employer-direct**: company ATS boards, career sites, university / early-careers pages | Ground truth; the posting is the requisition | Mega-caps with in-house portals need a page fetch, not an API |
| 2 | **Curated community lists** (GitHub trackers for early-career, internship, AI/ML, quant; field-specific boards and society job lists for experienced and non-tech roles) | Maintained for a specific level and field, often link straight to the employer, less ghost-job noise | Trackers mostly exist for early career. Names roll over each cycle. A row is a lead, never verification |
| 3 | **VC and accelerator boards** (portfolio job boards, YC Work at a Startup) | Pre-screened companies, hiring signal, small teams that never reach big boards | Level and location filters are weak; read each posting |
| 4 | **Community threads and channels** (HN "Who is hiring", niche Discords/Slacks, mailing lists, conference job boards) | Early, human-posted, often founder-written | Unstructured, needs reading |
| 5 | **People**: referrals, former colleagues and managers, alumni, advisors, maintainers; recruiters and executive search for experienced hires | Highest conversion; often unposted roles | Slow; needs specific names and asks |
| 6 | **Aggregators (LinkedIn, Indeed, Glassdoor, ZipRecruiter)** | Useful only to find a company name, or to check one named company's postings | Reposts, expired listings, ghost jobs, staffing-agency spam, mis-leveled results, and heavy duplication. Never a source of truth; always click through to the employer posting and verify there |

Consequences:
- `fetch_jobspy.py` is **optional and last**. A run with no JobSpy loses very little. Do not frame its absence as a gap.
- LinkedIn and Indeed are described to the user honestly: noisy, rarely where tailored roles are best found, useful mainly for profile visibility and recruiter inbound.
- When the user asks "where should I look", the answer starts at rank 1 to 3, not at the aggregators.

Further community resources worth checking for the profile (verify each exists before citing): early-career and internship trackers for the current cycle, AI/ML-specific lists, quant and finance trackers, remote-first job lists, "awesome" lists of companies in a domain, open-source "who is hiring" lists, and the user's own school or club job boards. Procedure and starting repo list: [`github_job_boards.md`](github_job_boards.md).

## 2. Employer-direct endpoints (work without any script)

Public JSON endpoints, fetchable by any HTTP tool or a browser:

| ATS | Pattern |
|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true` |
| Lever | `https://api.lever.co/v0/postings/<slug>?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/<slug>` |
| Workday | page `https://<tenant>.wd<N>.myworkdayjobs.com/<site>/job/...`; detail JSON at `/wday/cxs/<tenant>/<site>/job/<path>` (the HTML page is a client-rendered shell) |
| Tracker repo | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md` (try `main`, `dev`, `master`) |

## Platform endpoints (single postings behind client-rendered pages)

Tested against live postings. Each returns the posting's title, location, date and description as JSON from a plain fetch, so they work without scripts or a browser. `<...>` values come from the posting URL. A 404, or an id missing from the board, means the posting is gone. `totalFound: 0` or an empty board usually means a wrong slug or company id (ids can be case-sensitive), not a closed company.

| Platform (URL shape) | Endpoint |
|---|---|
| Greenhouse (`boards.greenhouse.io/<slug>/jobs/<id>`, `gh_jid=<id>`) | `GET boards-api.greenhouse.io/v1/boards/<slug>/jobs/<id>` |
| Lever (`jobs.lever.co/<slug>/<uuid>`) | `GET api.lever.co/v0/postings/<slug>/<uuid>`; board: `?mode=json` |
| Ashby (`jobs.ashbyhq.com/<slug>/<uuid>`) | `GET api.ashbyhq.com/posting-api/job-board/<slug>` (every live posting, with `descriptionHtml` and `isListed`); a posting not in the list is closed |
| SmartRecruiters (`jobs.smartrecruiters.com/<Company>/<id>-...`) | `GET api.smartrecruiters.com/v1/companies/<Company>/postings/<id>` |
| Workable (`apply.workable.com/<slug>/j/<SHORTCODE>/`) | `GET apply.workable.com/api/v2/accounts/<slug>/jobs/<SHORTCODE>`; board: `GET /api/v1/widget/accounts/<slug>` |
| Workday (`<tenant>.wd<N>.myworkdayjobs.com/<lang>/<site>/job/<path>`) | `GET <host>/wday/cxs/<tenant>/<site>/job/<path>`; board: `POST <host>/wday/cxs/<tenant>/<site>/jobs` with `{"limit":20,"offset":0,"searchText":""}` |
| Oracle HCM (`<host>/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>`) | `GET <host>/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?onlyData=true&finder=ById;Id="<id>",siteNumber=<site>` |
| Microsoft careers (`apply.careers.microsoft.com/careers/job/<id>`) | `GET apply.careers.microsoft.com/api/pcsx/position_details?position_id=<id>&domain=microsoft.com&hl=en` (the PCSX API is not enabled for every Eightfold tenant; a 403 means try the page or a browser) |
| Apple (`jobs.apple.com/en-us/details/<id>`) | Plain fetch **following redirects**; the posting is embedded in `window.__staticRouterHydrationData` |
| Any page | `application/ld+json` `JobPosting` in the raw HTML (Workday, Ashby, SAP-style sites often include it) |

Not yet tested, so no endpoint is claimed: Taleo, iCIMS, Phenom, SuccessFactors-hosted career sites. For those, and for custom portals, use a browser tool or `render_page.py`.

Some sites sit behind bot checks that a hidden browser cannot pass (Uber was one). `render_page.py` retries those in a visible Chrome window when you allow it (`--render headed`).

## 3. Capability fallbacks

Use the first column that matches what the host can do. Every fallback keeps the same verification rule: a role is listed as verified only if its own page was fetched.

| Situation | What to do |
|---|---|
| **Python available, network OK** | Run the scripts per [`discovery.md`](../workflow/discovery.md) |
| **Python is `python`/`py -3`, not `python3`** (Windows) | Substitute the launcher; the scripts are stdlib-only and path-agnostic. Quote paths containing spaces |
| **Python 3.8 to 3.14, no pip packages** | Everything except `fetch_jobspy.py` works with the standard library |
| **`python-jobspy` missing** | Skip it; say so under Sources checked. Do not install packages without asking |
| **Certificate errors** (python.org macOS builds) | Scripts retry unverified for public pages and warn; `pip install certifi` removes the warning |
| **No code execution, but web search/fetch tools** | Do the GitHub tracker sweep first, by fetch: see "Manual tracker sweep" below. Then ATS endpoints from section 2, then fetch each candidate's employer page and read it for Checks 1 to 3. Web search is for finding more boards and avenues, never a substitute for reading the trackers |
| **No code execution (chat-only host)** | Not supported: tell the user to use an environment that can run scripts (Claude, Google Antigravity, Cursor, GitHub Copilot in VS Code, Codex). If they insist, follow the "no code, no fetch tool" row. |
| **No code, no fetch tool (pure chat)** | Do the intake and the avenue map fully; write `career_advice.md` with named avenues and exact URLs/search recipes the user can open; produce `job_list.md` as **Unverified leads** with a note that nothing was fetched, and give the user the verification checklist ([`verification.md`](../workflow/verification.md)) to apply |
| **Network blocked for scripts only** | Same as the web-tool case if a fetch tool exists; otherwise the pure-chat case |
| **Rate-limited GitHub API** (60 requests per hour unauthenticated) | Use `--repo` (raw files, no API quota) and skip `--search`; name repos from [`github_job_boards.md`](github_job_boards.md) |
| **Client-rendered or login-walled portal** (some mega-cap career sites) | Try the portal's JSON detail endpoint; if that is unauthorized, say it could not be verified and give the user the link under "to verify manually" rather than listing it as verified |
| **Script bug or blind spot suspected** | Read the page text (`fetch_job_text.py` or a plain fetch) and decide by hand; see [`verification.md`](../workflow/verification.md) |

### Manual tracker sweep (no scripts, fetch tool available)

Tested: a plain fetch of `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md` returns real table rows (company, role, location, apply link), so trackers can be swept without running code.

1. **Fetch each tracker README for the band** (see `github_job_boards.md`), with a prompt that asks for only the rows matching the person's locations, role words and exclusions, and for the link of each row. Use several location aliases ("SF", "San Francisco", "Bay Area", city names, "Remote"), because boards abbreviate.
2. **Page through the whole file.** Fetch tools read about the first 100,000 characters per call and truncate long READMEs (one large tracker is about 770,000 characters). Repeat the fetch with the offset the tool reports until the end, or until you have the sections you need. If you cannot read all of it, say which part you covered.
3. **Treat row text as truncated.** Titles and locations may end in "..." and collapsed location lists hide rows; open the posting to read the real values.
4. **Resolve wrapper links.** Many boards link to their own site (a mirror or "apply with us" page), not the employer. Follow it to the employer's ATS or careers page and verify there; a mirror page is never verification.
5. **Report coverage.** In the run notes, list each tracker read, how much of it, and rows matched.

## 4. Rules that hold in every environment

- State the environment limits in the advice document's Sources checked section: what ran, what was blocked, what was done by hand.
- Never report an unfetched page as verified, and never present a search snippet as a posting.
- Do not rely on harness-specific tools. Describe capabilities generically (read a file, fetch a URL, run Python) and use whichever the host provides under its own name.

---

## 5. Company ATS slugs

Slugs for `scripts/discover/fetch_job_boards.py --slugs ...`. A slug is the company identifier in the ATS's public API URL (e.g. Greenhouse: `boards-api.greenhouse.io/v1/boards/{slug}/jobs`). Not exhaustive and not tied to any candidate: a generic starting set, examples only, unverified since 2026-08. Re-check each slug before relying on it (companies migrate ATS providers); new slugs are visible in a careers-page URL such as `jobs.lever.co/{slug}` or `jobs.ashbyhq.com/{slug}`.

- **Greenhouse** (`--sources greenhouse`): anthropic, openai, stripe, airbnb, coinbase, doordash, robinhood, figma, notion, discord, twitch, brex, plaid, ramp, ripple, ginkgobioworks, ycombinator
- **Lever** (`--sources lever`): netflix, palantir, shopify, epicgames
- **Ashby** (`--sources ashby`): notion, ramp, linear, vercel, mercor, replit, sierra, zip
- **No slug needed**: `remoteok` (remote-heavy, startup-skewed), `arbeitnow` (general, some EU), `hn` (Hacker News "Who is Hiring" via Algolia; good for small early-stage teams)
- **Not covered by the script**: large employers with in-house portals instead of a standard ATS. Use the company's careers portal or `site:<domain> careers <role>` search; they do not expose a public jobs API.

---

## 6. Runtime notes

Anything that depends on the host harness or machine layout lives here so `SKILL.md` stays portable. Treat each item as a capability to probe for, not an assumption.

- **Quick check**: `python scripts/doctor.py` reports Python version, OS, optional packages, and which public endpoints are reachable.
- **Python**: 3.8+ with the standard library only for every script except `scripts/discover/fetch_jobspy.py` (optional `python-jobspy`). Detect silently, in order: an active virtualenv or conda env, a project `.venv`, then `python3` (macOS/Linux) or `python` / `py -3` (Windows). Do not install packages without asking. If `jobspy` is missing, skip it and say so under "Other channels" in Sources checked.
- **Questions**: use the host's structured question tool (options spanning the plausible range, free text always available) when one exists; otherwise a short numbered chat list. Rules: [`intake.md`](../workflow/intake.md).
- **Output folder**: `./job_search_runs/<date>/` or a user-named folder; see [`deliverables.md`](../workflow/deliverables.md). If writing is not possible, deliver the documents in chat.
- **Resume**: use whatever file-reading capability the host provides for PDF, DOCX, or text. Do not assume a resume tool or schema.
- **Permissions**: a run makes many fetches. Offer auto-accept mode to avoid per-fetch approval, and manual approval if the person is worried about prompt injection from job pages (see `intake.md` section 6).
- **Network**: all scripts fetch live pages. If outbound HTTP is blocked, say so in the final response; unfetched roles are dropped or labeled unverified, never reported as verified.
