"""Save BIZ directory pages and export personnel JSON, without visiting profiles.

From backend/ with .venv-homework activated:
    python scripts/fetch_biz_faculty.py
    python scripts/fetch_biz_faculty.py --department 4

Complete any website verification in the visible browser. Reparse saved HTML
offline with scripts/reparse_biz_staff_pages.py after changing the parser.
"""
import argparse
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from biz_staff_page import DIRECTORY_URL, directory_page, discover_departments, page_url, pagination, parse_biz_staff_page, soup_for
from reparse_biz_staff_pages import build_report, write_json
from fetch_faculty import BLOCK_TEXT, PageFailure, now


class BizLoader:
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
                soup = soup_for(html)
                text = soup.get_text(" ", strip=True)
                challenge = bool(BLOCK_TEXT.search(text)) or ("_Incapsula_Resource" in html and len(text) < 80)
                if not challenge and len(text) >= 80:
                    if directory_page(self.page.url, url) != directory_page(url, url):
                        raise PageFailure("redirected to a different department/page")
                    if response and response.status >= 400:
                        raise PageFailure(f"HTTP {response.status}")
                    if not soup.find("h1", string=lambda s: s and "Faculty Directory" in s):
                        # Nested h1 spans are allowed too.
                        if not any("Faculty Directory" in h.get_text() for h in soup.find_all("h1")):
                            raise PageFailure("not a faculty directory page")
                    return html, self.page.url
                if time.monotonic() >= deadline:
                    if self.interactive and challenge and sys.stdin.isatty():
                        answer = input("  Complete verification in browser, then Enter; s to skip: ").strip().lower()
                        if answer != "s":
                            response = None  # manual navigation may have replaced the response
                            deadline = time.monotonic() + 15
                            continue
                    raise PageFailure("verification blocked the page or page content is empty")
                self.page.wait_for_timeout(500)
        except Error as exc:
            raise PageFailure(str(exc).splitlines()[0]) from exc


def fetch_department(loader, dep, pages_dir, checkpoint, max_pages):
    pending, visited, fingerprints = {1}, set(), set()
    dep.update(status="pending", pages=[], pagination_complete=False)
    while pending:
        number = min(pending)
        pending.remove(number)
        url = page_url(dep["department_id"], number)
        entry = {"page": number, "requested_url": url, "status": "pending"}
        dep["pages"].append(entry)
        try:
            html, final_url = loader.load(url)
        except PageFailure as exc:
            entry.update(status="failed", error=str(exc))
            dep["status"] = "failed"
            checkpoint()
            return

        filename = f"{dep['code']}-page-{number}.html"
        (pages_dir / filename).write_text(html, encoding="utf-8")
        entry.update(url=final_url, html_file=filename, fetched_at=now())
        people, checks = parse_biz_staff_page(html, final_url, dep["department"])
        fingerprint = tuple(sorted(person["name"].casefold() for person in people))
        if fingerprint in fingerprints and people:
            checks["errors"].append("pagination returned the same people as an earlier page")
        fingerprints.add(fingerprint)
        entry.update(status="parse_failed" if checks["errors"] else "success", checks=checks)
        visited.add(number)
        # Inspect pagination even if parsing failed, but stop fetching on that failure.
        discovered = pagination(html, final_url, dep["department_id"])
        pending.update(set(discovered) - visited)
        if checks["errors"]:
            dep.update(status="parse_failed", pagination_complete=not pending)
            print("  Parse failed: " + "; ".join(checks["errors"]), flush=True)
            checkpoint()
            return
        if pending and max(pending) > max_pages:
            entry["checks"]["errors"].append(f"pagination exceeds safety limit {max_pages}")
            dep["status"] = "parse_failed"
            checkpoint()
            return
        if pending:
            pending.update(set(range(1, max(pending) + 1)) - visited)
        checkpoint()
    dep.update(status="success", pagination_complete=True)
    checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--department", action="append", default=[], help="department ID; repeat to select several")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/biz.json", help="crawl report")
    parser.add_argument("--staff-out", type=Path, default=BACKEND_DIR / "data/biz_staff.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/biz_staff_pages")
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--no-interaction", action="store_true")
    args = parser.parse_args()
    if args.delay < 0.5 or args.max_pages < 1:
        parser.error("--delay must be >= 0.5; --max-pages must be >= 1")
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    report = {"schema_version": 1, "source_url": DIRECTORY_URL, "started_at": now(), "completed": False, "departments": []}
    args.pages.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        write_json(args.out, report)
        write_json(args.staff_out, build_report(report, args.pages))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                loader = BizLoader(browser.new_page(), args.delay, not args.no_interaction)
                html, _ = loader.load(DIRECTORY_URL)
                (args.pages / "directory.html").write_text(html, encoding="utf-8")
                departments = discover_departments(html)
                if not departments:
                    raise PageFailure("no departments discovered; inspect directory.html")
                unknown = set(args.department) - {d["department_id"] for d in departments}
                if unknown:
                    raise PageFailure("unknown department IDs: " + ", ".join(sorted(unknown)))
                report["departments"] = [
                    {**d, "status": "pending", "pages": [], "pagination_complete": False}
                    for d in departments if not args.department or d["department_id"] in args.department
                ]
                checkpoint()
                for dep in report["departments"]:
                    print(dep["department"], flush=True)
                    fetch_department(loader, dep, args.pages, checkpoint, args.max_pages)
                report["completed"] = True
            finally:
                browser.close()
    except (KeyboardInterrupt, EOFError):
        print("Stopped; saved downloaded pages and partial JSON.", file=sys.stderr)
        return 130
    except (PageFailure, OSError, PlaywrightError) as exc:
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
