"""Reparse saved School of Computing people pages without visiting the website.

From backend/: python scripts/reparse_soc_staff_pages.py

Reads the crawl report from scripts/fetch_soc_faculty.py (data/soc.json) for each department's
name, URL and saved HTML file, and writes data/soc_staff.json for scripts/import_staff_page.py.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from soc_staff_page import parse_soc_staff_page


def build_report(crawl, pages_dir):
    departments = []
    for dep in crawl["departments"]:
        people, errors, groups = [], [], {}
        if dep.get("html_file"):
            try:
                html = (pages_dir / dep["html_file"]).read_text(encoding="utf-8")
                people, checks = parse_soc_staff_page(html, dep.get("final_url") or dep["url"])
                errors, groups = checks["errors"], checks["groups"]
            except OSError as exc:
                errors = [str(exc)]
        else:
            errors = [dep.get("error", "HTML missing")]
        status = "success" if people and not errors else "parse_failed"
        if dep["status"] in {"failed", "pending"}:
            status = dep["status"]
        n = len(people) or 1
        departments.append({
            **{key: dep[key] for key in ("code", "department", "faculty", "url")},
            "status": status, "layout": "soc-angular", "people": people,
            "checks": {
                "count": len(people), "groups": groups, "errors": errors,
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
    parser.add_argument("--crawl", type=Path, default=BACKEND_DIR / "data/soc.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/soc_staff_pages")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/soc_staff.json")
    args = parser.parse_args()
    crawl = json.loads(args.crawl.read_text(encoding="utf-8"))
    report = build_report(crawl, args.pages)
    write_json(args.out, report)
    for dep in report["departments"]:
        print(f"{dep['department']}: {dep['status']}, {len(dep['people'])} people {dep['checks']['groups']}")
        for error in dep["checks"]["errors"]:
            print(f"  {error}")
    print(f"Saved: {args.out}; summary: {report['summary']}")
    return 0 if report["completed"] and all(d["status"] == "success" for d in report["departments"]) else 2


if __name__ == "__main__":
    sys.exit(main())
