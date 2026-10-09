"""
Re-parse saved department pages into one clean JSON file, without visiting any website.

    python scripts/reparse_staff_pages.py                        # data/fass.json -> data/fass_staff.json
    python scripts/reparse_staff_pages.py --crawl data/fass.json --out data/fass_staff.json

Reads the crawl report from scripts/fetch_faculty.py (for each department's code, name and URL)
and the HTML it saved in data/staff_pages/<code>.html, runs staff_page.parse_staff_page on each,
and writes only what the site needs: department name, layout, people. Use this after improving
the parser: the pages were saved once, so there's nothing to fetch again.

Each department gets quality checks so a bad parse is visible before importing:
    count       people found
    *_pct       share of people with a position / photo / link / research areas
    dirty_names names that still contain link text, emails or phone numbers
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from staff_page import BeautifulSoup, detect_layout, parse_staff_page  # noqa: E402

FACULTY = "Faculty of Arts and Social Sciences"


def department_name(raw):
    """'Department of Chinese Studies(opens in new tab)' -> 'Chinese Studies' (the name NUSMods uses)."""
    name = re.sub(r"\(\s*opens in new tab\s*\)", "", raw, flags=re.IGNORECASE).strip()
    name = re.sub(r"^Department of\s+", "", name)
    name = re.sub(r"\s+Programme$", "", name)
    return name


def checks(people):
    n = len(people) or 1

    def pct(field):
        return round(100 * sum(1 for p in people if p[field]) / n)

    return {
        "count": len(people),
        "position_pct": pct("position"),
        "photo_pct": pct("photo_url"),
        "link_pct": pct("profile_urls"),
        "research_pct": pct("research_areas"),
        "dirty_names": [
            p["name"] for p in people
            if re.search(r"opens in|@|\bemail\b|\d{4}-\d{4}", p["name"], re.IGNORECASE) or len(p["name"]) > 80
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crawl", default=os.path.join(BACKEND_DIR, "data", "fass.json"))
    parser.add_argument("--pages", default=os.path.join(BACKEND_DIR, "data", "staff_pages"))
    parser.add_argument("--out", default=os.path.join(BACKEND_DIR, "data", "fass_staff.json"))
    args = parser.parse_args()

    with open(args.crawl, encoding="utf-8") as f:
        crawl = json.load(f)

    departments = []
    print(f"{'code':8} {'layout':14} {'people':>6} {'pos%':>5} {'photo%':>6} {'link%':>5} {'RA%':>4}  note")
    for dep in crawl["departments"]:
        code, url = dep["code"], dep.get("url") or dep.get("requested_url")
        path = os.path.join(args.pages, f"{code}.html")
        if not os.path.exists(path):
            print(f"{code:8} {'-':14} {'-':>6}  no saved page (crawl status: {dep['status']})")
            continue
        with open(path, encoding="utf-8") as f:
            html = f.read()
        layout = detect_layout(BeautifulSoup(html, "html.parser"))
        people = parse_staff_page(html, url)
        report = checks(people)
        note = "UNKNOWN LAYOUT" if layout == "unknown" else ("dirty names!" if report["dirty_names"] else "")
        print(f"{code:8} {layout:14} {report['count']:6} {report['position_pct']:5} {report['photo_pct']:6} "
              f"{report['link_pct']:5} {report['research_pct']:4}  {note}")
        departments.append({
            "code": code,
            "department": department_name(dep["department"]),
            "faculty": FACULTY,
            "url": url,
            "fetched_at": dep.get("fetched_at"),
            "layout": layout,
            "checks": report,
            "people": people,
        })

    out = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crawl": os.path.relpath(args.crawl, BACKEND_DIR),
        "departments": departments,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    total = sum(d["checks"]["count"] for d in departments)
    print(f"\n{len(departments)} departments, {total} people -> {os.path.relpath(args.out, BACKEND_DIR)}")


if __name__ == "__main__":
    main()
