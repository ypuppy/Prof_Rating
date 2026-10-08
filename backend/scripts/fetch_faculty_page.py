"""
Fetch one NUS department "faculty" page and report whether we actually got it.

Usage (from backend/):
    python scripts/fetch_faculty_page.py https://fass.nus.edu.sg/philo/faculty/
    python scripts/fetch_faculty_page.py https://fass.nus.edu.sg/philo/faculty/ --out data/faculty_pages/philo.html

What it does: one plain GET with an honest User-Agent, then prints the status, size and content type.
If the response is the Imperva (Incapsula) bot-check stub instead of the page, it says so and exits 2.
If real HTML comes back, it is saved to --out for a later parser to read.

What it deliberately does NOT do: retry, rotate user agents, run a headless browser, or try to solve
or skip the CAPTCHA. nus.edu.sg and fass.nus.edu.sg put these pages behind Imperva; getting past that
is the site saying no, so the way in is a person opening the page in a browser.
"""
import argparse
import os
import sys
import urllib.error
import urllib.request

USER_AGENT = "ProfRating/0.1 (NUS student project; fetches public faculty lists)"

# Imperva serves a tiny page that only loads its challenge script
BLOCK_MARKERS = ("_Incapsula_Resource", "Incapsula incident", "Additional security check is required")


def looks_blocked(html: str) -> bool:
    return any(marker in html for marker in BLOCK_MARKERS)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--out", help="where to save the HTML if the real page comes back")
    args = parser.parse_args()

    req = urllib.request.Request(args.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            status = res.status
            content_type = res.headers.get("Content-Type", "")
            body = res.read()
    except urllib.error.HTTPError as e:
        status, content_type, body = e.code, e.headers.get("Content-Type", ""), e.read()

    html = body.decode("utf-8", errors="replace")
    print(f"HTTP {status}, {len(body)} bytes, {content_type or 'no content type'}")

    if looks_blocked(html):
        print(
            "Blocked: the server returned Imperva's bot-check page, not the faculty list.\n"
            "Open the URL in a browser instead (it may ask you to complete a CAPTCHA)."
        )
        sys.exit(2)

    if status != 200:
        sys.exit(f"Unexpected HTTP {status}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Saved to {args.out}")
    else:
        print("Got the page. Pass --out to save it.")


if __name__ == "__main__":
    main()
