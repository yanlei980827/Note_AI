"""Offline unit tests for the PDF export module."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import pdf_export
import screenshot
from pdf_export import (
    ScreenshotError,
    _build_markdown_pdf_html,
    _build_pdf_html,
    export_article_pdf,
    export_markdown_pdf,
    markdown_to_html,
)


class BuildPdfHtmlTest(unittest.TestCase):
    def test_uses_print_css_with_article_head(self):
        html = _build_pdf_html("测试标题", "<div>正文</div>", author="芯片茶馆", publish_time="2026年8月13日 21:00")
        self.assertIn("@page", html)
        self.assertIn("size: A4", html)
        self.assertIn("page-break-inside: avoid", html)
        self.assertIn('<h1 class="article-title">测试标题</h1>', html)
        self.assertIn("芯片茶馆", html)
        self.assertIn("<div>正文</div>", html)

    def test_uses_screenshot_css_as_base(self):
        html = _build_pdf_html("标题", "<p>正文</p>")
        # 打印样式在截图样式基础上叠加
        self.assertIn("visibility: visible !important", html)
        self.assertIn(".article-head", html)


class BuildMarkdownPdfHtmlTest(unittest.TestCase):
    def test_wraps_whole_document_without_article_head(self):
        doc = _build_markdown_pdf_html("<h1>x</h1>", title="articles")
        self.assertIn("@page", doc)
        self.assertIn("<h1>x</h1>", doc)
        self.assertIn("<title>articles</title>", doc)
        # 整份 markdown 不叠加单篇文章的公众号头部
        # 整份 markdown 不渲染单篇文章的公众号头部 div
        self.assertNotIn('<div class="article-head">', doc)


class MarkdownToHtmlTest(unittest.TestCase):
    def test_headings_hr_and_paragraph(self):
        html = markdown_to_html("# 标题一\n\n## 1.1 小节\n\n---\n\n正文")
        self.assertIn('<h1 id="标题一">标题一</h1>', html)
        self.assertIn('<h2 id="11-小节">1.1 小节</h2>', html)
        self.assertIn("<hr>", html)
        self.assertIn("<p>正文</p>", html)

    def test_blockquote_and_quote_bold_mark(self):
        html = markdown_to_html("> 来源：https://x\n\n> **已截图**\n\n正文")
        self.assertIn("<blockquote><p>来源：https://x</p></blockquote>", html)
        self.assertIn("<strong>已截图</strong>", html)
        self.assertIn("<p>正文</p>", html)

    def test_nested_list_and_indented_continuation(self):
        md = "- 标题\n  内容行\n- 第二项\n  - 子项"
        html = markdown_to_html(md)
        self.assertIn("<li>标题<br>内容行</li>", html)
        self.assertIn("<li>第二项", html)
        self.assertIn("<li>第二项<ul>", html)
        self.assertIn("<li>子项</li>", html)

    def test_ordered_list(self):
        html = markdown_to_html("1. 甲\n2. 乙")
        self.assertIn("<ol>", html)
        self.assertIn("<li>甲</li>", html)
        self.assertIn("<li>乙</li>", html)

    def test_fenced_code_keeps_content_escaped(self):
        html = markdown_to_html("```verilog\nwire a;\n<b> & </b>\n```")
        self.assertIn('<pre><code class="language-verilog">', html)
        self.assertIn("wire a;", html)
        self.assertIn("&lt;b&gt; &amp; &lt;/b&gt;", html)

    def test_pipe_table(self):
        md = "| 信号 | 说明 |\n| --- | --- |\n| clk | 时钟 |"
        html = markdown_to_html(md)
        self.assertIn("<table>", html)
        self.assertIn("<th>信号</th>", html)
        self.assertIn("<td>clk</td>", html)

    def test_image_and_link_escape_attributes(self):
        md = "![](debug_assets/a.png) [链接](https://example.com?a=1&b=2)"
        html = markdown_to_html(md)
        self.assertIn('<img src="debug_assets/a.png" alt="">', html)
        self.assertIn('<a href="https://example.com?a=1&amp;b=2">链接</a>', html)

    def test_inline_emphasis_and_code(self):
        md = "**加粗** *斜体* `code` ~~删除~~"
        html = markdown_to_html(md)
        self.assertIn("<strong>加粗</strong>", html)
        self.assertIn("<em>斜体</em>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("<del>删除</del>", html)

    def test_hard_break(self):
        html = markdown_to_html("第一行  \n第二行")
        self.assertIn("<p>第一行<br>第二行</p>", html)

    def test_multiline_paragraph_keeps_line_breaks(self):
        html = markdown_to_html("第一行\n第二行")
        self.assertIn("<p>第一行<br>第二行</p>", html)

    def test_multiline_quote_keeps_line_breaks(self):
        html = markdown_to_html(
            "> 来源：https://mp.weixin.qq.com/s/7OlZxLRCNamOKvddR2BbqQ\n"
            "> update 2026/08/16 14 : 45"
        )
        self.assertIn(
            "<blockquote><p>来源：https://mp.weixin.qq.com/s/7OlZxLRCNamOKvddR2BbqQ"
            "<br>update 2026/08/16 14 : 45</p></blockquote>",
            html,
        )

    def test_toc_plain_links_have_no_bullet(self):
        md = (
            "<!-- toc-start -->\n\n# 目录\n\n"
            "[1 标题](#1-标题)  \n　　[1.1 小节](#11-小节)  \n\n"
            "<!-- toc-end -->\n\n---\n\n# 1 标题"
        )
        html = markdown_to_html(md)
        self.assertNotIn("<ul", html)
        self.assertNotIn("<li>", html)
        self.assertIn('<a href="#1-标题">1 标题</a>', html)
        self.assertIn('　　<a href="#11-小节">1.1 小节</a>', html)
        self.assertIn('<a href="#11-小节">1.1 小节</a>', html)

    def test_crlf_input(self):
        html = markdown_to_html("# 标题\r\n\r\n正文\r\n")
        self.assertIn('<h1 id="标题">标题</h1>', html)
        self.assertIn("<p>正文</p>", html)

    def test_skips_html_comments_and_adds_heading_ids(self):
        md = "<!-- toc-start -->\n\n# 目录\n\n- [1 标题](#1-标题)\n\n<!-- toc-end -->\n\n---\n\n# 1 标题"
        html = markdown_to_html(md)
        self.assertNotIn("toc-start", html)
        self.assertNotIn("toc-end", html)
        self.assertIn('<h1 id="目录">目录</h1>', html)
        self.assertIn('<a href="#1-标题">1 标题</a>', html)
        self.assertIn('<h1 id="1-标题">1 标题</h1>', html)

    def test_nbsp_indent_is_paragraph_not_code(self):
        md = "- 覆盖范围\n\n   \xa0 \xa0所有寄存器地址映射有效性、死地址、未绑定地址。\n"
        html = markdown_to_html(md)
        self.assertNotIn("<pre>", html)
        self.assertIn("<li>覆盖范围<br>所有寄存器地址映射有效性、死地址、未绑定地址。</li>", html)

    def test_ascii_four_space_indent_is_code(self):
        html = markdown_to_html("    wire a;\n    assign b = a;")
        self.assertIn("<pre><code>wire a;", html)

    def test_toc_plain_links_keep_indent(self):
        md = (
            "<!-- toc-start -->\n\n# 目录\n\n"
            "[1 标题](#1-标题)  \n　　[1.1 小节](#11-小节)  \n　　　　[1.1.1 子节](#111-子节)  \n\n"
            "<!-- toc-end -->\n\n---\n\n# 1 标题"
        )
        html = markdown_to_html(md)
        self.assertIn('<a href="#1-标题">1 标题</a><br>　　<a href="#11-小节">1.1 小节</a>', html)
        self.assertIn('　　　　<a href="#111-子节">1.1.1 子节</a>', html)

    def test_link_label_with_escaped_brackets(self):
        html = markdown_to_html("- [UART TX bit\\[0\\]翻转](#14-bit0)")
        self.assertIn('<a href="#14-bit0">UART TX bit[0]翻转</a>', html)

    def test_print_css_has_green_blockquote(self):
        self.assertIn("#2f9e44", pdf_export.PRINT_CSS)
        self.assertIn("background: #f0f8ef", pdf_export.PRINT_CSS)


class NoBrowserTest(unittest.TestCase):
    def test_export_raises_friendly_error_without_browser(self):
        original = pdf_export.find_browser
        pdf_export.find_browser = lambda: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "a.pdf"
                with self.assertRaises(ScreenshotError) as ctx:
                    export_article_pdf("标题", "<p>x</p>", out, base_dir=tmp)
                self.assertIn("Chrome/Edge", str(ctx.exception))
        finally:
            pdf_export.find_browser = original

    def test_export_markdown_raises_without_browser(self):
        original = pdf_export.find_browser
        pdf_export.find_browser = lambda: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                md = Path(tmp) / "a.md"
                md.write_text("# 标题\n", encoding="utf-8")
                out = Path(tmp) / "a.pdf"
                with self.assertRaises(ScreenshotError) as ctx:
                    export_markdown_pdf(md, out, base_dir=tmp)
                self.assertIn("Chrome/Edge", str(ctx.exception))
        finally:
            pdf_export.find_browser = original


class RunBrowserLabelTest(unittest.TestCase):
    def test_error_message_uses_label(self):
        original_run = screenshot.subprocess.run

        def boom(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

        screenshot.subprocess.run = boom
        try:
            with self.assertRaises(ScreenshotError) as ctx:
                screenshot._run_browser("C:/fake/chrome.exe", ["--x"], label="PDF")
            self.assertIn("生成PDF超时", str(ctx.exception))
        finally:
            screenshot.subprocess.run = original_run


class ExportRoundTripTest(unittest.TestCase):
    def test_export_writes_pdf_and_cleans_temp_files(self):
        calls = {}

        def fake_run(browser, args, label="截图"):
            calls["args"] = args
            calls["label"] = label
            for arg in args:
                if arg.startswith("--print-to-pdf="):
                    Path(arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4 fake")
            return ""

        original_find = pdf_export.find_browser
        original_run = pdf_export._run_browser
        pdf_export.find_browser = lambda: "C:/fake/chrome.exe"
        pdf_export._run_browser = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                out = base / "PDF" / "文章.pdf"
                result = export_article_pdf("标题", "<p>正文</p>", out, base_dir=base)
                self.assertEqual(result, out)
                self.assertTrue(out.is_file())
                self.assertGreater(out.stat().st_size, 0)
                self.assertIn("--print-to-pdf=", " ".join(calls["args"]))
                self.assertEqual(calls["label"], "PDF")
                self.assertIn("--no-pdf-header-footer", calls["args"])
                # 临时 HTML 不应残留在 markdown 目录
                leftovers = [p.name for p in base.iterdir() if p.name != "PDF"]
                self.assertEqual(leftovers, [])
        finally:
            pdf_export.find_browser = original_find
            pdf_export._run_browser = original_run

    def test_export_raises_when_browser_writes_nothing(self):
        original_find = pdf_export.find_browser
        original_run = pdf_export._run_browser
        pdf_export.find_browser = lambda: "C:/fake/chrome.exe"
        pdf_export._run_browser = lambda browser, args, label="截图": ""
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "b.pdf"
                with self.assertRaises(ScreenshotError) as ctx:
                    export_article_pdf("标题", "<p>x</p>", out, base_dir=tmp)
                self.assertIn("未生成 PDF", str(ctx.exception))
        finally:
            pdf_export.find_browser = original_find
            pdf_export._run_browser = original_run


class ExportWholeMarkdownTest(unittest.TestCase):
    def test_export_whole_markdown_pdf(self):
        calls = {}

        def fake_run(browser, args, label="截图"):
            calls["args"] = args
            calls["label"] = label
            for arg in args:
                if arg.startswith("--print-to-pdf="):
                    Path(arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4 fake")
            return ""

        original_find = pdf_export.find_browser
        original_run = pdf_export._run_browser
        pdf_export.find_browser = lambda: "C:/fake/chrome.exe"
        pdf_export._run_browser = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                md = base / "articles.md"
                md.write_text(
                    "# 1 第一篇文章\n\n## 1.1 小节\n\n正文\n\n---\n\n# 2 第二篇文章\n",
                    encoding="utf-8",
                )
                out = base / "PDF" / "articles.pdf"
                result = export_markdown_pdf(md, out, base_dir=base)
                self.assertEqual(result, out)
                self.assertTrue(out.is_file())
                self.assertGreater(out.stat().st_size, 0)
                self.assertIn("--print-to-pdf=", " ".join(calls["args"]))
                self.assertEqual(calls["label"], "PDF")
                # 只留下 md 文件本身，临时 HTML 被清理
                leftovers = [p.name for p in base.iterdir() if p.name != "PDF"]
                self.assertEqual(leftovers, ["articles.md"])
        finally:
            pdf_export.find_browser = original_find
            pdf_export._run_browser = original_run

    def test_export_markdown_missing_file_raises(self):
        original_find = pdf_export.find_browser
        original_run = pdf_export._run_browser
        pdf_export.find_browser = lambda: "C:/fake/chrome.exe"
        pdf_export._run_browser = lambda browser, args, label="截图": ""
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "x.pdf"
                with self.assertRaises(ScreenshotError) as ctx:
                    export_markdown_pdf(Path(tmp) / "missing.md", out, base_dir=tmp)
                self.assertIn("不存在", str(ctx.exception))
        finally:
            pdf_export.find_browser = original_find
            pdf_export._run_browser = original_run


if __name__ == "__main__":
    unittest.main()

class BookmarkInjectionTest(unittest.TestCase):
    def test_injection_failure_does_not_break_export(self):
        # 浏览器写出非合法 PDF → pypdf 读取失败被吞掉，PDF 仍返回
        original_find = pdf_export.find_browser
        original_run = pdf_export._run_browser
        pdf_export.find_browser = lambda: "C:/fake/chrome.exe"

        def fake_run(browser, args, label="截图"):
            for arg in args:
                if arg.startswith("--print-to-pdf="):
                    Path(arg.split("=", 1)[1]).write_bytes(b"not a real pdf")
            return ""

        pdf_export._run_browser = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                md = base / "a.md"
                md.write_text("# 1 标题\n\n正文\n", encoding="utf-8")
                out = base / "PDF" / "a.pdf"
                result = export_markdown_pdf(md, out, base_dir=base)
                self.assertEqual(result, out)
                self.assertTrue(out.is_file())
        finally:
            pdf_export.find_browser = original_find
            pdf_export._run_browser = original_run

    @unittest.skipUnless(pdf_export.find_browser(), "需要本机 Chrome/Edge")
    def test_real_pdf_has_outline_bookmarks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            md = base / "book.md"
            md.write_text(
                "# 1 第一篇\n\n## 1.1 小节\n\n正文内容。\n\n---\n\n# 2 第二篇\n\n## 2.1 小节\n\n正文内容。\n",
                encoding="utf-8",
            )
            out = base / "PDF" / "book.pdf"
            export_markdown_pdf(md, out, base_dir=base)
            from pypdf import PdfReader

            reader = PdfReader(str(out))
            self.assertGreater(len(reader.outline), 0)
            titles = []

            def collect(items):
                for item in items:
                    if isinstance(item, list):
                        collect(item)
                    else:
                        titles.append(str(item.title))

            collect(reader.outline)
            self.assertIn("1 第一篇", titles)
            self.assertIn("2 第二篇", titles)
            self.assertIn("1.1 小节", titles)
