# Availability, Hiring Channels, and Timing

Level match is not enough. A posting also has to fit **when the candidate can actually start** and **which hiring channel the employer uses for someone in their situation**. The same posting can be a clean fit for one person and a timing miss for another.

## 1. Establish availability (during intake)

Record, from the resume or by asking:
- **Earliest start date**, and how firm it is.
- **Constraints on starting**: graduation or thesis-defense date, notice period, garden leave or non-compete, visa or work-authorization transfer lead time, relocation, family or caregiving windows.
- **Months until available** = earliest start minus today's date.
- **Situation**, one of: `student (graduating)`, `recent graduate / PhD`, `employed (notice period)`, `between jobs (available now)`, `returning after a gap`, `career changer`. A person can be two of these.

If a constraint does not apply, say "none" and move on; do not ask about graduation to someone who has already graduated.

## 2. Classify every posting by hiring channel

| Channel | How to recognise it | Typically for |
|---|---|---|
| **University / cohort req** | New Grad, University Graduate, Campus, Early Career, graduate programme; states a graduation window or cohort start; often on a separate university or early-careers page | Students and recent graduates; start dates months out are expected |
| **Industry / open req** | No cohort language; "N+ years of experience"; team-specific; no graduation window | People who can start within weeks of an offer |
| **Internship / student researcher** | Intern, co-op, student researcher; requires enrollment | Students returning to school afterwards |
| **Fellowship / residency** | Fixed-term program with cohort dates | Depends on the stated eligibility |
| **Returnship / re-entry program** | Explicitly for people returning after a career break | Returners |
| **Contract / part-time / interim** | Fixed term, hourly, or fractional | Bridges, gap fill, flexible arrangements |
| **Executive / leadership search** | Director+ titles, confidential or retained search | Senior and management candidates |
| **Rotational / apprenticeship** | Structured multi-team program, often paired with training | Early-career and career changers |

Read the posting for the channel signals; never infer the channel from the company name alone.

## 3. Apply the timing rule to the person's situation

| Situation | Rule |
|---|---|
| **Student or graduating, more than ~2 months from available** | University / cohort reqs are primary; check the stated graduation window and start date against theirs (mismatch = `ERR_TIMING_INELIGIBLE`). Industry reqs are **timing risk**: never a direct match, only in a separate tier with the reason, and only when the posting states a flexible start or admits students. Internships are ineligible if they will have graduated before or during the term, unless allowed. |
| **Recent graduate, available now** | Industry reqs at or below the calibrated band are fair game; university reqs only inside their stated graduation window. |
| **PhD or postdoc with a defense date** | Treat the defense date as the start date; research roles with a stated start window are primary; industry reqs are timing risk until the defense is within weeks. |
| **Employed** | Open reqs fit; factor the notice period and any non-compete into the stated start. Do not suggest approaches that would tip off the current employer (see discretion in the advice document). |
| **Between jobs** | Everything at the band is fair game; prioritize speed and how fast a company moves. |
| **Returning after a gap** | Add returnship and re-entry programs and contract bridges; judge level by prior experience, not the gap. |
| **Career changer** | Calibrate on transferable seniority, note what is new, and include rotational / adjacent-role channels. |
| **Needs sponsorship or transfer** | Scan each posting for sponsorship or right-to-work language; add transfer lead time to availability. |

University / cohort reqs are ignored for experienced candidates unless the posting is open to them.

## 4. Employers that route entry-level hiring through university recruiting

Some employers fill entry-level roles almost entirely through campus pipelines (cohort reqs, campus recruiters, intern conversion) and do not consider students for open industry reqs. When the candidate is a student or recent graduate, sweep the university / early-careers listings first and treat these employers' industry reqs as timing risk.

Signals that an employer works this way:
- A dedicated university or early-careers page, or cohort-titled reqs ("New College Grad <year>").
- Non-cohort reqs that say experience "does not include internships" or carry level suffixes.
- Internship postings that describe themselves as the pipeline to full-time offers.

Confirm against live postings each run. When such an employer has **no open cohort req** for the candidate's window, say so ("university req for <window> not posted / not found") and put the employer on the watch list rather than substituting industry reqs.

## 5. Reporting

Each role in the deliverables states its channel and a timing verdict: `Eligible (window fits)`, `Timing risk (<reason>, candidate available in N months)`, or `Ineligible`. The final response states the availability date used and the situation it came from.
