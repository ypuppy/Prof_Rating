"""Offline parser for the CDE faculty directory. No network or database access."""
import re
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from names import normalize_name

BASE = "https://cde.nus.edu.sg"
FACULTY = "College of Design and Engineering"

# List-entry URLs only: the fetcher follows each entry's pagination separately.
# Keep query parameters (especially ChBE category) when following pagination.
SOURCE = [
    {
        "code": "me",
        "department": "Mechanical Engineering",
        "urls": [
            f"{BASE}/me/about-us/people/academic-staff/",
        ],
    },
    {
        "code": "mse",
        "department": "Materials Science and Engineering",
        "urls": [
            f"{BASE}/mse/academic-staff/",
        ],
    },
    {
        "code": "chbe",
        "department": "Chemical and Biomolecular Engineering",
        "urls": [
            f"{BASE}/chbe/about-us/people/?category=educators",
            f"{BASE}/chbe/about-us/people/?category=tenure-track",
            f"{BASE}/chbe/about-us/people/?category=emeritus-honorary",
            f"{BASE}/chbe/about-us/people/?category=visiting-adjunct-faculty",
        ],
    },
    {
        "code": "arch",
        "department": "Architecture",
        "urls": [
            f"{BASE}/arch/staff/",
        ],
    },
    {
        "code": "bme",
        "department": "Biomedical Engineering",
        "urls": [
            f"{BASE}/bme/about-us/people/academic-staff/",
        ],
    },
    {
        "code": "dbe",
        "department": "Built Environment",
        # Mixed Faculty / Adjunct / Research page: filter sections in the parser.
        "urls": [
            f"{BASE}/dbe/about-us/faculty-research-2/",
        ],
    },
    {
        "code": "cee",
        "department": "Civil and Environmental Engineering",
        "urls": [
            f"{BASE}/cee/about-us/people/faculty-staff/",
        ],
    },
    {
        "code": "ece",
        "department": "Electrical and Computer Engineering",
        "urls": [
            f"{BASE}/ece/about-us/people/academic-staff/",
        ],
    },
    {
        "code": "dd",
        "department": "Design",
        # Current site uses /dd/, not the old /did/ prefix. /staff/ is a hub.
        # These lists may overlap; deduplicate people after combining them.
        "urls": [
            f"{BASE}/dd/full-time/",
            f"{BASE}/dd/part-time/",
            f"{BASE}/dd/adjunct/",
            f"{BASE}/dd/teaching-assistants-instructors/",
        ],
    },
    {
        "code": "isem",
        "department": "Industrial Systems Engineering and Management",
        "urls": [
            f"{BASE}/isem/faculty-members/",
            f"{BASE}/isem/about-us/people/adjunct-staff/",
            f"{BASE}/isem/about-us/people/teaching-support-staff/",
        ],
    },
]


class PaginationError(ValueError):
    """A visible pagination link could not be followed safely."""


def clean(text):
    return " ".join(re.sub(r"\(opens in (?:a )?new (?:tab|window)\)", "", text, flags=re.I).split())


