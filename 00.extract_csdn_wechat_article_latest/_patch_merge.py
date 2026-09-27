# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(r"D:\sandbox\extract_csdn_wechat_article_0815_fix")

def patch(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"NOT FOUND in {path.name}: {what}"
    assert text.count(old) == 1, f"NOT UNIQUE in {path.name}: {what}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path.name}: {what}")

ext = BASE / "article_extractor.py"

patch(ext,
"""    @staticmethod
    def _normalize_code_blocks(content_node) -> None:""",
"""    @staticmethod
    def _merge_list_heading_content(content_node) -> None:
        \"\"\"Hook for subclasses to adjust list structure before conversion.\"\"\"
        return None

    @staticmethod
    def _normalize_code_blocks(content_node) -> None:""",
"add base _merge_list_heading_content hook")

patch(ext,
"""        self._normalize_code_blocks(content_node)
        self._drop_empty_headings(content_node)""",
"""        self._normalize_code_blocks(content_node)
        self._drop_empty_headings(content_node)
        self._merge_list_heading_content(content_node)""",
"call merge hook in extract_article_html")

wx = BASE / "wechat_extractor.py"

patch(wx,
'LIST_ITEM_HEADING_RE = re.compile(r"^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$")',
'''LIST_ITEM_HEADING_RE = re.compile(r"^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$")


def _is_single_heading_list(list_node) -> bool:
    \"\"\"True if the list contains exactly one <li> whose only content is a heading.\"\"\"
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
"add _is_single_heading_list helper")

patch(wx,
"    @staticmethod\n    def _convert_body(body_html: str) -> str:",
'''    @staticmethod
    def _merge_list_heading_content(content_node) -> None:
        \"\"\"微信把「加粗小标题」写成 <ul><li><h3>xxx</h3></li></ul>，标题下面的内容是
        紧跟在 <ul> 后面的独立 <p>/<ol> 节点，markdownify 会输出顶格段落，与 `- ` 列表项
        不在同一层次。这里把这类「单标题列表项」后面紧邻的内容节点移入 <li>，
        markdownify 输出时内容会自动缩进到 `- ` 下面（同一列表层次）。\"\"\"
        for list_node in content_node.find_all(["ul", "ol"]):
            items = list_node.find_all("li", recursive=False)
            if len(items) != 1:
                continue
            li = items[0]
            children = [
                child
                for child in li.children
                if getattr(child, "name", None)
                or (getattr(child, "string", None) or "").strip()
            ]
            if len(children) != 1 or getattr(children[0], "name", None) not in (
                "h1", "h2", "h3", "h4", "h5", "h6",
            ):
                continue
            siblings = []
            node = list_node
            while True:
                node = node.find_next_sibling()
                if getattr(node, "name", None) not in ("p", "ul", "ol"):
                    break
                # 遇到另一个「标题列表项」就停止，避免把下一节标题吸进来
                if node.name in ("ul", "ol") and _is_single_heading_list(node):
                    break
                siblings.append(node)
            for sibling in siblings:
                li.append(sibling.extract())

    @staticmethod
    def _convert_body(body_html: str) -> str:''',
"add wechat _merge_list_heading_content override")

tst = BASE / "test_extractor.py"

patch(tst,
"class EmptyHeadingSession(FakeSession):",
'''LIST_HEADING_HTML = """<!doctype html>
<html>
  <head><meta property="og:title" content="标题"/></head>
  <body>
    <div id="js_content">
      <ul><li><h3>最优测试方案</h3></li></ul>
      <p>全局/模块复位后，第一段内容。</p>
      <ol><li>项目一</li><li>项目二</li></ol>
      <ul><li><h3>覆盖范围</h3></li></ul>
      <p>覆盖范围内容。</p>
    </div>
  </body>
</html>
"""


class ListHeadingSession(FakeSession):
    def get(self, url, **kwargs):
        if url == ARTICLE_URL:
            return FakeResponse(LIST_HEADING_HTML.encode("utf-8"), "text/html; charset=utf-8")
        raise AssertionError(f"unexpected URL: {url}")


class EmptyHeadingSession(FakeSession):''',
"add ListHeadingSession")

patch(tst,
"    def test_list_item_heading_demoted_to_plain_text(self):",
'''    def test_list_heading_content_merged_into_list_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=ListHeadingSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            # 标题列表项后面的内容必须缩进到 `- ` 下面，与列表项同一层次
            self.assertIn(
                "- 最优测试方案\\n\\n  全局/模块复位后，第一段内容。",
                result.markdown,
            )
            self.assertIn("  1. 项目一", result.markdown)
            self.assertIn("  2. 项目二", result.markdown)
            self.assertIn("- 覆盖范围\\n\\n  覆盖范围内容。", result.markdown)

    def test_list_item_heading_demoted_to_plain_text(self):''',
"add merged list heading content test")

print("CODE PATCHED")
