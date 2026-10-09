"""
Parse a saved NUS department "faculty" page into people.

The pages can't be fetched by a script (Imperva bot check), so a person saves them from a browser
(scripts/fetch_faculty.py) and this module reads the saved HTML. Pure functions: no network, no DB.

FASS department sites are all WordPress + Beaver Builder, but each department laid its page out
differently. detect_layout() picks one of these, and each has its own parser:

    headings       Philosophy, Sociology: one block per person with an <h4> name heading,
                   an <h5> or bold line for the position, "Research Areas:", an accordion bio
    cards          Chinese Studies, History, Economics, ... (11 departments): a grid of
                   .people-profile-block cards with .people-name / .people-designation
    photo_columns  Social Work: a column per person, photo module + text "Name / titles / Email"
    table          Centre for Language Studies: one table, Position | Name | Profile | Convenor,
                   with single-cell rows naming the language
    paragraphs     English, Linguistics and Theatre Studies: a text block with one paragraph
                   per person: linked name, email, research areas

Every parser returns the same dicts:
    name, position, roles, section, research_areas, profile_urls, photo_url, bio
Phone numbers and email addresses are on the pages but deliberately not kept.
"""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString

from names import normalize_name

_SPACE = re.compile(r"\s+")
_NEW_TAB = re.compile(r"\(\s*opens in (?:a )?new (?:tab|window)\s*\)", re.IGNORECASE)
_HOST = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)
_EMAIL = re.compile(r"\S+@\S+\.\w+")
# Lines that are labels or contact details, not a job title
_NOT_A_TITLE = re.compile(r"^(?:e-?mail|tel|phone|office|profile page|research areas?|website)\b", re.IGNORECASE)


# ---------- text helpers ----------

def _clean(text):
    return _SPACE.sub(" ", _NEW_TAB.sub("", (text or "").replace("\xa0", " "))).strip()


def _is_sr_only(node, stop):
    """True if `node` sits inside a screen-reader-only element (below `stop`)."""
    for parent in node.parents:
        if parent is stop:
            return False
        if "sr-only" in (parent.get("class") or []):
            return True
    return False


def _text(tag):
    """Visible text of a tag. No separator between inline pieces: the editor sometimes splits a
    word across spans ("L</span><span>ogic"), and a separator would break it in two."""
    if tag is None:
        return ""
    return _clean("".join(s for s in tag.find_all(string=True) if not _is_sr_only(s, tag)))


def _lines(tag):
    """Visible text split on <br> and paragraph breaks, cleaned, empties dropped. Doesn't modify the tree."""
    if tag is None:
        return []
    out, current = [], []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            if not _is_sr_only(node, tag) and node.parent.name not in ("script", "style"):
                current.append(str(node))
        elif node.name in ("br", "p", "div", "li", "tr"):
            out.append("".join(current))
            current = []
    out.append("".join(current))
    return [line for line in (_clean(x) for x in out) if line]


def _split_title(text):
    """'Senior Lecturer | Director, Roots & Wings' -> ('Senior Lecturer', ['Director, Roots & Wings']).
    Only " | " separates roles: commas are ambiguous ("Deputy Head, Senior Lecturer")."""
    parts = [p.strip(" ,;") for p in (text or "").split("|")]
    parts = [p for p in parts if p]
    return (parts[0], parts[1:]) if parts else (None, [])


def _name_and_roles(raw):
    """'BILVEER SINGH (Deputy Head of Department)' -> ('BILVEER SINGH', ['Deputy Head of Department'])."""
    name = _clean(raw)
    roles = []
    match = re.match(r"^(.*?)\s*\(([^()]*(?:head|director|dean|coordinator|co-ordinator|chair)[^()]*)\)\s*$",
                     name, re.IGNORECASE)
    if match:
        name, roles = match.group(1).strip(), [match.group(2).strip()]
    return name, roles


