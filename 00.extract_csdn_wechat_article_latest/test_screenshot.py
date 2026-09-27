"""Offline unit tests for the long-screenshot module (plus an optional
end-to-end test that runs when Chrome/Edge is installed locally)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import screenshot
from screenshot import ScreenshotError


class BuildArticleHtmlTest(unittest.TestCase):
    def test_includes_title_body_and_height_script(self):
        html = screenshot._build_article_html("标题 & 测试", "<div>正文</div>")
        self.assertIn("<title>标题 &amp; 测试</title>", html)
        self.assertIn('<h1 class="article-title">标题 &amp; 测试</h1>', html)
        self.assertIn("<div>正文</div>", html)
        self.assertIn('meta charset="utf-8"', html)
        self.assertIn("scrollHeight", html)
        self.assertIn("DOMContentLoaded", html)

    def test_renders_title_and_body_without_metadata_rows(self):
        # 无作者/发布时间元数据时，不渲染公众号名行与时间行
        html = screenshot._build_article_html("测试标题", "<div>正文</div>")
        self.assertIn('<div class="article-head">', html)
        self.assertIn('<h1 class="article-title">测试标题</h1>', html)
        self.assertNotIn('class="account-row"', html)
        self.assertNotIn('class="article-meta"', html)
        body_start = html.index("<body>\n") + len("<body>\n")
        self.assertIn('<div class="article-head">', html[body_start:])

    def test_escapes_title_html(self):
        html = screenshot._build_article_html("<script>x</script>", "")
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)


class BuildArticleHtmlHeaderTest(unittest.TestCase):
    def test_includes_account_row_and_meta_before_body(self):
        # 长截图要包含文章标题前面的内容：公众号名/作者行 → 标题 → 原创/作者/发布时间 → 正文
        html = screenshot._build_article_html(
            "测试标题",
            "<div>正文</div>",
            author="芯片茶馆",
            publish_time="2026年8月13日 21:00",
        )
        self.assertIn('class="account-row"', html)
        self.assertIn("芯片茶馆", html)
        self.assertIn('<h1 class="article-title">测试标题</h1>', html)
        self.assertIn('class="article-meta"', html)
        self.assertIn("2026年8月13日 21:00", html)
        self.assertLess(html.index("芯片茶馆"), html.index('<h1 class="article-title">'))
        self.assertLess(html.index('<h1 class="article-title">'), html.index("2026年8月13日 21:00"))
        self.assertLess(html.index("2026年8月13日 21:00"), html.index("<div>正文</div>"))

    def test_omits_header_rows_when_no_metadata(self):
        html = screenshot._build_article_html("测试标题", "<div>正文</div>")
        self.assertNotIn('class="account-row"', html)
        self.assertNotIn('class="article-meta"', html)

    def test_escapes_metadata(self):
        html = screenshot._build_article_html(
            "标题", "<div>正文</div>", author='<b>公众号</b>', publish_time='2026<&'
        )
        self.assertNotIn("<b>公众号</b>", html)
        self.assertIn("&lt;b&gt;公众号&lt;/b&gt;", html)
        self.assertIn("2026&lt;&amp;", html)

    def test_can_mark_browser_title_without_touching_article_title(self):
        html = screenshot._build_article_html(
            "测试标题",
            "<div>正文</div>",
            title_suffix=" A2MD-1234",
            include_height_probe=False,
        )
        self.assertIn("<title>测试标题 A2MD-1234</title>", html)
        self.assertIn('<h1 class="article-title">测试标题</h1>', html)
        self.assertNotIn("scrollHeight", html)
        self.assertNotIn("A2MD-1234</h1>", html)


class ParsePageHeightTest(unittest.TestCase):
    def test_parses_height(self):
        self.assertEqual(screenshot._parse_page_height("<title>H:12345</title>"), 12345)

    def test_rejects_missing_marker(self):
        with self.assertRaises(ScreenshotError):
            screenshot._parse_page_height("<title>12345</title>")

    def test_rejects_zero_height(self):
        with self.assertRaises(ScreenshotError):
            screenshot._parse_page_height("<title>H:0</title>")


class NoBrowserTest(unittest.TestCase):
    def test_capture_raises_friendly_error_without_browser(self):
        original = screenshot.find_browser
        screenshot.find_browser = lambda: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "shot.png"
                with self.assertRaises(ScreenshotError) as ctx:
                    screenshot.capture_article_screenshot("标题", "<p>x</p>", out, base_dir=tmp)
                self.assertIn("Chrome/Edge", str(ctx.exception))
        finally:
            screenshot.find_browser = original


class FastStoneBackendTest(unittest.TestCase):
    def test_raises_helpful_error_without_fscapture_exe(self):
        original_browser = screenshot.find_browser
        original_fscapture = screenshot.find_fscapture
        screenshot.find_browser = lambda: "chrome.exe"
        screenshot.find_fscapture = lambda: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "shot.png"
                with self.assertRaises(ScreenshotError) as ctx:
                    screenshot.capture_article_screenshot_with_fscapture(
                        "标题",
                        "<p>x</p>",
                        out,
                        base_dir=tmp,
                    )
                self.assertIn("FSCapture", str(ctx.exception))
        finally:
            screenshot.find_browser = original_browser
            screenshot.find_fscapture = original_fscapture


@unittest.skipUnless(screenshot.find_browser(), "本机未安装 Chrome/Edge，跳过端到端截图测试")
class CaptureRoundTripTest(unittest.TestCase):
    def test_captures_full_page_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            body = (
                "<div><h2>一、POR</h2>"
                "<p>电源电压从0慢慢爬升过程中，MCU/FPGA内核状态是随机不定态。</p>"
                "<pre><code>if (!rst_n) por_flag <= 1'b0;</code></pre>"
                "<p>结尾段落，用于撑高页面。" * 10 + "</p></div>"
            )
            out = base / "shot.png"
            result = screenshot.capture_article_screenshot(
                "测试标题", body, out, base_dir=base
            )
            self.assertEqual(result, out)
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)
            width, height = struct.unpack(">II", out.read_bytes()[16:24])
            self.assertEqual(width, screenshot.SCREENSHOT_WIDTH)
            self.assertGreater(height, 200)
            # 临时 HTML / 浏览器配置目录不应残留在文章目录
            leftovers = [p.name for p in base.iterdir() if p.name != "shot.png"]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