def soup_for(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, noscript, .sr-only, .screen-reader-text, [aria-hidden='true']"):
        tag.decompose()
    return soup


def page_parts(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.hostname != "cde.nus.edu.sg":
        raise PaginationError(f"Not a CDE URL: {url}")
    match = re.search(r"/page/(\d+)/?$", parts.path)
    path = (parts.path[:match.start()] if match else parts.path).rstrip("/") + "/"
    query = parse_qs(parts.query, keep_blank_values=True)
    values = query.pop("paged", None)
    if values is not None and (len(values) != 1 or not values[0].isdigit()):
        raise PaginationError(f"Invalid paged parameter: {url}")
    number = int(values[0]) if values is not None else int(match.group(1)) if match else 1
    if number < 1 or (match and values is not None and int(match.group(1)) != number):
        raise PaginationError(f"Conflicting/invalid page number: {url}")
    filters = {key: values for key, values in query.items() if any(values)}
    # Default ASC sorting and empty search do not change the list's scope.
    if filters.get("sort") == ["ASC"]:
        filters.pop("sort")
    return parts, path, number, filters


def page_key(url):
    parts, path, number, filters = page_parts(url)
    return parts.hostname, path, number, tuple(sorted((key, tuple(values)) for key, values in filters.items()))


def scope_key(url):
    key = page_key(url)
    return key[0], key[1], key[3]


def pagination(html, base_url):
    """Read actual links, preserving category/search/sort/pid instead of inventing URLs.

    Supports WordPress page-numbers and numeric/First/Last/Next links. Category
    changes on explicitly configured category pages are excluded.
    """
    _, current_path, _, current_filters = page_parts(base_url)
    urls, seen = [], set()
    for link in soup_for(html).select("a[href]"):
        label = clean(link.get_text(" ")).lower()
        in_pager = "page-numbers" in (link.get("class") or []) or any(
            "pagination" in str(parent.get("class", "")).lower()
            for parent in link.parents if getattr(parent, "attrs", None)
        )
        if not (in_pager or label.isdigit() or label in {"first", "last", "next", "previous", "next »", "« previous"}):
            continue
        url = urljoin(base_url, link["href"])
        parts = urlsplit(url)
        if parts.hostname != "cde.nus.edu.sg":
            continue
        _, path, number, filters = page_parts(url)
        if path != current_path:
            continue
        if current_filters.get("category") and filters.get("category") != current_filters["category"]:
            if in_pager:
                raise PaginationError(f"Pagination loses/changes the selected category: {url}")
            continue
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        key = page_key(url)
        if key not in seen:
            seen.add(key)
            urls.append(url)
    return urls


# Teaching and research titles. On pages that also list administrative staff (Architecture),
# cards without one (Secretary, Executive, Lab Technologist...) are excluded, but counted.
ACADEMIC = re.compile(r"\b(?:professor|lecturer|instructor|fellow|tutor|teaching assistant)s?\b|\bemeritus\b", re.I)
HONORIFIC = re.compile(r"\s*\((?:Dr|Prof|Mr|Ms|Mrs|Mdm)\.?\)|^(?:Dr|Prof)\.?\s+", re.I)


def _text(tag):
    return clean(tag.get_text(" ")) if tag else ""


def _image(tag, base_url):
    image = tag.find("img") if tag else None
    src = (image.get("data-src") or image.get("src")) if image else None
    return urljoin(base_url, src) if src and not src.startswith("data:") else None


def _links(tags, base_url):
    """Absolute http(s) hrefs of the given <a> tags, in order, without duplicates, emails or PDFs."""
    links = []
    for link in tags:
        href = urljoin(base_url, link.get("href", ""))
        parts = urlsplit(href)
        # "@" in the host: an email typed as a link (http://name@nus.edu.sg)
        if (parts.scheme in {"http", "https"} and "@" not in parts.netloc
                and not parts.path.lower().endswith(".pdf") and href not in links):
            links.append(href)
    return links


def _titles(texts):
    """Every title in the site's order, split on '|', without repeats. Nothing is picked as 'the' rank."""
    titles = []
    for text in texts:
        for part in text.split("|"):
            part = clean(part)
            if part and part.casefold() not in {t.casefold() for t in titles}:
                titles.append(part)
    return titles


def _person(fields):
    return {
        "name": clean(HONORIFIC.sub("", fields["name"])),
        "position": " · ".join(fields["titles"]) or None,
        "roles": [],
        "section": fields.get("section"),
        "research_areas": fields.get("research_areas"),
        "profile_urls": fields.get("links", []),
        "photo_url": fields.get("photo"),
        "bio": None,
    }


def _category(base_url):
    """ChBE splits its lists by ?category=tenure-track etc.: use that as the section."""
    category = parse_qs(urlsplit(base_url).query).get("category", [""])[0]
    return category.replace("-", " ").capitalize() or None


def _heading_above(tag, name="h3"):
    """Text of the nearest non-empty heading before tag (a page's group title), or None."""
    heading = tag.find_previous(lambda t: t.name == name and clean(t.get_text(" ")))
    return _text(heading) or None


# Each layout = (find the cards on a page, read one card). A reader returns a dict with
# name, titles and optionally section, research_areas, links, photo.

def _division(card):
    """ME's research division ("Fluid Mechanics"); ISEM puts its own department name here instead."""
    division = _text(card.select_one(".content-department")).strip("()")
    return None if division.startswith("Department of") else division or None


def _ws_people(card, base_url):
    """ME-style card (.ws-people-content): every field has its own class.

    <div class="content-name"><a href=profile><h3>Name</h3></a></div>
    <div class="content-title"> / <div class="content-designation">  titles (either may hold the rank)
    <div class="content-department">  research division, e.g. "Fluid Mechanics"
    <div class="content-email">  not kept
    """
    return {
        "name": _text(card.select_one(".content-name")),
        "titles": _titles(_text(t) for t in card.select(".content-title, .content-designation")),
        "section": _division(card) or _category(base_url),
        "links": _links(card.select(".content-name a[href], .content-website a[href]"), base_url),
        "photo": _image(card.select_one(".content-image"), base_url),
    }


def _profile_wrapper(card, base_url):
    """Architecture card (.profile-wrapper): photo link, then a link holding name and title.

    <div class="profile-img"><a href=profile><img></a></div>
    <a href=profile><div class="profile-name">Name (Dr)</div><div class="profile-title">A|B</div></a>
    """
    return {
        "name": _text(card.select_one(".profile-name")),
        "titles": _titles([_text(card.select_one(".profile-title"))]),
        "links": _links(card.select("a[href]"), base_url),
        "photo": _image(card.select_one(".profile-img"), base_url),
    }


def _heading_columns(soup):
    """DBE: Beaver Builder columns (.fl-col) holding two or more non-empty h2 headings."""
    columns = []
    for column in soup.select(".fl-col"):
        if column.select_one(".fl-col"):
            continue  # only innermost columns
        if sum(1 for h in column.select("h2.fl-heading") if _text(h)) >= 2:
            columns.append(column)
    return columns


def _heading_column(card, base_url):
    """DBE column: photo, then h2 name, h2 title(s), h2 email, then a "Profile" button.

    Section is the h3 above (Faculty / Adjunct Staff / Research Staff). Headings after the
    email ("Profile Updating") are page notes, not titles.
    """
    headings = [h for h in card.select("h2.fl-heading") if _text(h)]
    titles = []
    for heading in headings[1:]:
        if "@" in _text(heading) or heading.select_one("a[href^='mailto:']"):
            break
        titles.append(_text(heading))
    return {
        "name": _text(headings[0]) if headings else "",
        "titles": _titles(titles),
        "section": _heading_above(card),
        "links": _links(card.select("a[href]:not([href^='mailto:'])"), base_url),
        "photo": _image(card, base_url),
    }


def _header_row(table):
    first = table.find("tr")
    return [_text(cell).lower() for cell in first.find_all(["th", "td"])] if first else []


def _name_table_rows(soup):
    """Design part-time: tables whose first row is a header with 'Name' and a title column."""
    rows = []
    for table in soup.find_all("table"):
        headers = _header_row(table)
        if "name" in headers and any(re.search(r"title|position|designation", h) for h in headers):
            # One-cell rows are group labels inside the table, not people
            rows += [row for row in table.find_all("tr")[1:] if len(row.find_all(["td", "th"])) > 1]
    return rows


def _name_table_row(row, base_url):
    """<tr><td>Name (Ms)</td><td>Part-time Lecturer</td><td>email (not kept)</td></tr>"""
    headers = _header_row(row.find_parent("table"))
    cells = row.find_all(["td", "th"])
    title_index = next(i for i, h in enumerate(headers) if re.search(r"title|position|designation", h))
    cell = lambda i: _text(cells[i]) if i < len(cells) else ""  # noqa: E731
    return {
        "name": cell(headers.index("name")),
        "titles": _titles([cell(title_index)]),
        "section": _heading_above(row),
    }


def _rank_table_rows(soup):
    """ISEM adjunct: header-less tables of [photo | name | research areas], one per rank h3."""
    rows = []
    for table in soup.find_all("table"):
        if "name" in _header_row(table):
            continue
        if ACADEMIC.search(_heading_above(table) or ""):
            rows += [row for row in table.find_all("tr") if row.find("img")]
    return rows


def _rank_table_row(row, base_url):
    """The rank comes from the heading above: "Adjunct Associate Professors" -> "Adjunct Associate Professor"."""
    cells = row.find_all(["td", "th"])
    group = _heading_above(row.find_parent("table"))
    research = [clean(line) for line in cells[2].get_text("\n").splitlines() if clean(line)] if len(cells) > 2 else []
    return {
        "name": _text(cells[1]) if len(cells) > 1 else "",
        "titles": [re.sub(r"\b(Professor|Lecturer)s\b", r"\1", group)],
        "section": group,
        "research_areas": ", ".join(research) or None,
        "photo": _image(cells[0], base_url),
    }


def _person_cells(soup):
    """ISEM teaching support: a table where each cell is one person, named by an h3."""
    return [cell for table in soup.find_all("table") for cell in table.find_all("td")
            if any(_text(h) for h in cell.find_all("h3"))]


def _person_cell(cell, base_url):
    """<td><img><h3>Name</h3><p><a href=mailto:>Email</a></p><p>Teaching Assistant</p></td>

    Section is the page's h2 ("Teaching Support Staff"): the h3s are names here.
    """
    name = next(h for h in cell.find_all("h3") if _text(h))
    titles = [_text(par) for par in name.find_all_next("p")
              if par.find_parent("td") is cell and _text(par)
              and not par.select_one("a[href^='mailto:']") and "@" not in _text(par)]
    return {
        "name": _text(name),
        "titles": _titles(titles),
        "section": _heading_above(cell.find_parent("table"), "h2"),
        "photo": _image(cell, base_url),
    }


# name -> (find cards, read a card). One small reader per site template, chosen by detect_layout().
# A department on a new template is "unknown layout" (parse_failed) until a reader is added here.
LAYOUTS = {
    "ws-people": (lambda soup: soup.select(".ws-people-content"), _ws_people),
    "profile-wrapper": (lambda soup: soup.select(".profile-wrapper"), _profile_wrapper),
    "heading-columns": (_heading_columns, _heading_column),
    "name-table": (_name_table_rows, _name_table_row),
    "rank-tables": (_rank_table_rows, _rank_table_row),
    "person-cells": (_person_cells, _person_cell),
}
# Layouts whose pages also list administrative staff. The others are academic-staff lists, where
# a card may show only a leadership role ("Head of Department") and must still be kept
MIXED_LAYOUTS = {"profile-wrapper"}

# Research fellows/engineers/assistants mostly don't teach (SoC leaves them out too)
EXCLUDED_SECTION = re.compile(r"\bresearch staff\b", re.I)


def detect_layout(soup):
    """Returns (layout name, cards)."""
    found = [(name, find(soup)) for name, (find, _) in LAYOUTS.items()]
    found = [(name, cards) for name, cards in found if cards]
    if len(found) > 1:
        raise ValueError("page matches several layouts: " + ", ".join(name for name, _ in found))
    return found[0] if found else ("unknown", [])


def merge_people(people):
    merged = {}
    for person in people:
        key = normalize_name(person["name"])
        if key not in merged:
            merged[key] = dict(person, roles=list(person["roles"]), profile_urls=list(person["profile_urls"]))
            continue
        kept = merged[key]
        for field in ("roles", "profile_urls"):
            kept[field].extend(value for value in person[field] if value not in kept[field])
        if person["position"] and person["position"] != kept["position"]:
            if person["position"] not in kept["roles"]:
                kept["roles"].append(person["position"])
        for field in ("position", "section", "photo_url", "research_areas", "bio"):
            if not kept[field] and person[field]:
                kept[field] = person[field]
    return list(merged.values())


def parse_cde_staff_page(html, base_url):
    """Return (people, checks), with the same eight personnel fields as FASS/BIZ/SoC.

    Every card is either parsed or excluded (administrative or research staff), and the check
    cards == parsed + excluded makes a silently skipped card an error.
    """
    soup = soup_for(html)
    errors, people, excluded, nameless = [], [], 0, 0
    try:
        layout, cards = detect_layout(soup)
    except ValueError as exc:
        return [], {"count": 0, "card_count": 0, "excluded_count": 0, "duplicate_count": 0,
                    "layout": "ambiguous", "errors": [str(exc)]}
    if layout == "unknown":
        errors.append("unknown layout: no known staff card on the page (new template or verification page)")
    else:
        reader = LAYOUTS[layout][1]
        for card in cards:
            fields = reader(card, base_url)
            if not fields["name"]:
                nameless += 1
                errors.append("a staff card has no name")
                continue
            administrative = layout in MIXED_LAYOUTS and not any(ACADEMIC.search(t) for t in fields["titles"])
            if administrative or EXCLUDED_SECTION.search(fields.get("section") or ""):
                excluded += 1
                continue
            people.append(_person(fields))
    raw_count = len(people)
    people = merge_people(people)
    if layout != "unknown" and not people:
        errors.append("parsed 0 people")
    if len(cards) != raw_count + excluded + nameless:
        errors.append(f"{len(cards)} cards but {raw_count} parsed and {excluded} excluded")
    return people, {
        "count": len(people), "card_count": len(cards), "excluded_count": excluded,
        "duplicate_count": raw_count - len(people), "layout": layout, "errors": errors,
    }