def _url(raw, base_url):
    """Absolute http(s) URL, or None if it's not a usable link (mailto:, malformed, ...)."""
    raw = (raw or "").strip()
    # Salvage hrefs with junk pasted in front: "http://5.\thttps://discovery..." -> the last URL
    if raw.rfind("http") > 0:
        raw = raw[raw.rfind("http"):]
    href = urljoin(base_url, raw)
    parts = urlparse(href)
    if parts.scheme not in ("http", "https") or not _HOST.match(parts.hostname or "") or re.search(r"\s", href):
        return None
    return href


def _links(tags, base_url):
    urls = []
    for tag in tags:
        for a in ([tag] if tag.name == "a" else tag.find_all("a", href=True)):
            # The editor left invisible links behind (only "(opens in new tab)" inside), pointing at
            # another person's page; a reader never sees them, so neither should we.
            # Icon-only links (a Font Awesome glyph) still have visible text and are kept, and so do
            # links wrapped around a photo.
            if not a.get("href") or not (_text(a) or a.find("img")):
                continue
            href = _url(a["href"], base_url)
            if href and href not in urls:
                urls.append(href)
    return urls


def _img_src(img, base_url):
    return urljoin(base_url, img["src"]) if img is not None and img.get("src") else None


def _person(name, position=None, roles=(), section=None, research_areas=None,
            profile_urls=(), photo_url=None, bio=None):
    return {
        "name": name,
        "position": position or None,
        "roles": [r for r in roles if r],
        "section": section or None,
        "research_areas": research_areas or None,
        "profile_urls": list(profile_urls),
        "photo_url": photo_url,
        "bio": bio or None,
    }


def _content(soup):
    """The page body without the site header, menus and footer."""
    return (soup.select_one(".fl-builder-content-primary")
            or soup.select_one(".entry-content")
            or soup.body
            or soup)


# ---------- layout: headings (Philosophy, Sociology) ----------

def _find(segment, *args, **kwargs):
    for tag in segment:
        if tag.name == args[0] and all(c in (tag.get("class") or []) for c in [kwargs.get("class_")] if c):
            return tag
        found = tag.find(*args, **kwargs)
        if found is not None:
            return found
    return None


def _is_name_heading(tag):
    return getattr(tag, "name", None) == "h4" and "fl-heading" in (tag.get("class") or [])


def _is_name_module(tag):
    return _is_name_heading(tag) or (hasattr(tag, "find") and tag.find("h4", class_="fl-heading") is not None)


def _segment(name_tag):
    """
    The name's module plus the modules after it in the same column, up to the next name.
    Most people have a column to themselves, but some columns list several people in a row.
    Newer pages make the <h4> itself the module; older ones wrap it in a div.fl-module.
    """
    if "fl-module" in (name_tag.get("class") or []):
        module = name_tag
    else:
        module = name_tag.find_parent("div", class_="fl-module")
    if module is None:
        return [name_tag.parent]
    segment = [module]
    for sibling in module.find_next_siblings():
        if _is_name_module(sibling):
            break
        segment.append(sibling)
    return segment


def _research_areas(segment):
    label = None
    for tag in segment:
        label = tag.find(lambda t: t.name in ("strong", "b") and "research area" in t.get_text().lower())
        if label:
            break
    if label is None:
        return None
    block = label.find_parent("p") or label.parent
    match = re.search(r"Research Areas?\s*:\s*(.*)", _text(block), re.IGNORECASE)
    if not match:
        return None
    # Some entries continue with another label in the same paragraph
    areas = re.split(r"(?:Teaching Areas|Profile page|Email|Website)\s*:", match.group(1), flags=re.IGNORECASE)[0]
    return areas.strip(" ;,") or None


