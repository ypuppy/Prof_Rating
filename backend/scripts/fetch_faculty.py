"""Export FASS departments' faculty pages to fass_faculty.json.

First-time setup (macOS, in your homework folder):
    python3 -m venv .venv-homework
    source .venv-homework/bin/activate
    python -m pip install playwright
    python -m playwright install chromium

Usage:
    python fetch_faculty.py
    python fetch_faculty.py --department ecs --department philo
    python fetch_faculty.py --resume
    python fetch_faculty.py --out sol.json

Read the departments directory, then try each department's /faculty/ URL.
If necessary, follow a Faculty link from that department's homepage.
Export page text, headings, links and tables, not inferred person records.
Individual profile links are recorded but not visited. Complete any browser
verification manually. Results are saved after every department.
"""

import argparse
import json
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

HTML_OUTPUT_DIR = BACKEND_DIR / "data" / "staff_pages"

DIRECTORY_URL = "https://fass.nus.edu.sg/about-us/departments/"
HOST = "fass.nus.edu.sg"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "fass_faculty.json"
DEPARTMENT_NAME = re.compile(
    r"^(?:department of\b|centre for language studies\b|"
    r"south asian studies programme\b|office of programmes\b)", re.I
)
BLOCK_TEXT = re.compile(
    r"additional security check is required|incapsula incident|"
    r"access denied|request unsuccessful|verify (?:that )?you are human|"
    r"checking your browser", re.I
)
VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCK_TAGS = set("address article br div h1 h2 h3 h4 h5 h6 li p section table tr ul ol".split())
SKIP_TAGS = set("script style noscript svg nav header footer aside form button".split())
SKIP_CLASSES = {"fl-page-header", "fl-page-footer", "fl-page-nav-wrap", "breadcrumb", "breadcrumbs"}


def now():
    return datetime.now(timezone.utc).isoformat()


def compact(text):
    return " ".join(text.split())


class Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


