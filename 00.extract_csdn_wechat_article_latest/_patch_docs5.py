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
'''16. **微信标题列表项内容合并（2026-08-16 新增）**：基类 `extract_article_html` 在 `_drop_empty_headings` 后调用
    `_merge_list_heading_content(content_node)` 钩子（基类空实现）。微信覆写：把「`<ul>/<ol>` 内只有一个 `<li>` 且 li 内容是
    单个 h1-h6」的列表（`_is_single_heading_list` 判断）后面紧邻的 `<p>`/`<ol>`/非标题 `<ul>`/`<ol>` 兄弟节点移入该 `<li>`，
    遇到下一个标题列表项即停止；markdownify 输出 `- 标题` + 缩进 2 空格的内容（同一列表层次，含嵌套有序列表）。
    CSDN/知乎不覆写，行为不变。

## 文件结构与职责''',
"add convention 16 (merge list heading content)")

patch(mem,
"## 常见调试命令",
'''25. 列表项内容层次 bug：微信「加粗小标题」写成 `<ul><li><h3>xxx</h3></li></ul>`，标题下面的内容在 `<ul>` 外的独立
    `<p>/<ol>` 节点，markdownify 输出 `- 标题` 后接顶格段落（内容与 `-` 不在同一层次）→ 已修：基类 `extract_article_html`
    新增钩子 `_merge_list_heading_content`（默认空），微信覆写把「单标题 li 列表」后面紧邻的 `<p>`/`<ol>`/非标题列表兄弟
    移入 `<li>`（遇到下一个标题列表项停止），markdownify 输出时内容自然缩进 2 空格；新增
    `test_list_heading_content_merged_into_list_item`；debug.md #4 文章 21 行内容已缩进修正。

## 常见调试命令''',
"add history 25")

readme = BASE / "README.md"

patch(readme,
"  微信列表项里误带的标题标记（`- ### 标题`）会自动去掉，按普通列表项/段落处理。",
'''  微信列表项里误带的标题标记（`- ### 标题`）会自动去掉，按普通列表项/段落处理；
  微信正文里 `- 小标题` 列表项后的内容会自动缩进到列表项下，与 `-` 保持同一层次（含嵌套列表）。''',
"README: list content indentation note")

print("DOCS PATCHED")
