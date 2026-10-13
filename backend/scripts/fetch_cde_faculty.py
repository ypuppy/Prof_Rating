"""Save configured CDE staff pages and export personnel without visiting profiles.

From backend/ with .venv-homework activated:
    python scripts/fetch_cde_faculty.py --department me
    python scripts/fetch_cde_faculty.py

Complete any verification in the visible browser. After changing the parser:
    python scripts/reparse_cde_staff_pages.py
"""
import argparse
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from cde_staff_page import BASE, FACULTY, SOURCE, PaginationError, page_key, pagination, parse_cde_staff_page, scope_key
from fetch_faculty import PageFailure, blocked, now, snapshot_html
from reparse_cde_staff_pages import build_report, departments_succeeded, write_json


class CdeLoader:
    def __init__(self, page, delay=2, interactive=True):
        self.page, self.delay, self.interactive = page, delay, interactive
        self.last_request = 0

    def load(self, url, code):
        from playwright.sync_api import Error
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        print(f"  Visit: {url}", flush=True)
        try:
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            deadline = time.monotonic() + 15
            while True:
                html, final_url = self.page.content(), self.page.url
                snapshot = snapshot_html(html, final_url)
                challenge = blocked(snapshot)
                if not challenge and len(snapshot["text"]) >= 80:
                    parts = urlsplit(final_url)
                    if parts.hostname != "cde.nus.edu.sg" or not parts.path.startswith(f"/{code}/"):
                        raise PageFailure("redirected outside the department")
                    if response and response.status >= 400:
                        raise PageFailure(f"HTTP {response.status}")
                    return html, final_url
                if time.monotonic() >= deadline:
                    if challenge and self.interactive and sys.stdin.isatty():
                        answer = input("  请在浏览器完成验证，然后按 Enter；s 跳过：").strip().lower()
                        if answer != "s":
                            response = None
                            deadline = time.monotonic() + 15
                            continue
                    raise PageFailure("verification blocked the page or content is empty")
                self.page.wait_for_timeout(500)
        except Error as exc:
            raise PageFailure(str(exc).splitlines()[0]) from exc


def fetch_department(loader, dep, pages_dir, checkpoint, max_pages=100):
    pending, visited, fingerprints = deque(dep["urls"]), set(), set()
    dep.update(status="pending", pages=[], pagination_complete=False)
    while pending:
        url = pending.popleft()
        requested_key = page_key(url)
        if requested_key in visited:
            continue
        if len(dep["pages"]) >= max_pages:
            dep.update(status="failed", error=f"exceeded page limit {max_pages}")
            checkpoint()
            return
        entry = {"requested_url": url, "status": "pending"}
        dep["pages"].append(entry)
        try:
            html, final_url = loader.load(url, dep["code"])
        except PageFailure as exc:
            entry.update(status="failed", error=str(exc))
            dep["status"] = "failed"
            checkpoint()
            return
        filename = f"{dep['code']}-{len(dep['pages']):03d}.html"
        (pages_dir / filename).write_text(html, encoding="utf-8")
        entry.update(url=final_url, html_file=filename, fetched_at=now())
        people, checks = parse_cde_staff_page(html, final_url)
        try:
            actual_key = page_key(final_url)
            default_category_added = requested_key[:3] == actual_key[:3] and not requested_key[3]
            if actual_key in visited or (actual_key != requested_key and not default_category_added):
                raise PaginationError("redirected to a different/previous page or filter")
            next_urls = pagination(html, final_url)
            fingerprint = (scope_key(final_url), tuple(sorted(p["name"].casefold() for p in people)))
            if people and fingerprint in fingerprints:
                raise PaginationError("pagination returned the same people as an earlier page")
            fingerprints.add(fingerprint)
        except PaginationError as exc:
            checks["errors"].append(str(exc))
            entry["error"] = str(exc)
            next_urls = []
        entry.update(checks=checks, pagination_urls=next_urls,
                     status="parse_failed" if checks["errors"] else "success")
        if checks["errors"]:
            dep["status"] = "parse_failed"
            print("  Parse failed: " + "; ".join(checks["errors"]), flush=True)
            checkpoint()
            return
        visited.update({requested_key, actual_key})
        for next_url in next_urls:
            if page_key(next_url) not in visited:
                pending.append(next_url)
        print(f"  {len(people)} people; layout={checks['layout']}", flush=True)
        checkpoint()
    dep.update(status="success", pagination_complete=True)
    checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--department", action="append", default=[], choices=[d["code"] for d in SOURCE])
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "data/cde.json")
    parser.add_argument("--staff-out", type=Path, default=BACKEND_DIR / "data/cde_staff.json")
    parser.add_argument("--pages", type=Path, default=BACKEND_DIR / "data/cde_staff_pages")
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--no-interaction", action="store_true")
    args = parser.parse_args()
    if args.delay < 0.5 or args.max_pages < 1:
        parser.error("--delay must be >= 0.5; --max-pages must be >= 1")
    from playwright.sync_api import sync_playwright, Error
    report = {
        "schema_version": 1, "source_url": BASE + "/about-us/", "started_at": now(), "completed": False,
        "departments": [{**d, "faculty": FACULTY, "status": "pending", "pages": []}
                        for d in SOURCE if not args.department or d["code"] in args.department],
    }
    args.pages.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        write_json(args.out, report)
        write_json(args.staff_out, build_report(report, args.pages))

    try:
        checkpoint()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                loader = CdeLoader(browser.new_page(), args.delay, not args.no_interaction)
                for dep in report["departments"]:
                    print(dep["department"], flush=True)
                    fetch_department(loader, dep, args.pages, checkpoint, args.max_pages)
                report["completed"] = True
            finally:
                browser.close()
    except (KeyboardInterrupt, EOFError):
        print("Stopped; downloaded HTML and partial JSON are saved.", file=sys.stderr)
        return 130
    except (PageFailure, PaginationError, Error, OSError) as exc:
        report["error"] = str(exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        checkpoint()
    staff = build_report(report, args.pages)
    print(f"Saved: {args.staff_out}; summary: {staff['summary']}")
    return 0 if departments_succeeded(staff) else 2


if __name__ == "__main__":
    sys.exit(main())
