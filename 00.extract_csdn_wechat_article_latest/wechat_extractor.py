"""Extract a WeChat article into Markdown with local image files."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from article_extractor import (
    ArticleMetadata,
    BaseArticleExtractor,
    validate_url,
    write_markdown_file,
)


# Tag factory used by _normalize_code_blocks to build <pre><code> replacements.
_TAG_FACTORY = BeautifulSoup("", "html.parser")

WECHAT_ORIGIN = "https://mp.weixin.qq.com"

CONTENT_SELECTORS = (
    ("div", {"id": "js_content"}),
    ("div", {"id": "js_article"}),
    ("div", {"class": "rich_media_content"}),
    ("div", {"id": "js_content_area"}),
)

DROP_CLASSES = (
    "js_media_tip",
    "js_media_tail",
    "js_media_qr",
    "js_media_warning",
    "rich_media_tool",
    "rich_media_meta_list",
)

# WeChat rich-text editors often put a literal bullet character at the
# start of <li> items. markdownify then renders "\u2022 text" as "- \u2022 text".
LIST_ITEM_BULLET_RE = re.compile(r"^(\d+\.|[-*+])\s+[•◦▪●○◆◇·・‣⁃][ \t\xa0]+")

# WeChat <ol> items often keep a manually typed number in the text
# ("1. 内容"), so markdownify renumbers them and the text repeats it,
# producing "1. 1. 内容".
LIST_ITEM_NUMBER_RE = re.compile(r"^(\d+\.)\s+(\d+\.)[ \t\xa0]+")

# 微信正文常把「一、」「二、」这类中文序号的章节名写成普通段落（不是 h2 标签），
# markdownify 转出的纯文本行既不是标题也没有强调标记。符合「中文序号 + 短句 +
# 无句末标点」的独立行在排版上就是小节标题，这里升级为 `##`，交给 _number_headings 统一编号。
# 带句号/问号/冒号/逗号或过长的行属于正常段落（如「一、为什么…？这个很朴素。」），不转换。
CHINESE_ORDINAL_HEADING_RE = re.compile(
    r"^([一二三四五六七八九十]{1,3})、[^。！？；：，]{1,40}$"
)

# 微信编辑器会把「加粗小标题」写成 <li><h3>xxx</h3></li>，markdownify 转成 `- ### xxx`；
# 用户要求「·」后面不要带标题等级，列表项里的文字按段落处理，因此去掉 `- ` 后面的 `#` 标记。
LIST_ITEM_HEADING_RE = re.compile(r"^(\s*[-*+]\s+)#{1,6}[ \t]+(.*)$")

# 微信嵌套结构偶尔会把「- 标题」输出成 2 空格缩进的列表项（`  - 标题`），而其内容只缩进
# 2 空格（不足嵌套列表项的内容列 4 空格），CommonMark/Typora 会把内容渲染成列表项外的独立段落。
# 检测「2 空格缩进列表项 + 其后 2 空格缩进内容」并降为顶格列表项，内容缩进正好匹配 `- ` 的内容列。
INDENTED_LIST_ITEM_RE = re.compile(r"^  [-*+]\s+(.+)$")
STANDALONE_LIST_BULLET_RE = re.compile(r"^(\s*(?:[-*+]|\d+\.))\s+[•◦▪●○◆◇·・‣⁃]\s*$")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
STANDALONE_ORDER_RE = re.compile(r"^\s*(\d+)[.．、]?\s*$")


def _can_be_order_item_title(line: str) -> bool:
    text = line.strip()
    if not text or len(text) > 80:
        return False
    if _starts_new_markdown_block(text):
        return False
    if LIST_ITEM_RE.match(text):
        return False
    if re.search(r"[。！？；：，.!?;:]$", text):
        return False
    return True


def _starts_new_markdown_block(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if STANDALONE_ORDER_RE.match(text):
        return True
    if LIST_ITEM_RE.match(text):
        return True
    return bool(re.match(r"^(#{1,6}\s+|>|```|~~~|---$|<!--|\|)", text))


def _is_order_item_continuation(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    return not _starts_new_markdown_block(text)


def _normalize_standalone_order_numbers(markdown: str) -> str:
    """Normalize a standalone order number before its item text."""
    lines = markdown.split("\n")
    out = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if not in_fence:
            order = STANDALONE_ORDER_RE.match(line)
            if order:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if (
                    j < len(lines)
                    and re.match(rf"^\s*{re.escape(order.group(1))}[.)．]\s+", lines[j])
                ):
                    i = j
                    continue
                if j < len(lines) and _can_be_order_item_title(lines[j]):
                    marker_indent = " " * (len(order.group(1)) + 2)
                    out.append(f"{order.group(1)}. {lines[j].strip()}")
                    i = j + 1
                    while i < len(lines):
                        blanks = []
                        while i < len(lines) and not lines[i].strip():
                            blanks.append(lines[i])
                            i += 1
                        if i >= len(lines):
                            out.extend(blanks)
                            break
                        if not _is_order_item_continuation(lines[i]):
                            out.extend(blanks)
                            break
                        out.extend(blanks)
                        out.append(marker_indent + lines[i].strip())
                        i += 1
                    continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _merge_standalone_list_bullets(markdown: str) -> str:
    """Collapse '- ·' followed by an indented text line into '- text'."""
    lines = markdown.split("\n")
    out = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if not in_fence:
            item = STANDALONE_LIST_BULLET_RE.match(line)
            if item:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if (
                    j < len(lines)
                    and lines[j].startswith((" ", "\t"))
                    and not LIST_ITEM_RE.match(lines[j])
                ):
                    out.append(f"{item.group(1)} {lines[j].strip()}")
                    i = j + 1
                    continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _normalize_indented_list_items(markdown: str) -> str:
    lines = markdown.split("\n")
    out = []
    in_fence = False
    for i, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        if not in_fence:
            item = INDENTED_LIST_ITEM_RE.match(line)
            if item:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if (
                    j < len(lines)
                    and lines[j].startswith("  ")
                    and not re.match(r"^\s*[-*+]\s", lines[j])
                ):
                    line = "- " + item.group(1)
        out.append(line)
    return "\n".join(out)


HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
CONTENT_WRAPPER_TAGS = ("section", "div")


def _single_heading_element(node):
    """Return the sole heading element inside node, allowing section/div wrappers.

    WeChat wraps headings in <section> in some articles, so <li> may contain
    <section><h3>...</h3></section> instead of a bare <h3>.
    """
    children = [
        child
        for child in node.children
        if getattr(child, "name", None)
        or (getattr(child, "string", None) or "").strip()
    ]
    if len(children) != 1:
        return None
    child = children[0]
    if getattr(child, "name", None) in HEADING_TAGS:
        return child
    if getattr(child, "name", None) in CONTENT_WRAPPER_TAGS:
        return _single_heading_element(child)
    return None


def _is_single_heading_list(list_node) -> bool:
    """True if the list contains exactly one <li> whose only content is a heading."""
    items = list_node.find_all("li", recursive=False)
    if len(items) != 1:
        return False
    return _single_heading_element(items[0]) is not None


class WeChatArticleExtractor(BaseArticleExtractor):
    """Fetch a WeChat article page and convert its body to Markdown."""

    source_label = "微信"
    referer = WECHAT_ORIGIN

    @staticmethod
    def _extract_metadata(soup, url: str) -> ArticleMetadata:
        title_node = (
            soup.find("h1", id="activity-name")
            or soup.find("h1", class_="rich_media_title")
            or soup.find("meta", property="og:title")
            or soup.find("title")
        )
        title = ""
        if title_node is not None:
            if title_node.name == "meta":
                title = title_node.get("content", "")
            else:
                title = title_node.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            title = "未命名微信文章"

        author_node = (
            soup.find("meta", attrs={"name": "author"})
            or soup.find("meta", attrs={"property": "og:article:author"})
            or soup.find("span", id="js_name")
            or soup.find("a", id="js_name")
        )
        author = ""
        if author_node is not None:
            author = (author_node.get("content") or author_node.get_text(" ", strip=True) or "").strip()

        time_node = (
            soup.find("em", id="publish_time")
            or soup.find("span", id="publish_time")
            or soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "weibo:article:create_at"})
        )
        publish_time = ""
        if time_node is not None:
            publish_time = (time_node.get("content") or time_node.get_text(" ", strip=True) or "").strip()

        return ArticleMetadata(title=title, author=author, publish_time=publish_time, url=url)

    @staticmethod
    def _find_content(soup):
        for name, attrs in CONTENT_SELECTORS:
            node = soup.find(name, attrs=attrs)
            if node is not None:
                return node
        return None

    @staticmethod
    def _remove_noise(content_node) -> None:
        BaseArticleExtractor._remove_noise(content_node)
        for class_name in DROP_CLASSES:
            for tag in content_node.find_all(class_=class_name):
                tag.decompose()

    @staticmethod
    def _extract_code_text(node) -> Optional[str]:
        """Extract plain code text from a WeChat code node (``<code>`` or the
        section-style block newer editors use instead of ``<pre>``).

        新版微信编辑器把一行代码拆成多个高亮 token span（leaf
        或被彩色 span 包裹的 leaf），行尾用 <span leaf=""><br/></span>
        标记；旧版每行是一个完整的 leaf span。不能用
        find_all(attrs={"leaf": ""})：BeautifulSoup 会把没有 leaf 属性的
        彩色包裹 span 也匹配进来，导致每个 token 文本重复。"""
        leaf_spans = [
            span for span in node.find_all("span") if span.has_attr("leaf")
        ]
        if leaf_spans:
            new_style = any(span.find("br") is not None for span in leaf_spans)
            if new_style:
                lines = []
                current = []
                for span in leaf_spans:
                    span_text = span.get_text()
                    if span_text:
                        current.append(span_text)
                    if span.find("br") is not None:
                        lines.append("".join(current))
                        current = []
                if current:
                    lines.append("".join(current))
                text = "\n".join(lines)
            else:
                text = "\n".join(
                    span.get_text() for span in leaf_spans if span.get_text()
                )
        else:
            text = node.get_text("\n")
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
        return clean_text if clean_text.strip() else None

    @staticmethod
    def _is_code_section(node) -> bool:
        """True for a WeChat section-style code block without a <pre> wrapper.

        新版微信编辑器偶尔不用 <pre>，而是用带代码样式的 <section>
        （white-space: nowrap + Consolas/monospace 字体）直接包裹高亮
        token span；这类块 markdownify 会当成普通段落输出，代码全部
        裸露在正文里，需要转成 <pre><code>。"""
        style = node.get("style") or ""
        if "white-space: nowrap" not in style:
            return False
        if "Consolas" not in style and "monospace" not in style:
            return False
        return any(span.has_attr("leaf") for span in node.find_all("span"))

    @staticmethod
    def _normalize_code_blocks(content_node) -> None:
        """Rewrite WeChat code blocks into plain <pre><code> so line numbers and
        decoration spans do not leak into the Markdown code fence."""

        for pre in content_node.find_all("pre"):
            code = pre.find("code")
            if code is None:
                continue
            for child in list(pre.children):
                if getattr(child, "name", None) == "section" and child is not code:
                    child.decompose()
            for column in code.find_all(style=re.compile(r"user-select:\s*none")):
                column.decompose()
            clean_text = WeChatArticleExtractor._extract_code_text(code)
            if clean_text is not None:
                code.clear()
                code.string = clean_text

        # 微信新版编辑器把代码块写成带代码样式的 <section>（没有 <pre>），
        # 统一转成 <pre><code>，避免代码裸露在正文里。
        for section in content_node.find_all("section"):
            if not WeChatArticleExtractor._is_code_section(section):
                continue
            if section.find_parent("pre") is not None:
                continue
            clean_text = WeChatArticleExtractor._extract_code_text(section)
            if clean_text is None:
                continue
            new_pre = _TAG_FACTORY.new_tag("pre")
            new_code = _TAG_FACTORY.new_tag("code")
            new_code.string = clean_text
            new_pre.append(new_code)
            section.replace_with(new_pre)

    @staticmethod
    def _merge_list_heading_content(content_node) -> None:
        """微信把「加粗小标题」写成 <ul><li><h3>xxx</h3></li></ul>，标题下面的内容是
        紧跟在 <ul> 后面的独立 <p>/<ol> 节点，markdownify 会输出顶格段落，与 `- ` 列表项
        不在同一层次。这里把这类「单标题列表项」后面紧邻的内容节点移入 <li>，
        markdownify 输出时内容会自动缩进到 `- ` 下面（同一列表层次）。"""
        for list_node in content_node.find_all(["ul", "ol"]):
            items = list_node.find_all("li", recursive=False)
            if len(items) != 1:
                continue
            li = items[0]
            if _single_heading_element(li) is None:
                continue
            siblings = []
            node = list_node
            while True:
                node = node.find_next_sibling()
                if getattr(node, "name", None) not in (
                    "p", "ul", "ol", "section", "div",
                ):
                    break
                # 遇到另一个「标题列表项」或独立标题块就停止，避免把下一节标题吸进来
                if node.name in ("ul", "ol") and _is_single_heading_list(node):
                    break
                if node.name in ("section", "div") and _single_heading_element(node) is not None:
                    break
                siblings.append(node)
            for sibling in siblings:
                li.append(sibling.extract())

    @staticmethod
    def _convert_body(body_html: str) -> str:
        markdown = BaseArticleExtractor._convert_body(body_html)
        lines = []
        in_fence = False
        for line in markdown.split("\n"):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
            if not in_fence:
                line = LIST_ITEM_NUMBER_RE.sub(r"\1 ", line)
                line = LIST_ITEM_BULLET_RE.sub(r"\1 ", line)
                line = LIST_ITEM_HEADING_RE.sub(r"\1\2", line)
            if CHINESE_ORDINAL_HEADING_RE.match(line.strip()):
                line = "## " + line.strip()
            lines.append(line)
        markdown = _normalize_standalone_order_numbers("\n".join(lines))
        markdown = _merge_standalone_list_bullets(markdown)
        return _normalize_indented_list_items(markdown)

    def _metadata_lines(self, metadata: ArticleMetadata):
        if metadata.author:
            return [f"> 作者：{metadata.author}"]
        return []
