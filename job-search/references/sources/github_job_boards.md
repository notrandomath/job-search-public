# GitHub Job-Board Sweep (When a Tracker Fits the Profile)

Community trackers exist mainly for early-career, internship, and some niche (AI/ML, quant, remote) roles. Sweep them via `scripts/discover/fetch_github_boards.py` whenever the person's level and field are covered by one. For mid-career, senior, or non-engineering scope there is usually no tracker; say so in Sources checked and spend the effort on the avenues that fit (see [`sources_and_fallbacks.md`](sources_and_fallbacks.md)).

## Pick board categories by band; do not overfit on new-grad lists

New-grad trackers only fit people inside a graduation window. A person one to a few years out, or anyone below the senior band, is poorly served by them, and their best roles often carry titles like "Junior", "Entry-level", "Associate", "Software Engineer I/II" at small and mid-size employers, with no graduation window at all. Sweep the category (or categories) that match the calibrated band, and when the band is ambiguous sweep two adjacent ones:

| Band | Board categories to sweep | Title words to match |
|---|---|---|
| Student / new graduate in window | new-grad and internship trackers | new grad, university grad, early career, 2027 |
| 0 to 3 years out, no window | early-career, junior, entry-level, "software engineer jobs", "AI jobs", "ML jobs", remote and visa boards | junior, entry level, associate, engineer I / II, L2, L3 |
| Mid (about 3 to 6 years) | general engineering and AI/ML job boards, remote boards, company-specific boards | engineer II / III, L3 to L4, software engineer without level |
| Senior and up | few trackers exist; use AI/ML and remote boards, VC portfolio boards, recruiter channels | senior, staff, L4 to L6, lead |

**What exists (tested October 2026, all parsed to rows).** Keyword search ranks by popularity and misses small boards (it missed a senior board once), so list board-publisher owners instead: `fetch_github_boards.py --owner <owner ...>` fetches every job-board-looking repo of each owner and reports each one.

| Band | Boards |
|---|---|
| New grad / student in window | `SimplifyJobs/New-Grad-Positions`, `vanshb03/New-Grad-2027`, `speedyapply/2027-SWE-College-Jobs`, `speedyapply/2027-AI-College-Jobs`, `jobright-ai/2026-*-New-Grad` (about 17 fields), `zapplyjobs/New-Grad-*` (SWE, IT, data science, hardware, healthcare), `dreamworkhq/New-Grad-Software-Engineer-Jobs`, `ApplyGuy/2027-New-Grad-Jobs`, `workopia/US-New-Grad-Internship-Jobs`, `resumax/new-grad-tech-jobs` |
| Junior / early career, mixed level | `ambicuity/New-Grad-Jobs` (all fields, many "Junior" and "Engineer I" titles; README keeps the 10 newest per category, full set on its live site), `dreamworkhq/Python-Developer-Jobs`, `dreamworkhq/Frontend-React-Jobs`, `dreamworkhq/Data-Science-Jobs`, `dreamworkhq/Data-Engineering-Jobs`, `dreamworkhq/DevOps-SRE-Cloud-Jobs`, `dreamworkhq/Cybersecurity-Jobs`, `dreamworkhq/AI-ML-Jobs`, `dreamworkhq/Remote-Tech-Jobs`, `maurobonfietti/remote-jobs` |
| Mid and senior | `dreamworkhq/Senior-Software-Engineer-Jobs` (600 rows, staff and senior), `rovero/experienced-jobs-feed` (about 9,900 rows from Greenhouse, Lever and Ashby APIs, senior, staff and principal), `jobs-jobr-pro/*` (20 repos, about 50 rows each: per field and per city), plus the dreamworkhq field boards above, which mix levels |

Board-publisher owners to list with `--owner`: `dreamworkhq`, `zapplyjobs`, `workopia`, `jobright-ai`, `speedyapply`, `SimplifyJobs`, `vanshb03`, `ApplyGuy`, `resumax`, `ambicuity`. Many boards are mixed-level, so filter by title words and stated years. `remoteintech/remote-jobs` and `lukasz-madon/awesome-remote-job` are company directories, not postings, and `capy-zhiao/Job_Monitor` is a notifier tool backed by its own site.

**Find boards with web search first, then the script.** Web search finds small boards that the GitHub repository API (ranked by stars) buries. Two rules from testing:

1. **Restrict the search to github.com** with the search tool's domain filter (`allowed_domains: ["github.com"]`) or `site:github.com`. Without it, a query containing "GitHub" returns job postings *at* GitHub the employer.
2. **Describe the repo, not the website.** Repos phrase themselves like "senior software engineer jobs in the US, updated daily. Staff, principal, lead..." Query in that language, one per band and field, for example: `senior software engineer jobs repository updated daily staff principal`, `junior OR entry level software engineer jobs list updated daily`, `new grad 2027 <field> jobs list`, `AI machine learning jobs list updated daily`, `<role family> jobs <location or remote> list`. "Senior Engineer Github Job Board" alone does not work; the descriptive form did.

