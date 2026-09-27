"""Export Markdown to PDF via headless Chrome/Edge (no extra dependencies).

Two entry points:

- :func:`export_article_pdf` renders one extracted article's HTML fragment
  (kept for compatibility).
- :func:`export_markdown_pdf` renders the whole ``.md`` file (all articles
  inside it) into one paginated PDF; the GUI uses this one.

Markdown is converted to HTML by the built-in lightweight converter
(:func:`markdown_to_html`), which covers the syntax this project produces
(headings, blockquotes, lists, fenced code, pipe tables, images, links,
inline code/bold/italic) plus common Markdown basics. Chrome's
``--print-to-pdf`` paginates automatically; the page CSS is augmented with
print rules (A4, smaller margins, no header/footer).
"""

from __future__ import annotations

import html
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from screenshot import (
    PAGE_CSS,
    VIRTUAL_TIME_BUDGET_MS,
    ScreenshotError,
    _best_effort_rmtree,
    _build_article_html,
    _run_browser,
    find_browser,
)
from article_extractor import (
    TOC_END_MARKER,
    TOC_START_MARKER,
    _extract_headings,
    heading_slug,
)

# 打印环境补充样式：A4 页、更紧凑页边距、避免代码块/图片/表格被拦腰分页。
PRINT_CSS = PAGE_CSS + """
/* ---- PDF 打印专用覆盖（优先级高于上方页面样式） ---- */
@page {
  size: A4;
  margin: 12mm 10mm;
}
body {
  padding: 0;
  max-width: 760px;
  font-size: 14px;
}
h1, h2, h3, h4, h5, h6 {
  page-break-after: avoid;
}
pre, img, table, blockquote {
  page-break-inside: avoid;
}
/* 引用块改为绿色，方便区分正文与来源/总结 */
blockquote {
  border-left: 4px solid #2f9e44;
  background: #f0f8ef;
  color: #2e6b34;
}
a {
  word-break: break-all;
}
/* 目录列表隐藏项目符号（圆点） */
ul.toc, ul.toc ul {
  list-style: none;
}
ul.toc {
  padding-left: 0;
}
ul.toc ul {
  padding-left: 1.5em;
}
"""


# ---------------------------------------------------------------------------
# 轻量 Markdown → HTML 转换器（无需第三方 markdown 库）
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.*)$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*(.*)$")
_HR_RE = re.compile(r"^\s*((-\s*){3,}|(\*\s*){3,}|(_\s*){3,})$")
_QUOTE_RE = re.compile(r"^>[ \t]?(.*)$")
_UL_ITEM_RE = re.compile(r"^(\s*)[-*+][ \t]+(.*)$")
_OL_ITEM_RE = re.compile(r"^(\s*)(\d{1,9})[.)][ \t]+(.*)$")
_HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^[\s:\-|]+$")
_INDENTED_CODE_RE = re.compile(r"^( {4,}|\t)(.*)$")
_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!])")