def _bio(segment):
    for tag in segment:
        for row in tag.select(".fl-accordion-content tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "introduction" in _text(cells[0]).lower():
                # " " between tags keeps words apart; then drop the space it leaves before punctuation
                return re.sub(r"\s+([.,;:!?])", r"\1", _clean(cells[1].get_text(" "))) or None
    return None


def _title_from_text(segment):
    """Position written as the first line of the text under the name (Sociology), when there's no <h5>."""
    for tag in segment[1:]:
        if "fl-rich-text" in (tag.get("class") or []) or tag.select_one(".fl-rich-text"):
            for line in _lines(tag):
                if _EMAIL.search(line) or _NOT_A_TITLE.match(line) or len(line) > 80:
                    continue
                return line
            return None
    return None


def _photo(name_tag, base_url):
    """
    Photos sit in a neighbouring column, so match by position: in the smallest column group around
    the name that has any photos, the n-th photo belongs to the n-th name, if the counts agree.
    """
    for group in name_tag.find_parents("div", class_="fl-col-group"):
        names = group.find_all("h4", class_="fl-heading")
        imgs = group.select(".fl-module-photo img") or group.find_all("img", class_="fl-photo-img")
        if not imgs:
            if len(names) > 1:
                return None
            continue  # look one level up
        if len(imgs) == len(names):
            return _img_src(imgs[names.index(name_tag)], base_url)
        return None  # counts don't line up: better no photo than someone else's
    return None


def _parse_headings(root, base_url):
    people = []
    for name_tag in root.find_all("h4", class_="fl-heading"):
        name = _text(name_tag)
        if not name:
            continue
        segment = _segment(name_tag)
        title_lines = _lines(_find(segment, "h5", class_="fl-heading"))
        position, roles = (title_lines[0], title_lines[1:]) if title_lines else (_title_from_text(segment), [])
        people.append(_person(
            name,
            position=position,
            roles=roles,
            section=_text(name_tag.find_previous("h3", class_="fl-heading")),
            research_areas=_research_areas(segment),
            profile_urls=_links(segment, base_url),
            photo_url=_photo(name_tag, base_url),
            bio=_bio(segment),
        ))
    return people


# ---------- layout: cards (Chinese Studies, History, Economics, ...) ----------

_SECTION_HEADINGS = ".fl-heading, h2, h3"


def _parse_cards(root, base_url):
    people = []
    for card in root.select(".people-profile-block"):
        name, roles = _name_and_roles(_text(card.select_one(".people-name")))
        if not name:
            continue
        position, more_roles = _split_title(_text(card.select_one(".people-designation")))
        section = card.find_previous(lambda t: t.name in ("h2", "h3", "h4") or "fl-heading" in (t.get("class") or []))
        link = card.find("a", href=True)
        people.append(_person(
            name,
            position=position,
            roles=roles + more_roles,
            section=_text(section),
            profile_urls=_links([link], base_url) if link else [],
            photo_url=_img_src(card.select_one(".people-image img"), base_url),
        ))
    return people


# ---------- layout: photo_columns (Social Work) ----------

def _parse_photo_columns(root, base_url):
    people = []
    section = None
    # Columns in page order; a text-only column is a section label ("ADJUNCT FACULTY")
    for col in root.select(".fl-col"):
        if col.select_one(".fl-col"):  # only innermost columns
            continue
        text = col.select_one(".fl-rich-text")
        photo = col.select_one(".fl-module-photo")
        if text is None:
            continue
        lines = _lines(text)
        if not lines:
            continue
        if photo is None:
            section = " ".join(lines)
            continue
        name, *rest = lines
        titles = []
        for line in rest:
            if _EMAIL.search(line) or _NOT_A_TITLE.match(line):
                break
            titles.append(line.strip(" ,;"))
        photo_link = photo.find("a", href=True)
        people.append(_person(
            _name_and_roles(name)[0],
            position=titles[0] if titles else None,
            roles=titles[1:],
            section=section or "Faculty",
            profile_urls=_links([photo_link] if photo_link else [text], base_url),
            photo_url=_img_src(photo.find("img"), base_url),
        ))
    return people


# ---------- layout: table (Centre for Language Studies) ----------

def _staff_table(root):
    for table in root.find_all("table"):
        header = table.find("tr")
        if header and any(_text(c).lower() == "name" for c in header.find_all(["td", "th"])):
            return table
    return None


def _parse_table(root, base_url):
    table = _staff_table(root)
    rows = table.find_all("tr")
    headers = [_text(c).lower() for c in rows[0].find_all(["td", "th"])]

    def col(*words):
        return next((i for i, h in enumerate(headers) if any(w in h for w in words)), None)

    i_pos, i_name, i_link, i_role = col("position"), col("name"), col("profile", "email"), col("convenor", "coordinator")
    people, section = [], None
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) == 1:
            section = _text(cells[0])  # "Arabic", "Chinese", ...
            continue
        if i_name is None or i_name >= len(cells) or not _text(cells[i_name]):
            continue
        get = lambda i: _text(cells[i]) if i is not None and i < len(cells) else ""  # noqa: E731
        people.append(_person(
            get(i_name),
            position=get(i_pos),
            roles=[get(i_role)],
            section=section,
            profile_urls=_links([cells[i_link]], base_url) if i_link is not None and i_link < len(cells) else [],
        ))
    return people


