"""Reparse saved BIZ HTML without visiting the website.

From backend/: python scripts/reparse_biz_staff_pages.py
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from biz_staff_page import department_name, directory_page, pagination, parse_biz_staff_page


def build_report(crawl, pages_dir):
    departments = []
    for dep in crawl["departments"]:
        people, seen, errors = [], set(), []
        saved_numbers, linked_numbers = set(), set()
        page_checks = []
        for page in dep["pages"]:
            if not page.get("html_file"):
                errors.append(f"{page['requested_url']}: {page.get('error', 'HTML missing')}")
                continue
            try:
                html = (pages_dir / page["html_file"]).read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(str(exc))
                continue
            parsed, checks = parse_biz_staff_page(html, page["url"], dep["department"])
            target = directory_page(page["url"], dep["url"])
            if target:
                saved_numbers.add(target[1])
                linked_numbers.update(pagination(html, page["url"], target[0]))
            page_checks.append({"url": page["url"], **checks})
            errors.extend(f"{page['url']}: {error}" for error in checks["errors"])
            for person in parsed:
                key = person["name"].casefold()
                if key in seen:
                    errors.append(f"duplicate across pages: {person['name']}")
                    continue
                seen.add(key)
                people.append(person)
        complete = dep.get("pagination_complete", False)
        # Recheck links instead of trusting reports created by an older parser.
        missing = linked_numbers - saved_numbers
        if missing:
            complete = False
            errors.append("linked pages have no saved HTML: " + ", ".join(map(str, sorted(missing))))
        if not complete:
            errors.append("pagination incomplete; this department may be missing people")
        status = "success" if complete and people and not errors else "parse_failed"
        if dep["status"] in {"failed", "pending"}:
            status = dep["status"]
        n = len(people) or 1
        departments.append({
            # Cards are matched on the site's label; the export uses the name the rest of the app uses
            **{key: dep[key] for key in ("code", "faculty", "url")},
            "department": department_name(dep["department"]),
            "status": status, "layout": "biz-directory", "people": people,
            "checks": {
                "count": len(people), "errors": errors, "pages": page_checks,
                **{field + "_pct": round(100 * sum(bool(p[field]) for p in people) / n)
                   for field in ("position", "photo_url", "profile_urls", "research_areas")},
            },
        })
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed": crawl["completed"], "departments": departments,
        "summary": {status: sum(d["status"] == status for d in departments)
                    for status in ("success", "failed", "parse_failed", "pending")},
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawl", type=Path, default=BACKEND_DIR / "data/biz.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/biz_staff_pages")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/biz_staff.json")
    args = parser.parse_args()
    crawl = json.loads(args.crawl.read_text(encoding="utf-8"))
    report = build_report(crawl, args.pages)
    write_json(args.out, report)
    for dep in report["departments"]:
        print(f"{dep['department']}: {dep['status']}, {len(dep['people'])} people")
    print(f"Saved: {args.out}; summary: {report['summary']}")
    return 0 if report["completed"] and all(d["status"] == "success" for d in report["departments"]) else 2


if __name__ == "__main__":
    sys.exit(main())
