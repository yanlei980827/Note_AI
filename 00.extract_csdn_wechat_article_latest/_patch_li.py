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
"CHINESE_ORDINAL_HEADING_RE = re.compile(\n    r\"^([一二三四五六七八九十]{1,3})、[^。！？；：，]{1,40}$\"\n)",
'''CHINESE_ORDINAL_HEADING_RE = re.compile(
    r"^([一二三四五六七八九十]{1,3})、[^。！？；：，]{1,40}$"
)

# 微信编辑器会把「加粗小标题」写成 <li><h3>xxx</h3></li>，markdownify 转成 `- ### xxx`；
# 用户要求「·」后面不要带标题等级，列表项里的文字按段落处理，因此去掉 `- ` 后面的 `#` 标记。
LIST_ITEM_HEADING_RE = re.compile(r"^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$")''',
"add LIST_ITEM_HEADING_RE")

patch(wx,
'''                line = LIST_ITEM_NUMBER_RE.sub(r"\\1 ", line)
                line = LIST_ITEM_BULLET_RE.sub(r"\\1 ", line)
                if CHINESE_ORDINAL_HEADING_RE.match(line.strip()):''',
'''                line = LIST_ITEM_NUMBER_RE.sub(r"\\1 ", line)
                line = LIST_ITEM_BULLET_RE.sub(r"\\1 ", line)
                line = LIST_ITEM_HEADING_RE.sub(r"\\1\\2", line)
                if CHINESE_ORDINAL_HEADING_RE.match(line.strip()):''',
"strip heading markers inside list items")

tst = BASE / "test_extractor.py"

patch(tst,
"    def test_chinese_ordinal_paragraph_becomes_heading(self):",
'''    def test_list_item_heading_demoted_to_plain_text(self):
        html = (
            "<div>"
            "<ul><li><h3>最优测试方案</h3></li></ul>"
            "<ul><li><h2>覆盖范围</h2></li></ul>"
            "</div>"
        )
        md = WeChatArticleExtractor._convert_body(html)
        self.assertIn("- 最优测试方案", md)
        self.assertIn("- 覆盖范围", md)
        self.assertNotIn("- ###", md)
        self.assertNotIn("- ##", md)

    def test_chinese_ordinal_paragraph_becomes_heading(self):''',
"add list-item heading test")

print("CODE PATCHED")
