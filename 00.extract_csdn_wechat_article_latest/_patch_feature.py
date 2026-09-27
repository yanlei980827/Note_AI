# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(r"D:\sandbox\extract_csdn_wechat_article_0815_fix")

def patch(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"NOT FOUND in {path.name}: {what}"
    assert text.count(old) == 1, f"NOT UNIQUE in {path.name}: {what}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path.name}: {what}")

# ---------- article_extractor.py ----------
ext = BASE / "article_extractor.py"

patch(ext,
"import os\nimport re\nimport tempfile\n",
"import os\nimport re\nimport shutil\nimport tempfile\n",
"add shutil import")

patch(ext,
"def write_markdown_file(\n",
'''def _backup_before_replace(target: Path) -> Optional[Path]:
    """Copy an existing markdown and its ``<stem>_assets`` image folder into
    ``<stem>_assets/backup/<timestamp>`` before the file gets overwritten."""
    if not target.is_file():
        return None
    assets_dir = target.parent / f"{target.stem}_assets"
    backup_root = assets_dir / "backup"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / stamp
    suffix = 1
    while backup_dir.exists():
        backup_dir = backup_root / f"{stamp}_{suffix}"
        suffix += 1
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_dir / target.name)
    if assets_dir.is_dir():
        shutil.copytree(
            assets_dir,
            backup_dir / assets_dir.name,
            ignore=shutil.ignore_patterns("backup"),
        )
    return backup_dir


def write_markdown_file(
''',
"add _backup_before_replace helper")

patch(ext,
"    mode: str = \"append\",\n) -> Path:\n",
"    mode: str = \"append\",\n    progress: Optional[ProgressCallback] = None,\n) -> Path:\n",
"add progress param")

patch(ext,
"""    else:
        newline = "\\r\\n" if os.name == "nt" else "\\n"
        _atomic_write(target, _number_headings(_newline_to(markdown, newline)))
    return target""",
"""    else:
        newline = "\\r\\n" if os.name == "nt" else "\\n"
        if target.exists() and target.is_file():
            backup_dir = _backup_before_replace(target)
            _notify(progress, f"覆盖前已备份原文件到：{backup_dir}")
        _atomic_write(target, _number_headings(_newline_to(markdown, newline)))
    return target""",
"backup before replace write")

# ---------- app_gui.py ----------
gui = BASE / "app_gui.py"

patch(gui,
"""        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=self.MODE_LABELS,
            state="readonly",
            width=16,
        )
        mode_combo.pack(side="left")""",
"""        self.mode_menu = tk.OptionMenu(
            mode_frame,
            self.mode_var,
            *self.MODE_LABELS,
            command=self._on_mode_change,
        )
        self.mode_menu.config(
            font=("Microsoft YaHei UI", 9),
            relief="groove",
            anchor="w",
            width=14,
        )
        self.mode_menu.pack(side="left")
        mode_dropdown = self.mode_menu["menu"]
        mode_dropdown.config(font=("Microsoft YaHei UI", 9))
        for index, label in enumerate(self.MODE_LABELS):
            if label == self.MODE_LABELS[1]:
                mode_dropdown.entryconfig(
                    index,
                    foreground="red",
                    font=("Microsoft YaHei UI", 9, "bold"),
                )
        self.mode_warn = tk.Label(
            mode_frame,
            text="",
            fg="red",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.mode_warn.pack(side="left", padx=(16, 0))""",
"red bold overwrite option + warning label")

patch(gui,
"""        self._build_ui()
        self.root.after(120, self._poll_queue)""",
"""        self._build_ui()
        self._on_mode_change(self.mode_var.get())
        self.root.after(120, self._poll_queue)""",
"init mode warning state")

patch(gui,
"    def _show_cookie_help(self) -> None:",
"""    def _on_mode_change(self, value: str) -> None:
        is_replace = value == self.MODE_LABELS[1]
        if is_replace:
            self.mode_warn.config(
                text="⚠ 覆盖会替换原文件并覆盖之前的所有备份，请谨慎选择！"
            )
            self.mode_menu.config(fg="red")
        else:
            self.mode_warn.config(text="")
            self.mode_menu.config(fg="black")

    def _show_cookie_help(self) -> None:""",
"add _on_mode_change")

patch(gui,
"            saved = write_markdown_file(result.markdown, result.markdown_path, mode=mode)",
"""            saved = write_markdown_file(
                result.markdown,
                result.markdown_path,
                mode=mode,
                progress=self._progress_hook,
            )""",
"pass progress to write_markdown_file")

# ---------- test_extractor.py ----------
tst = BASE / "test_extractor.py"

patch(tst,
"    def test_append_continues_image_index(self):",
'''    def test_replace_creates_backup_of_markdown_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\\n", encoding="utf-8")
            assets = Path(tmp) / "notes_assets"
            assets.mkdir()
            old_image = assets / "image-0001.png"
            old_image.write_bytes(PNG_BYTES)
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="replace")
            write_markdown_file(result.markdown, target, mode="replace")

            replaced = target.read_text(encoding="utf-8")
            self.assertNotIn("旧文章内容", replaced)
            self.assertIn("# 1 微信文章标题", replaced)

            backup_root = assets / "backup"
            self.assertTrue(backup_root.is_dir())
            backups = sorted(backup_root.glob("*/notes.md"))
            self.assertEqual(len(backups), 2)
            first_backup_md = backups[0]
            self.assertIn("旧文章内容", first_backup_md.read_text(encoding="utf-8"))
            backup_image = first_backup_md.parent / "notes_assets" / "image-0001.png"
            self.assertTrue(backup_image.is_file())
            self.assertEqual(backup_image.read_bytes(), PNG_BYTES)

    def test_replace_without_existing_file_skips_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="replace")

            self.assertTrue(target.is_file())
            self.assertFalse((Path(tmp) / "notes_assets" / "backup").exists())

    def test_append_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")

            self.assertFalse((Path(tmp) / "notes_assets" / "backup").exists())

    def test_append_continues_image_index(self):''',
"add backup tests")

print("ALL PATCHES APPLIED")
