"""Parser tests on a small page that mimics the FASS layout, including the awkward bits of the real one."""
from staff_page import parse_staff_page

BASE = "https://fass.nus.edu.sg/philo/faculty/"


def person_column(name, title, rich_text="", bio=None):
    accordion = (
        f'<div class="fl-module fl-module-accordion"><div class="fl-accordion-content"><table><tr>'
        f'<td>Brief Introduction</td><td>{bio}</td></tr></table></div></div>' if bio else ""
    )
    return (
        f'<div class="fl-module fl-module-heading"><h4 class="fl-heading"><span class="fl-heading-text">{name}</span></h4></div>'
        f'<div class="fl-module fl-module-heading"><h5 class="fl-heading"><span class="fl-heading-text">{title}</span></h5></div>'
        f'<div class="fl-module fl-module-rich-text"><div class="fl-rich-text">{rich_text}</div></div>'
        + accordion
    )


def photo(src):
    return f'<div class="fl-module fl-module-photo"><img class="fl-photo-img" src="{src}"></div>'


def group(photos, people_html):
    return (
        '<div class="fl-col-group fl-col-group-nested">'
        f'<div class="fl-col"><div class="fl-col-content">{photos}</div></div>'
        f'<div class="fl-col"><div class="fl-col-content">{people_html}</div></div>'
        '</div>'
    )


PAGE = (
    '<h3 class="fl-heading"><span class="fl-heading-text">Main Faculty</span></h3>'
    + group(
        photo("/philo/wp-content/qu.jpg"),
        person_column(
            "QU Hsueh Ming", "Professor<br>Head of Department<br>",
            '<p><strong>Profile page:</strong> <a href="https://discovery.nus.edu.sg/5305">https://discovery.nus.edu.sg/5305</a>'
            # invisible leftover link: only screen-reader text inside
            '<a class="orange-link" href="http://nus.academia.edu/SomeoneElse"><span class="sr-only">(opens in new tab)</span></a></p>'
            # a word split across spans, and a second label in the same paragraph
            '<p><strong>Research Areas: </strong><span>L</span><span>ogic, Kant</span> Teaching Areas: Ethics</p>',
            bio="Joined NUS in 2015.",
        ),
    )
    + '<h3 class="fl-heading"><span class="fl-heading-text">Courtesy Joint Appointments</span></h3>'
    # three people listed in one column, photos in the neighbouring column
    + group(
        photo("/a.jpg") + photo("/b.jpg") + photo("/c.jpg"),
        person_column("Anna ALPHA", "Lecturer<br>NUS College",
                      '<p><a href="http://5.\thttps://discovery.nus.edu.sg/1-anna">link</a></p>')
        + person_column("Ben BETA", "Senior Lecturer")
        + person_column("Cara GAMMA", "Lecturer", "<p><strong>Research Areas:&nbsp;</strong></p>"),
    )
    # someone with no photo at all
    + group("", person_column("Dan DELTA", "Research Fellow"))
)


def by_name():
    return {p["name"]: p for p in parse_staff_page(PAGE, BASE)}


def test_finds_everyone_with_their_section():
    people = by_name()
    assert list(people) == ["QU Hsueh Ming", "Anna ALPHA", "Ben BETA", "Cara GAMMA", "Dan DELTA"]
    assert people["QU Hsueh Ming"]["section"] == "Main Faculty"
    assert people["Ben BETA"]["section"] == "Courtesy Joint Appointments"


def test_title_lines_split_into_position_and_roles():
    qu = by_name()["QU Hsueh Ming"]
    assert (qu["position"], qu["roles"]) == ("Professor", ["Head of Department"])


def test_research_areas_rejoin_split_words_and_stop_at_next_label():
    people = by_name()
    assert people["QU Hsueh Ming"]["research_areas"] == "Logic, Kant"
    assert people["Cara GAMMA"]["research_areas"] is None  # label with nothing after it


def test_links_skip_invisible_and_salvage_malformed():
    people = by_name()
    assert people["QU Hsueh Ming"]["profile_urls"] == ["https://discovery.nus.edu.sg/5305"]
    assert people["Anna ALPHA"]["profile_urls"] == ["https://discovery.nus.edu.sg/1-anna"]


def test_photos_match_by_position_and_resolve_relative_urls():
    people = by_name()
    assert people["QU Hsueh Ming"]["photo_url"] == "https://fass.nus.edu.sg/philo/wp-content/qu.jpg"
    assert [people[n]["photo_url"] for n in ("Anna ALPHA", "Ben BETA", "Cara GAMMA")] == [
        "https://fass.nus.edu.sg/a.jpg", "https://fass.nus.edu.sg/b.jpg", "https://fass.nus.edu.sg/c.jpg",
    ]
    assert people["Dan DELTA"]["photo_url"] is None


def test_bio_only_when_present():
    people = by_name()
    assert people["QU Hsueh Ming"]["bio"] == "Joined NUS in 2015."
    assert people["Ben BETA"]["bio"] is None


