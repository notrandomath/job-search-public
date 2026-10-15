# Lite Mode: A Short, Cheap Run

For people low on tokens or time who accept less thoroughness. Chosen at intake (see `intake.md` section 5b). Lite trades coverage and verification depth for cost; it never trades honesty. Everything stated in the other workflow files still applies except where this file narrows it.

## Budget

About **8 tool calls in total**, including intake file reads. Stop when the budget is spent; do not extend it silently. If the user wants more, say standard mode would do it and offer to continue.

## Intake in lite

- Read the resume. Ask the goal question, location and work authorization, exclusions, and (for the advice report) the yes/no. Skip follow-up questions, evidence uploads, and the search-scope menu: infer scope from the goal and say what you inferred in one line.
- Still show the permission warning in one line.

## Sources in lite (in this order, stop early)

1. **One GitHub tracker run** for the person's band (new-grad tracker for people in a graduation window; a mixed-level board such as `dreamworkhq/*` for others; see `github_job_boards.md`). One `fetch_github_boards.py` call with location and exclusions, or one raw README fetch if scripts cannot run. GitHub is never skipped, even in lite.
2. **One ATS call** (`fetch_job_boards.py`) for the companies the user named, if any, for at most about 10 slugs.
3. **Nothing else.** No aggregators, no web-search sweep, no deep avenues, no per-company recruiting-window research beyond what the one fetch returned.

## Verification in lite

- One batch run of `verify_jobs.py` over the top 10 to 15 candidates by fit (set `--max-yoe` and `--allow-titles` from the calibrated band as usual). Rows that pass go in "Apply now".
- Candidates not fetched are **not** listed as verified. Put at most 10 of them under a separate heading, "Unchecked leads (from the tracker, not fetched)", with the tracker as the source, and tell the reader to confirm each is open before applying.
- Do not skip the exclusion filter or the level check.

## Advice report in lite (only if they said yes)

Still four sections, shorter: 
- Named companies: say what the single fetch showed and mark any opening window "inferred" or "not checked". Do not research windows.
- Avenues: choose from the avenue map ones that need no live lookup (VC and community boards by name, recruiter or sourcer outreach, referral and alumni routes, communities and venues from the resume, upstream work, fellowships you already know of). Include the 3 most promising resume-derived ones. Skip any avenue that would require fetching to confirm.
- Plan: a short table.
- Notes: say plainly this was a lite run, what was and was not checked, and that standard mode covers more.

## Adjacent roles in lite

Lite does not run the trajectory test (`trajectory_test.md`), so it does not offer contract, QA or test, support, agency or other adjacent roles at all, and does not ask the intake question about them. Say in one line that adjacent roles were skipped and that standard mode evaluates them.

## What lite must still do

- Honor exclusions everywhere.
- Label unfetched rows honestly (above).
- Use the Source column truthfully.
- State at the top of `job_list.md` that this is a lite run with partial verification.
