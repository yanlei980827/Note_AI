# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(r"D:\sandbox\extract_csdn_wechat_article_0815_fix")

def patch(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"NOT FOUND in {path.name}: {what}"
    assert text.count(old) == 1, f"NOT UNIQUE in {path.name}: {what}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path.name}: {what}")

mem = BASE / "extract_csdn_wechat_article_memory.md"

patch(mem,
"## 文件结构与职责",
'''15. **微信列表项里的标题标记（2026-08-16 新增）**：微信正文把「加粗小标题」写成 `<li><h3>xxx</h3></li>`，
    markdownify 输出 `- ### xxx`。`_convert_body` 用 `LIST_ITEM_HEADING_RE`
    （`^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$` → `\\1\\2`）去掉 `- ` 后面的 `#` 标记，列表项文字按普通段落处理，
    不参与标题编号（代码围栏内不处理）。

## 文件结构与职责''',
"add convention 15 (list-item heading)")

patch(mem,
"## 常见调试命令",
'''24. 列表项里误带标题等级 bug：微信正文把「加粗小标题」写成 `<li><h3>xxx</h3></li>`，markdownify 输出 `- ### xxx`，
    用户要求「·」后面不要标题等级，列表项文字按段落 → 已修：`_convert_body` 新增 `LIST_ITEM_HEADING_RE`
    （`^(\\s*[-*+]\\s+)#{1,6}[ \\t]+(.*)$`），把 `- ### 标题` 降为 `- 标题`；新增
    `test_list_item_heading_demoted_to_plain_text`；debug.md 12 处已改为 `- 标题`。
    注：debug.md 在用户重建后为 4 篇新文章，「寄存器专项测试」为 #4，小节 4.1~4.6 由中文序号标题修复自动生成。

## 常见调试命令''',
"add history 24")

readme = BASE / "README.md"

patch(readme,
"  微信正文里以「一、」「二、」等中文序号开头、且不带句末标点的短行会被识别为小节标题并自动编号\n  （如 `3.2 寄存器属性测试`）。",
'''  微信正文里以「一、」「二、」等中文序号开头、且不带句末标点的短行会被识别为小节标题并自动编号
  （如 `3.2 寄存器属性测试`）；
  微信列表项里误带的标题标记（`- ### 标题`）会自动去掉，按普通列表项/段落处理。''',
"README: list-item heading note")

print("DOCS PATCHED")
