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
"    遇到下一个标题列表项即停止；markdownify 输出 `- 标题` + 缩进 2 空格的内容（同一列表层次，含嵌套有序列表）。\n    CSDN/知乎不覆写，行为不变。",
'''    遇到下一个标题列表项即停止；markdownify 输出 `- 标题` + 缩进 2 空格的内容（同一列表层次，含嵌套有序列表）。
    真实微信 HTML 中标题可能被 `<section>/<div>` 包裹（`<li><section><h3>…`）、内容也在 `<section>` 里，
    `_single_heading_element` 递归穿透包装层找唯一标题，兄弟收集同样接受 `<section>/<div>`（遇到独立标题块停止）。
    CSDN/知乎不覆写，行为不变。''',
"convention 16: section/div support")

patch(mem,
"## 常见调试命令",
'''26. 列表项内容合并漏掉 section 包裹结构 bug：debug.md 4.2「最优测试方案」内容仍顶格（同文 4.1/4.3 等已缩进）
    → 已修：真实微信 HTML 中部分标题是 `<li><section><h3>…`（标题被 section 包裹）、内容在 `<section>` 里，
    旧合并逻辑只认 li 内直接 h1-h6 → 直接跳过；新增 `_single_heading_element`（递归穿透 section/div 找唯一标题），
    `_merge_list_heading_content` 复用该判断，兄弟收集接受 `<section>/<div>`（遇独立标题块停止）；新增
    `test_list_heading_content_merged_when_wrapped_in_section`；debug.md 4.2 的 5 行内容已手动缩进修正。

## 常见调试命令''',
"add history 26")

readme = BASE / "README.md"

patch(readme,
"  微信正文里 `- 小标题` 列表项后的内容会自动缩进到列表项下，与 `-` 保持同一层次（含嵌套列表）。",
'''  微信正文里 `- 小标题` 列表项后的内容会自动缩进到列表项下，与 `-` 保持同一层次（含嵌套列表；
  标题/内容被 `<section>` 等标签包裹时同样识别）。''',
"README: section support note")

print("DOCS PATCHED")
