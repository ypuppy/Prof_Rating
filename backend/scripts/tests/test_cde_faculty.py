"""CDE-only offline checks; no database or website required."""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from cde_staff_page import BASE, SOURCE, PaginationError, page_key, pagination, parse_cde_staff_page
from fetch_cde_faculty import fetch_department
from fetch_faculty import PageFailure
from reparse_cde_staff_pages import build_report

URL = BASE + "/me/about-us/people/academic-staff/"


def card(name="Anna EXAMPLE", title="Deputy Head", designation="Associate Professor", division="Fluid Mechanics"):
    """A real ME card (.ws-people-content), trimmed from me-001.html."""
    profile = "/me/staff/anna/"
    return (
        '<div class="ws-people-content"><div class="content-image">'
        f'<a href="{profile}"><div class="people-image"><img src="/anna.jpg"></div></a></div>'
        '<div class="content-texts">'
        f'<div class="content-name"><a href="{profile}"><h3>{name}</h3></a></div>'
        f'<div class="content-title"><a href="{profile}"><h5>{title}</h5></a></div>'
        f'<div class="content-designation"><a href="{profile}"><h5>{designation}</h5></a></div>'
        f'<div class="content-department"><a href="{profile}"><h5>{division}</h5></a></div>'
        '<div class="content-email"><a href="mailto:anna@nus.edu.sg"><h5>anna@nus.edu.sg</h5></a></div>'
        '<div class="content-website"></div></div></div>'
    )


def arch_card(name="Anna EXAMPLE (Dr)", title="Associate Professor|Deputy Head (Tenure Track)", slug="anna"):
    """A real Architecture card (.profile-wrapper), trimmed from arch-001.html."""
    profile = f"https://cde.nus.edu.sg/arch/staffs/{slug}/"
    return (
        '<div class="col-6 col-md-4 col-lg-3 shuffle-item mb-5 profile-wrapper">'
        f'<div class="profile-img"><a class="rounded-circle" href="{profile}"><img class="img-fluid" src="/arch/{slug}.jpg"></a></div>'
        f'<a href="{profile}"><div class="profile-name mt-3">{name}</div>'
        f'<div class="profile-title text-uppercase">{title}</div><div class="arrow sm"></div></a></div>'
    )


def dbe_column(name="CHEW YIT LIN, MICHAEL", title="Professor", email="bdgchewm@nus.edu.sg",
               profile="https://blog.nus.edu.sg/chewm/", extra=""):
    """A real DBE person column (Beaver Builder .fl-col), trimmed from dbe-001.html."""
    heading = '<h2 class="fl-module fl-module-heading fl-heading fl-heading-text">{}</h2>'
    return (
        '<div class="fl-col fl-col-small"><div class="fl-col-content">'
        '<figure class="fl-module fl-module-photo"><img src="/dbe/photo.jpg"></figure>'
        + heading.format(name) + heading.format(title)
        + heading.format(f'<a href="mailto:{email}">{email}</a>') + extra
        + f'<div class="fl-module-uabb-button"><a class="uabb-button" href="{profile}" title="Profile">Profile</a></div>'
        '</div></div>'
    )


def dbe_page(faculty, research):
    return (f'<div class="fl-col"><h2 class="fl-heading">Faculty, Adjunct &amp; Research</h2></div>'
            f'<h3>Faculty</h3>{faculty}<h3>Research Staff</h3>{research}')


class Loader:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def load(self, url, code):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value, url


