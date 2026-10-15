#!/usr/bin/env python3
"""
Fetch live job postings from major job boards (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter)
using python-jobspy.

Requirements:
    pip install python-jobspy

Usage:
    python3 fetch_jobspy.py --search-term "<role>" --location "<City, Region>" --country "<Country>"
    python3 fetch_jobspy.py --search-term "<role>" --country "<Country>" --sites linkedin indeed google --hours-old 168 --results-wanted 25 --output scratch/jobspy_results.json
"""

import argparse
import json
import sys

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'lib'))
from _common import setup_stdio

setup_stdio()
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch live job postings using python-jobspy.")
    parser.add_argument("--search-term", type=str, required=True, help="Job title or search query (e.g. 'Software Engineer')")
    parser.add_argument("--location", type=str, required=True, help="Target location, e.g. '<City>, <State>' or 'Remote'")
    parser.add_argument(
        "--sites",
        nargs="+",
        default=["linkedin", "indeed", "glassdoor", "google"],
        help="Job boards to query: linkedin, indeed, glassdoor, google, zip_recruiter (default: linkedin indeed glassdoor google)",
    )
    parser.add_argument("--results-wanted", type=int, default=20, help="Number of results desired per site (default: 20)")
    parser.add_argument("--hours-old", type=int, default=168, help="Max posting age in hours (default: 168 = 7 days)")
    parser.add_argument("--country", type=str, required=True, help="Country for Indeed/Glassdoor/ZipRecruiter (e.g. USA, UK, Canada, India); no default")
    parser.add_argument("--is-remote", action="store_true", help="Filter for remote jobs only")
    parser.add_argument("--output", type=str, help="Output JSON file path (prints to stdout if omitted)")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        from jobspy import scrape_jobs
    except ImportError:
        sys.stderr.write(
            "ERROR: 'python-jobspy' is not installed in the current Python environment.\n"
            "Install it via: pip install python-jobspy (optional; see references/sources/sources_and_fallbacks.md)\n"
        )
        sys.exit(1)

    # Validate sites
    valid_sites = {"linkedin", "indeed", "glassdoor", "google", "zip_recruiter"}
    requested_sites = [s.lower() for s in args.sites if s.lower() in valid_sites]
    if not requested_sites:
        sys.stderr.write(f"ERROR: No valid sites specified. Choose from: {', '.join(valid_sites)}\n")
        sys.exit(1)

    sys.stderr.write(
        f"Querying [{', '.join(requested_sites)}] for '{args.search_term}' in '{args.location}' "
        f"(max {args.results_wanted} results/site, {args.hours_old}h recency)...\n"
    )

    try:
        jobs_df = scrape_jobs(
            site_name=requested_sites,
            search_term=args.search_term,
            location=args.location,
            results_wanted=args.results_wanted,
            hours_old=args.hours_old,
            country_indeed=args.country,
            is_remote=args.is_remote,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR during scraping: {e}\n")
        sys.exit(1)

    if jobs_df is None or jobs_df.empty:
        sys.stderr.write("No jobs found matching the criteria.\n")
        jobs_list = []
    else:
        # Normalize into clean JSON objects
        records = jobs_df.to_dict(orient="records")
        jobs_list = []
        for r in records:
            # Format date safely
            date_posted = r.get("date_posted")
            if isinstance(date_posted, datetime):
                date_str = date_posted.isoformat()
            elif date_posted is not None and not (isinstance(date_posted, float) and str(date_posted) == "nan"):
                date_str = str(date_posted)
            else:
                date_str = None

            job_obj = {
                "source": r.get("site"),
                "company": r.get("company"),
                "title": r.get("title"),
                "location": r.get("location"),
                "url": r.get("job_url"),
                "date_posted": date_str,
                "is_remote": r.get("is_remote"),
                "job_type": r.get("job_type"),
                "compensation": {
                    "min_amount": r.get("min_amount"),
                    "max_amount": r.get("max_amount"),
                    "currency": r.get("currency"),
                    "interval": r.get("interval"),
                },
                "raw_description": (r.get("description") or "")[:4000] if r.get("description") else None,
            }
            jobs_list.append(job_obj)

    sys.stderr.write(f"Retrieved {len(jobs_list)} jobs.\n")

    json_data = json.dumps(jobs_list, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_data)
        sys.stderr.write(f"Saved results to {args.output}\n")
    else:
        print(json_data)


if __name__ == "__main__":
    main()
