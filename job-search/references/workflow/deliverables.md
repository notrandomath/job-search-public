# Deliverables: Job List, Plus Optional Advice

A run produces **a job list, and a career-advice report only if the user wants one** (ask at intake; see `intake.md`). Nothing else: no JSON, no index, no dossier, no scratch files in the output folder. Raw fetches and intermediate lists stay in a temporary location and are not delivered.

| File | Purpose |
|---|---|
| `job_list.md` (always) | The roles the user asked for, verified, in whatever shape they asked |
| `career_advice.md` (opt-in) | The counselor's advice: what to do, where to look, when programs open, and why, for this person and this goal |

## Output folder and optional reuse

- Default location: `./job_search_runs/<YYYY-MM-DD>/` (add `_2`, `_3` for same-day reruns), or a folder the user names.
- If the environment cannot write files, give the documents in chat in the same structure.
- Writing the files is the default. **Reusing them is opt-in.** Only when the user asks, and the environment allows reading the folder, a later run may:
  - skip roles already in earlier `job_list.md` files (`scripts/lib/prior_jobs.py` / `verify_jobs.py --prior-dir`);
  - start from the profile block of the latest `career_advice.md` instead of re-running the full intake.
- Never create an extra cache file to support this. The documents are the cache.

---

## `career_advice.md`

Write for one person. Every sentence either uses their facts or gives a specific next step. No generic motivational material, no advice that would be identical for another candidate.

### Required sections, in this order

Short beats thorough: the reader should finish it in a few minutes. Tables over prose, no recap of the resume, no candidate name or profile block, no run date or assumptions at the top.

**Exactly four sections, no others.** No "strategic evaluation", "why this program is great", comparison essays, or extra summaries: the avenues and plan already carry the reasoning. The bold labels below describe what each section does; they are not headings to copy. Use plain reader-facing headings: "Where the companies you named stand", "Avenues, best first", "Plan", "Notes".

