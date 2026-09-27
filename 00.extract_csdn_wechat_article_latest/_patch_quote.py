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
'        lines.append("")\n        return "\\n".join(lines) + body_markdown\n',
'''        lines.append("")
        # 引用块（> update ...）与正文之间必须有空行，否则 CommonMark/Typora 的
        # lazy continuation 会把紧贴的正文第一段并进引用块渲染（debug.md 复现过）
        return "\\n".join(lines) + "\\n" + body_markdown
''',
"blank line between quote block and body")

tst = BASE / "test_extractor.py"
patch(tst,
"    def test_screenshot_flag_adds_marked_line(self):",
'''    def test_body_not_merged_into_quote_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            # 引用块（> update ...）与正文之间必须有空行，否则正文第一段会被
            # CommonMark/Typora 的 lazy continuation 并进引用块渲染
            self.assertRegex(
                result.markdown,
                r"> update \\d{4}/\\d{2}/\\d{2} \\d{2} : \\d{2}\\n\\n第一段内容。",
            )
            self.assertNotRegex(
                result.markdown,
                r"> update \\d{4}/\\d{2}/\\d{2} \\d{2} : \\d{2}\\n[^\\n>]",
            )

    def test_screenshot_flag_adds_marked_line(self):''',
"add quote-block body test")

# debug.md 修复（用户明确要求修 debug.md 中这一处）
dbg = Path(r"D:\sandbox\debug.md")
text = dbg.read_text(encoding="utf-8")
old = "> update 2026/08/16 03 : 30\n不像RTL功能仿真"
new = "> update 2026/08/16 03 : 30\n\n不像RTL功能仿真"
assert text.count(old) == 1, f"debug.md pattern count={text.count(old)}"
dbg.write_text(text.replace(old, new, 1), encoding="utf-8")
print("patched debug.md: blank line after update")

print("ALL PATCHES APPLIED")
