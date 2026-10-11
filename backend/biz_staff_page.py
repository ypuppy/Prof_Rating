"""Offline parser for the BIZ faculty directory. No network or database access."""
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

DIRECTORY_URL = "https://bizfaculty.nus.edu.sg/faculty-directory/"
FACULTY = "NUS Business School"


def clean(text):
    return " ".join(text.split())


def department_name(label):
    """'Management & Organisation' (the site's label) -> 'Management and Organisation' (the name NUSMods uses)."""
    return clean(label.replace("&", " and "))


def soup_for(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select(".sr-only, .screen-reader-text, script, style, noscript, [aria-hidden='true']"):
        tag.decompose()
    return soup


def text_lines(tag):
    """Keep inline text together; split only at line/block boundaries."""
    copy = BeautifulSoup(str(tag), "html.parser")
    for br in copy.find_all("br"):
        br.replace_with("\n")
    for block in copy.find_all(["div", "p", "li", "h4", "h5"]):
        block.insert_before("\n")
        block.insert_after("\n")
    return [clean(line) for line in copy.get_text().splitlines() if clean(line)]


def directory_page(raw, base_url):
    """Return (department ID, page number), excluding surname/search filters."""
    parts = urlsplit(urljoin(base_url, raw))
    if parts.scheme not in {"http", "https"} or parts.hostname != urlsplit(DIRECTORY_URL).hostname:
        return None
    match = re.fullmatch(r"/faculty-directory/(?:page/(\d+)/)?", parts.path)
    query = parse_qs(parts.query, keep_blank_values=True)
    if not match or set(query) - {"dept", "paged"}:
        return None
    values = query.get("dept", [""])
    if len(values) != 1 or (values[0] and not values[0].isdigit()):
        return None
    paged = query.get("paged")
    if paged is not None and (len(paged) != 1 or not paged[0].isdigit()):
        return None
    path_number = match.group(1)
    if path_number and paged is not None and int(path_number) != int(paged[0]):
        return None
    number = int(paged[0] if paged is not None else (path_number or 1))
    return (values[0], number) if number > 0 else None


def page_url(department_id, number=1):
    query = {"dept": department_id} if department_id else {}
    if number != 1:
        query["paged"] = number
    return DIRECTORY_URL + ("?" + urlencode(query) if query else "")


def discover_departments(html):
    departments = {}
    for link in soup_for(html).select("a[href]"):
        target = directory_page(link["href"], DIRECTORY_URL)
        name = clean(link.get_text(" "))
        if target and target[0] and target[1] == 1 and name and name.lower() != "all":
            departments.setdefault(target[0], {
                "code": "biz-" + target[0], "department_id": target[0],
                "department": name, "faculty": FACULTY, "url": page_url(target[0]),
            })
    return list(departments.values())


def pagination(html, base_url, department_id):
    numbers = set()
    for link in soup_for(html).select("a[href]"):
        target = directory_page(link["href"], base_url)
        if target and target[0] == department_id:
            numbers.add(target[1])
    return sorted(numbers)


def parse_biz_staff_page(html, base_url, department_label):
    """Return (people, checks). Unknown card structures produce explicit errors.

    Find the smallest ancestor containing exactly one h4 name and a standalone
    department label. This avoids depending on unverified WordPress CSS classes.
    """
    soup = soup_for(html)
    root = soup.find("main") or soup
    headings = [h for h in root.find_all("h4") if clean(h.get_text(" "))]
    people, errors = [], []
    for heading in headings:
        name = clean(heading.get_text(" "))
        card = None
        for parent in heading.parents:
            if parent.name in {"main", "body", "html", "[document]"}:
                break
            if len(parent.find_all("h4")) > 1:
                break
            lines = text_lines(parent)
            if department_label in lines:
                if card is None:
                    card = parent
                # A photo often sits beside the text in a neighbouring column.
                if parent.find("img"):
                    card = parent
                    break
        if card is None:
            errors.append(f"{name}: cannot identify a card with department {department_label!r}")
            continue

        # Remove the name before reading text: nested spans must not split it.
        content = BeautifulSoup(str(card), "html.parser")
        content.find("h4").decompose()
        lines = text_lines(content)
        department_index = lines.index(department_label)
        # Keep every title in the site's order rather than guessing which one is the rank
        titles = lines[:department_index]
        position = " · ".join(titles) or None
        profiles = []
        for link in heading.select("a[href]"):
            url = urljoin(base_url, link["href"])
            if urlsplit(url).scheme in {"http", "https"} and url not in profiles:
                profiles.append(url)
        image = card.find("img")
        photo = (image.get("data-src") or image.get("src")) if image else None
        people.append({
            "name": name, "position": position, "roles": [], "section": None,
            "research_areas": None, "profile_urls": profiles,
            "photo_url": urljoin(base_url, photo) if photo else None, "bio": None,
        })
        if not position:
            errors.append(f"{name}: missing position")
    if not people:
        errors.append("parsed 0 people")
    if len(people) != len(headings):
        errors.append(f"parsed {len(people)} people but found {len(headings)} h4 headings")
    names = [p["name"].casefold() for p in people]
    if len(set(names)) != len(names):
        errors.append("duplicate names on this page")
    return people, {"count": len(people), "heading_count": len(headings), "errors": errors}