def test_page_without_people_returns_empty_list():
    assert parse_staff_page("<html><body>Additional security check is required</body></html>", BASE) == []


# ---------- other FASS layouts ----------

from staff_page import detect_layout  # noqa: E402


def wrap(inner):
    """Page chrome around the content, so nav/footer text can't leak into results."""
    return (
        '<html><body><nav><a href="/x">Menu</a><h4 class="fl-heading">Not a person</h4></nav>'
        f'<div class="fl-builder-content fl-builder-content-primary">{inner}</div>'
        '<footer><p><a href="https://nus.edu.sg">NUS</a></p></footer></body></html>'
    )


def card(name, designation, href, img):
    return (
        '<div class="fl-col people-listing-block"><div class="people-profile-block">'
        f'<a href="{href}"><div class="people-image"><img src="{img}"></div><br>'
        f'<div class="people-name">{name}</div><div class="people-designation">{designation}</div>'
        '<div class="people-tel">6516-0000</div></a>'
        '<div class="people-email"><a href="mailto:x@nus.edu.sg">Email</a></div></div></div>'
    )


CARDS = wrap(
    '<h2 class="fl-heading">Full-Time Faculty</h2>'
    + card("CHAN Cheow Thia 曾昭程", "Assistant Professor | Assistant Head", "/cs/people/chan/", "/c.jpg")
    + card("BILVEER SINGH (Deputy Head of Department)", "Associate Professor", "/pol/people/b/", "/b.jpg")
    + '<h2 class="fl-heading">Adjunct and Courtesy Faculty</h2>'
    + card("Au, Kin-Chung Al", "Adjunct Lecturer", "/psy/people/au/", "/a.jpg")
)


def test_cards_layout():
    assert detect_layout(CARDS) == "cards"
    people = {p["name"]: p for p in parse_staff_page(CARDS, BASE)}
    assert list(people) == ["CHAN Cheow Thia 曾昭程", "BILVEER SINGH", "Au, Kin-Chung Al"]
    chan = people["CHAN Cheow Thia 曾昭程"]
    assert (chan["position"], chan["roles"]) == ("Assistant Professor", ["Assistant Head"])
    assert chan["profile_urls"] == ["https://fass.nus.edu.sg/cs/people/chan/"]
    assert chan["photo_url"] == "https://fass.nus.edu.sg/c.jpg"
    assert people["BILVEER SINGH"]["roles"] == ["Deputy Head of Department"]  # moved out of the name
    assert people["Au, Kin-Chung Al"]["section"] == "Adjunct and Courtesy Faculty"
    # phone and email are on the page but not kept
    assert all("6516" not in str(p) and "mailto" not in str(p) for p in people.values())


def photo_col(img_href, name_html, titles_html):
    return (
        '<div class="fl-col"><div class="fl-col-content">'
        f'<div class="fl-module fl-module-photo"><a href="{img_href}"><img src="/p.png">'
        '<span class="sr-only">(opens in new tab)</span></a></div>'
        f'<div class="fl-module fl-module-rich-text"><div class="fl-rich-text"><p>{name_html}<br>{titles_html}'
        '<br>Email: <a href="mailto:a@nus.edu.sg">a@nus.edu.sg</a></p></div></div></div></div>'
    )


PHOTO_COLUMNS = wrap(
    photo_col("/swk/people/lee/", "<b>Lee Geok Ling</b>", "Associate Professor,<br>Head of Department")
    + photo_col("/swk/people/ghoh/", '<b><a href="/swk/people/ghoh/">Corinne</a> Ghoh</b>', "Associate Professor")
    + '<div class="fl-col"><div class="fl-module fl-module-rich-text"><div class="fl-rich-text">'
      '<p>ADJUNCT FACULTY</p></div></div></div>'
    + photo_col("/swk/people/tan/", "<strong>Tan Ah Kow</strong>", "Adjunct Lecturer")
)


def test_photo_columns_layout():
    assert detect_layout(PHOTO_COLUMNS) == "photo_columns"
    people = parse_staff_page(PHOTO_COLUMNS, BASE)
    assert [p["name"] for p in people] == ["Lee Geok Ling", "Corinne Ghoh", "Tan Ah Kow"]
    assert (people[0]["position"], people[0]["roles"]) == ("Associate Professor", ["Head of Department"])
    assert people[0]["profile_urls"] == ["https://fass.nus.edu.sg/swk/people/lee/"]  # link around the photo
    assert [p["section"] for p in people] == ["Faculty", "Faculty", "ADJUNCT FACULTY"]


TABLE = wrap(
    '<table><tr><td>Position</td><td>Name</td><td>Profile/Email</td><td>Convenor/Coordinator</td></tr>'
    '<tr><td>Arabic</td></tr>'
    '<tr><td>Senior Lecturer</td><td>Dr Salawdeh, K.O. Omar</td>'
    '<td><a href="https://discovery.nus.edu.sg/3719"></a> <a href="mailto:o@nus.edu.sg"></a></td>'
    '<td>Coordinator, LAR2201</td></tr>'
    '<tr><td>Chinese</td></tr>'
    '<tr><td>Lecturer</td><td>Ms Lim Mei</td><td></td><td></td></tr></table>'
)


