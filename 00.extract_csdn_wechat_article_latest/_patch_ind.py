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
"LIST_ITEM_HEADING_RE = re.compile(r\"^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$\")",
'''LIST_ITEM_HEADING_RE = re.compile(r"^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$")

# 微信嵌套结构偶尔会把「- 标题」输出成 2 空格缩进的列表项（`  - 标题`），而其内容只缩进
# 2 空格（不足嵌套列表项的内容列 4 空格），CommonMark/Typora 会把内容渲染成列表项外的独立段落。
# 检测「2 空格缩进列表项 + 其后 2 空格缩进内容」并降为顶格列表项，内容缩进正好匹配 `- ` 的内容列。
INDENTED_LIST_ITEM_RE = re.compile(r"^  [-*+]\\s+(.+)$")


def _normalize_indented_list_items(markdown: str) -> str:
    lines = markdown.split("\\n")
    out = []
    in_fence = False
    for i, line in enumerate(lines):
        if re.match(r"^\\s*(```|~~~)", line):
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
                    and not re.match(r"^\\s*[-*+]\\s", lines[j])
                ):
                    line = "- " + item.group(1)
        out.append(line)
    return "\\n".join(out)''',
"add _normalize_indented_list_items")

patch(wx,
'''            lines.append(line)
        return "\\n".join(lines)

    def _metadata_lines(self, metadata: ArticleMetadata):''',
'''            lines.append(line)
        return _normalize_indented_list_items("\\n".join(lines))

    def _metadata_lines(self, metadata: ArticleMetadata):''',
"apply indented list normalization in _convert_body")

tst = BASE / "test_extractor.py"

patch(tst,
"from article_extractor import _number_headings\n",
"from article_extractor import _number_headings\nfrom wechat_extractor import _normalize_indented_list_items\n",
"import _normalize_indented_list_items")

patch(tst,
"    def test_list_heading_content_merged_when_wrapped_in_section(self):",
'''    def test_indented_list_heading_demoted_to_top_level(self):
        md = "  - 最优测试方案\\n\\n  摒弃冗余随机激励，内容。\\n\\n  1. 项目一\\n"
        out = _normalize_indented_list_items(md)
        self.assertIn("- 最优测试方案\\n\\n  摒弃冗余随机激励，内容。", out)
        self.assertNotIn("  - ", out)

    def test_list_heading_content_merged_when_wrapped_in_section(self):''',
"add indented list normalization test")

print("CODE PATCHED")
