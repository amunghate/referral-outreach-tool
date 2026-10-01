#!/usr/bin/env python3
"""Prepare and track LinkedIn referral messages without automating LinkedIn actions."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path


DEFAULT_TRACKER = Path(__file__).with_name("linkedin-referral-outreach.csv")
DEFAULT_DRAFTS = Path(__file__).with_name("linkedin-referral-drafts.csv")
TRACKER_FIELDS = (
    "name",
    "role_company",
    "location",
    "linkedin_profile",
    "status",
    "sent_date",
    "notes",
)
READY_STATUSES = {"qualified - unsent", "ready", "queued"}
WORK_HISTORY_FIELDS = {
    "experience",
    "work_history",
    "employment_history",
    "previous_companies",
    "past_companies",
}


def read_tracker(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Tracker has no CSV header: {path}")
            fields = list(reader.fieldnames)
            rows = [
                {field: (row.get(field) or "").strip() for field in fields}
                for row in reader
            ]
            return fields, rows
    except FileNotFoundError as exc:
        raise SystemExit(f"Tracker not found: {path}") from exc


def write_tracker(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    output_fields = list(dict.fromkeys([*TRACKER_FIELDS, *fields]))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def blocked(
    row: dict[str, str],
    all_rows: list[dict[str, str]],
    excluded_names: set[str],
    excluded_companies: tuple[str, ...],
) -> bool:
    name = normalized(row.get("name", ""))
    url = normalized(row.get("linkedin_profile", "")).rstrip("/")
    if name in excluded_names:
        return True
    current_company = normalized(row.get("role_company", ""))
    work_history = normalized(
        " ".join(
            value
            for field, value in row.items()
            if field.casefold() in WORK_HISTORY_FIELDS
        )
    )
    if any(term in current_company or term in work_history for term in excluded_companies):
        return True
    return any(
        other is not row
        and normalized(other.get("status", "")) in {
            "sent",
            "previously messaged (verify)",
        }
        and (
            (name and name == normalized(other.get("name", "")))
            or (url and url == normalized(other.get("linkedin_profile", "")).rstrip("/"))
        )
        for other in all_rows
    )


def make_draft(
    row: dict[str, str],
    candidate_summary: str,
    target_summary: str,
    location_preference: str,
) -> str:
    first_name = row.get("name", "").split()[0]
    role_company = row.get("role_company", "").strip()
    role = ""
    company = ""
    if "|" in role_company:
        role, company = (part.strip() for part in role_company.split("|", 1))
    elif " at " in role_company.lower():
        parts = re.split(r"\s+at\s+", role_company, maxsplit=1, flags=re.IGNORECASE)
        role, company = parts[0].strip(), parts[1].strip()
    else:
        role = role_company

    relevant_work = f"your work as {role} at {company}" if company else (
        f"your experience as {role}" if role else "your DevOps and cloud-platform experience"
    )
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    return (
        f"{greeting} I noticed {relevant_work} and wanted to reach out. "
        f"I'm exploring {target_summary}, ideally {location_preference}. "
        f"{candidate_summary.rstrip()} "
        "If you hear of a suitable opening, would you be comfortable referring me? "
        "Happy to share my resume. Thanks!"
    )


def prepare(args: argparse.Namespace) -> int:
    _, rows = read_tracker(args.tracker)
    ready = [
        row for row in rows
        if normalized(row.get("status", "")) in READY_STATUSES
        and row.get("name")
        and not blocked(
            row, rows, set(args.exclude_name), tuple(map(normalized, args.exclude_company))
        )
    ][: args.limit]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        fields = ["name", "role_company", "location", "linkedin_profile", "message"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ready:
            writer.writerow(
                {
                    "name": row.get("name", ""),
                    "role_company": row.get("role_company", ""),
                    "location": row.get("location", ""),
                    "linkedin_profile": row.get("linkedin_profile", ""),
                    "message": make_draft(
                        row,
                        args.candidate_summary,
                        args.target_summary,
                        args.location_preference,
                    ),
                }
            )
    print(f"Prepared {len(ready)} draft(s): {args.output}")
    print("Review each draft and recipient in LinkedIn before manually sending.")
    return 0


def mark_sent(args: argparse.Namespace) -> int:
    fields, rows = read_tracker(args.tracker)
    matches = [
        row for row in rows
        if normalized(row.get("name", "")) == normalized(args.name)
        and normalized(row.get("status", "")) in READY_STATUSES
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one ready candidate named {args.name!r}; found {len(matches)}."
        )
    row = matches[0]
    if blocked(
        row, rows, set(args.exclude_name), tuple(map(normalized, args.exclude_company))
    ):
        raise SystemExit(f"Refusing to mark excluded or previously messaged contact: {args.name}")
    row["status"] = "Sent"
    row["sent_date"] = date.today().isoformat()
    row["notes"] = "; ".join(filter(None, (row.get("notes", ""), "Marked sent manually")))
    write_tracker(args.tracker, fields, rows)
    print(f"Updated tracker for {row['name']}.")
    return 0


def add_candidate(args: argparse.Namespace) -> int:
    fields, rows = read_tracker(args.tracker)
    fields = list(dict.fromkeys([*TRACKER_FIELDS, *fields]))
    proposed = {
        "name": args.name.strip(),
        "role_company": args.role_company.strip(),
        "location": args.location.strip(),
        "linkedin_profile": args.linkedin_profile.strip(),
        "status": "Needs review",
        "sent_date": "",
        "notes": args.notes.strip(),
    }
    if blocked(
        proposed, rows, set(args.exclude_name), tuple(map(normalized, args.exclude_company))
    ):
        raise SystemExit("Candidate is excluded or already appears in the sent history.")
    proposed_url = normalized(proposed["linkedin_profile"]).rstrip("/")
    if any(
        normalized(row.get("name", "")) == normalized(proposed["name"])
        or (
            proposed_url
            and proposed_url == normalized(row.get("linkedin_profile", "")).rstrip("/")
        )
        for row in rows
    ):
        raise SystemExit("Candidate already exists in the tracker.")
    rows.append(proposed)
    write_tracker(args.tracker, fields, rows)
    print(f"Added {proposed['name']} as Needs review; qualify them after checking their profile.")
    return 0


def qualify(args: argparse.Namespace) -> int:
    fields, rows = read_tracker(args.tracker)
    matches = [
        row for row in rows
        if normalized(row.get("name", "")) == normalized(args.name)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one tracker entry named {args.name!r}; found {len(matches)}."
        )
    row = matches[0]
    if blocked(
        row, rows, set(args.exclude_name), tuple(map(normalized, args.exclude_company))
    ):
        raise SystemExit(f"Refusing to qualify excluded or previously messaged contact: {args.name}")
    if normalized(row.get("status", "")) != "needs review":
        raise SystemExit(f"Cannot qualify {args.name}: status is {row.get('status')!r}.")
    row["status"] = "Qualified - unsent"
    write_tracker(args.tracker, fields, rows)
    print(f"{row['name']} is now queued for draft generation.")
    return 0


def import_candidates(args: argparse.Namespace) -> int:
    fields, rows = read_tracker(args.tracker)
    try:
        with args.source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Candidate file has no CSV header: {args.source}")
            source_field_names = list(reader.fieldnames)
            source_fields = set(source_field_names)
            if not {"name", "role_company"}.issubset(source_fields):
                raise ValueError(
                    "Candidate CSV must include name and role_company columns."
                )
            candidates = list(reader)
    except FileNotFoundError as exc:
        raise SystemExit(f"Candidate CSV not found: {args.source}") from exc

    known_names = {normalized(row.get("name", "")) for row in rows}
    known_urls = {
        normalized(row.get("linkedin_profile", "")).rstrip("/")
        for row in rows
        if row.get("linkedin_profile")
    }
    imported = 0
    skipped = 0
    for source_row in candidates:
        candidate = {
            field: (source_row.get(field) or "").strip()
            for field in source_field_names
        }
        for field in TRACKER_FIELDS:
            candidate.setdefault(field, "")
        candidate["status"] = "Needs review"
        candidate["sent_date"] = ""
        name = normalized(candidate["name"])
        profile = normalized(candidate["linkedin_profile"]).rstrip("/")
        if not name or name in known_names or (profile and profile in known_urls):
            skipped += 1
            continue
        if blocked(
            candidate, rows, set(args.exclude_name), tuple(map(normalized, args.exclude_company))
        ):
            skipped += 1
            continue
        rows.append(candidate)
        known_names.add(name)
        if profile:
            known_urls.add(profile)
        imported += 1

    fields = list(dict.fromkeys([*TRACKER_FIELDS, *fields, *source_fields]))
    write_tracker(args.tracker, fields, rows)
    print(
        f"Imported {imported} new contact(s) as Needs review; "
        f"skipped {skipped} duplicate, excluded, or unnamed row(s)."
    )
    print("Review each person's LinkedIn profile and work history before qualifying.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracker", type=Path, default=DEFAULT_TRACKER)
    parser.add_argument(
        "--exclude-name", action="append", default=[], metavar="NAME",
        help="Exclude a person by full name (repeatable)",
    )
    parser.add_argument(
        "--exclude-company", action="append", default=[], metavar="TERM",
        help="Exclude a current or past employer term (repeatable)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare_parser = commands.add_parser("prepare", help="Write personalized drafts for qualified contacts")
    prepare_parser.add_argument("--limit", type=int, default=10)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_DRAFTS)
    prepare_parser.add_argument(
        "--candidate-summary",
        default="I bring experience across cloud infrastructure, automation, and delivery.",
        help="Short, truthful summary of your own experience",
    )
    prepare_parser.add_argument(
        "--target-summary",
        default="DevOps/Platform roles",
        help="Role types you are targeting",
    )
    prepare_parser.add_argument(
        "--location-preference",
        default="Pune hybrid or remote",
        help="Your preferred work location",
    )
    prepare_parser.set_defaults(func=prepare)

    add_parser = commands.add_parser("add", help="Add a candidate that still needs profile review")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--role-company", default="")
    add_parser.add_argument("--location", default="")
    add_parser.add_argument("--linkedin-profile", default="")
    add_parser.add_argument("--notes", default="")
    add_parser.set_defaults(func=add_candidate)

    qualify_parser = commands.add_parser("qualify", help="Queue a reviewed candidate for drafting")
    qualify_parser.add_argument("--name", required=True)
    qualify_parser.set_defaults(func=qualify)

    import_parser = commands.add_parser(
        "import-csv", help="Import contacts from a user-provided CSV for review"
    )
    import_parser.add_argument("--source", type=Path, required=True)
    import_parser.set_defaults(func=import_candidates)

    sent_parser = commands.add_parser("mark-sent", help="Record a message you manually sent")
    sent_parser.add_argument("--name", required=True)
    sent_parser.set_defaults(func=mark_sent)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare" and not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    try:
        return args.func(args)
    except (OSError, csv.Error, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