class CdeTests(unittest.TestCase):
    def test_source_has_ten_departments(self):
        self.assertEqual(len(SOURCE), 10)
        self.assertEqual(len({s["code"] for s in SOURCE}), 10)

    def test_ws_people_card_fields(self):
        people, checks = parse_cde_staff_page(card(), URL)
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "ws-people")
        self.assertEqual(people, [{
            "name": "Anna EXAMPLE", "position": "Deputy Head · Associate Professor", "roles": [],
            "section": "Fluid Mechanics", "research_areas": None,
            "profile_urls": [BASE + "/me/staff/anna/"], "photo_url": BASE + "/anna.jpg", "bio": None,
        }])
        self.assertNotIn("anna@nus.edu.sg", repr(people))

    def test_multi_word_divisions_and_titles_do_not_hide_people(self):
        # The old name-block parser skipped these cards: "Fluid Mechanics" and "Deputy Head (Research)"
        # looked like a second name, so the card was never found and nothing was reported
        html = card("One PERSON", "Deputy Head (Research)", "Professor", "Control & Mechatronics") + card("Two PERSON")
        people, checks = parse_cde_staff_page(html, URL)
        self.assertEqual(checks["errors"], [])
        self.assertEqual([p["name"] for p in people], ["One PERSON", "Two PERSON"])

    def test_architecture_cards(self):
        html = (arch_card() + arch_card("Shin EGASHIRA", "OSM Visiting Professor", "shin")
                + arch_card("T.K.SABAPATHY", "Adjunct Professor", "tk") + arch_card("Ires CHENG", "Secretary", "ires"))
        people, checks = parse_cde_staff_page(html, BASE + "/arch/staff/")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "profile-wrapper")
        self.assertEqual((checks["card_count"], checks["count"], checks["excluded_count"]), (4, 3, 1))
        anna, shin, tk = people
        self.assertEqual(anna["name"], "Anna EXAMPLE")
        self.assertEqual(anna["position"], "Associate Professor · Deputy Head (Tenure Track)")
        self.assertEqual(anna["profile_urls"], [BASE + "/arch/staffs/anna/"])
        self.assertEqual(anna["photo_url"], BASE + "/arch/anna.jpg")
        self.assertEqual((shin["name"], shin["position"]), ("Shin EGASHIRA", "OSM Visiting Professor"))
        self.assertEqual(tk["name"], "T.K.SABAPATHY")

    def test_dbe_heading_columns(self):
        html = dbe_page(
            dbe_column() + dbe_column("ANG YU QIAN", "Assistant Professor (Presidential Young Professor)",
                                      "bdgyqa@nus.edu.sg", "http://bdgyqa@nus.edu.sg",
                                      '<h2 class="fl-heading">Profile Updating</h2>'),
            dbe_column("Cen Chao", "Research Fellow", "dbe.cenc@nus.edu.sg"),
        )
        people, checks = parse_cde_staff_page(html, BASE + "/dbe/about-us/faculty-research-2/")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "heading-columns")
        self.assertEqual((checks["card_count"], checks["count"], checks["excluded_count"]), (3, 2, 1))
        chew, ang = people
        self.assertEqual((chew["name"], chew["position"], chew["section"]), ("CHEW YIT LIN, MICHAEL", "Professor", "Faculty"))
        self.assertEqual(chew["profile_urls"], ["https://blog.nus.edu.sg/chewm/"])
        self.assertEqual(chew["photo_url"], BASE + "/dbe/photo.jpg")
        # "Profile Updating" after the email is not a title; an email typed as a link is not a profile
        self.assertEqual(ang["position"], "Assistant Professor (Presidential Young Professor)")
        self.assertEqual(ang["profile_urls"], [])
        self.assertNotIn("@", repr(people))

    def test_design_name_table(self):
        html = ('<h3>Part-time Faculty</h3><table><tr><th>Name</th><th>Staff Title</th><th>Email Address</th></tr>'
                '<tr><td>Celia Wong (Ms)</td><td>Part-time Lecturer</td><td><a href="mailto:c@nus.edu.sg">c@nus.edu.sg</a></td></tr>'
                '<tr><td colspan="3">Group label</td></tr>'
                '<tr><td>Ryan Ho Yaowei (Mr)</td><td>Part-time Tutor</td><td>r@nus.edu.sg</td></tr></table>')
        people, checks = parse_cde_staff_page(html, BASE + "/dd/part-time/")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "name-table")
        self.assertEqual([(p["name"], p["position"], p["section"]) for p in people],
                         [("Celia Wong", "Part-time Lecturer", "Part-time Faculty"),
                          ("Ryan Ho Yaowei", "Part-time Tutor", "Part-time Faculty")])
        self.assertNotIn("@", repr(people))

    def test_isem_rank_tables_with_plural_headings(self):
        row = '<tr><td><img src="/isem/{0}.png"></td><td>{1}</td><td>Systems Engineering<br>Project Management</td></tr>'
        html = (f'<h3>Adjunct Professors</h3><h3></h3><table>{row.format("lui", "LUI Pao Chuen")}</table>'
                f'<h3>Adjunct Senior Lecturer</h3><table>{row.format("yap", "YAP Chee Meng")}</table>')
        people, checks = parse_cde_staff_page(html, BASE + "/isem/about-us/people/adjunct-staff/")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "rank-tables")
        lui, yap = people
        self.assertEqual((lui["name"], lui["position"], lui["section"]), ("LUI Pao Chuen", "Adjunct Professor", "Adjunct Professors"))
        self.assertEqual(lui["research_areas"], "Systems Engineering, Project Management")
        self.assertEqual(lui["photo_url"], BASE + "/isem/lui.png")
        self.assertEqual(yap["position"], "Adjunct Senior Lecturer")

    def test_isem_person_cells(self):
        cell = ('<td><img src="/isem/{0}.jpg"><p></p><h3><strong>{1}</strong></h3>'
                '<p><a href="mailto:{0}@nus.edu.sg" title="Email me">Email</a></p><p><strong>Teaching Assistant</strong></p></td>')
        html = (f'<h2>Teaching Support Staff</h2><table><tr>{cell.format("chd", "CHEN Hongdan")}'
                f'{cell.format("steve", "Steve YEO Keng Swee")}</tr><tr>{cell.format("lz", "ZHANG Licheng")}<td></td></tr></table>')
        people, checks = parse_cde_staff_page(html, BASE + "/isem/about-us/people/teaching-support-staff/")
        self.assertEqual(checks["errors"], [])
        self.assertEqual(checks["layout"], "person-cells")
        self.assertEqual([(p["name"], p["position"], p["section"]) for p in people],
                         [("CHEN Hongdan", "Teaching Assistant", "Teaching Support Staff"),
                          ("Steve YEO Keng Swee", "Teaching Assistant", "Teaching Support Staff"),
                          ("ZHANG Licheng", "Teaching Assistant", "Teaching Support Staff")])
        self.assertEqual(people[0]["photo_url"], BASE + "/isem/chd.jpg")
        self.assertNotIn("@", repr(people))

    def test_leadership_only_titles_kept_on_academic_lists(self):
        # Academic-staff pages: a card showing only "Head of Department" is still faculty.
        # Only Architecture's page, which also lists admin staff, filters by title.
        people, checks = parse_cde_staff_page(card("Dr LIM Chwee Teck", "Head of Department", ""), URL)
        self.assertEqual(checks["errors"], [])
        self.assertEqual([(p["name"], p["position"]) for p in people], [("LIM Chwee Teck", "Head of Department")])
        people, checks = parse_cde_staff_page(arch_card("Chrislyn LIM", "Associate Director"), BASE + "/arch/staff/")
        self.assertEqual((people, checks["excluded_count"]), ([], 1))

    def test_unknown_layout_and_nameless_card_are_errors(self):
        _, checks = parse_cde_staff_page('<main><h2>Academic Staff</h2><h3>Anna EXAMPLE</h3></main>', URL)
        self.assertEqual(checks["layout"], "unknown")
        self.assertTrue(any("unknown layout" in e for e in checks["errors"]))
        _, checks = parse_cde_staff_page(card() + card(name=""), URL)
        self.assertIn("a staff card has no name", checks["errors"])
        _, checks = parse_cde_staff_page(card() + arch_card(), URL)
        self.assertEqual(checks["layout"], "ambiguous")

    def test_pagination_preserves_query_and_deduplicates_formats(self):
        current = BASE + '/chbe/about-us/people/?category=tenure-track'
        html = '''<a class="page-numbers" href="?category=tenure-track&amp;paged=2&amp;search=&amp;sort=ASC">2</a>
          <a class="page-numbers" href="/chbe/about-us/people/page/2/?category=tenure-track">2</a>
          <a href="?category=educators">Educators</a>'''
        links = pagination(html, current)
        self.assertEqual(len(links), 1)
        self.assertIn("category=tenure-track", links[0])
        self.assertEqual(page_key(links[0]), page_key(BASE + '/chbe/about-us/people/page/2/?category=tenure-track'))
        with self.assertRaises(PaginationError):
            pagination('<a class="page-numbers" href="?paged=2">2</a>', current)

    def run_crawl(self, pages, urls=None):
        dep = {"code": "me", "department": "Mechanical Engineering", "urls": urls or [URL]}
        loader = Loader(pages)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch_department(loader, dep, root, lambda: None)
            report = build_report({"completed": True, "departments": [dep]}, root)
            return dep, loader.calls, report

    def test_fetches_next_page_and_reparses_offline(self):
        dep, calls, report = self.run_crawl({URL: card() + '<a class="page-numbers" href="?paged=2">2</a>', URL + '?paged=2': card("Ben EXAMPLE")})
        self.assertEqual(calls, [URL, URL + '?paged=2'])
        self.assertTrue(dep["pagination_complete"])
        self.assertEqual(report["summary"]["success"], 1)
        self.assertEqual(len(report["departments"][0]["people"]), 2)

    def test_parse_failure_stops_requests_and_retains_html(self):
        dep, calls, report = self.run_crawl({URL: '<main>Unknown layout</main>'}, [URL, URL + '?category=other'])
        self.assertEqual(calls, [URL])
        self.assertEqual(dep["status"], "parse_failed")
        self.assertIn("html_file", dep["pages"][0])
        self.assertEqual(report["summary"]["parse_failed"], 1)

    def test_duplicate_pagination_fails_but_categories_merge(self):
        dep, _, report = self.run_crawl({URL: card() + '<a class="page-numbers" href="?paged=2">2</a>', URL + '?paged=2': card()})
        self.assertEqual(dep["status"], "parse_failed")
        self.assertEqual(report["summary"]["parse_failed"], 1)
        other = URL + '?category=adjunct'
        dep, _, report = self.run_crawl({URL: card(), other: card()}, [URL, other])
        self.assertEqual(report["summary"]["success"], 1)
        self.assertEqual(len(report["departments"][0]["people"]), 1)

    def test_missing_next_page_cannot_pass_offline_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'me.html').write_text(card() + '<a class="page-numbers" href="?paged=2">2</a>', encoding='utf-8')
            dep = {"code": "me", "department": "Mechanical Engineering", "urls": [URL], "status": "success",
                   "pagination_complete": True, "pages": [{"requested_url": URL, "url": URL, "html_file": "me.html"}]}
            report = build_report({"completed": True, "departments": [dep]}, root)
            self.assertEqual(report["summary"]["parse_failed"], 1)

    def test_fetch_failure_is_not_a_parse_failure(self):
        dep, _, report = self.run_crawl({URL: PageFailure("HTTP 503")})
        self.assertEqual(dep["status"], "failed")
        self.assertEqual(report["summary"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
