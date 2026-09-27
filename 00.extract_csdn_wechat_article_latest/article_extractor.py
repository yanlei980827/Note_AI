"""Shared logic for extracting web articles to Markdown with local images."""

from __future__ import annotations

import base64
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
from urllib.parse import parse_qs, unquote_to_bytes, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown


ProgressCallback = Callable[[str, int, int], None]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

IMAGE_EXTENSIONS = {
    "jpg": ".jpg",
    "jpeg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "bmp": ".bmp",
    "svg": ".svg",
    "ico": ".ico",
    "avif": ".avif",
    "jfif": ".jpg",
}

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/avif": ".avif",
}

WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"}
SVG_TEXT_HINT_RE = re.compile(r"[┌┐└┘├┤│─]")

# 每次成功写入后，把「文章链接 | Markdown 文件路径」追加到当前 Markdown
# 同级目录下的 backup.md，便于日后回溯每个链接写进了哪个 Markdown。
ARTICLE_BACKUP_FILE = Path("backup.md")


@dataclass
class ArticleMetadata:
    title: str
    author: str = ""
    publish_time: str = ""
    url: str = ""


@dataclass
class ArticleExtraction:
    metadata: ArticleMetadata
    markdown: str
    image_count: int
    markdown_path: Path
    body_html: str = ""


