# Stage 3: Verification Stage (Checklist Gate)

This runbook defines the mandatory verification protocol for Stage 3 of the `job-search` skill.

> [!IMPORTANT]
> **The Golden Binary Rule**:
> Every candidate role discovered in Stage 2 must be audited against the appropriate verification gate before inclusion in any final deliverable:
>
> 1. **Live Actionable Roles (the apply-now table in `job_list.md`)**:
>    Must satisfy the **Live Verification Gate**:
>    $$\text{Verified} = \text{Check 1 (Exists & Non-Empty Live Page)} \land \text{Check 2 (Calibrated Level Match)} \land \text{Check 3 (Not Timing-Ineligible)}$$
>    **If a candidate role fails any check, it is ❌ NOT VERIFIED (NOT PROPER) and must be discarded immediately.** Only postings verified as **✅ VERIFIED (PROPER)** are permitted in the apply-now table.
>
> 2. **Watch-list entries (`job_list.md` watch list and the timing guidance in `career_advice.md` when it was requested)**:
>    Watchlist/monitoring items (cohorts not yet opened, annual cycles, university pipelines) must satisfy the **Watchlist Institutional Gate**:
>    $$\text{Watchlist Verified} = \text{Check W1 (Verified Institutional Program URL)} \land \text{Check W2 (Cohort Level Alignment)}$$
>    The program page or university careers URL must be live (HTTP 200), and the program track must align with the candidate's calibrated band.

---

## Verify at the employer, never at an aggregator

A page on a tracker, aggregator, wrapper or mirror site is **not** verification, even when it loads and shows a full description, because copies outlive the posting. Always confirm the role on the employer's own side:

1. Find the employer link on the page (an ATS posting URL, or a careers link carrying a Greenhouse `gh_jid`).
2. Check that requisition at its source: the ATS posting page, or for Greenhouse the public board API (`boards-api.greenhouse.io/v1/boards/<slug>/jobs/<id>`), which is authoritative even when the employer's careers page is client-rendered.
3. If the employer's board does not list it, the role is **not verified** ("aggregator copy is stale"). If no employer link can be found, the role is not verified either; find it on the employer's careers page or drop it.

`verify_jobs.py` does this automatically: URLs on third-party hosts are followed to the employer and rejected when the employer side cannot be confirmed, and Greenhouse requisitions are always checked through the board API. Pass `--employer-hosts <host ...>` for an employer's own careers domain that the script cannot recognize from the company name. The result records `aggregator_url` and `employer_check` for your internal audit notes.

---

## Client-rendered and blocked pages

Many employer sites render the posting with JavaScript or refuse automated fetches, so a plain fetch returns an empty shell, a bot-verification page or a 403. **That is not a closed posting and it must never be reported as one.** Work down this ladder, stopping at the first rung that returns the real posting text. Rungs 1 to 3 need nothing but a fetch tool, so they work in browser-only hosts such as claude.ai web.

1. **Read the data behind the page.** `verify_jobs.py` does this automatically, and you can do the same by hand with a plain fetch.
   - Embedded data in the raw HTML: `application/ld+json` `JobPosting`, `__NEXT_DATA__`, `window.__appData`, Apple-style `__staticRouterHydrationData`.
   - The ATS's public JSON for that single posting: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Workday, Oracle HCM, Microsoft careers. The exact endpoints are in [`sources_and_fallbacks.md`](../sources/sources_and_fallbacks.md) ("Platform endpoints"). A 404 from the employer's own JSON, or an id missing from the employer's board, is real evidence the posting is gone.
