"""Save the School of Computing people pages and export personnel JSON, without visiting profiles.

From backend/ with .venv-homework activated:
    python scripts/fetch_soc_faculty.py
    python scripts/fetch_soc_faculty.py --department soc-cs

Each department is a single page (soc_staff_page.SOURCES) with everyone embedded in it, so there
is no pagination. Complete any website verification in the visible browser. Reparse saved HTML
offline with scripts/reparse_soc_staff_pages.py after changing the parser.
"""
import argparse
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from soc_staff_page import FACULTY, SOURCES, js_arrays, parse_soc_staff_page
from reparse_soc_staff_pages import build_report, write_json
from fetch_faculty import BLOCK_TEXT, PageFailure, now


class SocLoader:
    def __init__(self, page, delay, interactive):
        self.page, self.delay, self.interactive = page, delay, interactive
        self.last_request = 0

    def load(self, url):
        from playwright.sync_api import Error
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        print(f"  Visit: {url}", flush=True)
        try:
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            deadline = time.monotonic() + 15
            while True:
                html = self.page.content()
                # The people arrays are in the HTML itself: once they're there, the page is real
                if "allStaffs" in js_arrays(html):
                    if response and response.status >= 400:
                        raise PageFailure(f"HTTP {response.status}")
                    return html, self.page.url
                challenge = bool(BLOCK_TEXT.search(html)) or "_Incapsula_Resource" in html
                if time.monotonic() >= deadline:
                    if self.interactive and challenge and sys.stdin.isatty():
                        answer = input("  Complete verification in browser, then Enter; s to skip: ").strip().lower()
                        if answer != "s":
                            response = None  # manual navigation may have replaced the response
                            deadline = time.monotonic() + 15
                            continue
                    raise PageFailure("no staff list on the page (verification, or the layout changed)")
                self.page.wait_for_timeout(500)
        except Error as exc:
            raise PageFailure(str(exc).splitlines()[0]) from exc


def fetch_department(loader, dep, pages_dir, checkpoint):
    try:
        html, final_url = loader.load(dep["url"])
    except PageFailure as exc:
        dep.update(status="failed", error=str(exc))
        checkpoint()
        return
    filename = f"{dep['code']}.html"
    (pages_dir / filename).write_text(html, encoding="utf-8")
    people, checks = parse_soc_staff_page(html, final_url)
    dep.update(final_url=final_url, html_file=filename, fetched_at=now(), checks=checks,
               status="parse_failed" if checks["errors"] else "success")
    if checks["errors"]:
        print("  Parse failed: " + "; ".join(checks["errors"]), flush=True)
    else:
        print(f"  {len(people)} people {checks['groups']}", flush=True)
    checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--department", action="append", default=[], choices=[s["code"] for s in SOURCES],
                        help="department code; repeat to select several")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/soc.json", help="crawl report")
    parser.add_argument("--staff-out", type=Path, default=BACKEND_DIR / "data/soc_staff.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/soc_staff_pages")
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--no-interaction", action="store_true")
    args = parser.parse_args()
    if args.delay < 0.5:
        parser.error("--delay must be >= 0.5")
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    report = {
        "schema_version": 1, "started_at": now(), "completed": False,
        "departments": [
            {**source, "faculty": FACULTY, "status": "pending"}
            for source in SOURCES if not args.department or source["code"] in args.department
        ],
    }
    args.pages.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        write_json(args.out, report)
        write_json(args.staff_out, build_report(report, args.pages))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                loader = SocLoader(browser.new_page(), args.delay, not args.no_interaction)
                for dep in report["departments"]:
                    print(dep["department"], flush=True)
                    fetch_department(loader, dep, args.pages, checkpoint)
                report["completed"] = True
            finally:
                browser.close()
    except (KeyboardInterrupt, EOFError):
        print("Stopped; saved downloaded pages and partial JSON.", file=sys.stderr)
        return 130
    except (OSError, PlaywrightError) as exc:
        report["error"] = str(exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        checkpoint()
    staff = build_report(report, args.pages)
    print(f"Saved: {args.staff_out}; summary: {staff['summary']}")
    return 0 if all(d["status"] == "success" for d in staff["departments"]) else 2


if __name__ == "__main__":
    sys.exit(main())