def test_table_layout():
    assert detect_layout(TABLE) == "table"
    people = parse_staff_page(TABLE, BASE)
    assert [(p["name"], p["position"], p["section"]) for p in people] == [
        ("Dr Salawdeh, K.O. Omar", "Senior Lecturer", "Arabic"),
        ("Ms Lim Mei", "Lecturer", "Chinese"),
    ]
    assert people[0]["profile_urls"] == ["https://discovery.nus.edu.sg/3719"]  # icon link kept, mailto dropped
    assert people[0]["roles"] == ["Coordinator, LAR2201"]
    assert people[1]["roles"] == []


PARAGRAPHS = wrap(
    '<h2 class="fl-heading">Faculty</h2><div class="fl-rich-text">'
    '<p><strong>English Language and Linguistics</strong></p>'
    '<p><strong><a href="https://discovery.nus.edu.sg/1583">HIRAMOTO Mie <span class="sr-only">(opens in new tab)</span></a>'
    '</strong><br><a href="mailto:m@nus.edu.sg">m@nus.edu.sg</a><br>Contact linguistics, sociolinguistics</p>'
    '</div><h5>English Literature</h5><h6>Teaching and Research Faculty</h6><div class="fl-rich-text">'
    '<p><a href="https://discovery.nus.edu.sg/1"><strong>Jane DOE</strong></a><br>'
    '<a href="mailto:j@nus.edu.sg">j@nus.edu.sg</a></p>'
    '<p><a href="https://discovery.nus.edu.sg/2">John ROE</a><br><a href="mailto:r@nus.edu.sg">r@nus.edu.sg</a></p>'
    '</div>'
)


def test_paragraphs_layout():
    assert detect_layout(PARAGRAPHS) == "paragraphs"
    people = {p["name"]: p for p in parse_staff_page(PARAGRAPHS, BASE)}
    assert list(people) == ["HIRAMOTO Mie", "Jane DOE", "John ROE"]
    assert people["HIRAMOTO Mie"]["research_areas"] == "Contact linguistics, sociolinguistics"
    assert people["HIRAMOTO Mie"]["section"] == "English Language and Linguistics"
    assert people["Jane DOE"]["section"] == "English Literature – Teaching and Research Faculty"
    assert people["Jane DOE"]["research_areas"] is None


# Newer Beaver Builder: the <h4> is itself the module, the title is a bold line, and some
# people are listed twice (deputy heads at the top, then again under Faculty)
HEADING_MODULES = wrap(
    '<h3 class="fl-heading">Deputy Heads</h3>'
    '<div class="fl-col-group"><div class="fl-col"><div class="fl-col-content">'
    '<div class="fl-module fl-module-photo"><a href="https://discovery.nus.edu.sg/9"><img src="/k.png"></a></div>'
    '<h4 class="fl-module fl-module-heading fl-heading"><a href="https://discovery.nus.edu.sg/9">Kelvin Low'
    '<span class="sr-only">(opens in new tab)</span></a></h4>'
    '<div class="fl-module fl-module-rich-text fl-rich-text"><p><strong>Professor</strong></p>'
    '<p><a href="mailto:k@nus.edu.sg">k@nus.edu.sg</a></p></div></div></div></div>'
    '<h3 class="fl-heading">Faculty</h3>'
    + "".join(
        '<div class="fl-col-group"><div class="fl-col"><div class="fl-col-content">'
        f'<div class="fl-module fl-module-photo"><img src="/{n}.png"></div>'
        f'<h4 class="fl-module fl-module-heading fl-heading">{n}</h4>'
        f'<div class="fl-module fl-module-rich-text fl-rich-text"><p><strong>{t}</strong></p></div>'
        '</div></div></div>'
        for n, t in (("Kelvin Low", "Professor"), ("Ali Kassem", "Lecturer"), ("Ann Lee", "Senior Lecturer"))
    )
)


def test_heading_modules_with_bold_titles_and_duplicates():
    assert detect_layout(HEADING_MODULES) == "headings"
    people = parse_staff_page(HEADING_MODULES, BASE)
    assert [(p["name"], p["position"]) for p in people] == [
        ("Kelvin Low", "Professor"), ("Ali Kassem", "Lecturer"), ("Ann Lee", "Senior Lecturer"),
    ]
    kelvin = people[0]
    assert kelvin["section"] == "Deputy Heads"  # first listing wins
    assert kelvin["profile_urls"] == ["https://discovery.nus.edu.sg/9"]


def test_unknown_layout_returns_nothing():
    page = wrap("<p>Our faculty list is coming soon.</p>")
    assert detect_layout(page) == "unknown"
    assert parse_staff_page(page, BASE) == []
