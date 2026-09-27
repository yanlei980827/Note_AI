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
"LIST_ITEM_NUMBER_RE = re.compile(r\"^(\\d+\\.)\\s+(\\d+\\.)[ \\t\\xa0]+\")",
'''LIST_ITEM_NUMBER_RE = re.compile(r"^(\\d+\\.)\\s+(\\d+\\.)[ \\t\\xa0]+")

# 微信正文常把「一、」「二、」这类中文序号的章节名写成普通段落（不是 h2 标签），
# markdownify 转出的纯文本行既不是标题也没有强调标记。符合「中文序号 + 短句 +
# 无句末标点」的独立行在排版上就是小节标题，这里升级为 `##`，交给 _number_headings 统一编号。
# 带句号/问号/冒号/逗号或过长的行属于正常段落（如「一、为什么…？这个很朴素。」），不转换。
CHINESE_ORDINAL_HEADING_RE = re.compile(
    r"^([一二三四五六七八九十]{1,3})、[^。！？；：，]{1,40}$"
)''',
"add CHINESE_ORDINAL_HEADING_RE")

patch(wx,
'''            if not in_fence:
                line = LIST_ITEM_NUMBER_RE.sub(r"\\1 ", line)
                line = LIST_ITEM_BULLET_RE.sub(r"\\1 ", line)
            lines.append(line)''',
'''            if not in_fence:
                line = LIST_ITEM_NUMBER_RE.sub(r"\\1 ", line)
                line = LIST_ITEM_BULLET_RE.sub(r"\\1 ", line)
                if CHINESE_ORDINAL_HEADING_RE.match(line.strip()):
                    line = "## " + line.strip()
            lines.append(line)''',
"promote chinese-ordinal heading lines to ##")

tst = BASE / "test_extractor.py"

patch(tst,
"from wechat_extractor import (",
"from article_extractor import _number_headings\nfrom wechat_extractor import (",
"import _number_headings")

patch(tst,
"    def test_screenshot_flag_adds_marked_line(self):",
'''    def test_chinese_ordinal_paragraph_becomes_heading(self):
        html = (
            "<div>"
            "<p>一、寄存器复位值测试</p><p>内容。</p>"
            "<p>二、寄存器属性测试</p><p>内容。</p>"
            "<p>一、为什么我们最先想要按照前仿的划分来做？这个很朴素。</p>"
            "<ul><li>一、列表项不算标题</li></ul>"
            "</div>"
        )
        md = WeChatArticleExtractor._convert_body(html)
        self.assertIn("## 一、寄存器复位值测试", md)
        self.assertIn("## 二、寄存器属性测试", md)
        self.assertIn("一、为什么我们最先想要按照前仿的划分来做？这个很朴素。", md)
        self.assertIn("- 一、列表项不算标题", md)
        self.assertNotIn("## 一、为什么", md)
        self.assertNotIn("## - 一、", md)
        numbered = _number_headings("# 寄存器专项测试\\n\\n" + md)
        self.assertIn("## 1.1 寄存器复位值测试", numbered)
        self.assertIn("## 1.2 寄存器属性测试", numbered)

    def test_screenshot_flag_adds_marked_line(self):''',
"add chinese-ordinal heading test")

print("CODE PATCHED")
