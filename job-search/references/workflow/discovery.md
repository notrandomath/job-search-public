# Discovery: Finding Roles Across Every Relevant Avenue

One procedure for every request. Whether the user named companies, wants a market sweep, or both is decided by the intake, not by a separate "flow".

## 1. Build the search plan from the avenue map

From [`avenue_map.md`](../knowledge/avenue_map.md) take every avenue marked relevant. For each one, write down the concrete source you will query (a company, a portfolio board, a repo, a venue). The plan is what keeps the search from collapsing onto whichever source is easiest to scrape.

## 2. Resolve named companies

For each company the user named (and each one the plan adds):
- Map to its ATS slug in [`sources_and_fallbacks.md`](../sources/sources_and_fallbacks.md), or find it (`boards.greenhouse.io/{slug}`, `jobs.lever.co/{slug}`, `jobs.ashbyhq.com/{slug}`, `*.myworkdayjobs.com`).
- For a student or recent graduate, find the university / early-careers page. Companies that hire students mainly through university recruiting must be swept there first ([`hiring-channels.md`](../knowledge/hiring-channels.md)).
- Report all current matches. If a company has none, say so and **find its expected opening window**: check its careers or university page, last cycle's posting dates (earlier postings, tracker history), and recruiting guides, and record the source and whether it is announced, inferred from last cycle, or unknown. Do this for every company the user named, and always when they asked when it opens. Do not pad with roles from other companies.
- Never cap a named company's roles at an arbitrary number.

## 3. Sweep sources

**Match the source category to the person's band, not to the most popular boards.** Someone past the new-grad window (or with a few years of experience) is not served by new-grad trackers: use the junior, entry-level and early-career categories in [`github_job_boards.md`](../sources/github_job_boards.md), small and mid-size employer boards, and aggregators, and match "Junior", "Associate", "Engineer I/II" titles. Use the interview and application evidence from intake, weighted by route (cold applications and recruiter outreach set the shape; referral interviews inform level only; roles the person was not targeting never override the stated goal): if cold or recruiter-sourced interviews came from small-employer "Junior" postings, search that shape, in the locations those came from, and treat aggregators such as Indeed as worth using for this person (fetch what you can, and find the same roles through employer career pages when the aggregator cannot be fetched). Offer to widen the location when evidence shows roles outside the stated area. To find the boards for the band, run web searches restricted to GitHub (`site:github.com "<level> <role> jobs" updated daily`, one per band and field) and then fetch what they surface; see `github_job_boards.md`.

**The community GitHub tracker sweep is mandatory whenever a tracker fits the person's level and field (it does for any student or early-career search), and it is never replaced by web search.** If the scripts cannot run (sandbox blocks, no Python), fetch the raw tracker file directly with a plain web fetch (`https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md`, see `sources_and_fallbacks.md`) and read the rows yourself. A blocked script is a reason to switch method, not to skip the source. With a fetch tool but no code execution, follow "Manual tracker sweep" in `sources_and_fallbacks.md` (fetch the raw README with a row-filtering prompt, page through it with offsets, resolve wrapper links to the employer); web search alone is not the sweep. Before writing the list, confirm the tracker repos named in `github_job_boards.md` for this level were actually read, and state in the run notes which ones were.

Source priority follows [`sources_and_fallbacks.md`](../sources/sources_and_fallbacks.md): employer-direct and curated GitHub trackers first, VC and community boards next, aggregators (LinkedIn, Indeed) last and optional. Run `python scripts/doctor.py` first; if a step cannot run, use the fallback in that file instead of skipping the avenue. Use `python` or `py -3` where `python3` does not exist. Save raw output to a scratch location (not the output folder):

```bash
# Employer ATS APIs (Greenhouse, Lever, Ashby, plus HN and aggregators)
python3 scripts/discover/fetch_job_boards.py --slugs <slugs> --sources greenhouse lever ashby --keywords "<keywords>" --output ats.json
python3 scripts/discover/fetch_job_boards.py --sources hn remoteok arbeitnow --keywords "<keywords>" --output aggregators.json

# Community GitHub trackers (when a tracker fits the level and field; see github_job_boards.md)
python3 scripts/discover/fetch_github_boards.py --repo <owner/repo> --locations "<location>" --exclude <excluded> --output gh.json
python3 scripts/discover/fetch_github_boards.py --search "<level> <role focus>" --locations "<location>" --exclude <excluded> --output gh_dynamic.json

# Aggregator search (optional, lowest signal; needs python-jobspy; skip and say so if absent)
python3 scripts/discover/fetch_jobspy.py --search-term "<role>" --location "<City, Region>" --country "<Country>" --sites linkedin indeed google --hours-old 168 [--results-wanted N] [--is-remote]
```

Beyond the scripts, use web search and direct page fetches for avenues no script covers: VC portfolio boards, accelerator listings, university career pages, research residencies, conference sponsor lists. These are leads until a live posting is fetched.

## 3b. Deep mode

When the user chose deep search at intake, also run the avenues in [`deep_search.md`](deep_search.md) and report which ran, were empty, or were blocked.

## 4. Merge and triage

- Deduplicate by canonical URL, then by company plus normalized title.
- Drop hard exclusions and active-pipeline companies (with parents/subsidiaries): `verify_jobs.py --exclude-companies`.
- If the user keeps earlier runs and opted into reuse, drop already-listed roles: `verify_jobs.py --prior-dir <runs folder>` (or `scripts/lib/prior_jobs.py`).
- Rank by the goal from intake, not by company prestige alone.

## 5. Verify

Every role that will appear as "apply now" goes through [`verification.md`](verification.md). Watchlist entries need a live program page, not a live requisition.

## 6. Know when the list is short

If a request cannot be filled with verified roles, say how many exist and why (window not open, level mismatch, sources blocked). Never fill space with unverified or mis-leveled roles.
