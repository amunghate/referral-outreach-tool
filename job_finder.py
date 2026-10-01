#!/usr/bin/env python3
"""Find and rank public DevOps roles against a local candidate profile."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_PROFILE = Path(__file__).with_name("resume_profile.json")
USER_AGENT = "local-job-finder/1.0"


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str
    published: str = ""

    def searchable_text(self) -> str:
        return " ".join(
            (self.title, self.company, self.location, self.description)
        ).lower()


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def remotive_jobs(query: str) -> list[Job]:
    url = "https://remotive.com/api/remote-jobs?" + urlencode({"search": query})
    payload = fetch_json(url)
    return [
        Job(
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            location=item.get("candidate_required_location", "Remote"),
            url=item.get("url", ""),
            description=item.get("description", ""),
            source="Remotive",
            published=item.get("publication_date", ""),
        )
        for item in payload.get("jobs", [])
    ]


def arbeitnow_jobs(query: str) -> list[Job]:
    payload = fetch_json("https://www.arbeitnow.com/api/job-board-api")
    terms = set(tokenize(query))
    jobs: list[Job] = []
    for item in payload.get("data", []):
        job = Job(
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            location=item.get("location", ""),
            url=item.get("url", ""),
            description=item.get("description", ""),
            source="Arbeitnow",
            published=str(item.get("created_at", "")),
        )
        if not terms or terms.intersection(set(tokenize(job.searchable_text()))):
            jobs.append(job)
    return jobs


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+#./-]*", value.lower())


def load_profile(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Profile not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid profile JSON ({path}): {exc}") from exc


def score_job(job: Job, profile: dict[str, Any]) -> tuple[int, list[str]]:
    text = job.searchable_text()
    matched: list[str] = []
    for skill in profile.get("skills", []):
        if skill.lower() in text:
            matched.append(skill)
    title_text = job.title.lower()
    title_bonus = sum(
        12 for target in profile.get("target_titles", []) if target.lower() in title_text
    )
    location_bonus = 15 if is_location_eligible(job, profile) else 0
    score = min(100, len(matched) * 5 + title_bonus + location_bonus)
    return score, matched


def is_location_eligible(job: Job, profile: dict[str, Any]) -> bool:
    """Allow Pune roles and remote roles that do not exclude India."""
    location = job.location.lower()
    pune_terms = ("pune", "ravet")
    remote_terms = ("remote", "work from anywhere", "distributed")
    india_terms = ("india", "apac", "asia pacific", "worldwide", "global", "anywhere")
    if any(term in location for term in pune_terms):
        return True
    return any(term in location for term in remote_terms) and any(
        term in location for term in india_terms
    )


def deduplicate(jobs: list[Job]) -> list[Job]:
    seen: set[str] = set()
    unique: list[Job] = []
    for job in jobs:
        key = job.url or f"{job.company}:{job.title}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def search(
    profile: dict[str, Any], query: str, limit: int, eligible_only: bool = True
) -> list[dict[str, Any]]:
    jobs: list[Job] = []
    errors: list[str] = []
    for provider in (remotive_jobs, arbeitnow_jobs):
        try:
            jobs.extend(provider(query))
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    ranked = []
    for job in deduplicate(jobs):
        if eligible_only and not is_location_eligible(job, profile):
            continue
        score, matched = score_job(job, profile)
        ranked.append(
            {
                "score": score,
                "matched_skills": matched,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "published": job.published,
                "url": job.url,
            }
        )
    ranked.sort(key=lambda item: (item["score"], item["published"]), reverse=True)
    if errors:
        print("Provider warnings:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    return ranked[:limit]


def resume_review(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_assessment": (
            "Use this checklist to tailor your own profile to the target roles. "
            "Validate every claim and add measurable evidence where possible."
        ),
        "strengths": [
            "Target titles: " + ", ".join(profile.get("target_titles", [])),
            "Relevant skills: " + ", ".join(profile.get("skills", [])),
            "Preferred locations: " + ", ".join(profile.get("locations", [])),
        ],
        "priority_changes": [
            "Add measurable outcomes to experience bullets (time, cost, uptime, scale, or incident reduction).",
            "Replace vague impact claims with specific before-and-after numbers.",
            "Clarify leadership scope, team size, systems operated, and on-call responsibilities.",
            "Tailor the headline and relevant skills to each target role.",
        ],
        "target_titles": profile.get("target_titles", []),
        "missing_evidence_to_collect": [
            "Scale of the largest systems, clusters, or workloads you supported",
            "Deployment frequency and delivery-time improvements",
            "Cloud cost reductions and reliability outcomes",
            "Availability objectives and incident-response metrics",
            "Number of teams or engineers enabled by your platform work",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Fetch and rank public job listings")
    search_parser.add_argument("--query", default="DevOps Engineer")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument(
        "--all-locations",
        action="store_true",
        help="Include jobs outside Pune and remote roles that do not mention India/APAC",
    )
    search_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    review_parser = subparsers.add_parser("resume-review", help="Print resume improvement guidance")
    review_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    args = parser.parse_args()
    profile = load_profile(args.profile)
    if args.command == "resume-review":
        result = resume_review(profile)
    else:
        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": args.query,
            "location_scope": (
                "Pune or remote from India/APAC/worldwide"
                if not args.all_locations
                else "all locations"
            ),
            "jobs": search(
                profile,
                args.query,
                max(1, args.limit),
                eligible_only=not args.all_locations,
            ),
        }
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.command == "resume-review":
        print(result["overall_assessment"])
        for heading in ("strengths", "priority_changes", "missing_evidence_to_collect"):
            print(f"\n{heading.replace('_', ' ').title()}:")
            for item in result[heading]:
                print(f"- {item}")
    else:
        for job in result["jobs"]:
            print(f"[{job['score']:>3}] {job['title']} — {job['company']} ({job['source']})")
            print(f"      {job['location']} | {job['url']}")
            print(f"      Skills: {', '.join(job['matched_skills'][:8]) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