_INLINE_PATTERNS = (
    ("bolditalic", re.compile(r"\*\*\*([^*\n]+)\*\*\*")),
    ("bolditalic_under", re.compile(r"___([^_\n]+)___")),
    ("strike", re.compile(r"~~([^~\n]+)~~")),
    ("image", re.compile(r"!\[([^\]\\]*(?:\\.[^\]\\]*)*)\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")),
    ("link", re.compile(r"\[([^\]\\]*(?:\\.[^\]\\]*)*)\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")),
    ("code", re.compile(r"`([^`\n]+)`")),
    ("bold", re.compile(r"\*\*([^*\n]+)\*\*")),
    ("italic", re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")),
    ("bold_under", re.compile(r"__([^_\n]+)__")),
    ("italic_under", re.compile(r"(?<!_)_([^_\n]+)_(?!_)")),
)


def _unescape(text: str) -> str:
    return _ESCAPE_RE.sub(lambda match: match.group(1), text)


def _escape_literal(text: str) -> str:
    return html.escape(_unescape(text), quote=False)


def _render_inline(text: str) -> str:
    out: List[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] == "\\" and index + 1 < length:
            # 成对处理反斜杠转义（如链接标签里的 \[ \]），避免逐字符拆开
            out.append(_escape_literal(text[index : index + 2]))
            index += 2
            continue
        matched = False
        for kind, pattern in _INLINE_PATTERNS:
            match = pattern.match(text, index)
            if not match:
                continue
            if kind == "image":
                alt = match.group(1)
                src = match.group(2)
                out.append(
                    '<img src="%s" alt="%s">'
                    % (html.escape(src, quote=True), html.escape(alt, quote=True))
                )
            elif kind == "link":
                label = match.group(1)
                href = match.group(2)
                out.append(
                    '<a href="%s">%s</a>'
                    % (html.escape(href, quote=True), _render_inline(label))
                )
            elif kind == "code":
                out.append("<code>%s</code>" % html.escape(match.group(1), quote=False))
            elif kind in ("bold", "bold_under"):
                out.append("<strong>%s</strong>" % _render_inline(match.group(1)))
            elif kind in ("italic", "italic_under"):
                out.append("<em>%s</em>" % _render_inline(match.group(1)))
            elif kind in ("bolditalic", "bolditalic_under"):
                out.append(
                    "<strong><em>%s</em></strong>" % _render_inline(match.group(1))
                )
            elif kind == "strike":
                out.append("<del>%s</del>" % _render_inline(match.group(1)))
            index = match.end()
            matched = True
            break
        if not matched:
            out.append(_escape_literal(text[index]))
            index += 1
    return "".join(out)


def _render_paragraph(lines: List[str]) -> str:
    """渲染段落；多行内容保留为多行，与 Markdown 源文件一致。"""
    rendered: List[str] = []
    for raw in lines:
        if not raw.strip():
            continue
        stripped = raw.strip(" \t")
        rendered.append(_render_inline(stripped))
    return "<p>%s</p>" % "<br>".join(rendered)


def _render_code_block(code_lines: List[str], lang: str) -> str:
    code = html.escape("\n".join(code_lines), quote=False)
    if lang:
        return '<pre><code class="language-%s">%s</code></pre>' % (
            html.escape(lang, quote=True),
            code,
        )
    return "<pre><code>%s</code></pre>" % code


def _render_quote(quote_lines: List[str]) -> str:
    groups: List[List[str]] = []
    current: List[str] = []
    for raw in quote_lines:
        if raw.strip() == "":
            if current:
                groups.append(current)
                current = []
            continue
        current.append(raw)
    if current:
        groups.append(current)
    inner = [_render_paragraph(group) for group in groups]
    return "<blockquote>%s</blockquote>" % "\n".join(inner)


def _match_list_item(line: str) -> Optional[Tuple[str, int, str]]:
    match = _UL_ITEM_RE.match(line)
    if match:
        return ("ul", len(match.group(1)), match.group(2).strip())
    match = _OL_ITEM_RE.match(line)
    if match:
        return ("ol", len(match.group(1)), match.group(3).strip())
    return None


def _render_list_region(
    region: List[Tuple[str, object]], toc: bool = False
) -> str:
    """Render a list region; ``toc`` marks the generated 目录 so bullets are hidden."""
    root: List[dict] = []
    stack: List[Tuple[int, dict]] = []
    for entry in region:
        if entry[0] == "blank":
            continue
        if entry[0] == "cont":
            if stack:
                stack[-1][1]["lines"].append(str(entry[1]))
            continue
        kind, indent, content = entry[1]  # type: ignore[misc]
        node = {
            "kind": kind,
            "indent": indent,
            "lines": [content],
            "children": [],
        }
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root.append(node)
        stack.append((indent, node))

    def render_nodes(nodes: List[dict]) -> str:
        parts: List[str] = []
        index = 0
        while index < len(nodes):
            indent = nodes[index]["indent"]
            run = []
            while index < len(nodes) and nodes[index]["indent"] == indent:
                run.append(nodes[index])
                index += 1
            position = 0
            while position < len(run):
                kind = run[position]["kind"]
                end = position
                while end < len(run) and run[end]["kind"] == kind:
                    end += 1
                tag = "ol" if kind == "ol" else "ul"
                if toc and tag == "ul":
                    parts.append('<ul class="toc">')
                else:
                    parts.append("<%s>" % tag)
                for node in run[position:end]:
                    inner = "<br>".join(_render_inline(line) for line in node["lines"])
                    child_html = render_nodes(node["children"]) if node["children"] else ""
                    parts.append("<li>%s%s</li>" % (inner, child_html))
                parts.append("</%s>" % tag)
                position = end
        return "\n".join(parts)

    return render_nodes(root)


def _is_table_row(line: str) -> bool:
    return bool(_TABLE_ROW_RE.match(line))


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    if not stripped or "-" not in stripped:
        return False
    return bool(_TABLE_SEP_RE.match(stripped))


def _split_table_row(row: str) -> List[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _render_table(header: List[str], rows: List[List[str]]) -> str:
    out = ["<table>"]
    out.append(
        "<thead><tr>%s</tr></thead>"
        % "".join("<th>%s</th>" % _render_inline(cell) for cell in header)
    )
    if rows:
        out.append("<tbody>")
        for row in rows:
            out.append(
                "<tr>%s</tr>"
                % "".join("<td>%s</td>" % _render_inline(cell) for cell in row)
            )
        out.append("</tbody>")
    out.append("</table>")
    return "\n".join(out)


def _starts_new_block(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _HTML_COMMENT_RE.match(line):
        return True
    if _HEADING_RE.match(line) or _FENCE_RE.match(line) or _HR_RE.match(line):
        return True
    if stripped.startswith(">"):
        return True
    if _match_list_item(line) is not None:
        return True
    if _INDENTED_CODE_RE.match(line):
        return True
    if _is_table_row(line):
        return True
    return False


def _collect_list_region(lines: List[str], start: int) -> Tuple[List[Tuple[str, object]], int]:
    region: List[Tuple[str, object]] = []
    index = start
    count = len(lines)
    while index < count:
        line = lines[index]
        stripped = line.strip()
        if stripped == "":
            j = index
            while j < count and lines[j].strip() == "":
                j += 1
            if j < count:
                if _match_list_item(lines[j]) is not None:
                    index += 1
                    continue
                if lines[j][0] in " \t" and not _starts_new_block(lines[j]):
                    index += 1
                    continue
            break
        item = _match_list_item(line)
        if item is not None:
            region.append(("item", item))
            index += 1
            continue
        if line[0] in " \t" and not _starts_new_block(line):
            region.append(("cont", stripped))
            index += 1
            continue
        break
    return region, index


def markdown_to_html(markdown_text: str) -> str:
    """Convert a Markdown document to an HTML body fragment.

    Supports the syntax generated by this project plus common basics:
    ATX headings, blockquotes, bullet/ordered lists (with nesting and
    indented continuation lines), fenced and indented code blocks, pipe
    tables, images, links, horizontal rules, paragraphs, and inline
    code/bold/italic/strike.
    """
    text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    blocks: List[str] = []
    index = 0
    count = len(lines)
    in_toc = False
    while index < count:
        line = lines[index]
        stripped = line.strip()
        if stripped == "":
            index += 1
            continue

        if TOC_START_MARKER in line:
            in_toc = True
            index += 1
            continue
        if TOC_END_MARKER in line:
            in_toc = False
            index += 1
            continue

        if _HTML_COMMENT_RE.match(line):
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            lang = fence.group(2).strip()
            code_lines: List[str] = []
            index += 1
            while index < count:
                close = _FENCE_RE.match(lines[index])
                if close and close.group(1)[0] == fence.group(1)[0]:
                    if len(close.group(1)) >= len(fence.group(1)):
                        index += 1
                        break
                code_lines.append(lines[index])
                index += 1
            blocks.append(_render_code_block(code_lines, lang))
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            slug = heading_slug(text)
            blocks.append(
                '<h%d id="%s">%s</h%d>'
                % (level, html.escape(slug, quote=True), _render_inline(text), level)
            )
            index += 1
            continue

        if _HR_RE.match(line):
            blocks.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            quote_lines: List[str] = []
            while index < count and lines[index].strip().startswith(">"):
                quote_match = _QUOTE_RE.match(lines[index])
                quote_lines.append(quote_match.group(1) if quote_match else "")
                index += 1
            blocks.append(_render_quote(quote_lines))
            continue

        if _is_table_row(line) and index + 1 < count and _is_table_separator(lines[index + 1]):
            header = _split_table_row(line)
            index += 2
            rows: List[List[str]] = []
            while index < count and _is_table_row(lines[index]):
                rows.append(_split_table_row(lines[index]))
                index += 1
            blocks.append(_render_table(header, rows))
            continue

        item = _match_list_item(line)
        if item is not None:
            region, index = _collect_list_region(lines, index)
            blocks.append(_render_list_region(region, toc=in_toc))
            continue

        indent_match = _INDENTED_CODE_RE.match(line)
        if indent_match:
            code_lines = []
            while index < count:
                inner = _INDENTED_CODE_RE.match(lines[index])
                if inner:
                    code_lines.append(inner.group(2))
                    index += 1
                    continue
                if lines[index].strip() == "":
                    j = index
                    while j < count and lines[j].strip() == "":
                        j += 1
                    if j < count and _INDENTED_CODE_RE.match(lines[j]):
                        code_lines.extend([""] * (j - index))
                        index = j
                        continue
                break
            blocks.append(_render_code_block(code_lines, ""))
            continue

        para_lines: List[str] = [line]
        index += 1
        while index < count:
            if lines[index].strip() == "":
                break
            if _starts_new_block(lines[index]):
                break
            para_lines.append(lines[index])
            index += 1
        blocks.append(_render_paragraph(para_lines))

    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# PDF 导出
# ---------------------------------------------------------------------------


def _build_pdf_html(
    title: str,
    body_html: str,
    author: str = "",
    publish_time: str = "",
) -> str:
    """Build the article HTML with print-friendly CSS for PDF export."""
    return _build_article_html(
        title,
        body_html,
        author=author,
        publish_time=publish_time,
        css=PRINT_CSS,
    )


def _build_markdown_pdf_html(body_html: str, title: str = "") -> str:
    """Wrap a whole-document HTML body (no per-article head) for printing."""
    safe_title = html.escape(title or "", quote=False)
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{safe_title}</title>\n"
        f"<style>{PRINT_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body_html}\n"
        "</body>\n</html>\n"
    )


def _render_html_to_pdf(
    html_doc: str,
    output_pdf: Path,
    base_dir: Path,
    browser: str,
) -> Path:
    """Write ``html_doc`` to a temp file next to ``base_dir`` and print to PDF.

    Returns ``output_pdf`` on success; raises :class:`ScreenshotError` when
    the browser fails or writes nothing.
    """
    output_pdf = Path(output_pdf).expanduser()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if not output_pdf.parent.is_dir():
        raise ScreenshotError(f"PDF 保存目录不可用：{output_pdf.parent}")

    base_dir = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    fd = None
    html_path = None
    profile_dir = tempfile.mkdtemp(prefix=".article2md_pdf_profile_")
    try:
        fd, raw_path = tempfile.mkstemp(
            prefix=".article2md_pdf_", suffix=".html", dir=str(base_dir)
        )
        html_path = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(html_doc)
        fd = None
        page_url = html_path.resolve().as_uri()
        target = str(output_pdf.resolve())

        args = [
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-background-networking",
            "--virtual-time-budget=%d" % VIRTUAL_TIME_BUDGET_MS,
            "--user-data-dir=%s" % profile_dir,
            "--no-pdf-header-footer",
            "--print-to-pdf=%s" % target,
            page_url,
        ]
        _run_browser(browser, args, label="PDF")

        if not output_pdf.is_file() or output_pdf.stat().st_size == 0:
            raise ScreenshotError("浏览器未生成 PDF 文件")
        return output_pdf
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if html_path is not None:
            try:
                html_path.unlink()
            except OSError:
                pass
        _best_effort_rmtree(profile_dir)


def export_article_pdf(
    title: str,
    body_html: str,
    output_pdf: Path,
    base_dir: Optional[Path] = None,
    author: str = "",
    publish_time: str = "",
) -> Path:
    """Render a single article (images relative to ``base_dir``) to a PDF.

    Kept for compatibility with the earlier single-article export; the GUI
    now uses :func:`export_markdown_pdf` so the whole ``.md`` file is printed.
    """
    browser = find_browser()
    if not browser:
        raise ScreenshotError(
            "未找到 Chrome/Edge 浏览器，无法输出 PDF。请安装 Chrome 或 Edge 后重试。"
        )
    base_dir = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    html_doc = _build_pdf_html(
        title, body_html, author=author, publish_time=publish_time
    )
    return _render_html_to_pdf(html_doc, output_pdf, base_dir, browser)


def export_markdown_pdf(
    markdown_path: Path,
    output_pdf: Path,
    base_dir: Optional[Path] = None,
) -> Path:
    """Render the whole Markdown file (all articles) into one PDF.

    ``markdown_path`` is the ``.md`` file that was just written/updated;
    relative image paths are resolved against ``base_dir`` (defaults to the
    markdown file's own directory).
    """
    browser = find_browser()
    if not browser:
        raise ScreenshotError(
            "未找到 Chrome/Edge 浏览器，无法输出 PDF。请安装 Chrome 或 Edge 后重试。"
        )

    markdown_path = Path(markdown_path).expanduser()
    if not markdown_path.is_file():
        raise ScreenshotError(f"Markdown 文件不存在：{markdown_path}")
    base = Path(base_dir).expanduser() if base_dir is not None else markdown_path.parent
    try:
        md_text = markdown_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise ScreenshotError(f"读取 Markdown 失败：{exc}") from exc

    body_html = markdown_to_html(md_text)
    html_doc = _build_markdown_pdf_html(body_html, title=markdown_path.stem)
    result = _render_html_to_pdf(html_doc, output_pdf, base, browser)
    headings = _extract_headings(md_text)
    if headings:
        try:
            _add_pdf_bookmarks(result, headings)
        except Exception:
            # 书签注入失败不影响 PDF 本身（页面内目录仍可点击跳转）
            pass
    return result

def _norm_for_search(text: str) -> str:
    """去掉空白与标点，用于 PDF 提取文本与标题的宽松匹配。"""
    return re.sub(r"[\W_]+", "", text.lower())


def _bookmark_page(pages_text: List[str], title: str) -> int:
    """Return the page index containing ``title``.

    目录页会先出现标题文本，标题本身在后面再次出现，因此取最后出现页。
    """
    needle = _norm_for_search(title)[:14]
    if not needle:
        return 0
    last = 0
    for index, page_text in enumerate(pages_text):
        if needle in page_text:
            last = index
    return last


def _add_pdf_bookmarks(pdf_path: Path, headings: List[Tuple[int, str]]) -> None:
    """用项目内置的 pypdf 把 markdown 标题层级写入 PDF 书签（outline）。

    书签层级与 markdown 的 h1/h2/h3 对应；失败时由调用方兜底，PDF 仍保留
    可点击的页面内目录。
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(_norm_for_search(page.extract_text() or ""))
        except Exception:
            pages_text.append("")

    writer = PdfWriter()
    writer.append(reader)
    parents = {}
    for level, title in headings:
        if level > 3:
            level = 3
        page_no = _bookmark_page(pages_text, title)
        parent = parents.get(level - 1) if level > 1 else None
        item = writer.add_outline_item(title, page_no, parent=parent)
        parents[level] = item

    tmp_path = pdf_path.with_name(pdf_path.stem + ".bookmarks.tmp.pdf")
    try:
        with open(tmp_path, "wb") as handle:
            writer.write(handle)
        os.replace(tmp_path, pdf_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
