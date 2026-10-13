"""Reparse saved CDE HTML without network access.

From backend/: python scripts/reparse_cde_staff_pages.py
"""
import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from cde_staff_page import FACULTY, PaginationError, merge_people, page_key, pagination, parse_cde_staff_page
from fetch_faculty import now


def build_report(crawl, pages_dir):
    departments = []
    for dep in crawl["departments"]:
        people, errors, page_checks = [], [], []
        saved, expected = set(), {page_key(url) for url in dep["urls"]}
        for entry in dep.get("pages", []):
            if not entry.get("html_file"):
                errors.append(entry.get("error", "HTML missing"))
                continue
            try:
                html = (pages_dir / entry["html_file"]).read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(str(exc))
                continue
            final_url = entry["url"]
            parsed, checks = parse_cde_staff_page(html, final_url)
            people.extend(parsed)
            page_checks.append({"url": final_url, **checks})
            errors.extend(f"{final_url}: {error}" for error in checks["errors"])
            try:
                actual_key = page_key(final_url)
                requested_key = page_key(entry["requested_url"])
                saved.add(actual_key)
                if actual_key[:3] == requested_key[:3] and not requested_key[3]:
                    saved.add(requested_key)
                if entry.get("error"):
                    errors.append(f"{final_url}: {entry['error']}")
                expected.update(page_key(url) for url in pagination(html, final_url))
            except PaginationError as exc:
                errors.append(str(exc))
        missing = expected - saved
        if missing:
            errors.append(f"{len(missing)} configured/pagination URLs have no saved HTML")
        complete = dep.get("pagination_complete", False) and not missing
        if not complete:
            errors.append("pagination or configured categories incomplete")
        people = merge_people(people)
        status = "success" if people and complete and not errors else "parse_failed"
        if dep["status"] in {"failed", "pending"}:
            status = dep["status"]
        n = len(people) or 1
        departments.append({
            "code": dep["code"], "department": dep["department"], "faculty": FACULTY,
            "url": dep["urls"][0], "urls": dep["urls"], "status": status,
            "layout": "cde", "people": people,
            "checks": {
                "count": len(people), "errors": errors, "pages": page_checks,
                **{field + "_pct": round(100 * sum(bool(p[field]) for p in people) / n)
                   for field in ("position", "photo_url", "profile_urls", "research_areas")},
            },
        })
    return {
        "schema_version": 1, "generated_at": now(), "completed": crawl["completed"],
        "departments": departments,
        "summary": {status: sum(dep["status"] == status for dep in departments)
                    for status in ("success", "failed", "parse_failed", "pending")},
    }


def write_json(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def departments_succeeded(report):
    return bool(report["departments"]) and all(dep["status"] == "success" for dep in report["departments"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crawl", type=Path, default=BACKEND_DIR / "data/cde.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/cde_staff_pages")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/cde_staff.json")
    args = parser.parse_args()
    crawl = json.loads(args.crawl.read_text(encoding="utf-8"))
    report = build_report(crawl, args.pages)
    write_json(args.out, report)
    for dep in report["departments"]:
        print(f"{dep['code']}: {dep['status']}, {len(dep['people'])} people")
        for error in dep["checks"]["errors"]:
            print(f"  {error}")
    print(f"Saved: {args.out}; summary: {report['summary']}")
    return 0 if report["completed"] and departments_succeeded(report) else 2


if __name__ == "__main__":
    sys.exit(main())
