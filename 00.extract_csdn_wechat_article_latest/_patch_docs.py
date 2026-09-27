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
'''13. **覆盖模式自动备份（2026-08-16 新增）**：`write_markdown_file(markdown, target, mode, progress=None)` 在 `mode="replace"`
    且目标文件已存在时，覆盖写入前先调 `_backup_before_replace()`，把原 md 和对应 `<stem>_assets` 图片目录整体复制到
    `<stem>_assets\\backup\\<YYYYmmdd_HHMMSS>`（同秒重复自动加 `_1` 后缀；复制 assets 时用
    `ignore_patterns("backup")` 排除 backup 自身，避免递归复制）；备份路径经 `_notify(progress, ...)` 上报，
    GUI `_worker` 传 `progress=self._progress_hook`，日志会显示「覆盖前已备份原文件到：...」。append 模式不触发备份。
    **注意**：backup 目录在 assets 内，`_existing_max_image_index` 只扫 assets 顶层 `image-*.ext`，不受 backup 影响；
    但 `_download_image` 也不会扫 backup 里的图片，所以备份不会污染新文章的图片序号。

## 文件结构与职责''',
"add convention 13 (overwrite backup)")

patch(mem,
"  - 界面：来源下拉（微信/CSDN/知乎）、Cookie（可选）、文章链接（粘贴/清空）、Markdown 路径（浏览文件/选目录/打开）、写入方式（续写/覆盖）、开始提取、日志区、进度条、状态栏。",
'''  - 界面：来源下拉（微信/CSDN/知乎）、Cookie（可选）、文章链接（粘贴/清空）、Markdown 路径（浏览文件/选目录/打开）、写入方式（续写/覆盖）、开始提取、日志区、进度条、状态栏。
  - 写入方式下拉是 `tk.OptionMenu`（2026-08-16 由 ttk.Combobox 更换，因为 Combobox 下拉不支持单项着色）：
    「覆盖（替换）」菜单项用 `entryconfig(foreground="red", font=bold)` 红字加粗，选中后旁边显示红色加粗警示
    「⚠ 覆盖会替换原文件并覆盖之前的所有备份，请谨慎选择！」（`_on_mode_change` 切换，按钮文字同步变红）。''',
"update GUI description (OptionMenu)")

patch(mem,
"  - 工具函数：`validate_url`、`make_safe_filename`（Windows 保留名 CON/PRN/AUX/NUL/COM1.. 加下划线前缀）、`guess_extension`（优先 `wx_fmt` 查询参数 → 路径后缀 → Content-Type，默认 .jpg）、`write_markdown_file`、`_normalize_append_tail`（append 前清理尾部、防止 Setext 标题）、`_atomic_write`。",
'''  - 工具函数：`validate_url`、`make_safe_filename`（Windows 保留名 CON/PRN/AUX/NUL/COM1.. 加下划线前缀）、`guess_extension`（优先 `wx_fmt` 查询参数 → 路径后缀 → Content-Type，默认 .jpg）、`write_markdown_file`（mode=append/replace，replace 前自动备份）、`_backup_before_replace`（覆盖前把原 md+assets 复制到 assets\\backup\\<时间戳>）、`_normalize_append_tail`（append 前清理尾部、防止 Setext 标题）、`_atomic_write`。''',
"update tool function list")

patch(mem,
"## 常见调试命令",
'''21. 新功能：覆盖模式的危险警示与保护 → 写入方式下拉框的「覆盖（替换）」项改为红色加粗（ttk.Combobox 无法给单项着色，
    换成 `tk.OptionMenu` 并对菜单项 `entryconfig` foreground/font），选中后旁边显示红色加粗警示「⚠ 覆盖会替换原文件并覆盖之前的所有备份，请谨慎选择！」；
    覆盖写入前把原 md + `<stem>_assets` 备份到 `<stem>_assets\\backup\\<时间戳>`（`_backup_before_replace`，同秒去重、排除 backup 自身），
    GUI 日志显示备份路径；新增 `test_replace_creates_backup_of_markdown_and_assets` / `test_replace_without_existing_file_skips_backup` /
    `test_append_does_not_create_backup` 3 个测试。

## 常见调试命令''',
"add history 21")

# 更新行数标注
ext = BASE / "article_extractor.py"
lines = ext.read_text(encoding="utf-8").count("\n")
patch(mem,
"article_extractor.py`（核心，约 454 行）",
f"article_extractor.py`（核心，约 {lines} 行）",
"update line count")

readme = BASE / "README.md"

patch(readme,
"- 支持续写：把新文章追加到已有 Markdown 文件末尾；也支持覆盖模式",
'''- 支持续写：把新文章追加到已有 Markdown 文件末尾；也支持覆盖模式
- 覆盖（替换）模式有危险警示和保护：写入方式下拉框中「覆盖（替换）」为红色加粗选项，选中后界面显示红色警示文字；
  覆盖写入前会自动把原 Markdown 和对应的 `<文件名>_assets` 图片目录复制一份到 `<文件名>_assets\\backup\\<时间戳>` 下，
  不会直接丢掉旧内容''',
"README: overwrite warning + backup bullet")

patch(readme,
"   - 覆盖（替换）：用新文章覆盖整个 Markdown 文件。",
'''   - 覆盖（替换）：用新文章覆盖整个 Markdown 文件。该选项在界面中是红色加粗并带红色警示，
     提醒会覆盖原文件及之前的所有备份；选择它时，覆盖前会自动把原 Markdown 和对应的
     `<文件名>_assets` 图片目录备份到 `<文件名>_assets\\backup\\<时间戳>` 下。''',
"README: overwrite usage description")

print("DOCS PATCHED")
