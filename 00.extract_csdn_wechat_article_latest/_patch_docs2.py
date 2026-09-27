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
"   提取时间用 `datetime.now()`，格式 `%Y/%m/%d %H : %M`（注意 `HH : MM` 中间有空格）。",
'''   提取时间用 `datetime.now()`，格式 `%Y/%m/%d %H : %M`（注意 `HH : MM` 中间有空格）。
   **引用块后必须有空行再接正文**：`_build_markdown` 返回 `"\\n".join(lines) + "\\n" + body_markdown`（lines 末尾有一个空串，
   join 后补一个 `\\n` 形成空行），否则 CommonMark/Typora 的 lazy continuation 会把紧贴的正文第一段并进引用块渲染
   （debug.md「分层验证后仿思路」复现过：`> update` 后无空行，正文首段被吞进引用块）。''',
"convention 3: blank line after quote block")

patch(mem,
"## 常见调试命令",
'''22. 正文首段被吞进文章头部引用块 bug：微信文章「分层验证后仿思路」提取到 debug.md 后，正文第一段「不像RTL功能仿真，后仿，…」
    被渲染进 `> update ...` 引用块 → 已修：`_build_markdown` 生成 md 时引用块与正文之间只拼了一个 `\\n`（`"> update ...\\n" + body_markdown`），
    CommonMark/Typora 的 lazy continuation 会把紧贴的正文第一段并入引用块；改为 `"\\n".join(lines) + "\\n" + body_markdown` 保证空行分隔；
    新增 `test_body_not_merged_into_quote_block`；debug.md 中该处（update 后无空行）已直接补空行修正。

## 常见调试命令''',
"add history 22")

readme = BASE / "README.md"

patch(readme,
"- 提取时间写在引用块中，格式为 `update 年/月/日 xx : xx`",
'''- 提取时间写在引用块中，格式为 `update 年/月/日 xx : xx`
- 文章头部引用块（`> 来源：` / `> update ...`）与正文之间自动保留空行，正文不会被渲染进引用块''',
"README: quote block blank line")

print("DOCS PATCHED")
