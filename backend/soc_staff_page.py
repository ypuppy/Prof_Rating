"""Offline parser for the School of Computing people pages. No network or database access.

The pages (e.g. https://www.comp.nus.edu.sg/cs/people/) are AngularJS apps: the HTML only has
{{i.name}} templates, and the people are JavaScript arrays inside an inline <script>:

    $scope.allStaffs = [
        { name: "AI Xin", title: "Lecturer (Educator Track)", image: "https://...", ... },
        ...
    ];

So we read those arrays straight out of the saved HTML instead of running the page's JavaScript.
"""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

FACULTY = "School of Computing"

# One page per department. Names match the reference data (NUSMods)
SOURCES = [
    {"code": "soc-cs", "department": "Computer Science", "url": "https://www.comp.nus.edu.sg/cs/people/"},
    {"code": "soc-disa", "department": "Information Systems and Analytics",
     "url": "https://www.comp.nus.edu.sg/disa/people/"},
]

# Arrays to import, with the section heading the page shows for them. Left out on purpose:
# allStaffs_deptadmin and allStaffs_arealeader (the same faculty again, plus an assistant) and
# allStaffs_research (research fellows and assistants, who mostly don't teach)
GROUPS = {
    "allStaffs": "Faculty",
    "allStaffs_teaching": "Teaching Staff",
    "allStaffs_adjunct": "Adjunct, Part-time & Visiting Faculty",
    "allStaffs_courtesy": "Courtesy Appointment",
}
REQUIRED_GROUP = "allStaffs"

ESCAPES = {"n": "\n", "t": "\t", "r": "", '"': '"', "'": "'", "\\": "\\", "/": "/"}
FIELD = re.compile(r'(\w+)\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)


def clean(text):
    return " ".join(text.split())


def js_string(raw):
    """The inside of a "..." JavaScript string -> its value ('a\\"b' -> 'a"b')."""
    return re.sub(r"\\(.)", lambda m: ESCAPES.get(m.group(1), m.group(1)), raw, flags=re.S)


def _skip_string(text, i):
    """text[i] is a quote: return the index just after the matching closing quote."""
    quote, i = text[i], i + 1
    while i < len(text) and text[i] != quote:
        i += 2 if text[i] == "\\" else 1
    return i + 1


def _matching(text, i, open_char, close_char):
    """text[i] is open_char: return the index of its matching close_char, skipping strings."""
    depth = 0
    while i < len(text):
        char = text[i]
        if char in "\"'":
            i = _skip_string(text, i)
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"no matching {close_char!r}")


def js_arrays(html):
    """{'allStaffs': '<text between [ and ]>', ...} for every `$scope.allStaffs... = [` on the page."""
    arrays = {}
    for match in re.finditer(r"\$scope\.(allStaffs\w*)\s*=\s*\[", html):
        start = match.end() - 1
        arrays[match.group(1)] = html[start + 1:_matching(html, start, "[", "]")]
    return arrays


def js_objects(array_text):
    """Each { ... } in an array, as a dict of its string fields."""
    objects, i = [], 0
    while i < len(array_text):
        char = array_text[i]
        if char in "\"'":
            i = _skip_string(array_text, i)
        elif char == "{":
            end = _matching(array_text, i, "{", "}")
            body = array_text[i + 1:end]
            objects.append({key: js_string(value) for key, value in FIELD.findall(body)})
            i = end + 1
        else:
            i += 1
    return objects


def _url(value, base_url):
    """Absolute http(s) URL, or None. DISA's profile links are relative ('/disa/people/anand')."""
    value = (value or "").strip()
    if not value:
        return None
    value = urljoin(base_url, value)
    return value if urlsplit(value).scheme in {"http", "https"} else None


def to_person(record, section, base_url):
    research = clean(BeautifulSoup(record.get("researcharea", ""), "html.parser").get_text(" "))
    profile = _url(record.get("Bio"), base_url) if record.get("biolinkstat") == "1" else None
    # Not kept: email (an image of the address), officetel, tel
    return {
        "name": clean(record.get("name", "")),
        "position": clean(record.get("title", "")) or None,
        # Admin appointments, one per line: "Vice-Dean, Research\nDirector, ..."
        "roles": [clean(line) for line in record.get("ApptAdm", "").splitlines() if clean(line)],
        "section": section,
        "research_areas": research.replace(" ,", ",") or None,
        "profile_urls": [profile] if profile else [],
        "photo_url": _url(record.get("image"), base_url),
        "bio": None,
    }


def parse_soc_staff_page(html, base_url):
    """Return (people, checks). A missing array or a record without a name is an error."""
    arrays = js_arrays(html)
    people, errors, seen = [], [], set()
    group_counts = {}
    if REQUIRED_GROUP not in arrays:
        errors.append(f"no $scope.{REQUIRED_GROUP} array; the page layout may have changed")
    for group, section in GROUPS.items():
        if group not in arrays:
            continue
        records = js_objects(arrays[group])
        # Every record has a name field, so the two counts disagree if js_objects went wrong
        expected = len(re.findall(r"\bname\s*:", arrays[group]))
        if len(records) != expected:
            errors.append(f"{group}: read {len(records)} records but found {expected} names")
        group_counts[group] = len(records)
        for record in records:
            person = to_person(record, section, base_url)
            if not person["name"]:
                errors.append(f"{group}: a record without a name")
                continue
            # Someone listed in two groups is kept once, under the first (Faculty comes first)
            key = record.get("socid") or person["name"].casefold()
            if key in seen:
                continue
            seen.add(key)
            people.append(person)
    if not people and not errors:
        errors.append("parsed 0 people")
    return people, {"count": len(people), "groups": group_counts, "errors": errors}