1. **Where the named companies stand.**
   - Start with the thing the person actually asked. A table of the companies they named or care about: what is open now, and when the rest open (with expected window, and say plainly when that timing is inference or unconfirmed). When a named company has nothing open, look up its recruiting cycle (its careers or university page, last cycle's posting dates, reputable recruiting guides) and give the expected window with the source; if you cannot find one, say so. This is required whenever the user named the company or asked when it opens.
   - Answer any direct questions they asked (for example whether a role stated as "N+ years" accepts someone at their stage) explicitly, with what you could and could not confirm.
2. **Avenues, in priority order.**
   - One numbered list, highest value first, each with concrete names, links, and next steps for this person.
   - **Combine two sets in the same ranked list:** about 5 general avenues from the avenue map (open programs, referrals, residencies, startups and VC boards, trackers and alerts) and the 5 most promising resume-derived avenues from the avenue generator (see `avenue_map.md`). Rank them together by expected value for this person, not in two blocks. Each resume-derived avenue names the resume item that makes it credible.
   - **An avenue is a channel or a way of getting in front of hiring people, not a list of employers to apply to.** Valid: a VC portfolio job board, a recruiter or sourcer outreach, a conference or workshop community, authors of the papers their work builds on, an upstream contribution, a fellowship or residency, a referral route, alerts on a tracker. Invalid: "apply to NVIDIA, Stripe and Roblox", "target Big Tech new-grad pipelines", "filter LinkedIn for systems roles". Open reqs belong in `job_list.md`, not here. Test every avenue: does it say who to contact, where to go, or what to make, beyond "apply"? If not, delete it.
   - An avenue must be realistic at the person's level: do not point entry-level people at channels or roles that need experience they lack.
   - Include people and referrals as an avenue (who to ask, search recipes built from their real history), not as a separate section. Cover every avenue the avenue map marks relevant; one line per avenue left out is not needed.
3. **Plan.**
   - A dated table (this week, next two weeks, later) that sequences the avenues above, plus the one or two fixes (resume, dates) that block applications.
4. **Notes (last, small).**
   - Date written, assumptions, what could not be checked, and sources as links. Keep it to a short paragraph.

## `job_list.md`

Exactly what the user asked for, shaped by the intake's scope answer. No quota, no fixed bucket sizes.

### Structure

1. **Header**: one line with availability used for timing verdicts and scope requested. Put the run date and sources in a short "Run notes" block at the bottom.
2. **Apply now**: verified live roles, one table, ordered by fit to the goal. For a student or recent graduate, cohort reqs whose window fits come first and timing-risk industry reqs go last under their own heading; for everyone else, order by fit and timing.
2a. **Stretch roles** (include when any exist; keep it short): live, verified-at-the-employer roles that miss one soft criterion, such as a stated minimum one or two years above the person's band (`stretch_candidate` in `verify_jobs.py` output), or a cohort-labeled role whose eligibility is not a hard graduation window. One table with `Company` | `Role` | `Source` | `Location` | `Start date` | `Odds and what helps` (one line, honest: say `reasonable` or `long shot`, and what improves it, such as a referral or a recruiter note; a stated number is the recruiter's discretion, not a wall). Never mix them into "Apply now", and never list a role with a hard eligibility rule the person fails (a required graduation year, citizenship, a degree they lack).
2b. **Stepping-stone roles** (only if the person said yes to adjacent roles at intake): contract, QA or test, support and similar roles, in their own table after "Apply now". Run each through [`trajectory_test.md`](../knowledge/trajectory_test.md) first and add its one-line result (what the resume gains, any conversion route, the main risk). Roles that fail the test are dropped and named in "Not listed and why". Lite runs do not offer stepping-stone roles at all. Never mix them into the main table or use them to pad a short list.
3. **Watch list** (only if the user asked for future or unopened roles): programs not yet open, with expected window and where to check. Each needs a live program page.
4. **Leads from hiring posts** (deep mode only, when any were found): `Company` | `Poster / role` | `Source` (link to the post) | `Posted` | `How to reach`. Mark them "unlisted lead, confirm with the poster". They are never presented as verified postings.
5. **Not listed and why** (short): named companies with no matching verified role, and the reason.

### Apply-now columns

`Company` | `Role` (markdown link to the application URL) | `Source` (where the role was found, as a link) | `Location` | `Start date` (as the posting states it; write "Not stated" when it does not, and add any stated graduation window or eligibility constraint in brackets)

Nothing else per row. Do **not** show level evidence, "why it fits", or verification status in the list; the user wants a clean list. Keep that audit trail (channel and timing verdict, stated years, fetch date, wrapper-page flags) in an internal notes file in the scratch location for your own use and for answering follow-up questions. It is not a delivered artifact.

### Rules

- Every row carries a Source link next to the role, so the reader can see where it came from and re-check it. The Role link is the application page; the Source link is the board, tracker, or API that surfaced it.
- **Make the source obvious by using its address as the link text**, not a generic label: `github.com/SimplifyJobs/New-Grad-Positions`, `jobs.ashbyhq.com/openai`, `job-boards.greenhouse.io/anthropic`, `nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite`, `apply.careers.microsoft.com`. Separate multiple sources with ` · `. Never write only "tracker" or "board".
- **Source states how the role was actually found, not where it is hosted.** If it came from a tracker repo, the source is that repo's address. If you found it with a web search, write `web search` (and the query in the internal notes), and do not claim the company's ATS board as the source unless you actually enumerated that board. If it came from an ATS API call, the ATS address is correct. Never invent a provenance to look more rigorous.
- **When live fetching is impossible** (no network, no fetch tool), retitle the section "Unverified leads", mark every row `not fetched`, and say what the user must check. Never label such rows verified.
- Company diversity matters: do not cluster the list on one employer unless the user asked for that company.
- Every row must come from a fetched page. Search snippets and tracker rows are leads only.
- State shortfalls plainly ("only 6 verified roles exist for this scope") rather than padding.
- Drop excluded companies everywhere, including the advice document.