def build_session(referer: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer,
        }
    )
    return session


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("链接不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("请输入有效的 http/https 链接")
    return url


def make_safe_filename(name: str, fallback: str = "article") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    cleaned = cleaned[:100].rstrip(" .")
    if not cleaned:
        cleaned = fallback
    upper = cleaned.upper()
    if upper in WINDOWS_RESERVED_NAMES or re.match(
        r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\.", upper
    ):
        cleaned = "_" + cleaned
    return cleaned


def _newline_to(text: str, newline: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline == "\n":
        return normalized
    return normalized.replace("\n", newline)


def _normalize_append_tail(raw: str, newline: str) -> str:
    """Trim trailing blank lines and standalone horizontal rules so the
    appended ``---`` separator never forms a Setext heading with the
    existing article's last paragraph."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    while (
        lines
        and lines[-1].strip() == "---"
        and (len(lines) == 1 or not lines[-2].strip())
    ):
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    base = "\n".join(lines)
    if newline == "\n":
        return base
    return base.replace("\n", newline)


# ---- 目录（TOC）相关 ----
TOC_START_MARKER = "<!-- toc-start -->"
TOC_END_MARKER = "<!-- toc-end -->"
TOC_INDENT = "　　"


def heading_slug(text: str) -> str:
    """GitHub 风格锚点：小写、去标点、空白转连字符。

    Markdown 目录链接与 PDF 标题 id 共用此函数，保证点击跳转一致。
    """
    slug = re.sub(r"\s+", "-", (text or "").strip().lower())
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "section"


def _extract_headings(markdown: str):
    """Return [(level, text), ...] for ATX headings outside code fences and the TOC block."""
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    headings = []
    in_fence = False
    in_toc = False
    for line in normalized.split("\n"):
        if TOC_START_MARKER in line:
            in_toc = True
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            continue
        if in_toc:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            text = match.group(2).strip()
            if text:
                headings.append((len(match.group(1)), text))
    return headings


def _strip_toc_block(markdown: str, newline: str = "\n") -> str:
    """Remove the generated TOC block (markers + list + following ---)."""
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    start = end = None
    for index, line in enumerate(lines):
        if start is None and TOC_START_MARKER in line:
            start = index
        elif TOC_END_MARKER in line:
            end = index
    if start is None or end is None or end < start:
        return markdown
    rest = lines[end + 1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    if rest and rest[0].strip() == "---":
        rest.pop(0)
    while rest and not rest[0].strip():
        rest.pop(0)
    head = lines[:start]
    while head and not head[-1].strip():
        head.pop()
    cleaned = "\n".join(head + rest)
    if newline == "\n":
        return cleaned
    return cleaned.replace("\n", newline)


def _build_toc_block(markdown: str, newline: str = "\n") -> str:
    """Generate the TOC block for the given markdown (or "" when no headings)."""
    headings = [item for item in _extract_headings(markdown) if item[0] <= 3]
    if not headings:
        return ""
    toc_lines = [TOC_START_MARKER, "", "# 目录", ""]
    for level, text in headings:
        indent = TOC_INDENT * (level - 1)
        # 链接标签里转义方括号，避免标题含 [0] 之类时破坏 markdown 链接
        label = text.replace("[", "\\[").replace("]", "\\]")
        toc_lines.append(f"{indent}[{label}](#{heading_slug(text)})  ")
    toc_lines += ["", TOC_END_MARKER, "", "---"]
    block = "\n".join(toc_lines)
    if newline == "\n":
        return block
    return block.replace("\n", newline)


def _ensure_toc(markdown: str, newline: str = "\n") -> str:
    """Regenerate the TOC at the top of the markdown and return the new text.

    The existing TOC (if any) is removed first, then rebuilt from the
    current headings so appends never leave stale entries.
    """
    stripped = _strip_toc_block(markdown, newline)
    toc = _build_toc_block(stripped, newline)
    if not toc:
        return markdown
    body = _newline_to(stripped, "\n").lstrip("\n")
    body = _newline_to(body, newline)
    if not body:
        return toc
    return toc + newline + newline + body


def _refresh_numbering_and_toc(markdown: str, newline: str = "\n") -> str:
    """Renumber the current document body and rebuild the TOC.

    The file may already contain a generated TOC at the top. We strip it out
    first, renumber all headings from the current document structure, and then
    generate a fresh TOC so manual edits to earlier headings are reflected on
    the next write.
    """
    body = _strip_toc_block(markdown, "\n")
    numbered = _number_headings(body, start_article=1)
    return _ensure_toc(numbered, newline)


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# 剥离标题开头的原有序号，避免与软件自动编号重叠：
#   阿拉伯数字  1、 1. 1.2 1：
#   中文数字   一、 十一、 二〇
#   罗马数字   Ⅰ、 Ⅱ. I. III、
#   圈号       ① ⑴ ⒈
#   括号序号   （一）（1）
#   第X章     第一章 第2节
HEADING_NUMBER_STRIP_RE = re.compile(
    r"^\s*(?:"
    r"\d+(?:[.．]\d+)*(?=[、.．:：)）\s]|$)[、.．:：)）]*\s*"
    r"|[一二三四五六七八九十百千万零两〇]+(?=[、.．:：)）\s]|$)[、.．:：)）]*\s*"
    r"|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅺⅻ]+(?=[、.．:：)）\s]|$)[、.．:：)）]*\s*"
    r"|[ivxlcdmIVXLCDM]+(?=[、.．:：)）]|$)[、.．:：)）]*\s*"
    r"|[\u2460-\u249B]+[、.．:：)）]?\s*"
    r"|[（(]\s*[一二三四五六七八九十百千万零两〇\d]+\s*[)）]"
    r"|第\s*[一二三四五六七八九十百千万零两〇\d]+\s*[章节篇部课讲回][、.．:：)）]?\s*"
    r")"
)
# 序号剥离后可能残留的引导分隔符：第一章：POR -> ：POR
HEADING_LEAD_SEPARATOR_RE = re.compile(r"^[、.．:：)）\s]+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _strip_heading_ordinal(text: str) -> str:
    """Remove leading article ordinals (1、 一、 Ⅰ、 ① 第一章 ...) from a heading."""
    text = text.strip()
    original = text
    while HEADING_NUMBER_STRIP_RE.match(text):
        text = HEADING_NUMBER_STRIP_RE.sub("", text, count=1)
    text = HEADING_LEAD_SEPARATOR_RE.sub("", text)
    return text if text else original


def _heading_text_key(text: str) -> str:
    """Heading comparison key ignoring all whitespace."""
    return "".join(text.split())


def _next_nonblank(lines, index: int) -> str:
    for i in range(index + 1, len(lines)):
        if lines[i].strip():
            return lines[i].strip()
    return ""


def _is_article_start(lines, index: int, article: int) -> bool:
    """A ``#`` heading starts a new article only when it is the first heading
    in the file, or when it is followed by the ``> 来源：`` metadata block
    (which the tool writes for every real article). Other ``#`` headings are
    body headings of the current article (WeChat/CSDN articles often contain
    their own ``#`` headings) and are demoted to H2 so one extracted article
    never splits into several numbered articles."""
    if article == 0:
        return True
    return _next_nonblank(lines, index).startswith("> 来源：")


def _number_headings(markdown: str, start_article: int = 1) -> str:
    """Prefix ATX headings with per-article hierarchy numbers.

    Each top-level ``#`` that starts a new article becomes ``# 1.``, ``# 2.`` ...;
    inside an article H2/H3/... become ``1.1``, ``1.1.1`` ...
    ``#`` headings that appear inside an article body (no ``> 来源：`` metadata
    and not after a ``---`` separator) are treated as the article's own
    section headings and demoted to ``##`` so one extracted article never
    splits into several numbered articles.
    Tool-added numbers and original article ordinals (Arabic "1、",
    Chinese "一、", Roman "Ⅰ、", circled "①", bracketed "（一）" and
    "第X章" forms) are stripped before renumbering so appends keep the
    numbering stable without duplicated ordinals.
    If an article body starts with a heading identical to its title (many
    WeChat/CSDN articles repeat the title inside the content), that duplicate
    is skipped so the title is not numbered twice.
    """
    newline = "\r\n" if "\r\n" in markdown else "\n"
    lines = markdown.replace("\r\n", "\n").split("\n")
    out = []
    article = max(1, start_article) - 1
    counters = [0] * 6
    in_fence = False
    article_title = ""
    first_body_heading_seen = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if in_fence:
            out.append(line)
            continue
        heading = HEADING_RE.match(line)
        if heading is None:
            out.append(line)
            continue
        level = len(heading.group(1))
        text = _strip_heading_ordinal(heading.group(2))
        if level == 1 and not _is_article_start(lines, index, article):
            level = 2
        if level == 1:
            article += 1
            counters = [0] * 6
            article_title = _heading_text_key(text)
            first_body_heading_seen = False
        elif not first_body_heading_seen:
            first_body_heading_seen = True
            if article_title and _heading_text_key(text) == article_title:
                # 正文第一个标题与文章标题完全相同：视为标题重复，不再编号
                continue
        if article == 0:
            article = 1
        counters[level - 1] += 1
        for i in range(level, 6):
            counters[i] = 0
        # 一级标题编号带点号（# 1. 标题），子级沿用 1.1 / 1.1.1 层级
        number = str(article) + "." + ".".join(str(c) for c in counters[1:level])
        out.append("#" * level + " " + number + " " + text)
    result = "\n".join(out)
    if newline == "\n":
        return result
    return result.replace("\n", newline)


def _next_article_number(markdown: str) -> int:
    """Infer the next article number from existing content without changing it."""
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    in_fence = False
    in_toc = False
    h1_count = 0
    max_number = 0
    for line in lines:
        if TOC_START_MARKER in line:
            in_toc = True
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            continue
        if in_toc:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match or len(match.group(1)) != 1:
            continue
        h1_count += 1
        number = re.match(r"^\s*(\d+)(?=[.．、\s]|$)", match.group(2))
        if number:
            max_number = max(max_number, int(number.group(1)))
    return max(max_number, h1_count) + 1


def _ends_with_standalone_hr(markdown: str) -> bool:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[-1].strip() != "---":
        return False
    return len(lines) == 1 or not lines[-2].strip()


def _linebreak_count_at_end(text: str, newline: str) -> int:
    count = 0
    while text.endswith(newline * (count + 1)):
        count += 1
    return count


def _append_article_preserving_existing(raw: str, markdown: str, newline: str) -> str:
    """Append a new article block to the existing raw text.

    This helper only handles the low-level join/separator layout. The caller
    may still renumber headings and rebuild the TOC afterward.
    """
    article = _newline_to(markdown, newline)
    trailing_breaks = _linebreak_count_at_end(raw, newline)
    gap = newline * max(0, 2 - trailing_breaks)
    if _ends_with_standalone_hr(raw):
        return raw + gap + article
    return raw + gap + "---" + newline + newline + article


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _svg_text_content(svg) -> str:
    """Return visible text from a meaningful SVG, or "" when it looks decorative."""
    text = (svg.get_text("\n") or "").replace("\xa0", " ").replace("\r", "")
    lines = [line.rstrip() for line in text.split("\n")]
    visible = [line for line in lines if line.strip()]
    if len(visible) < 3:
        return ""
    joined = "\n".join(visible).strip("\n")
    if not joined:
        return ""
    if SVG_TEXT_HINT_RE.search(joined):
        return joined
    return ""


def _svg_markup_text_content(svg_markup: str) -> str:
    """Return visible text from an SVG markup string, or "" when it looks decorative."""
    markup = (svg_markup or "").strip()
    if not markup:
        return ""
    soup = BeautifulSoup(markup, "html.parser")
    svg = soup.find("svg")
    if svg is None:
        return ""
    return _svg_text_content(svg)


def _svg_data_uri_text_content(source: str) -> str:
    """Decode an SVG data URI and return its visible text content when textual."""
    source = (source or "").strip()
    if not source.startswith("data:image/svg+xml"):
        return ""
    header, _, payload = source.partition(",")
    if not payload:
        return ""
    try:
        if ";base64" in header:
            raw = base64.b64decode(payload)
        else:
            raw = unquote_to_bytes(payload)
    except Exception:
        return ""
    return _svg_markup_text_content(raw.decode("utf-8", errors="ignore"))


def _make_preformatted_block(text: str):
    """Build a small <pre><code> block so markdownify preserves line breaks."""
    factory = BeautifulSoup("", "html.parser")
    pre = factory.new_tag("pre")
    code = factory.new_tag("code")
    code.string = text
    pre.append(code)
    return pre


def _article_url_from_line(line: str) -> str:
    """Return the URL on a ``> 来源：URL`` line ("" when not a source line)."""
    text = (line or "").strip()
    prefix = "> 来源："
    if not text.startswith(prefix):
        return ""
    return text[len(prefix):].strip()


def _article_url_from_markdown(markdown: str) -> str:
    """Return the first ``> 来源：URL`` found in ``markdown`` ("" if missing)."""
    normalized = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.split("\n"):
        url = _article_url_from_line(line)
        if url:
            return url
    return ""


def _replace_article_by_url(
    raw: str,
    markdown: str,
    url: str,
    newline: str,
) -> Optional[str]:
    """Replace the first article whose ``> 来源：`` matches ``url`` with the
    freshly extracted ``markdown``.

    The matched article keeps its position in the raw document layout; the
    caller may still renumber headings and rebuild the TOC afterward.
    Returns the new file text, or None when ``url`` is empty or no article
    matches (the caller should fall back to appending a new article).
    """
    url = (url or "").strip()
    if not url:
        return None
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    start = None
    article_number = None
    in_toc = False
    in_fence = False
    for index, line in enumerate(lines):
        if TOC_START_MARKER in line:
            in_toc = True
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            continue
        if in_toc:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.startswith("# "):
            continue
        source_line = _next_nonblank(lines, index)
        if not source_line.startswith("> 来源："):
            continue
        if _article_url_from_line(source_line) != url:
            continue
        number_match = re.match(r"^#\s*(\d+)\s*[.、．]?\s*", line)
        if number_match:
            article_number = int(number_match.group(1))
        start = index
        break
    if start is None:
        return None
    if article_number is None:
        article_number = _next_article_number(raw)

    end = None
    in_toc = False
    in_fence = False
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if TOC_START_MARKER in line:
            in_toc = True
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            continue
        if in_toc:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # 文章边界以下一个 ``# N.`` 文章标题为准，正文里的 --- 分隔线不算边界
        if line.startswith("# ") and _next_nonblank(lines, index).startswith("> 来源："):
            end = index
            break

    numbered = _number_headings(
        _newline_to(markdown, newline),
        start_article=article_number,
    )
    article_lines = numbered.replace("\r\n", "\n").split("\n")
    while article_lines and not article_lines[-1].strip():
        article_lines.pop()

    if end is None:
        new_lines = lines[:start] + article_lines
    else:
        new_lines = lines[:start] + article_lines + ["", "---", ""] + lines[end:]
    combined = "\n".join(new_lines).rstrip("\n") + "\n"
    return _newline_to(combined, newline)


UPDATE_TIME_RE = re.compile(
    r"> update\s+(\d{4})/(\d{2})/(\d{2})\s+(\d{2})\s*:\s*(\d{2})"
)


def _article_update_time(lines, start: int):
    """Parse the ``> update YYYY/MM/DD HH : MM`` stamp after an article heading.

    Returns a datetime, or None when the article has no parseable stamp.
    """
    for index in range(start, min(start + 12, len(lines))):
        match = UPDATE_TIME_RE.search(lines[index])
        if match:
            try:
                return datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                    int(match.group(5)),
                )
            except ValueError:
                return None
    return None


def _trim_article_tail(text: str) -> str:
    """Remove the trailing ``---`` separator block from an article segment."""
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == "---":
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines)


def _collect_articles(lines):
    """Split a normalized (LF) markdown text into article segments.

    Each segment spans from a ``# N.`` article heading (followed by
    ``> 来源：``) to the next article heading (exclusive). The TOC region and
    code fences are skipped, and the trailing ``---`` separator is trimmed, so
    ``---`` lines inside an article body (WeChat horizontal rules) never split
    an article. Returns a list of dicts with keys ``url``, ``update`` and
    ``text``.
    """
    articles = []
    start = None
    url = ""
    in_toc = False
    in_fence = False
    for index, line in enumerate(lines):
        if TOC_START_MARKER in line:
            in_toc = True
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            continue
        if in_toc:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("# ") and _next_nonblank(lines, index).startswith("> 来源："):
            if start is not None:
                articles.append(
                    {
                        "start": start,
                        "url": url,
                        "update": _article_update_time(lines, start),
                        "text": _trim_article_tail(
                            "\n".join(lines[start:index])
                        ),
                    }
                )
            start = index
            url = _article_url_from_line(_next_nonblank(lines, index))
    if start is not None:
        articles.append(
            {
                "start": start,
                "url": url,
                "update": _article_update_time(lines, start),
                "text": _trim_article_tail("\n".join(lines[start:])),
            }
        )
    return articles


def deduplicate_markdown(markdown: str) -> Optional[str]:
    """Remove duplicate articles that share the same ``> 来源：`` URL.

    For each URL only the copy with the newest ``> update`` stamp is kept
    (ties keep the last copy, i.e. the most recently appended one); the other
    duplicates are dropped, all articles are renumbered 1..N, and a fresh TOC
    is rebuilt. Returns the new text, or None when there is nothing to dedup.
    """
    newline = "\r\n" if "\r\n" in markdown else "\n"
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    articles = _collect_articles(lines)
    if len(articles) < 2:
        return None
    by_url = {}
    for article in articles:
        by_url.setdefault(article["url"], []).append(article)
    duplicate_groups = [group for group in by_url.values() if len(group) > 1]
    if not duplicate_groups:
        return None
    keep_ids = set()
    for group in duplicate_groups:
        best = max(
            group,
            key=lambda article: (article["update"] or datetime.min, article["start"]),
        )
        keep_ids.add(id(best))
    kept = [
        article
        for article in articles
        if len(by_url[article["url"]]) == 1 or id(article) in keep_ids
    ]
    pieces = []
    for number, article in enumerate(kept, start=1):
        numbered = _number_headings(article["text"], start_article=number)
        pieces.append(numbered.replace("\r\n", "\n").rstrip("\n"))
    combined = "\n\n---\n\n".join(pieces) + "\n"
    combined = _newline_to(combined, newline)
    return _ensure_toc(combined, newline)


@dataclass
class DedupSummary:
    removed: int
    remaining: int
    backup_path: Optional[Path]


@dataclass
class RefreshSummary:
    backup_path: Optional[Path]


def refresh_markdown_structure_file(
    target: Union[str, os.PathLike],
    backup: bool = True,
) -> Optional[RefreshSummary]:
    """Renumber headings and rebuild the TOC for ``target`` in place.

    This is the file-level version of ``_refresh_numbering_and_toc`` used by
    the GUI button. A timestamped ``.bak-YYYYMMDD_HHMMSS`` copy of the
    original is written next to the file before the change (unless ``backup``
    is False). Returns a ``RefreshSummary`` when the file changed, or ``None``
    when the file is already up to date.
    """
    path = Path(target)
    if not path.is_file():
        raise ValueError(f"目标文件不存在：{path}")
    raw = path.read_text(encoding="utf-8", newline="")
    newline = "\r\n" if "\r\n" in raw else "\n"
    result = _refresh_numbering_and_toc(raw, newline)
    if result == raw:
        return None

    backup_path = None
    if backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
        backup_path.write_text(raw, encoding="utf-8", newline="")
    _atomic_write(path, result)
    return RefreshSummary(backup_path=backup_path)


def deduplicate_markdown_file(
    target: Union[str, os.PathLike],
    backup: bool = True,
) -> Optional[DedupSummary]:
    """Remove duplicate articles from ``target`` in place.

    A timestamped ``.bak-YYYYMMDD_HHMMSS`` copy of the original is written
    next to the file before the change (unless ``backup`` is False). Returns a
    ``DedupSummary`` with the removed/remaining counts and the backup path,
    or None when the file has no duplicate articles.
    """
    path = Path(target)
    if not path.is_file():
        raise ValueError(f"目标文件不存在：{path}")
    raw = path.read_text(encoding="utf-8", newline="")
    result = deduplicate_markdown(raw)
    if result is None:
        return None
    newline = "\r\n" if "\r\n" in raw else "\n"
    backup_path = None
    if backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
        backup_path.write_text(raw, encoding="utf-8", newline="")
    _atomic_write(path, result)
    before = len(
        _collect_articles(raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    )
    remaining = len(_collect_articles(result.replace("\r\n", "\n").split("\n")))
    return DedupSummary(
        removed=max(0, before - remaining),
        remaining=remaining,
        backup_path=backup_path,
    )


def write_markdown_file(
    markdown: str,
    target: Union[str, os.PathLike],
    mode: str = "append",
    progress: Optional[ProgressCallback] = None,
    url: str = "",
) -> Path:
    """Write markdown to target.

    Existing non-empty files are refreshed on every write: the chosen article
    text is appended or replaced, then the whole document is renumbered and
    the TOC at the top is rebuilt from the current headings. This keeps the
    file consistent even after manual edits to earlier titles. Every
    successful write also appends ``文章链接 | Markdown 文件路径`` to the
    ``backup.md`` file beside ``target``. When ``url`` is empty, the first
    ``> 来源：`` line in ``markdown`` is used as a fallback source URL.
    """

    target = Path(target)
    mode = (mode or "append").lower()
    if mode not in ("append", "replace"):
        raise ValueError(f"不支持的模式：{mode}")

    if target.is_dir():
        raise ValueError("目标路径是目录，请选择 .md 文件路径")

    if target.exists() and target.is_file():
        raw = target.read_text(encoding="utf-8", newline="")
        newline = "\r\n" if "\r\n" in raw else "\n"
        if raw.strip():
            if mode == "replace":
                raise ValueError(
                    "目标 Markdown 文件已有内容。为避免覆盖原内容，已取消写入；"
                    "请改用续写模式，或选择空文件/新文件。"
                )
            replaced = _replace_article_by_url(raw, markdown, url, newline)
            if replaced is not None:
                # 同一链接再次写入时先原地替换，再按当前文档结构统一重编号。
                final = _refresh_numbering_and_toc(replaced, newline)
                _atomic_write(target, final)
                _notify(progress, "检测到该文章链接已存在，已用最新内容覆盖更新原文章")
            else:
                combined = _append_article_preserving_existing(raw, markdown, newline)
                # 先追加，再按当前文档结构统一重编号并重建目录。
                final = _refresh_numbering_and_toc(combined, newline)
                _atomic_write(target, final)
                _notify(progress, "已有非空文件：已追加新文章，并按当前结构更新标题序号与目录")

        else:
            # 空文件/纯空白文件：直接写入新文章和目录，不加前置分隔符，
            # 避免文件以 --- 开头被 Typora 等编辑器误识别为 YAML front matter。
            _atomic_write(target, _refresh_numbering_and_toc(markdown, newline))
    else:
        newline = "\r\n" if os.name == "nt" else "\n"
        _atomic_write(target, _refresh_numbering_and_toc(markdown, newline))

    backup_url = (url or "").strip() or _article_url_from_markdown(markdown)
    backup_path = _article_backup_path(target)
    logged = log_article_backup(backup_url, target)
    if backup_url:
        if logged is not None:
            _notify(progress, f"已记录文章链接到备份文件：{logged}")
        else:
            _notify(progress, f"文章链接备份失败：{backup_path}")
    return target


def _notify(progress: Optional[ProgressCallback], message: str, done: int = 0, total: int = 0) -> None:
    if progress is None:
        return
    try:
        progress(message, done, total)
    except Exception:
        pass

def _next_backup_number(backup: Path) -> int:
    """叠加下一条序号：统计已有非空行数 + 1。"""
    if not backup.is_file():
        return 1
    count = 0
    try:
        with open(backup, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.strip():
                    count += 1
    except OSError:
        return 1
    return count + 1


def _article_backup_path(markdown_path: Union[str, os.PathLike]) -> Path:
    """Return the backup file path beside ``markdown_path``."""
    backup_name = Path(ARTICLE_BACKUP_FILE).name or "backup.md"
    return Path(markdown_path).expanduser().resolve().with_name(backup_name)


def log_article_backup(
    url: str,
    markdown_path: Union[str, os.PathLike],
) -> Optional[Path]:
    """Append ``序号 | 日期时间 | 文章链接 | Markdown 文件路径`` to the
    ``backup.md`` file beside ``markdown_path``.

    Called after every successful write so each extracted article link maps
    one-to-one to the Markdown file it was written into. The sequence number
    continues from the existing entries, and the stamp is ``%Y/%m/%d %H:%M:%S``.
    Returns the backup path, or None when ``url`` is empty or the append
    fails (a backup failure must never block article extraction).
    """
    url = (url or "").strip()
    if not url:
        return None
    backup = _article_backup_path(markdown_path)
    try:
        backup.parent.mkdir(parents=True, exist_ok=True)
        number = _next_backup_number(backup)
        stamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        resolved = Path(markdown_path).expanduser().resolve()
        with open(backup, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{number} | {stamp} | {url} | {resolved}\n")
        return backup
    except OSError:
        return None


def guess_extension(url: str, content_type: str = "") -> str:
    parsed = urlparse(url)
    fmt = parse_qs(parsed.query).get("wx_fmt", [""])[0].lower()
    if fmt in IMAGE_EXTENSIONS:
        return IMAGE_EXTENSIONS[fmt]
    suffix = os.path.splitext(parsed.path)[1].lower()
    if suffix == ".jpeg":
        return ".jpg"
    if suffix in IMAGE_EXTENSIONS.values():
        return suffix
    mime = content_type.split(";")[0].strip().lower()
    if mime in CONTENT_TYPE_EXTENSIONS:
        return CONTENT_TYPE_EXTENSIONS[mime]
    return ".jpg"


class BaseArticleExtractor:
    """Shared article page fetching, image downloading and Markdown conversion."""

    source_label = "文章"
    referer = ""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
        cookie: str = "",
    ) -> None:
        self._session = session or build_session(self.referer)
        if cookie:
            self._session.headers["Cookie"] = cookie
        self.timeout = timeout

    def extract_article_html(
        self,
        url: str,
        markdown_path: Optional[Union[str, os.PathLike]] = None,
        progress: Optional[ProgressCallback] = None,
        save_screenshot: bool = False,
    ) -> ArticleExtraction:
        url = validate_url(url)
        extraction_time = datetime.now()

        _notify(progress, f"正在获取{self.source_label}文章页面...")
        html_text = self._fetch_page(url)
        _notify(progress, "正在解析文章内容...")

        soup = self._parse_html(html_text)
        metadata = self._extract_metadata(soup, url)
        markdown_path = self._resolve_markdown_path(markdown_path, metadata.title)
        base_dir = markdown_path.parent
        assets_dir = base_dir / f"{markdown_path.stem}_assets"
        image_start = self._existing_max_image_index(markdown_path, assets_dir) + 1

        content_node = self._find_content(soup)
        if content_node is None:
            raise ValueError(f"未能识别{self.source_label}文章正文，可能链接不是有效文章页")

        self._remove_noise(content_node)
        self._normalize_code_blocks(content_node)
        self._drop_empty_headings(content_node)
        self._merge_list_heading_content(content_node)
        _notify(progress, "正在下载文章图片...")
        image_count = self._localize_images(
            content_node,
            assets_dir,
            base_dir,
            image_start,
            progress,
        )

        body_html = str(content_node)
        body_markdown = self._convert_body(body_html)
        if not body_markdown.strip():
            raise ValueError("文章正文为空，未能提取到有效内容")
        markdown = self._build_markdown(
            metadata,
            body_markdown,
            extraction_time,
            save_screenshot=save_screenshot,
        )
        _notify(progress, "转换完成")
        return ArticleExtraction(
            metadata=metadata,
            markdown=markdown,
            image_count=image_count,
            markdown_path=markdown_path,
            body_html=body_html,
        )

    def _fetch_page(self, url: str) -> str:
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    @staticmethod
    def _parse_html(html_text: str) -> BeautifulSoup:
        try:
            return BeautifulSoup(html_text, "lxml")
        except Exception:
            return BeautifulSoup(html_text, "html.parser")

    @staticmethod
    def _extract_metadata(soup: BeautifulSoup, url: str) -> ArticleMetadata:
        raise NotImplementedError

    @staticmethod
    def _find_content(soup: BeautifulSoup):
        raise NotImplementedError

    @staticmethod
    def _resolve_markdown_path(
        markdown_path: Optional[Union[str, os.PathLike]],
        title: str,
    ) -> Path:
        if markdown_path is None:
            return Path.cwd() / f"{make_safe_filename(title)}.md"
        path = Path(markdown_path).expanduser()
        if path.is_dir():
            return path / f"{make_safe_filename(title)}.md"
        return path

    @staticmethod
    def _existing_max_image_index(markdown_path: Path, assets_dir: Path) -> int:
        max_index = 0
        pattern = re.compile(r"^image-(\d+)\.[A-Za-z0-9]+$")
        if assets_dir.is_dir():
            for name in os.listdir(assets_dir):
                match = pattern.match(name)
                if match:
                    max_index = max(max_index, int(match.group(1)))
        if markdown_path.is_file():
            try:
                text = markdown_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            reference_pattern = re.compile(r"image-(\d+)\.[A-Za-z0-9]+")
            for match in reference_pattern.finditer(text):
                max_index = max(max_index, int(match.group(1)))
        return max_index

    @staticmethod
    def _remove_noise(content_node) -> None:
        for svg in content_node.find_all("svg"):
            text = _svg_text_content(svg)
            if text:
                svg.replace_with(text)
            else:
                svg.decompose()
        for tag in content_node.find_all(["script", "style", "noscript", "iframe"]):
            tag.decompose()

    @staticmethod
    def _drop_empty_headings(content_node) -> None:
        """Remove headings without visible text so markdownify does not emit bare markers."""
        for tag in content_node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            if not tag.get_text(strip=True):
                tag.decompose()

    @staticmethod
    def _merge_list_heading_content(content_node) -> None:
        """Hook for subclasses to adjust list structure before conversion."""
        return None

    @staticmethod
    def _normalize_code_blocks(content_node) -> None:
        for pre in content_node.find_all("pre"):
            code = pre.find("code")
            if code is None:
                continue
            text = code.get_text("\n")
            text = text.replace("\xa0", " ")
            lines = [line.rstrip() for line in text.split("\n")]
            normalized = []
            blank = 0
            for line in lines:
                if not line.strip():
                    blank += 1
                    if blank > 1:
                        continue
                else:
                    blank = 0
                normalized.append(line)
            clean_text = "\n".join(normalized).strip("\n") + "\n"
            code.clear()
            code.string = clean_text

    def _localize_images(
        self,
        content_node,
        assets_dir: Path,
        base_dir: Path,
        start_index: int,
        progress: Optional[ProgressCallback],
    ) -> int:
        images = content_node.find_all("img")
        count = 0
        for offset, img in enumerate(images):
            index = start_index + offset
            source = self._image_source(img)
            source = str(source).strip()
            alt = img.get("alt") or ""
            if not source:
                img.decompose()
                continue

            # 微信偶尔会把正文里的流程图/时间轴塞进 SVG data URI。
            # 如果这个 SVG 本身就是文本图示，直接展开成 pre/code，
            # 这样正文不会只剩下一张空图片。
            textual_svg = _svg_data_uri_text_content(source)
            if textual_svg:
                img.replace_with(_make_preformatted_block(textual_svg))
                continue

            local_name = self._download_image(
                source,
                assets_dir,
                index,
                progress,
                total=len(images),
            )
            img.clear()
            img["alt"] = alt
            if local_name:
                if local_name.suffix.lower() == ".svg":
                    try:
                        svg_text = _svg_markup_text_content(
                            local_name.read_text(encoding="utf-8", errors="ignore")
                        )
                    except OSError:
                        svg_text = ""
                    if svg_text:
                        try:
                            local_name.unlink()
                        except OSError:
                            pass
                        img.replace_with(_make_preformatted_block(svg_text))
                        continue
                relative = os.path.relpath(str(local_name), str(base_dir)).replace("\\", "/")
                img["src"] = relative
                count += 1
            else:
                img["src"] = source
        return count

    @staticmethod
    def _image_source(img) -> str:
        return (
            img.get("data-src")
            or img.get("data-original")
            or img.get("data-url")
            or img.get("src")
            or ""
        )

    def _download_image(
        self,
        source: str,
        assets_dir: Path,
        index: int,
        progress: Optional[ProgressCallback],
        total: int,
    ) -> Optional[Path]:
        url = source.strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith(("http://", "https://")):
            return None

        try:
            response = self._session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            extension = guess_extension(url, response.headers.get("Content-Type", ""))
            assets_dir.mkdir(parents=True, exist_ok=True)
            local_path = assets_dir / f"image-{index:04d}{extension}"
            while local_path.exists():
                index += 1
                local_path = assets_dir / f"image-{index:04d}{extension}"
            _notify(progress, f"正在下载图片 {index}/{total}", index - 1, total)
            with open(local_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        handle.write(chunk)
            _notify(progress, f"图片 {index}/{total} 下载完成", index, total)
            return local_path
        except Exception:
            return None

    @staticmethod
    def _convert_body(body_html: str) -> str:
        markdown = html_to_markdown(
            body_html,
            heading_style="ATX",
            bullets="-",
            strip=["script", "style", "iframe"],
        )
        markdown = re.sub(r"[ \t]+\n", "\n", markdown)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
        return markdown + "\n"

    def _build_markdown(
        self,
        metadata: ArticleMetadata,
        body_markdown: str,
        extraction_time: datetime,
        save_screenshot: bool = False,
    ) -> str:
        lines = [
            f"# {metadata.title}",
            "",
            f"> 来源：{metadata.url}",
        ]
        lines.extend(self._metadata_lines(metadata))
        lines.append(
            f"> update {extraction_time.strftime('%Y/%m/%d %H : %M')}"
        )
        if save_screenshot:
            # 勾选「保存长截图」时，在 update 引用块内追加加粗“已截图”标记
            lines.append("> **已截图**")
        lines.append("")
        # 引用块（> update ...）与正文之间必须有空行，否则 CommonMark/Typora 的
        # lazy continuation 会把紧贴的正文第一段并进引用块渲染（debug.md 复现过）
        return "\n".join(lines) + "\n" + body_markdown

    def _metadata_lines(self, metadata: ArticleMetadata):
        return []
