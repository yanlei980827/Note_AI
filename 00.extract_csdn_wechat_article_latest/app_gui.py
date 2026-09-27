"""Tkinter GUI for extracting CSDN or WeChat articles to Markdown."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from article_extractor import make_safe_filename, refresh_markdown_structure_file
from cnblogs_extractor import CnblogsArticleExtractor
from csdn_extractor import CSDNArticleExtractor
from wechat_extractor import (
    WeChatArticleExtractor,
    validate_url,
    write_markdown_file,
)
from zhihu_extractor import ZhihuArticleExtractor


def _should_save_screenshot(save_screenshot: bool, use_fscapture: bool) -> bool:
    """Treat FastStone mode as a screenshot request too.

    The FSCapture checkbox only selects the long-screenshot backend. If the
    user turns it on, they clearly expect a screenshot artifact to be produced,
    so we auto-enable the screenshot flow instead of requiring a second check.
    """
    return bool(save_screenshot or use_fscapture)


class ArticleMarkdownApp:
    SOURCE_LABELS = ("微信", "CSDN", "知乎", "博客园")
    MODE_LABELS = ("续写（追加）", "覆盖（替换）")
    SOURCE_HOSTS = {
        "微信": "mp.weixin.qq.com",
        "CSDN": "blog.csdn.net",
        "知乎": "zhihu.com",
        "博客园": "cnblogs.com",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("文章提取 Markdown")
        self.root.geometry("820x560")
        self.root.minsize(720, 480)

        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.running = False
        self.default_dir = str(Path.cwd())

        self.url_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.cookie_var = tk.StringVar()
        self.source_var = tk.StringVar(value=self.SOURCE_LABELS[0])
        self.mode_var = tk.StringVar(value=self.MODE_LABELS[0])
        self.screenshot_var = tk.BooleanVar(value=False)
        self.fscapture_var = tk.BooleanVar(value=False)
        self.pdf_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self._on_mode_change(self.mode_var.get())
        self.root.after(120, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        padding = {"padx": 12, "pady": 6}
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(6, weight=1)

        title = ttk.Label(
            outer,
            text="文章提取 Markdown",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", **padding)

        source_frame = ttk.Frame(outer)
        source_frame.grid(row=1, column=0, sticky="ew", **padding)
        ttk.Label(source_frame, text="文章来源").pack(side="left", padx=(0, 12))
        source_combo = ttk.Combobox(
            source_frame,
            textvariable=self.source_var,
            values=self.SOURCE_LABELS,
            state="readonly",
            width=16,
        )
        source_combo.pack(side="left")

        cookie_frame = ttk.Frame(outer)
        cookie_frame.grid(row=2, column=0, sticky="ew", **padding)
        cookie_frame.columnconfigure(1, weight=1)
        ttk.Label(cookie_frame, text="Cookie（可选）").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        cookie_entry = ttk.Entry(cookie_frame, textvariable=self.cookie_var)
        cookie_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(
            cookie_frame,
            text="说明",
            width=6,
            command=self._show_cookie_help,
        ).grid(row=0, column=2, padx=(6, 0))

        url_frame = ttk.Frame(outer)
        url_frame.grid(row=3, column=0, sticky="ew", **padding)
        url_frame.columnconfigure(1, weight=1)
        ttk.Label(url_frame, text="文章链接").grid(row=0, column=0, sticky="w", padx=(0, 8))
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(url_frame, text="粘贴", width=6, command=self._paste_url).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Button(url_frame, text="清空", width=6, command=lambda: self.url_var.set("")).grid(
            row=0, column=3, padx=(6, 0)
        )

        out_frame = ttk.Frame(outer)
        out_frame.grid(row=4, column=0, sticky="ew", **padding)
        out_frame.columnconfigure(1, weight=1)
        ttk.Label(out_frame, text="Markdown 路径").grid(row=0, column=0, sticky="w", padx=(0, 8))
        out_entry = ttk.Entry(out_frame, textvariable=self.out_var)
        out_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(out_frame, text="浏览...", width=8, command=self._browse_file).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Button(out_frame, text="选目录", width=8, command=self._browse_folder).grid(
            row=0, column=3, padx=(6, 0)
        )
        ttk.Button(out_frame, text="打开", width=6, command=self._open_markdown).grid(
            row=0, column=4, padx=(6, 0)
        )
        ttk.Button(out_frame, text="去重", width=6, command=self._deduplicate).grid(
            row=0, column=5, padx=(6, 0)
        )
        ttk.Button(
            out_frame,
            text="重排标题/目录",
            width=12,
            command=self._refresh_structure,
        ).grid(row=0, column=6, padx=(6, 0))

        mode_frame = ttk.Frame(outer)
        mode_frame.grid(row=5, column=0, sticky="ew", **padding)
        ttk.Label(mode_frame, text="写入方式").pack(side="left", padx=(0, 12))
        self.mode_menu = tk.OptionMenu(
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
        self.mode_warn.pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            mode_frame,
            text="保存长截图",
            variable=self.screenshot_var,
        ).pack(side="left", padx=(16, 0))
        ttk.Checkbutton(
            mode_frame,
            text="用 FSCapture 自动长截图",
            variable=self.fscapture_var,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            mode_frame,
            text="输出 PDF（需 Chrome/Edge）",
            variable=self.pdf_var,
        ).pack(side="left", padx=(16, 0))
        self.extract_button = ttk.Button(
            mode_frame,
            text="开始提取",
            command=self._start,
            width=14,
        )
        self.extract_button.pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="运行日志", padding=8)
        log_frame.grid(row=6, column=0, sticky="nsew", **padding)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        progress.grid(row=7, column=0, sticky="ew", **padding)
        self.progress = progress

        status = ttk.Label(outer, textvariable=self.status_var, anchor="w")
        status.grid(row=8, column=0, sticky="ew", **padding)

    def _on_mode_change(self, value: str) -> None:
        is_replace = value == self.MODE_LABELS[1]
        if is_replace:
            self.mode_warn.config(
                text="非空文件会拒绝写入，不会覆盖原内容。"
            )
            self.mode_menu.config(fg="red")
        else:
            self.mode_warn.config(text="")
            self.mode_menu.config(fg="black")

    def _show_cookie_help(self) -> None:
        messagebox.showinfo(
            "Cookie 说明",
            "遇到 CSDN 安全验证、知乎 403 或正文不完整时，"
            "需要粘贴浏览器登录后的 Cookie：\n\n"
            "1. 用浏览器打开文章，并确认已登录知乎/CSDN。\n"
            "2. 按 F12 打开开发者工具，切到 Network（网络）面板。\n"
            "3. 按 F5 刷新页面。\n"
            "4. 在请求列表点第一条 document 请求，"
            "名字通常是文章链接的最后一段。\n"
            "5. 右侧切到 Headers，往下找到 Request Headers。\n"
            "6. 复制 cookie: 后面的整行值，通常很长。\n"
            "7. 粘贴到这里，再点击开始提取。\n\n"
            "Cookie 与账号绑定且会过期，遇到 403 时重新复制即可；"
            "它属于敏感信息，请勿发给他人。",
        )

    def _paste_url(self) -> None:
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            self._log("剪贴板中没有可粘贴的文本")
            return
        self.url_var.set(text)
        detected = self._detect_source(text)
        if detected:
            self.source_var.set(detected)

    @staticmethod
    def _detect_source(url: str):
        host = urlparse(url).netloc.lower()
        if "blog.csdn.net" in host:
            return "CSDN"
        if "zhihu.com" in host:
            return "知乎"
        if "mp.weixin.qq.com" in host:
            return "微信"
        if "cnblogs.com" in host:
            return "博客园"
        return None

    def _browse_file(self) -> None:
        current = self.out_var.get().strip()
        if current:
            current_path = Path(current)
            if current_path.is_dir():
                initial_dir = str(current_path)
                initial_file = "articles.md"
            else:
                initial_dir = str(current_path.parent)
                initial_file = current_path.name
        else:
            initial_dir = self.default_dir
            initial_file = "articles.md"
        path = filedialog.asksaveasfilename(
            title="选择 Markdown 文件",
            defaultextension=".md",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("Markdown 文件", "*.md"), ("所有文件", "*.*")],
        )
        if path:
            self.out_var.set(path)

    def _browse_folder(self) -> None:
        initial = self.out_var.get().strip() or self.default_dir
        path = filedialog.askdirectory(title="选择保存目录", initialdir=initial)
        if path:
            self.out_var.set(path)

    def _open_markdown(self) -> None:
        path_text = self.out_var.get().strip()
        if not path_text:
            messagebox.showinfo("提示", "请先选择 Markdown 文件路径")
            return
        path = Path(path_text).expanduser()
        if not path.exists():
            messagebox.showwarning("路径不存在", f"文件或目录不存在：\n{path}")
            return
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _deduplicate(self) -> None:
        if self.running:
            messagebox.showinfo("提示", "正在提取中，请稍后再操作。")
            return
        path_text = self.out_var.get().strip()
        if not path_text:
            messagebox.showwarning("提示", "请先选择 Markdown 文件路径。")
            return
        target = Path(path_text).expanduser()
        if not target.is_file():
            messagebox.showwarning("文件不存在", f"文件不存在：\n{target}")
            return
        if not messagebox.askyesno(
            "确认去重",
            "将删除重复文章（同一链接只保留最新提取的一篇），"
            "并自动备份原文件。\n是否继续？",
        ):
            return
        try:
            summary = deduplicate_markdown_file(target)
        except Exception as exc:
            messagebox.showerror("去重失败", str(exc))
            return
        if summary is None:
            messagebox.showinfo("去重完成", "没有发现重复文章。")
            return
        message = f"已删除 {summary.removed} 篇重复文章，保留 {summary.remaining} 篇。"
        if summary.backup_path is not None:
            message += f"\n原文件已备份到：\n{summary.backup_path}"
        messagebox.showinfo("去重完成", message)
        self._log(f"去重完成：{message}")

    def _refresh_structure(self) -> None:
        if self.running:
            messagebox.showinfo("提示", "正在提取中，请稍后再操作。")
            return
        path_text = self.out_var.get().strip()
        if not path_text:
            messagebox.showwarning("提示", "请先选择 Markdown 文件路径。")
            return
        target = Path(path_text).expanduser()
        if not target.is_file():
            messagebox.showwarning("文件不存在", f"文件不存在：\n{target}")
            return
        if not messagebox.askyesno(
            "确认重排",
            "将按当前标题层级重新编号全部标题并重建目录，"
            "并自动备份原文件。\n是否继续？",
        ):
            return
        try:
            summary = refresh_markdown_structure_file(target)
        except Exception as exc:
            messagebox.showerror("重排失败", str(exc))
            return
        if summary is None:
            messagebox.showinfo("重排完成", "没有发现需要调整的标题或目录。")
            self._log("重排完成：没有发现需要调整的标题或目录。")
            return
        message = "已完成标题重排并重建目录。"
        if summary.backup_path is not None:
            message += f"\n原文件已备份到：\n{summary.backup_path}"
        messagebox.showinfo("重排完成", message)
        self._log(f"重排完成：{message}")

    def _start(self) -> None:
        if self.running:
            return
        url = self.url_var.get().strip()
        try:
            validate_url(url)
        except ValueError as exc:
            messagebox.showwarning("链接无效", str(exc))
            return

        source = self.source_var.get()
        extractor = self._make_extractor(source)
        host = urlparse(url).netloc.lower()
        expected_host = self.SOURCE_HOSTS.get(source)
        if host and expected_host and expected_host not in host:
            confirmed = messagebox.askyesno(
                f"非{source}链接",
                f"链接域名不是 {expected_host}，仍要尝试提取吗？",
            )
            if not confirmed:
                return

        mode = "append" if self.mode_var.get() == self.MODE_LABELS[0] else "replace"
        raw_target = self.out_var.get().strip()

        self.running = True
        self.extract_button.configure(state="disabled")
        self.progress.configure(value=0, maximum=100)
        self.status_var.set("正在提取...")
        self._log("=" * 60)
        self._log(f"开始提取（{source}）：{url}")

        save_screenshot = _should_save_screenshot(
            bool(self.screenshot_var.get()),
            bool(self.fscapture_var.get()),
        )
        use_fscapture = bool(self.fscapture_var.get())
        if use_fscapture and not self.screenshot_var.get():
            self.screenshot_var.set(True)
            self._log("已启用 FSCapture，将自动保存长截图。")
        save_pdf = bool(self.pdf_var.get())
        thread = threading.Thread(
            target=self._worker,
            args=(
                url,
                raw_target,
                mode,
                extractor,
                save_screenshot,
                use_fscapture,
                save_pdf,
            ),
            daemon=True,
        )
        thread.start()

    def _make_extractor(self, source: str):
        cookie = self.cookie_var.get().strip()
        if source == "CSDN":
            return CSDNArticleExtractor(cookie=cookie)
        if source == "知乎":
            return ZhihuArticleExtractor(cookie=cookie)
        if source == "博客园":
            return CnblogsArticleExtractor(cookie=cookie)
        return WeChatArticleExtractor(cookie=cookie)

    def _worker(
        self,
        url: str,
        raw_target: str,
        mode: str,
        extractor,
        save_screenshot: bool = False,
        use_fscapture: bool = False,
        save_pdf: bool = False,
    ) -> None:
        try:
            markdown_path = Path(raw_target).expanduser() if raw_target else None
            result = extractor.extract_article_html(
                url,
                markdown_path=markdown_path,
                progress=self._progress_hook,
                save_screenshot=save_screenshot,
            )
            saved = write_markdown_file(
                result.markdown,
                result.markdown_path,
                mode=mode,
                progress=self._progress_hook,
                url=result.metadata.url,
            )
            screenshot_path = None
            screenshot_error = None
            if save_screenshot:
                try:
                    from screenshot import (
                        ScreenshotError,
                        capture_article_screenshot,
                        capture_article_screenshot_with_fscapture,
                    )

                    safe_title = make_safe_filename(result.metadata.title or "文章")
                    # 长截图保存到 markdown 同名的 _assets 图片目录，文件名用文章标题
                    shot_target = (
                        saved.parent / f"{saved.stem}_assets" / f"{safe_title}.png"
                    )
                    if use_fscapture:
                        self.queue.put(
                            ("log", "正在生成长截图（自动打开浏览器并调用 FSCapture）...")
                        )
                        try:
                            screenshot_path = capture_article_screenshot_with_fscapture(
                                result.metadata.title,
                                result.body_html,
                                shot_target,
                                base_dir=saved.parent,
                                author=result.metadata.author,
                                publish_time=result.metadata.publish_time,
                            )
                        except Exception as exc:
                            self.queue.put(
                                (
                                    "log",
                                    f"FSCapture 长截图失败：{exc}，改用 Chrome/Edge 回退...",
                                )
                            )
                            self.queue.put(
                                ("log", "正在生成长截图（调用本机 Chrome/Edge）...")
                            )
                            screenshot_path = capture_article_screenshot(
                                result.metadata.title,
                                result.body_html,
                                shot_target,
                                base_dir=saved.parent,
                                author=result.metadata.author,
                                publish_time=result.metadata.publish_time,
                            )
                    else:
                        self.queue.put(("log", "正在生成长截图（调用本机 Chrome/Edge）..."))
                        screenshot_path = capture_article_screenshot(
                            result.metadata.title,
                            result.body_html,
                            shot_target,
                            base_dir=saved.parent,
                            author=result.metadata.author,
                            publish_time=result.metadata.publish_time,
                        )
                    self.queue.put(("log", f"长截图已保存：{screenshot_path}"))
                except ScreenshotError as exc:
                    screenshot_error = str(exc)
                    self.queue.put(("log", f"长截图失败：{exc}"))
                except Exception as exc:
                    screenshot_error = str(exc)
                    self.queue.put(("log", f"长截图失败：{exc}"))
            pdf_path = None
            pdf_error = None
            if save_pdf:
                try:
                    from pdf_export import ScreenshotError as PdfError
                    from pdf_export import export_markdown_pdf

                    self.queue.put(("log", "正在输出 PDF（整份 Markdown，调用本机 Chrome/Edge）..."))
                    # PDF 保存到 markdown 同目录的 PDF 文件夹，文件名用 markdown 文件名
                    pdf_target = saved.parent / "PDF" / f"{saved.stem}.pdf"
                    pdf_path = export_markdown_pdf(saved, pdf_target, base_dir=saved.parent)
                    self.queue.put(("log", f"PDF 已保存：{pdf_path}"))
                except PdfError as exc:
                    pdf_error = str(exc)
                    self.queue.put(("log", f"输出 PDF 失败：{exc}"))
                except Exception as exc:
                    pdf_error = str(exc)
                    self.queue.put(("log", f"输出 PDF 失败：{exc}"))
            self.queue.put(("done", saved, result, screenshot_path, screenshot_error, pdf_path, pdf_error))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _progress_hook(self, message: str, done: int, total: int) -> None:
        self.queue.put(("progress", message, done, total))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, message, done, total = item
                    self._log(message)
                    self.status_var.set(message)
                    if total:
                        percent = min(100, int(done * 100 / total))
                        self.progress.configure(maximum=total)
                        self.progress.configure(value=done)
                        if done >= total:
                            self.progress.configure(maximum=100, value=100)
                elif kind == "done":
                    (
                        _,
                        saved,
                        result,
                        screenshot_path,
                        screenshot_error,
                        pdf_path,
                        pdf_error,
                    ) = item
                    self._finish_ok(
                        saved,
                        result,
                        screenshot_path,
                        screenshot_error,
                        pdf_path,
                        pdf_error,
                    )
                elif kind == "log":
                    _, message = item
                    self._log(message)
                elif kind == "error":
                    _, message = item
                    self._finish_error(message)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _finish_ok(
        self,
        saved: Path,
        result,
        screenshot_path=None,
        screenshot_error=None,
        pdf_path=None,
        pdf_error=None,
    ) -> None:
        self.running = False
        self.extract_button.configure(state="normal")
        self.progress.configure(maximum=100, value=100)
        self.status_var.set("提取完成")
        self._log(
            f"完成：标题「{result.metadata.title}」"
            f"，图片 {result.image_count} 张，已保存到 {saved}"
        )
        message = f"已保存到：\n{saved}"
        notes = []
        if screenshot_path:
            notes.append(f"长截图：\n{screenshot_path}")
            self._log(f"长截图已保存：{screenshot_path}")
        elif screenshot_error:
            notes.append(f"长截图生成失败：\n{screenshot_error}")
            self._log(f"长截图失败：{screenshot_error}")
        if pdf_path:
            notes.append(f"PDF：\n{pdf_path}")
            self._log(f"PDF 已保存：{pdf_path}")
        elif pdf_error:
            notes.append(f"PDF 生成失败：\n{pdf_error}")
            self._log(f"输出 PDF 失败：{pdf_error}")
        if screenshot_path or pdf_path:
            self.status_var.set("提取完成（含长截图/PDF）")
        elif screenshot_error or pdf_error:
            self.status_var.set("提取完成（部分附加文件失败）")
        for note in notes:
            message += f"\n\n{note}"
        messagebox.showinfo("提取完成", message)

    def _finish_error(self, message: str) -> None:
        self.running = False
        self.extract_button.configure(state="normal")
        self.progress.configure(value=0)
        self.status_var.set("提取失败")
        self._log(f"错误：{message}")
        messagebox.showerror("提取失败", message)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self.running and not messagebox.askokcancel(
            "正在提取", "提取尚未完成，确定要退出吗？"
        ):
            return
        self.root.destroy()
