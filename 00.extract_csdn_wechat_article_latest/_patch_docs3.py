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
'''14. **微信中文序号伪标题（2026-08-16 新增）**：微信正文常把「一、」「二、」这类中文序号的章节名写成普通段落（非 h2 标签），
    markdownify 转出的纯文本行既不是标题也没有强调标记。`WeChatArticleExtractor._convert_body` 用
    `CHINESE_ORDINAL_HEADING_RE`（`^[一二三四五六七八九十]{1,3}、[^。！？；：，]{1,40}$`）把「中文序号 + 短句 +
    无句末标点」的独立段落升级为 `## ` 标题，再由 `_number_headings` 统一编号（剥序后如 `## 3.2 寄存器属性测试`）。
    带句号/问号/冒号/逗号或过长的行不转换；列表项（`- 一、…`）不转换（行首不是中文序号）。
    debug.md「寄存器专项测试」一文曾因原文段落化出现 5 个「应为标题却是段落」的小节（二~六），已修。

## 文件结构与职责''',
"add convention 14 (chinese-ordinal heading)")

patch(mem,
"## 常见调试命令",
'''23. 中文序号章节名被当作段落 bug：debug.md「【验证专项】寄存器专项测试」中「二、寄存器属性测试」「三、地址粘连测试」
    「四、数据粘连测试」「五、地址边界测试」「六、全地址遍历测试」都是纯段落（应为 `##` 标题，与「一、→ 3.1」同级）
    → 已修：微信正文把这类中文序号章节名写成普通段落（非 h2），`_convert_body` 新增 `CHINESE_ORDINAL_HEADING_RE`
    （`^[一二三四五六七八九十]{1,3}、[^。！？；：，]{1,40}$`）把「中文序号 + 短句 + 无句末标点」的独立行升级为 `## ` 标题；
    新增 `test_chinese_ordinal_paragraph_becomes_heading`；debug.md 中 5 处改为 `## 3.2~3.6`，并统一 3.2 下
    「- 最优测试方案」为 `- ### 最优测试方案`（与 3.1 一致）。

## 常见调试命令''',
"add history 23")

readme = BASE / "README.md"

patch(readme,
"  正文第一个标题若与文章标题完全相同（微信文章常在正文开头重复标题），会自动跳过，避免标题重复出现。",
'''  正文第一个标题若与文章标题完全相同（微信文章常在正文开头重复标题），会自动跳过，避免标题重复出现；
  微信正文里以「一、」「二、」等中文序号开头、且不带句末标点的短行会被识别为小节标题并自动编号
  （如 `3.2 寄存器属性测试`）。''',
"README: chinese-ordinal heading note")

print("DOCS PATCHED")