# ---------- layout: paragraphs (English, Linguistics and Theatre Studies) ----------

def _parse_paragraphs(root, base_url):
    # Two levels of grouping: a discipline ("English Literature", as an <h5> or a bold paragraph)
    # and inside it a group ("Teaching and Research Faculty", an <h6>)
    people = []
    discipline = group = None
    for node in root.find_all(["h2", "h3", "h4", "h5", "h6", "p"]):
        if node.name in ("h2", "h3", "h4"):
            continue  # page title ("Faculty")
        if node.name == "h5":
            discipline, group = _text(node), None
            continue
        if node.name == "h6":
            group = _text(node)
            continue
        if not node.find_parent(class_="fl-rich-text"):
            continue
        lines = _lines(node)
        if not lines:
            continue
        links = [a for a in node.find_all("a", href=True) if _url(a["href"], base_url)]
        if not links:
            # A bold paragraph on its own is a discipline label ("English Language and Linguistics")
            if len(lines) == 1 and node.find(["strong", "b"]) and not _EMAIL.search(lines[0]):
                discipline, group = lines[0], None
            continue
        name, *rest = lines
        research = [line for line in rest if not _EMAIL.search(line)]
        people.append(_person(
            name,
            section=" – ".join(x for x in (discipline, group) if x),
            research_areas="; ".join(research),
            profile_urls=_links(links, base_url),
        ))
    return people


# ---------- dispatch ----------

def detect_layout(soup_or_html):
    soup = soup_or_html if isinstance(soup_or_html, BeautifulSoup) else BeautifulSoup(soup_or_html, "html.parser")
    root = _content(soup)
    if root.select(".people-profile-block"):
        return "cards"
    if len([h for h in root.find_all("h4", class_="fl-heading") if _text(h)]) >= 3:
        return "headings"
    if _staff_table(root) is not None:
        return "table"
    photo_cols = [c for c in root.select(".fl-col")
                  if not c.select_one(".fl-col") and c.select_one(".fl-module-photo") and c.select_one(".fl-rich-text")]
    if len(photo_cols) >= 3:
        return "photo_columns"
    linked_paras = [p for p in root.select(".fl-rich-text p") if p.find("a", href=re.compile(r"^https?://"))]
    if len(linked_paras) >= 3:
        return "paragraphs"
    return "unknown"


_PARSERS = {
    "headings": _parse_headings,
    "cards": _parse_cards,
    "photo_columns": _parse_photo_columns,
    "table": _parse_table,
    "paragraphs": _parse_paragraphs,
}


def _merge_duplicates(people):
    """
    Some pages list a person twice (Sociology shows its deputy heads at the top, then again under
    Faculty). Keep the first entry, fill its empty fields from the later ones, and pool roles and links.
    """
    merged = {}
    for person in people:
        key = normalize_name(person["name"])
        if key not in merged:
            merged[key] = person
            continue
        kept = merged[key]
        for field, value in person.items():
            if field in ("roles", "profile_urls"):
                kept[field] += [v for v in value if v not in kept[field]]
            elif not kept[field] and value:
                kept[field] = value
    return list(merged.values())


def parse_staff_page(html, base_url):
    """Returns a list of dicts: name, position, roles, section, research_areas, profile_urls, photo_url, bio."""
    soup = BeautifulSoup(html, "html.parser")
    layout = detect_layout(soup)
    if layout == "unknown":
        return []
    return _merge_duplicates(_PARSERS[layout](_content(soup), base_url))
