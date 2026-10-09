"""
Import a saved department "faculty" page into the staff directory.

The page is behind a CAPTCHA, so save it from a browser first (e.g. with fetch_faculty.py, where
you complete the check yourself), then:

    python scripts/import_staff_page.py sol.html \\
        --url https://fass.nus.edu.sg/philo/faculty/ \\
        --department Philosophy --faculty "Faculty of Arts and Social Sciences"          # dry run
    ... --apply                                                                           # write it

Or import every department from the JSON made by scripts/reparse_staff_pages.py:

    python scripts/import_staff_page.py --json data/fass_staff.json            # dry run
    python scripts/import_staff_page.py --json data/fass_staff.json --apply

- People are upserted by (page URL, normalised name): re-importing an updated page refreshes them.
- People who disappeared from the page are reported, not deleted.
- Existing professors whose normalised name matches exactly are linked automatically.
- Similar-but-not-equal professors are listed with the command to link them, for a human to decide.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import SessionLocal
from main import find_similar_professors
from names import normalize_name
from staff_page import parse_staff_page
from tables import Professor, StaffMember


def import_people(db, people, source_url, department, faculty):
    """Upserts and links inside the caller's transaction. Returns a report dict."""
    rows = [
        {
            **person,
            "name_key": normalize_name(person["name"]),
            "department": department,
            "faculty": faculty,
            "source_url": source_url,
        }
        for person in people
    ]
    keys = {r["name_key"] for r in rows}
    if len(keys) != len(rows):
        raise ValueError("Two people on the page have the same normalised name")

    if rows:
        stmt = insert(StaffMember).values(rows)
        update_cols = [c for c in rows[0] if c not in ("source_url", "name_key")]
        db.execute(stmt.on_conflict_do_update(
            index_elements=["source_url", "name_key"],
            set_={**{c: stmt.excluded[c] for c in update_cols}, "updated_at": stmt.excluded.updated_at},
        ))

    staff = db.scalars(select(StaffMember).where(StaffMember.source_url == source_url)).all()
    report = {
        "imported": len(rows),
        "gone": sorted(s.name for s in staff if s.name_key not in keys),
        "linked": [],
        "suggestions": [],
    }

    linked_staff_ids = set(db.scalars(select(Professor.staff_id).where(Professor.staff_id.is_not(None))))
    for s in staff:
        if s.id in linked_staff_ids or s.name_key not in keys:
            continue
        exact = db.scalars(
            select(Professor).where(Professor.name_key == s.name_key, Professor.staff_id.is_(None))
        ).first()
        if exact:
            exact.staff_id = s.id
            exact.department = exact.department or s.department
            exact.faculty = exact.faculty or s.faculty
            report["linked"].append((exact.id, exact.name, s.name))
            continue
        for match in find_similar_professors(db, s.name):
            prof = db.get(Professor, match["id"])
            if prof.staff_id is None:
                report["suggestions"].append((prof.id, prof.name, s.id, s.name))
    db.flush()
    return report


def print_report(label, report):
    print(f"{label}: {report['imported']} people")
    for prof_id, prof_name, staff_name in report["linked"]:
        print(f"  linked professor #{prof_id} {prof_name!r} -> {staff_name!r}")
    if report["gone"]:
        print(f"  no longer on the page (kept): {', '.join(report['gone'])}")


def print_suggestions(suggestions):
    if not suggestions:
        return
    print("Possible matches to check by hand:")
    for prof_id, prof_name, staff_id, staff_name in suggestions:
        print(f"  professor #{prof_id} {prof_name!r} may be {staff_name!r}:")
        print(f"    python scripts/link_professor.py --professor {prof_id} --staff {staff_id} --use-official-name --apply")


def sources_from_args(args, parser):
    """[(label, people, url, department, faculty)] from either one HTML page or a reparse JSON."""
    if args.json:
        with open(args.json, encoding="utf-8") as f:
            data = json.load(f)
        return [
            (d["code"], d["people"], d["url"], d["department"], d["faculty"])
            for d in data["departments"] if d["people"]
        ]
    if not (args.html_file and args.url and args.department and args.faculty):
        parser.error("give an HTML file with --url, --department and --faculty, or use --json")
    with open(args.html_file, encoding="utf-8") as f:
        people = parse_staff_page(f.read(), args.url)
    if not people:
        sys.exit("Found nobody on the page. Is it the CAPTCHA page instead of the faculty list?")
    return [(os.path.basename(args.html_file), people, args.url, args.department, args.faculty)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html_file", nargs="?", help="a saved page")
    parser.add_argument("--url", help="the page's address (links and photos are relative to it)")
    parser.add_argument("--department")
    parser.add_argument("--faculty")
    parser.add_argument("--json", help="import every department in a reparse_staff_pages.py JSON file instead")
    parser.add_argument("--apply", action="store_true", help="actually write (default is a dry run)")
    args = parser.parse_args()

    sources = sources_from_args(args, parser)
    suggestions, total = [], 0
    # One transaction for everything: a bad department means nothing is written
    with SessionLocal() as db:
        for label, people, url, department, faculty in sources:
            report = import_people(db, people, url, department, faculty)
            print_report(label, report)
            total += report["imported"]
            suggestions += [s for s in report["suggestions"] if s not in suggestions]
        db.commit() if args.apply else db.rollback()

    print(f"\n{len(sources)} source(s), {total} people")
    print_suggestions(suggestions)
    print("Applied." if args.apply else "Dry run: nothing written. Re-run with --apply.")


if __name__ == "__main__":
    main()