2. **Use the host's browser tool** if it has one (any tool that opens a page and returns rendered text). Open the posting itself, not just the list, and read the rendered text.
3. **Render it locally (optional).** `scripts/verify/render_page.py` uses Playwright if installed and any Chromium or Chrome it finds. It waits for the text to settle (never for network-idle), tries headless first, and may open a visible Chrome window for bot walls. `verify_jobs.py --render headless|headed|off` calls it for the pages that still failed. If Playwright is absent it says so and the run continues. **Never install anything without asking** (see "Offering the optional install" below).
4. **Search-index confirmation (lower confidence).** A web search for the exact title, employer and requisition id that returns the employer's own posting page confirms the role was recently indexed. It can lag a closure, so it is **never "verified"**; it only supports the label "likely open, not fetched" below.
5. **Never ask the user to copy or paste pages.** Roles that no rung could read go into one capped section instead (see below).

### Offering the optional install

Offer it **only when all of these hold**: the run hit pages it could not read (the verifier printed "Render skipped" or returned `could_not_machine_check` rows), the host can run commands and reach the network (`python3 scripts/setup_optional.py --check` prints `"can_install": true`), it is not a lite run, and you have not already asked in this run. In a browser-only or chat-only host (claude.ai web, a plain Gemini chat, anywhere you cannot execute code) do not offer it and do not mention installing; just use the ladder's other rungs.

Ask once through the question tool, multi-select, one option per item that `--check` lists as missing, plus "Not now". In the question, say for every item what it is, why it is needed, how big it is and where it goes, using the `what`, `why`, `size` and `where` fields from `--check`:
- **Playwright** (a Python library that drives a browser): opens JavaScript-rendered and bot-checked job pages and reads the posting text, which a plain fetch cannot. It installs into a private virtual environment at `~/.job-search-skill`, so the system Python is untouched.
- **Chromium** (an open-source browser build Playwright launches): only offered when Google Chrome is not already installed, because Chrome is used when present. It is a download of roughly 100 to 300 MB in Playwright's browser cache.

Also say that nothing else is installed or changed, that it can be removed with `python3 scripts/setup_optional.py --uninstall`, and that declining only means those pages are listed as "could not machine-check". Install exactly the chosen items with `python3 scripts/setup_optional.py --install <ids>`, then re-run `verify_jobs.py` on the rows that were unreadable. If the person declines or the install fails, continue without it and say so once in the notes.

