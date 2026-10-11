"""Run with python -m unittest discover -s scripts/tests (no database required)."""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from soc_staff_page import js_arrays, js_objects, js_string, parse_soc_staff_page
from fetch_soc_faculty import fetch_department
from fetch_faculty import PageFailure
from reparse_soc_staff_pages import build_report

URL = "https://www.comp.nus.edu.sg/disa/people/"


def record(name="Example PERSON", socid="example", **fields):
    values = {
        "name": name, "title": "Associate Professor", "email": '<img src=\\"https://x/secret.jpg\\">',
        "officetel": "COM3-01-01", "tel": "651 00000", "image": "https://www.comp.nus.edu.sg/photos/example.jpg",
        "socid": socid, "Bio": "/disa/people/example", "biolinkstat": "1", "ApptAdm": "",
        "researcharea": "<a href=\\\"\\\" ng-click=\\\"setFaculty('1','AI');\\\"><span>AI</span></a>, "
                        "<a href=\\\"\\\"><span>Security</span></a>",
        **fields,
    }
    body = ",\n".join(f'\t\t{key}: "{value}"' for key, value in values.items())
    return "{\n" + body + ",\n\t}"


def page(**groups):
    """A page like the real one: AngularJS templates, then the arrays in an inline script."""
    arrays = "\n".join(f"$scope.{group} = [\n{','.join(records)}\n\t];" for group, records in groups.items())
    return (
        "<html><body><div class='bbox'><b>{{i.name}}</b></div>"
        "<script>app.controller('FacController', function($scope) {\n"
        f"{arrays}\n$scope.staffs = $scope.allStaffs;\n}});</script></body></html>"
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


class SocTests(unittest.TestCase):
    def test_js_reading(self):
        self.assertEqual(js_string(r'say \"hi\"\nnext \'x\''), "say \"hi\"\nnext 'x'")
        # Brackets and braces inside strings must not end the array or the object
        text = 'x = 1; $scope.allStaffs = [{ name: "A ] }", title: "T" }, { name: "B" }]; $scope.other = [1];'
        arrays = js_arrays(text)
        self.assertEqual(set(arrays), {"allStaffs"})
        self.assertEqual(js_objects(arrays["allStaffs"]), [{"name": "A ] }", "title": "T"}, {"name": "B"}])

    def test_fields(self):
        people, checks = parse_soc_staff_page(page(allStaffs=[record(ApptAdm="Vice-Dean, Research\\nDirector, SBIP\\n")]), URL)
        self.assertEqual(checks["errors"], [])
        self.assertEqual(people, [{
            "name": "Example PERSON", "position": "Associate Professor",
            "roles": ["Vice-Dean, Research", "Director, SBIP"], "section": "Faculty",
            "research_areas": "AI, Security",
            "profile_urls": ["https://www.comp.nus.edu.sg/disa/people/example"],
            "photo_url": "https://www.comp.nus.edu.sg/photos/example.jpg", "bio": None,
        }])

    def test_no_contact_details_kept(self):
        people, _ = parse_soc_staff_page(page(allStaffs=[record()]), URL)
        text = repr(people)
        for secret in ("secret.jpg", "COM3-01-01", "651 00000"):
            self.assertNotIn(secret, text)

    def test_groups_sections_and_duplicates(self):
        teaching = '{ name: "Teacher ONE", title: "Lecturer", socid: "t1" }'
        html = page(
            allStaffs=[record("Prof A", "a"), record("Prof B", "b")],
            allStaffs_arealeader=[record("Prof A", "a")],
            allStaffs_research=[record("Research FELLOW", "r")],
            allStaffs_teaching=[teaching, record("Prof B", "b")],
        )
        people, checks = parse_soc_staff_page(html, URL)
        self.assertEqual(checks["errors"], [])
        self.assertEqual([(p["name"], p["section"]) for p in people],
                         [("Prof A", "Faculty"), ("Prof B", "Faculty"), ("Teacher ONE", "Teaching Staff")])
        self.assertEqual(people[2]["profile_urls"], [])
        self.assertIsNone(people[2]["photo_url"])

    def test_layout_change_is_an_error(self):
        _, checks = parse_soc_staff_page("<html><h3>FACULTY</h3>{{i.name}}</html>", URL)
        self.assertIn("no $scope.allStaffs array; the page layout may have changed", checks["errors"])

    def run_crawl(self, pages):
        dep = {"code": "soc-disa", "department": "Information Systems and Analytics",
               "faculty": "School of Computing", "url": URL, "status": "pending"}
        loader = FakeLoader(pages)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch_department(loader, dep, root, lambda: None)
            staff = build_report({"completed": True, "departments": [dep]}, root)
            saved = (root / dep["html_file"]).exists() if dep.get("html_file") else False
            return dep, staff, saved

    def test_crawl_and_reparse(self):
        dep, staff, saved = self.run_crawl({URL: page(allStaffs=[record()])})
        self.assertEqual(dep["status"], "success")
        self.assertTrue(saved)
        self.assertEqual(staff["summary"]["success"], 1)
        self.assertEqual(staff["departments"][0]["department"], "Information Systems and Analytics")
        self.assertEqual(len(staff["departments"][0]["people"]), 1)

    def test_parse_failure_keeps_html(self):
        dep, staff, saved = self.run_crawl({URL: "<html>{{i.name}}</html>"})
        self.assertEqual(dep["status"], "parse_failed")
        self.assertTrue(saved)
        self.assertEqual(staff["summary"]["parse_failed"], 1)

    def test_fetch_failure_is_distinct(self):
        dep, staff, saved = self.run_crawl({URL: PageFailure("HTTP 503")})
        self.assertEqual(dep["status"], "failed")
        self.assertFalse(saved)
        self.assertEqual(staff["summary"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