class TreeParser(HTMLParser):
    """Parse the browser's normalized HTML using the standard library."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def excluded(node):
    classes = set((node.attrs.get("class") or "").split())
    return node.tag in SKIP_TAGS or bool(classes & SKIP_CLASSES)


def raw_text(node, clean=False):
    if clean and excluded(node):
        return ""
    pieces = []
    for child in node.children:
        if isinstance(child, str):
            pieces.append(child)
        else:
            value = raw_text(child, clean)
            if child.tag in BLOCK_TAGS:
                value = "\n" + value + "\n"
            pieces.append(value)
    return "".join(pieces)


def clean_text(node):
    return "\n".join(
        line for line in (compact(x) for x in raw_text(node, True).splitlines()) if line
    )


def content_root(tree):
    nodes = list(tree.walk())
    selectors = [
        lambda n: "entry-content" in (n.attrs.get("class") or "").split(),
        lambda n: n.tag == "main" or n.attrs.get("role") == "main",
        lambda n: n.attrs.get("id") == "main",
        lambda n: "fl-builder-content" in (n.attrs.get("class") or "").split()
        and n.attrs.get("data-type") == "post",
        lambda n: n.attrs.get("id") == "content",
        lambda n: "fl-page-content" in (n.attrs.get("class") or "").split(),
        lambda n: n.tag == "body",
    ]
    for match in selectors:
        candidates = [n for n in nodes if match(n)]
        if candidates:
            return max(candidates, key=lambda n: len(clean_text(n)))
    return tree


def canonical_url(raw, base):
    parts = urlsplit(urljoin(base, raw))
    if parts.scheme not in {"http", "https"}:
        return None
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def links_in(node, base, clean=False):
    links, seen = [], set()
    for item in node.walk():
        if item.tag != "a" or not item.attrs.get("href"):
            continue
        if clean:
            current = item
            while current is not None and current is not node:
                if excluded(current):
                    break
                current = current.parent
            if current is not node:
                continue
        raw = item.attrs["href"].strip()
        if raw.startswith(("javascript:", "tel:")) or raw in {"", "#"}:
            continue
        address = raw if raw.startswith("mailto:") else canonical_url(raw, base)
        if not address:
            continue
        label = compact(raw_text(item)) or item.attrs.get("aria-label") or ""
        key = (label, address)
        if key not in seen:
            seen.add(key)
            links.append({"text": label, "url": address})
    return links


def snapshot_html(html, url):
    tree = TreeParser(html).root
    root = content_root(tree)
    title = next((compact(raw_text(n)) for n in tree.walk() if n.tag == "title"), "")
    headings, tables = [], []
    for node in root.walk():
        current = node
        while current is not root and current is not None and not excluded(current):
            current = current.parent
        if current is not root:
            continue
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            value = compact(raw_text(node, True))
            if value:
                headings.append({"level": int(node.tag[1]), "text": value})
        if node.tag == "table":
            rows = []
            for row in node.walk():
                if row.tag == "tr":
                    cells = [compact(raw_text(cell, True)) for cell in row.children
                             if isinstance(cell, Node) and cell.tag in {"th", "td"}]
                    if cells:
                        rows.append(cells)
            tables.append({"rows": rows})
    return {
        "url": url,
        "page_title": title,
        "text": clean_text(root),
        "headings": headings,
        "links": links_in(root, url, clean=True),
        "tables": tables,
        "all_links": links_in(tree, url),
        "body_text": clean_text(tree),
        "has_challenge_resource": "_Incapsula_Resource" in html,
        "content_selector": root.tag + ("#" + root.attrs["id"] if root.attrs.get("id") else ""),
    }


def discover_departments(snapshot):
    departments = {}
    for link in snapshot["all_links"]:
        if not DEPARTMENT_NAME.search(link["text"]):
            continue
        parts = urlsplit(link["url"])
        segments = [segment for segment in parts.path.split("/") if segment]
        if parts.hostname != HOST or len(segments) != 1:
            continue
        code = segments[0]
        departments.setdefault(code, {
            "department": link["text"], "code": code,
            "home_url": f"https://{HOST}/{code}/",
            "requested_url": f"https://{HOST}/{code}/faculty/",
        })
    return list(departments.values())


def within_department(url, department):
    parts = urlsplit(url)
    return parts.hostname == HOST and parts.path.startswith(f"/{department['code']}/")


def blocked(snapshot):
    # Protected real pages can include this resource too; it alone is not a block.
    text = snapshot["body_text"]
    return bool(BLOCK_TEXT.search(snapshot["page_title"] + "\n" + text)) or (
        snapshot["has_challenge_resource"] and len(text) < 80
    )


class PageFailure(Exception):
    pass


def validate_faculty(snapshot, department):
    if not within_department(snapshot["url"], department):
        raise PageFailure("页面跳转出了这个部门的路径。")
    heading_text = " ".join(x["text"] for x in snapshot["headings"])
    title_text = re.split(r"\s[–—-]\s", snapshot["page_title"], maxsplit=1)[0]
    if re.search(r"not found|page does not exist|404", title_text, re.I):
        raise PageFailure("返回了错误页面。")
    if len(snapshot["text"]) < 50 or not re.search(
        r"\bfaculty\b|\bour people\b|\bacademic(?: staff|s)\b|\bteaching staff\b",
        heading_text + " " + title_text, re.I
    ):
        raise PageFailure("返回的页面没有可识别的 Faculty/People 正文。")


def faculty_links(snapshot, department):
    matches, seen = [], set()
    for link in snapshot["all_links"]:
        url = link["url"]
        label = link["text"].lower()
        if not within_department(url, department) or url in seen:
            continue
        if re.search(r"recruit|career|vacanc|award|news|publication", label):
            continue
        if re.search(r"\bfaculty\b|\bacademic staff\b", label) or re.search(
            r"/(?:faculty\d*|department-faculty|full-time-staff)/?$", urlsplit(url).path
        ):
            seen.add(url)
            secondary = bool(re.search(r"adjunct|affiliat|visit|emeritus|honorary|part.time", label))
            matches.append((secondary, url))
    return [url for _, url in sorted(matches, key=lambda item: item[0])]


class BrowserLoader:
    def __init__(self, page, delay=2, interactive=True):
        self.page = page
        self.delay = delay
        self.interactive = interactive
        self.last_status = None
        self.last_request_at = 0
        page.on("response", self.on_response)

    def on_response(self, response):
        if response.request.is_navigation_request() and response.request.frame == self.page.main_frame:
            self.last_status = response.status

    def load(self, url, validator=None):
        from playwright.sync_api import Error as PlaywrightError
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_at = time.monotonic()
        self.last_status = None
        print(f"  访问：{url}", flush=True)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            deadline = time.monotonic() + 15
            failure = "正文尚未加载。"
            while True:
                html = self.page.content()
                snapshot = snapshot_html(html, self.page.url)
                challenge = blocked(snapshot)
                if not challenge:
                    if self.last_status is not None and self.last_status >= 400:
                        raise PageFailure(f"HTTP {self.last_status}")
                    if urlsplit(snapshot["url"]).hostname != HOST:
                        raise PageFailure("页面跳转出了 FASS 网站。")
                    try:
                        if validator:
                            validator(snapshot)
                        elif len(snapshot["text"]) < 50:
                            raise PageFailure("正文尚未加载。")
                        return snapshot,html
                    except PageFailure as exc:
                        failure = str(exc)
                else:
                    failure = "浏览器仍在验证页面。"
                if time.monotonic() >= deadline:
                    break
                self.page.wait_for_timeout(500)
            if challenge and self.interactive and sys.stdin.isatty():
                answer = input(
                    "  请在浏览器中手动完成验证，完成后回终端按 Enter；输入 s 跳过："
                ).strip().lower()
                if answer != "s":
                    self.page.wait_for_timeout(1000)
                    html = self.page.content()
                    snapshot = snapshot_html(html, self.page.url)
                    if blocked(snapshot):
                        raise PageFailure("手动验证后仍被拦截。")
                    if self.last_status is not None and self.last_status >= 400:
                        raise PageFailure(f"HTTP {self.last_status}")
                    if urlsplit(snapshot["url"]).hostname != HOST:
                        raise PageFailure("页面跳转出了 FASS 网站。")
                    if validator:
                        validator(snapshot)
                    elif len(snapshot["text"]) < 50:
                        raise PageFailure("页面正文为空。")
                    return snapshot,html
            raise PageFailure(failure)
        except PlaywrightError as exc:
            raise PageFailure(str(exc).splitlines()[0]) from exc


def export_department(loader, department):
    errors, tried = [], set()

    def attempt(url):
        from staff_page import parse_staff_page

        tried.add(url)
        try:
            snapshot,html = loader.load(url, lambda value: validate_faculty(value, department),
            )

            HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            html_path = HTML_OUTPUT_DIR / f"{department['code']}.html"
            html_path.write_text(html, encoding="utf-8")

            result = {
                **department,
                "status": "success",
                "fetched_at": now(),
                "attempt_errors": errors,
            }

            for field in (
                "url",
                "page_title",
                "text",
                "headings",
                "links",
                "tables",
                "content_selector",
            ):
                result[field] = snapshot[field]

            result["people"] = parse_staff_page(html, snapshot["url"])

            h4_count = sum(
                heading["level"] == 4 for heading in snapshot["headings"]
            )

            people_count = len(result["people"])

            if people_count == 0:
                result["status"] = "parse_failed"
                result["parse_error"] = (
                    f"parsed 0 people; page has {h4_count} h4 headings"
                )

            elif people_count != h4_count:
                result["status"] = "parse_failed"
                result["parse_error"] = (
                    f"parsed {people_count} people; but page has {h4_count} h4 headings"
                )

            if result["status"] == "parse_failed":
                print(f"  解析失败: {result['parse_error']}", flush=True)
            
            return result
        except PageFailure as exc:
            errors.append({"url": url, "error": str(exc)})
            return None 
        
        # tried.add(url)
        # try:
        #     snapshot = loader.load(url, lambda value: validate_faculty(value, department))
        #     result = {**department, "status": "success", "fetched_at": now(),
        #               "attempt_errors": errors}
        #     for field in ("url", "page_title", "text", "headings", "links", "tables", "content_selector"):
        #         result[field] = snapshot[field]
        #     return result
        # except PageFailure as exc:
        #     errors.append({"url": url, "error": str(exc)})
        #     return None

    result = attempt(department["requested_url"])
    if result:
        return result
    try:
        homepage, _ = loader.load(department["home_url"])
        for url in faculty_links(homepage, department)[:4]:
            if url not in tried:
                result = attempt(url)
                if result:
                    return result
    except PageFailure as exc:
        errors.append({"url": department["home_url"], "error": str(exc)})
    return {**department, "status": "failed", "attempt_errors": errors}


def save_json(path, report):
    report["updated_at"] = now()
    report["summary"] = {
        status: sum(x["status"] == status for x in report["departments"])
        for status in ("success", "failed", "parse_failed", "pending")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as f:
            temp_path = Path(f.name)
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def crawl(loader, output, selected=(), limit=None, resume=False):
    previous = {}
    if resume:
        if not output.is_file():
            raise PageFailure(f"找不到断点文件：{output}")
        old = json.loads(output.read_text(encoding="utf-8"))
        if old.get("schema_version") != 1 or old.get("source_url") != DIRECTORY_URL:
            raise PageFailure("断点文件的格式或来源不匹配。")
        previous = {x["code"]: x for x in old["departments"]}
    directory, _ = loader.load(DIRECTORY_URL)
    departments = discover_departments(directory)
    if not departments:
        raise PageFailure("目录中没有找到部门链接；请检查是否仍显示验证页。")
    if selected:
        unknown = set(selected) - {x["code"] for x in departments}
        if unknown:
            raise PageFailure("目录中没有这些部门代码：" + ", ".join(sorted(unknown)))
        departments = [x for x in departments if x["code"] in selected]
    if limit:
        departments = departments[:limit]
    if resume and set(previous) != {x["code"] for x in departments}:
        raise PageFailure("恢复时的部门范围与原文件不一致，请使用原来的 --department/--limit 参数。")
    report = {"schema_version": 1, "source_url": DIRECTORY_URL, "started_at": now(),
              "completed": False, "departments": []}
    for department in departments:
        old = previous.get(department["code"])
        report["departments"].append(old if old and old["status"] == "success"
                                     else {**department, "status": "pending"})
    save_json(output, report)
    try:
        for index, department in enumerate(departments):
            print(f"[{index + 1}/{len(departments)}] {department['department']}", flush=True)
            if report["departments"][index]["status"] == "success":
                print("  已有成功结果，跳过。", flush=True)
                continue
            report["departments"][index] = export_department(loader, department)
            print("  结果：" + report["departments"][index]["status"], flush=True)
            save_json(output, report)
        report["completed"] = True
    finally:
        save_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="JSON 输出路径")
    parser.add_argument("--department", action="append", default=[], help="只抓这个部门代码，可重复指定")
    parser.add_argument("--limit", type=int, help="只处理前 N 个部门")
    parser.add_argument("--resume", action="store_true", help="保留成功结果，重试失败和未完成部门")
    parser.add_argument("--delay", type=float, default=2, help="页面访问之间至少间隔的秒数，默认 2")
    parser.add_argument("--no-interaction", action="store_true", help="遇验证页时记录失败，不等待手动操作")
    args = parser.parse_args()
    if args.delay < 0.5 or (args.limit is not None and args.limit < 1):
        parser.error("--delay 至少为 0.5，--limit 必须为正整数。")
    output = args.out.expanduser().resolve()
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        sys.exit("请先激活作业虚拟环境，再运行 python -m pip install playwright。")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                context = browser.new_context()
                loader = BrowserLoader(context.new_page(), args.delay, not args.no_interaction)
                report = crawl(loader, output, args.department, args.limit, args.resume)
            finally:
                browser.close()
        print(f"已保存：{output}\n统计：{report['summary']}")
        if report["summary"]["failed"]:
            print("部分部门没有抓取成功；查看 attempt_errors，或使用 --resume 重试。")
        if report["summary"]["parse_failed"]:
            print("部分部门抓取成功，但解析失败；查看 parse_errors,and saved html files。")
        if report["summary"]["failed"] or report["summary"]["parse_failed"]:
            return 2

        return 0
    except (KeyboardInterrupt, EOFError):
        message = f"已停止；可查看已有结果文件：{output}" if output.is_file() else "已停止；尚未创建结果文件。"
        print(message, file=sys.stderr)
        return 130
    except (PageFailure, PlaywrightError, OSError, ValueError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