**Confidence tiers** (shown in the output as the script's `verification_tier`):

| Tier | Meaning | Where it goes |
|---|---|---|
| `verified` | Posting text read from the page, the ATS JSON or a browser, and all checks run | Apply now |
| `could_not_machine_check` | Blocked, bot-walled, unreachable or client-rendered and nothing above could read it | "Could not machine-check" section, capped (below) |
| `rejected` | Read successfully and failed a check (closed, wrong level, hard requirement) | Dropped |
| `unconfirmed` | Only a tracker or aggregator row; the employer side was not confirmed | "Unchecked leads", labeled as such |

The level and eligibility checks run on whatever real text exists (title, snippet, structured data). A role whose text never became readable cannot pass the level check, so it never enters "Apply now". A `could_not_machine_check` row is capped at the **top 10 to 15 by fit**, with the link, one line of reason, and (when rung 4 found it) "likely open per search". It never claims the role is verified or closed, and contract roles in this section are not recommended as career-forward on a title alone (the trajectory test cannot run without the text).

---

## Anti-Cheating & Integrity Invariant

> [!CAUTION]
> **Internet Search Snippets are NOT Verification**:
> Search engine snippets, aggregator summaries, and cache excerpts do **NOT** constitute verification. Search engines frequently index stale postings, dead URLs, expired requisitions, and speculative mirrors.
> **Verification MUST be performed via an actual, direct HTTP fetch of the target URL.**
>
> **Strict Anti-Fabrication Invariants**:
> - Never claim a link is verified, live, or has an active application button unless the tool/script actually fetched that exact URL and verified its contents.
> - If an exact URL cannot be read, it is **not verified**: either dropped (the employer's own data says it is gone or it failed a check), or, when the site only blocked or could not render the fetch, listed under "Could not machine-check" (see "Client-rendered and blocked pages"). Never describe it as verified, and never as closed without evidence.
> - Fabricating a verification claim or asserting link liveness based on search snippets without a live fetch is strictly prohibited.
> - **Internal Level Codes**: Never invent or guess an internal level code (e.g. "L3", "IC4"). Only cite an internal company band code if there is explicit evidence in the job posting text, URL slug, or HTML metadata. If unstated, classify solely by candidate band (e.g. `Calibrated <band> / <X–Y> YOE (internal band unstated in JD)`).

---

## The Three Verification Checks (Live Postings)

### Check 1: Existence & Non-Empty Page Verification
The agent must verify that the job opening genuinely exists, is currently live, and leads to substantive, non-empty job description content:

1. **Direct HTTP Status & Reachability**:
   - The URL must return a successful HTTP status code (`200 OK`).
   - `404 Not Found` or `410 Gone` from the employer's own page or job data means the posting is gone, and the opening fails Check 1.
   - `401`, `403`, `406`, `429`, `451`, `503`, a bot-verification page, or a timeout means **the site refused or did not answer an automated fetch**. That is not evidence the role is closed. Do not fail it as dead; take it through the ladder in "Client-rendered and blocked pages" below.
2. **Deep Inspection of the Raw HTML Payload (Don't Give Up Too Easily)**:
   - The body text must contain full, untruncated job description content (minimum length threshold: $\ge 300$ characters of clean, stripped text).
   - **Examine Embedded HTML Payloads for SPAs**: Modern enterprise portals (Workday, Ashby, Greenhouse and many in-house career sites) often embed the real job description in structured metadata rather than top-level paragraph tags:
     - **JSON-LD Schema**: `<script type="application/ld+json">` (contains `title`, `description`, `datePosted`, `validThrough`, `experienceRequirements`).
     - **Framework State**: `<script id="__NEXT_DATA__">`, `window.__INITIAL_STATE__`, or `__appData`.
     - **Meta Tags**: `<meta property="og:description">` or `<meta name="description">`.
     - If plain HTML text appears sparse, inspect the raw HTML payload for embedded JSON strings before concluding a page is empty.
3. **Dead / Expired Page & Redirect Detection**:
   - The page must **NOT** lead to:
     - An empty HTML shell, WAF challenge block ("Just a moment...", "cf-browser-verification"), or broken template.
     - A *"This job is no longer available"*, *"Position closed"*, *"Application window expired"*, or *"Search Current Openings"* notice.
     - A dead redirect where the ATS redirects from a specific requisition slug to a generic careers homepage (`/careers`, `/home`, or `/jobs` root) without the role details.
4. **Active Application Channel**:
   - The page must have an active application form, direct ATS submission embed, or clearly designated application button (e.g., `Apply Now`, `Submit Application`).
   - Closure wording counts only when it is visible, meaningful text on the page. A phrase in a screen-reader-only region, a script, a footer or a help text is not a closure (live Uber postings carry "Job removed" in a hidden announcement span next to "Apply now").

---

### Check 2: Calibrated Level Match Verification
Verify that the posting matches the candidate's calibrated band, grounded in [`leveling-rubric.md`](../knowledge/leveling-rubric.md). The band comes from intake and is passed to the script; nothing here assumes entry level.

1. **Stated years of experience.**
   - Scan the full job text (and embedded JSON-LD) for the stated minimum.
   - Fail (`ERR_MISLEVELED_YOE`) when the stated minimum exceeds the band's ceiling (`--max-yoe`). Example: for a candidate at 0 to 2 years the ceiling is 2; for a candidate with 8 years it might be 10.
   - **Hard versus soft is about who enforces it, not whether it has a number.** *Hard* means a legal rule or an automatic filter that no recruiter can wave through: work authorization or "no sponsorship", citizenship, a security clearance, a licence, and knockout questions such as a required graduation window, student status, or a required degree they lack. *Soft* means a human reads the application and decides, so a strong record, a referral or a short note can get through even when the posting states a concrete number: years of experience, preferred skills, "nice to have" tools. A failed hard requirement means the role is not offered (the script reports them under `hard_requirements`; `--needs-sponsorship` fails sponsorship, citizenship and clearance blockers; judge graduation window and degree from the person's profile). Evidence on enforcement: degree, work-authorization and clearance questions are the knockouts recruiters describe as truly automated, so a required degree with no alternative is treated as hard; but if the posting says "or equivalent experience" (or similar) the degree line is soft and the script does not flag it. Graduation-window and "new grad" eligibility is set by each employer's program rules (some state a fixed number of months after graduation) and exceptions are anecdotal and unconfirmed, so treat it as likely hard, give low odds if you list it at all, and tell the person to confirm eligibility with the recruiter. A missed soft requirement is a stretch: the script reports `yoe_gap` and `stretch_odds` (`reasonable` for a gap of one year, or two with an "equivalent experience" style qualifier; `long_shot` for a bigger gap), and you say so honestly. A huge gap (a senior-scope posting for a new graduate) is still not a realistic target, so do not offer it unless the person asks.
   - **Years are soft, school counts.** When the sentence carries a qualifier ("or equivalent experience", "including internships", research, an advanced degree; reported as `yoe_soft_qualifier`), or the person's internships, co-ops, research or substantial projects plausibly cover the gap, a posting one to three years above the band is a **stretch candidate** (`stretch_candidate`), not a hard fail: offer it in the stretch table with the one thing that covers the gap. Set `--max-yoe` from effective experience as described in the leveling rubric. A required graduation year, degree, work authorization or clearance is a hard rule, not a soft one.
   - Flag (do not fail) a posting whose stated minimum is far below the band's floor (`--min-yoe`, reported as `below_band`); treat it as an under-level role and say so.
2. **Title and scope.**
   - Seniority words in a title (Senior, Staff, Principal, Lead, Head of, Director, VP, Manager) disqualify only when they sit **above** the candidate's band. For a candidate whose band includes them, pass `--allow-titles` for those words and judge fit by scope.
   - Flag titles clearly below the band as under-level.
3. **Grounded internal bands.**
   - Cite a company's internal band code only when the posting text, URL slug, or metadata states it. Otherwise never invent one; write `Level: Calibrated <band> (<X to Y> years; internal band unstated in posting)`.

---

### Check 3: Hiring Channel & Timing Verification
Apply [`hiring-channels.md`](../knowledge/hiring-channels.md) to every posting that passed Checks 1–2:

1. **Classify the channel** from the posting text (university/cohort, industry/open, internship, fellowship, returnship, contract, executive search, rotational).
2. **Compare with the candidate's availability and situation** (earliest start, notice period, graduation or defense date, authorization lead time):
   - Posting states a window, cohort year, start-by date, enrollment, or eligibility rule the candidate cannot meet → fail (`ERR_TIMING_INELIGIBLE`).
   - Posting wants someone who can start sooner than the candidate can (the usual case for a student well before graduation) → **timing risk**: never a direct match; list it only in a separate timing-risk tier with the reason, or drop it.
   - Window or channel fits the situation → eligible.
3. **Sponsorship**: if the candidate needs it, scan the posting for sponsorship or right-to-work language and record the finding.
4. **Employers that hire entry-level through campus pipelines** (see `hiring-channels.md`): for a student or recent graduate, look for the cohort req first; if none is open, say so and move the company to the watch list instead of substituting its industry reqs.
5. **Exclusions**: drop any posting from a company (or its parent/subsidiaries) the user excluded or has an active pipeline with (`ERR_EXCLUDED_COMPANY`). Exclusions come only from this user's intake.

---

## Actionable Diagnostics & Failure Matrix

When a candidate job is evaluated, classify any failure under the following deterministic diagnostics:

| Failure Code | Root Cause | Actionable Remedy |
| :--- | :--- | :--- |
| `ERR_UNVERIFIED_FETCH` | URL could not be fetched (DNS failure, no answer) and nothing in the ladder could read it | Not verified $\rightarrow$ **Drop**, or list under "Could not machine-check" if it is a top-fit role from a site that blocks automated fetches. |
| `ERR_BLOCKED_OR_CLIENT_RENDERED` | 401/403/406/429/451/503, bot-verification page, or JS shell | Run the ladder in "Client-rendered and blocked pages"; never report as closed. |
| `ERR_DEAD_URL` | URL returns 404, 410, DNS failure, or redirects away from requisition to careers root | Check for updated ATS slug or direct career portal URL. If no live URL exists $\rightarrow$ **Drop immediately**. |
| `ERR_EMPTY_PAGE` | Page returns 200 but text $< 300$ chars or displays "job closed" / "role does not exist" | Posting has expired or is a ghost listing $\rightarrow$ **Drop immediately**. |
| `ERR_MISLEVELED_YOE` | JD's stated minimum years exceeds the band's ceiling (`--max-yoe`) | Posting exceeds candidate's calibrated level $\rightarrow$ **Drop immediately**. |
| `ERR_MISLEVELED_TITLE` | Title includes Senior/Staff/Lead/Principal | Out-of-band seniority $\rightarrow$ **Drop immediately**. |
| `ERR_TIMING_INELIGIBLE` | Posting's graduation window, start date, or enrollment requirement does not fit the candidate's availability | **Drop immediately**; watchlist the company's next cohort if relevant. |
| `ERR_EXCLUDED_COMPANY` | Company is blacklisted or the candidate has an active pipeline there (includes parent/subsidiaries) | **Drop immediately**; do not watchlist or suggest referrals. |
| `ERR_PREVIOUS_DUPLICATE`| Job already listed in an earlier run's `job_list.md` (only when the user opted into reuse) | **Exclude from new recommendations**. |

---

## Social and unlisted leads

Hiring posts from social sources are not postings and are not verified by a page fetch. A lead records the poster, the date, the stated role, and how to reach them, and is verified only if a matching posting exists on the employer's ATS (then verify that posting as usual). Otherwise it is listed as an unlisted lead to confirm with the poster. See [`deep_search.md`](deep_search.md).

---

## Recording the Audit (no separate file)

Verification evidence is kept in an internal scratch notes file for the agent's own use, not shown in `job_list.md` and not delivered. For each listed role record: fetch date, HTTP status, that an apply control was present, the stated YOE or cohort language, and the channel and timing verdict. Roles that fail are dropped and mentioned only if they are a named company the user asked about (reason in "Not listed and why").

---

## Automated Verification Script (`scripts/verify/verify_jobs.py`)

Run `scripts/verify/verify_jobs.py` to evaluate Checks 1 and 2 programmatically:

```bash
python3 scripts/verify/verify_jobs.py raw_jobs.json --output verified_roles.json --max-yoe <band ceiling> [--min-yoe <floor>] [--allow-titles senior staff ...] [--include-title-regex <role family regex>] [--exclude-title-regex <regex>] [--exclude-companies <name> ...] [--shell-hosts <host> ...] [--prior-dir ./job_search_runs] [--render headless|headed|off]
```

`verify_jobs.py` performs a live HTTP fetch (or reads the ATS's JSON for supported platforms), deep-inspects raw HTML (including JSON-LD, Next.js state, and OpenGraph metadata), verifies non-emptiness and absence of closed/redirect signals, validates YOE and titles against the candidate level, and marks `is_proper: bool`. Only roles with `is_proper == True` advance to deliverables.

**Scope of the script**: it automates Check 1, Check 2, the earlier-run filter (`--prior-dir`) and company exclusions (`--exclude-companies`). **Check 3 (hiring channel & timing) is judged by the agent** from the full text fetched with `scripts/verify/fetch_job_text.py`; apply it to every role the script marks proper before it enters a deliverable.