Take every repo whose description says it is a daily-updated job list, then pass them to `fetch_github_boards.py --repo <owner/repo> ...` (several at once) and read the sources report. Judge freshness from the repo's last-push date, not from search snippets, which disagreed with each other. When one publisher shows up, list its other repos with `--owner`. Treat repos named in this file as examples, not a complete list: boards appear, roll over and die each cycle.

Find more boards with `--owner` (list a publisher's repos) and `--search` ("junior software engineer jobs", "entry level jobs", "ai jobs"), and when a category has no tracker, say so and cover it through employer boards, VC portfolio boards and aggregators. Pass the matching words through `verify_jobs.py --allow-titles` or the title regexes so junior-titled roles are not dropped by a new-grad-shaped filter. Report the categories swept.

## Procedure

*Cycle-specific examples (repo names roll over each year). Find the current ones with `--search` and confirm each resolves before relying on it.*

1. **Check every tracker that fits the profile's level and field and returns parsed listings.** Query with `--repo`. Examples to start from (confirm each still exists and note the year in its name):
   - `SimplifyJobs/New-Grad-Positions`
   - `vanshb03/New-Grad-2027`
   - `speedyapply/2027-SWE-College-Jobs`
   - `speedyapply/2027-AI-College-Jobs`
   - `jobright-ai/2026-Software-Engineer-New-Grad`
   - `zapplyjobs/New-Grad-Jobs-2027`
   - plus the current-cycle internship tracker when internships are in scope (for example `SimplifyJobs/Summer2027-Internships`)

   Repo names roll over each cycle: the 2026 versions of the speedyapply lists were replaced by 2027 ones, so confirm the year in the name before relying on a board.

   **Deep mode adds boards that are not new-grad lists but still carry entry-level roles** (tested October 2026; all resolved and parsed): `dreamworkhq/AI-ML-Jobs`, `dreamworkhq/Data-Science-Jobs`, `dreamworkhq/Python-Developer-Jobs`, `dreamworkhq/Remote-Tech-Jobs`, `zapplyjobs/New-Grad-Data-Science-Jobs-2027`, `zapplyjobs/Visa-Sponsored-Jobs-2027`, `zapplyjobs/awesome-ml-internships-2027`, `jobright-ai/2026-Engineering-New-Grad`, `jobright-ai/2026-Data-Analysis-New-Grad`, `workopia/US-New-Grad-Internship-Jobs`. For these, filter by entry-level title words and by stated years, because the lists are mixed-level. Find more with `--search` (queries such as "ai jobs", "ml engineer jobs", "software engineer jobs") and by listing a known board owner's repositories.

   A repo that 404s or parses to 0 rows does not count; replace it with another board. Report how many returned listings.
2. Run at least one dynamic `--search` query built from the candidate's role focus and level (e.g. `"<level> <role focus>"`).
3. If the user named companies, keep the rows for those companies; otherwise use the boards market-wide.
4. Merge with ATS/portal results, deduplicate, then pass through the same disjoint filter and verification gate. A GitHub listing is a lead, never verification.

## Exclusions

`fetch_github_boards.py` excludes nothing by default. Pass the user's blacklist plus any active-pipeline companies (with parents/subsidiaries) collected at intake via `--exclude`. Never exclude a company the user explicitly listed as a target.

## Exception

The sweep may yield nothing when no repository matches (dynamic search returns zero repos and curated repos contain no rows for the target companies/role focus/locations) or GitHub is unreachable. The run must still attempt it, and the final response must say so, naming the repos and queries tried.

## Reporting

The script prints a **sources report** (and saves it as `sources_report` in the output JSON): every repo tried, how it was fetched (`python`, `curl` fallback or `file`), rows parsed, rows kept after filters, and the reason when a repo gave nothing (no README, tool or site-backed board, directory of companies, different layout). Nothing is dropped silently. The final response must list which repos were used, rows returned by each, and candidate roles each contributed, and name any that failed or parsed to 0 rows. A 0-row repo is not "covered": read it directly or use its live site, or say it was not checked.

If Python cannot reach GitHub, the script retries with `curl`. If both fail, fetch the raw file yourself (`curl -sL https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md`) and read it, or pass a saved copy with `--file`. `--repo` accepts several repos at once. Set `GITHUB_TOKEN` to avoid search rate limits.

## Example commands

```bash
python3 scripts/discover/fetch_github_boards.py --repo SimplifyJobs/New-Grad-Positions --locations "<Preferred Location>" --exclude <excluded companies> --output github_newgrad.json
python3 scripts/discover/fetch_github_boards.py --search "<level> <role focus>" --locations "<Preferred Location>" --exclude <excluded companies> --output github_dynamic.json
python3 scripts/discover/fetch_github_boards.py --file /path/or/raw-url/README.md --keywords "<keyword>"
# dynamic search tuning: --min-stars N --max-repos N
```
