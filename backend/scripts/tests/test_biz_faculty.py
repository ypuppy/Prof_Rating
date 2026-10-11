"""Run with python -m unittest discover -s scripts/tests (no database required)."""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from biz_staff_page import DIRECTORY_URL, department_name, directory_page, discover_departments, page_url, pagination, parse_biz_staff_page
from fetch_biz_faculty import fetch_department
from fetch_faculty import PageFailure
from reparse_biz_staff_pages import build_report


def card(name="Example Person", title="Head of Department<br>Associate Professor", profile=True):
    heading = f'<a href="https://discovery.nus.edu.sg/example">{name}<span class="sr-only">(opens in new tab)</span></a>' if profile else name
    return (
        '<article><div><img src="/photo.jpg"></div><div>'
        f'<h4>{heading}</h4><p>{title}</p><p>Accounting</p>'
        '<p>BIZ1 7-01</p><a href="mailto:example@nus.edu.sg">example@nus.edu.sg</a>'
        '<a href="/cv.pdf">Download CV</a></div></article>'
    )


class FakeLoader:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def load(self, url):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value, url


class BizTests(unittest.TestCase):
    def test_parse_fields_and_hidden_text_and_missing_profile(self):
        people, checks = parse_biz_staff_page(card(title="Head of Department<br>Associate <strong>Professor</strong>") + card("Other Person", "Lecturer", False), DIRECTORY_URL, "Accounting")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0]["name"], "Example Person")
        self.assertEqual(people[0]["position"], "Head of Department · Associate Professor")
        self.assertEqual(people[0]["roles"], [])
        self.assertEqual(people[0]["photo_url"], "https://bizfaculty.nus.edu.sg/photo.jpg")
        self.assertEqual(people[0]["profile_urls"], ["https://discovery.nus.edu.sg/example"])
        self.assertEqual(people[1]["profile_urls"], [])
        self.assertIsNone(people[0]["research_areas"])

    def test_discovery_and_pagination_do_not_mix_filters(self):
        html = '''<a href="?dept=1">Accounting<span class="sr-only">opens in new tab</span></a>
        <a href="?dept=14">Real Estate</a><a href="?dept=1">all</a>
        <a href="/faculty-directory/page/2/?dept=1">2</a>
        <a href="/faculty-directory/page/3/?dept=14">3</a>
        <a href="/faculty-directory/page/4/?dept=1&letter=a">4</a>
        <a href="https://other.example/faculty-directory/page/5/?dept=1">5</a>'''
        departments = discover_departments(html)
        self.assertEqual([d["department_id"] for d in departments], ["1", "14"])
        self.assertEqual(departments[0]["department"], "Accounting")
        self.assertEqual(pagination(html, page_url("1"), "1"), [1, 2])

    def test_department_names_match_reference_data(self):
        self.assertEqual(department_name("Management & Organisation"), "Management and Organisation")
        self.assertEqual(department_name("Accounting"), "Accounting")
        _, _, staff = self.run_crawl({page_url("1"): card()})
        self.assertEqual(staff["departments"][0]["department"], "Accounting")

    def test_export_uses_reference_name_but_matches_site_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.html").write_text(card().replace("<p>Accounting</p>", "<p>Strategy &amp; Policy</p>"), encoding="utf-8")
            dep = {"code": "biz-6", "department": "Strategy & Policy", "faculty": "NUS Business School",
                   "url": page_url("6"), "status": "success", "pagination_complete": True,
                   "pages": [{"url": page_url("6"), "html_file": "one.html"}]}
            report = build_report({"completed": True, "departments": [dep]}, root)
            self.assertEqual(report["departments"][0]["department"], "Strategy and Policy")
            self.assertEqual(len(report["departments"][0]["people"]), 1)

    def run_crawl(self, pages):
        dep = {"code": "biz-1", "department_id": "1", "department": "Accounting", "faculty": "NUS Business School", "url": page_url("1")}
        loader = FakeLoader(pages)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch_department(loader, dep, root, lambda: None, 100)
            staff = build_report({"completed": True, "departments": [dep]}, root)
            return dep, loader.calls, staff

    def test_query_pagination_and_invalid_parameters(self):
        self.assertEqual(directory_page("?dept=4&paged=2", DIRECTORY_URL), ("4", 2))
        self.assertEqual(directory_page("/faculty-directory/page/2/?dept=4", DIRECTORY_URL), ("4", 2))
        self.assertEqual(page_url("4", 2), DIRECTORY_URL + "?dept=4&paged=2")
        for raw in ("?dept=4&paged=0", "?dept=4&paged=x", "?dept=4&paged=2&paged=3",
                    "?dept=4&paged=2&letter=a", "/faculty-directory/page/2/?dept=4&paged=3"):
            with self.subTest(raw=raw):
                self.assertIsNone(directory_page(raw, DIRECTORY_URL))

    def test_query_links_fetch_second_page(self):
        dep, calls, staff = self.run_crawl({
            page_url("1"): card("One") + '<a class="page-numbers" href="/faculty-directory/?dept=1&amp;paged=2">2</a>',
            page_url("1", 2): card("Two"),
        })
        self.assertEqual(calls, [page_url("1"), page_url("1", 2)])
        self.assertTrue(dep["pagination_complete"])
        self.assertEqual(len(staff["departments"][0]["people"]), 2)

    def test_offline_reparse_rejects_old_false_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.html").write_text(card() + '<a href="?dept=1&amp;paged=2">2</a>', encoding="utf-8")
            dep = {"code": "biz-1", "department": "Accounting", "faculty": "NUS Business School",
                   "url": page_url("1"), "status": "success", "pagination_complete": True,
                   "pages": [{"url": page_url("1"), "html_file": "one.html"}]}
            report = build_report({"completed": True, "departments": [dep]}, root)
            self.assertEqual(report["summary"]["parse_failed"], 1)
            self.assertIn("linked pages have no saved HTML: 2", report["departments"][0]["checks"]["errors"])

    def test_all_pages_including_gap_and_offline_reparse(self):
        dep, calls, staff = self.run_crawl({
            page_url("1"): card("One") + '<a href="/faculty-directory/page/3/?dept=1">3</a>',
            page_url("1", 2): card("Two"), page_url("1", 3): card("Three"),
        })
        self.assertEqual(calls, [page_url("1", n) for n in (1, 2, 3)])
        self.assertTrue(dep["pagination_complete"])
        self.assertEqual(staff["summary"]["success"], 1)
        self.assertEqual(len(staff["departments"][0]["people"]), 3)

    def test_parse_failure_stops_requests_and_saves_html(self):
        dep, calls, staff = self.run_crawl({
            page_url("1"): '<h4>Unrecognised layout</h4><a href="/faculty-directory/page/2/?dept=1">2</a>',
        })
        self.assertEqual(calls, [page_url("1")])
        self.assertEqual(dep["status"], "parse_failed")
        self.assertIn("html_file", dep["pages"][0])
        self.assertFalse(dep["pagination_complete"])
        self.assertEqual(staff["summary"]["parse_failed"], 1)

    def test_repeated_page_not_reported_as_complete(self):
        dep, calls, staff = self.run_crawl({
            page_url("1"): card() + '<a href="/faculty-directory/page/2/?dept=1">2</a>',
            page_url("1", 2): card(),
        })
        self.assertEqual(dep["status"], "parse_failed")
        self.assertEqual(staff["summary"]["parse_failed"], 1)
        self.assertEqual(len(staff["departments"][0]["people"]), 1)

    def test_fetch_failure_is_distinct(self):
        dep, calls, staff = self.run_crawl({page_url("1"): PageFailure("HTTP 503")})
        self.assertEqual(dep["status"], "failed")
        self.assertEqual(staff["summary"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
