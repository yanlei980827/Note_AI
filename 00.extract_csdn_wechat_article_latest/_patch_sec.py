# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(r"D:\sandbox\extract_csdn_wechat_article_0815_fix")

def patch(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"NOT FOUND in {path.name}: {what}"
    assert text.count(old) == 1, f"NOT UNIQUE in {path.name}: {what}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path.name}: {what}")

wx = BASE / "wechat_extractor.py"

patch(wx,
'''def _is_single_heading_list(list_node) -> bool:
    """True if the list contains exactly one <li> whose only content is a heading."""
    items = list_node.find_all("li", recursive=False)
    if len(items) != 1:
        return False
    children = [
        child
        for child in items[0].children
        if getattr(child, "name", None)
        or (getattr(child, "string", None) or "").strip()
    ]
    return len(children) == 1 and getattr(children[0], "name", None) in (
        "h1", "h2", "h3", "h4", "h5", "h6",
    )''',
'''HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
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
    return _single_heading_element(items[0]) is not None''',
"support section/div wrapped headings")

patch(wx,
'''            siblings = []
            node = list_node
            while True:
                node = node.find_next_sibling()
                if getattr(node, "name", None) not in ("p", "ul", "ol"):
                    break
                # 遇到另一个「标题列表项」就停止，避免把下一节标题吸进来
                if node.name in ("ul", "ol") and _is_single_heading_list(node):
                    break
                siblings.append(node)''',
'''            siblings = []
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
                siblings.append(node)''',
"accept section/div siblings in merge loop")

tst = BASE / "test_extractor.py"

patch(tst,
"    def test_list_heading_content_merged_into_list_item(self):",
'''    def test_list_heading_content_merged_when_wrapped_in_section(self):
        html = (
            "<div>"
            "<ul><li><section><h3>最优测试方案</h3></section></li></ul>"
            "<section><p>摒弃冗余随机激励，内容。</p><ol><li>项目一</li><li>项目二</li></ol></section>"
            "<ul><li><h3>覆盖范围</h3></li></ul>"
            "<p>覆盖范围内容。</p>"
            "</div>"
        )
        extractor = WeChatArticleExtractor()
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find("div")
        extractor._merge_list_heading_content(node)
        md = extractor._convert_body(str(node))
        self.assertIn("- 最优测试方案\\n\\n  摒弃冗余随机激励，内容。", md)
        self.assertIn("  1. 项目一", md)
        self.assertIn("  2. 项目二", md)
        self.assertIn("- 覆盖范围\\n\\n  覆盖范围内容。", md)

    def test_list_heading_content_merged_into_list_item(self):''',
"add section-wrapped list heading test")

print("CODE PATCHED")
