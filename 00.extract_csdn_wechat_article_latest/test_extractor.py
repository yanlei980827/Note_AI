"""Tests for the WeChat article extraction core logic (no live network)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from article_extractor import (
    _build_toc_block,
    _number_headings,
    refresh_markdown_structure_file,
)
from wechat_extractor import _normalize_indented_list_items
from wechat_extractor import (
    WeChatArticleExtractor,
    validate_url,
    write_markdown_file,
)


ARTICLE_URL = "https://mp.weixin.qq.com/s/test-article-123"
IMAGE_URL = "https://mmbiz.qpic.cn/example/640?wx_fmt=png"
SVG_URL = "https://mmbiz.qpic.cn/example/diagram.svg"

SVG_BYTES = (
    """
    <svg xmlns="http://www.w3.org/2000/svg">
      <text>上电</text>
      <text>│</text>
      <text>├──100ms──┤ 电源/时钟稳定，PERST# 撤销</text>
      <text>│</text>
      <text>├──60ms───┤ LTSSM: Detect→Polling→Config，Gen1 L0 建立</text>
      <text>│</text>
      <text>└──1000ms─┘ 设备完全就绪，枚举完成（CRS 超时截止）</text>
    </svg>
    """.encode("utf-8")
)

FAKE_HTML = """<!doctype html>
<html>
  <head>
    <meta property="og:title" content="微信文章标题"/>
    <meta name="author" content="测试作者"/>
    <meta property="article:published_time" content="2026-08-03 10:00"/>
    <title>页面标题</title>
  </head>
  <body>
    <div id="js_article">
      <h1 class="rich_media_title" id="activity-name">微信文章标题</h1>
      <div class="rich_media_meta_list"><em id="publish_time">2026-08-03 10:00</em></div>
      <div class="rich_media_content" id="js_content">
        <p>第一段内容。</p>
        <p><img data-src="{image_url}" alt="示意图"/></p>
        <h2>小节</h2>
        <p>第二段内容。</p>
        <div class="js_media_tail"><p>页尾推广</p></div>
      </div>
    </div>
  </body>
</html>
""".format(image_url=IMAGE_URL)

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)


class FakeResponse:
    def __init__(self, content, content_type):
        self._content = content
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.status_code = 200
        self.text = content.decode("utf-8", errors="replace")

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]


class FakeSession:
    def get(self, url, **kwargs):
        if url == ARTICLE_URL:
            return FakeResponse(FAKE_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if url == IMAGE_URL:
            return FakeResponse(PNG_BYTES, "image/png")
        if url == SVG_URL:
            return FakeResponse(SVG_BYTES, "image/svg+xml")
        raise AssertionError(f"unexpected URL: {url}")

EMPTY_HEADING_HTML = """<!doctype html>
<html>
  <head><meta property="og:title" content="标题"/></head>
  <body>
    <div id="js_content">
      <h1 data-heading="true"><span leaf=""><br/></span></h1>
      <p>第一段内容。</p>
    </div>
  </body>
</html>
"""


LIST_HEADING_HTML = """<!doctype html>
<html>
  <head><meta property="og:title" content="标题"/></head>
  <body>
    <div id="js_content">
      <ul><li><h3>最优测试方案</h3></li></ul>
      <p>全局/模块复位后，第一段内容。</p>
      <ol><li>项目一</li><li>项目二</li></ol>
      <ul><li><h3>覆盖范围</h3></li></ul>
      <p>覆盖范围内容。</p>
    </div>
  </body>
</html>
"""


class ListHeadingSession(FakeSession):
    def get(self, url, **kwargs):
        if url == ARTICLE_URL:
            return FakeResponse(LIST_HEADING_HTML.encode("utf-8"), "text/html; charset=utf-8")
        raise AssertionError(f"unexpected URL: {url}")


class EmptyHeadingSession(FakeSession):
    def get(self, url, **kwargs):
        if url == ARTICLE_URL:
            return FakeResponse(EMPTY_HEADING_HTML.encode("utf-8"), "text/html; charset=utf-8")
        raise AssertionError(f"unexpected URL: {url}")


class ExtractorTests(unittest.TestCase):
    def test_validate_url(self):
        self.assertEqual(validate_url(ARTICLE_URL), ARTICLE_URL)
        with self.assertRaises(ValueError):
            validate_url("")
        with self.assertRaises(ValueError):
            validate_url("not-a-url")

    def test_extract_html_with_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            markdown_path = out_dir / "article.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(
                ARTICLE_URL,
                markdown_path=markdown_path,
            )

            self.assertEqual(result.metadata.title, "微信文章标题")
            self.assertEqual(result.metadata.author, "测试作者")
            self.assertEqual(result.metadata.publish_time, "2026-08-03 10:00")
            self.assertEqual(result.image_count, 1)
            self.assertEqual(result.markdown_path, markdown_path)
            self.assertIn("# 微信文章标题", result.markdown)
            self.assertIn("第一段内容。", result.markdown)
            self.assertIn("第二段内容。", result.markdown)
            self.assertIn("article_assets/image-0001.png", result.markdown)
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}",
            )
            self.assertNotIn("发布时间", result.markdown)
            self.assertNotIn("页尾推广", result.markdown)
            self.assertNotIn("data-src", result.markdown)

            image_file = out_dir / "article_assets" / "image-0001.png"
            self.assertTrue(image_file.is_file())
            self.assertEqual(image_file.read_bytes(), PNG_BYTES)

    def test_append_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("旧文章内容", appended)
            self.assertIn("---", appended)
            self.assertIn("# 1. 微信文章标题", appended)
            self.assertIn("notes_assets/image-0001.png", appended)

            with self.assertRaises(ValueError):
                write_markdown_file(result.markdown, target, mode="replace")
            self.assertEqual(target.read_text(encoding="utf-8"), appended)

    def test_replace_refuses_nonempty_markdown_and_preserves_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\n", encoding="utf-8")
            assets = Path(tmp) / "notes_assets"
            assets.mkdir()
            old_image = assets / "image-0001.png"
            old_image.write_bytes(PNG_BYTES)
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            with self.assertRaises(ValueError):
                write_markdown_file(result.markdown, target, mode="replace")

            self.assertEqual(target.read_text(encoding="utf-8"), "旧文章内容\n")
            self.assertEqual(old_image.read_bytes(), PNG_BYTES)
            self.assertFalse((assets / "backup").exists())

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
            target.write_text("旧文章内容\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")

            self.assertFalse((Path(tmp) / "notes_assets" / "backup").exists())

    def test_append_replaces_old_toc_format_with_current_format(self):
        # 旧目录格式（带 `- ` 的项目符）在续写时被当前格式替换，
        # 旧标题也会按当前文档结构重新编号。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            old_toc = (
                "<!-- toc-start -->\n\n"
                "# 目录\n\n"
                "- [旧文章](#旧文章)\n"
                "<!-- toc-end -->\n\n---\n\n"
                "# 旧文章\n\n正文内容保留。\n"
            )
            target.write_text(old_toc, encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            toc_part = written.split("<!-- toc-end -->", 1)[0]
            self.assertEqual(written.count("toc-start"), 1)
            self.assertNotRegex(toc_part, r"(?m)^\s*-\s+\[")
            self.assertIn("[1. 旧文章](#1-旧文章)", toc_part)
            self.assertIn("[2. 微信文章标题](#2-微信文章标题)", toc_part)
            self.assertIn("　　[2.1 小节](#21-小节)", toc_part)
            # 正文保留，但标题序号会按当前结构更新
            self.assertIn("# 1. 旧文章\n\n正文内容保留。", written)

    def test_backup_logs_url_and_markdown_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            import article_extractor

            backup_file = Path(tmp) / "backup.md"
            original_backup = article_extractor.ARTICLE_BACKUP_FILE
            article_extractor.ARTICLE_BACKUP_FILE = backup_file
            try:
                target = Path(tmp) / "notes.md"
                extractor = WeChatArticleExtractor(session=FakeSession())
                result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
                write_markdown_file(
                    result.markdown,
                    target,
                    mode="append",
                    url=result.metadata.url,
                )
                # 新文件和非空续写两次都要记录链接
                write_markdown_file(
                    result.markdown,
                    target,
                    mode="append",
                    url=result.metadata.url,
                )
                lines = backup_file.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 2)
                # 每行格式：序号 | 日期时间 | 链接 | Markdown 路径，序号持续累加
                self.assertTrue(lines[0].startswith("1 | "), lines[0])
                self.assertTrue(lines[1].startswith("2 | "), lines[1])
                for line in lines:
                    self.assertRegex(
                        line,
                        r"^\d+ \| \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \| " + ARTICLE_URL + r" \| ",
                    )
                    self.assertTrue(line.endswith(str(target.resolve())), line)
            finally:
                article_extractor.ARTICLE_BACKUP_FILE = original_backup

    def test_backup_uses_markdown_source_when_url_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            import article_extractor

            backup_file = Path(tmp) / "backup.md"
            original_backup = article_extractor.ARTICLE_BACKUP_FILE
            article_extractor.ARTICLE_BACKUP_FILE = backup_file
            try:
                target = Path(tmp) / "notes.md"
                markdown = self._sample_article(1, "文章A", ARTICLE_URL)
                write_markdown_file(markdown, target, mode="append")
                lines = backup_file.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("1 | "), lines[0])
                self.assertIn(ARTICLE_URL, lines[0])
                self.assertTrue(lines[0].endswith(str(target.resolve())), lines[0])
            finally:
                article_extractor.ARTICLE_BACKUP_FILE = original_backup

    def test_backup_is_written_next_to_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            import article_extractor

            original_backup = article_extractor.ARTICLE_BACKUP_FILE
            article_extractor.ARTICLE_BACKUP_FILE = Path(tmp) / "elsewhere" / "custom-backup.md"
            try:
                target_dir = Path(tmp) / "nested"
                target_dir.mkdir()
                target = target_dir / "notes.md"
                write_markdown_file(
                    self._sample_article(1, "文章A", ARTICLE_URL),
                    target,
                    mode="append",
                )
                same_dir_backup = target_dir / "custom-backup.md"
                wrong_dir_backup = Path(tmp) / "elsewhere" / "custom-backup.md"
                self.assertTrue(same_dir_backup.is_file(), same_dir_backup)
                self.assertFalse(wrong_dir_backup.exists(), wrong_dir_backup)
                self.assertIn(ARTICLE_URL, same_dir_backup.read_text(encoding="utf-8"))
            finally:
                article_extractor.ARTICLE_BACKUP_FILE = original_backup

    def test_backup_skipped_when_url_and_source_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            import article_extractor

            backup_file = Path(tmp) / "backup.md"
            original_backup = article_extractor.ARTICLE_BACKUP_FILE
            article_extractor.ARTICLE_BACKUP_FILE = backup_file
            try:
                target = Path(tmp) / "notes.md"
                markdown = "# 没有来源的文章\n\n只有正文，没有链接行。\n"
                write_markdown_file(markdown, target, mode="append")
                self.assertFalse(backup_file.exists())
            finally:
                article_extractor.ARTICLE_BACKUP_FILE = original_backup

    def test_backup_failure_reports_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            messages = []

            def progress(message, done=0, total=0):
                messages.append(message)

            with patch("article_extractor.log_article_backup", return_value=None):
                write_markdown_file(
                    self._sample_article(1, "文章A", ARTICLE_URL),
                    target,
                    mode="append",
                    progress=progress,
                )

            self.assertTrue(target.is_file())
            self.assertTrue(any("备份失败" in message for message in messages), messages)

    @staticmethod
    def _sample_article(number, title, url, extra=""):
        return (
            f"# {title}\n\n"
            f"> 来源：{url}\n"
            f"> update 2026/08/22 10 : 00\n\n"
            f"第{number}篇内容。\n{extra}"
        )

    def test_replace_existing_article_by_url_in_place(self):
        # 同一链接的文章再次添加时，以最新内容替换原文章：位置和编号不变，
        # 其余文章逐字保留；代码围栏内的 --- 不能当作文章分隔符。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            write_markdown_file(
                self._sample_article(1, "文章A", "https://a.com/1"),
                target, mode="append", url="https://a.com/1",
            )
            write_markdown_file(
                self._sample_article(2, "文章B", "https://b.com/2"),
                target, mode="append", url="https://b.com/2",
            )
            write_markdown_file(
                self._sample_article(3, "文章C", "https://c.com/3"),
                target, mode="append", url="https://c.com/3",
            )
            write_markdown_file(
                self._sample_article(
                    2, "文章B-新版", "https://b.com/2",
                    extra="\n```\n# 围栏内的 --- 不算分隔符\n```\n",
                ),
                target, mode="append", url="https://b.com/2",
            )
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("> 来源："), 3)
            self.assertIn("# 1. 文章A", text)
            self.assertIn("# 2. 文章B-新版", text)
            self.assertIn("# 3. 文章C", text)
            self.assertNotIn("# 2. 文章B\n", text)
            self.assertIn("第1篇内容。", text)
            self.assertIn("第3篇内容。", text)
            self.assertIn("围栏内的 --- 不算分隔符", text)

    def test_append_when_url_not_in_file(self):
        # 链接不在文件中时仍是普通续写（追加新文章）。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            write_markdown_file(
                self._sample_article(1, "文章A", "https://a.com/1"),
                target, mode="append", url="https://a.com/1",
            )
            write_markdown_file(
                self._sample_article(2, "文章D", "https://d.com/4"),
                target, mode="append", url="https://d.com/4",
            )
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("> 来源："), 2)
            self.assertIn("# 1. 文章A", text)
            self.assertIn("# 2. 文章D", text)

    def test_replace_first_and_last_article(self):
        # 首篇前面没有 --- 分隔符、末篇后面没有 --- 分隔符，两种边界都要能替换。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            write_markdown_file(
                self._sample_article(1, "文章A", "https://a.com/1"),
                target, mode="append", url="https://a.com/1",
            )
            write_markdown_file(
                self._sample_article(2, "文章B", "https://b.com/2"),
                target, mode="append", url="https://b.com/2",
            )
            write_markdown_file(
                self._sample_article(3, "文章C", "https://c.com/3"),
                target, mode="append", url="https://c.com/3",
            )
            write_markdown_file(
                self._sample_article(1, "文章A-新版", "https://a.com/1"),
                target, mode="append", url="https://a.com/1",
            )
            write_markdown_file(
                self._sample_article(3, "文章C-新版", "https://c.com/3"),
                target, mode="append", url="https://c.com/3",
            )
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("> 来源："), 3)
            self.assertIn("# 1. 文章A-新版", text)
            self.assertNotIn("# 1. 文章A\n", text)
            self.assertIn("# 2. 文章B", text)
            self.assertIn("# 3. 文章C-新版", text)
            self.assertNotIn("# 3. 文章C\n", text)
            self.assertTrue(text.rstrip().endswith("第3篇内容。"), text[-60:])

    def test_replace_article_with_internal_separator_keeps_whole_article(self):
        # 文章正文里的 --- 分隔线不是文章边界，替换时必须整篇替换。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            write_markdown_file(
                self._sample_article(1, "文章A", "https://a.com/1"),
                target, mode="append", url="https://a.com/1",
            )
            # 文章B 正文含 --- 分隔线与子标题
            with_hr = (
                "# 文章B\n\n"
                "> 来源：https://b.com/2\n"
                "> update 2026/08/22 10 : 00\n\n"
                "开头。\n\n---\n\n## 2.1 小节\n\n小节内容。\n"
            )
            write_markdown_file(with_hr, target, mode="append", url="https://b.com/2")
            write_markdown_file(
                self._sample_article(2, "文章B-新版", "https://b.com/2"),
                target, mode="append", url="https://b.com/2",
            )
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("> 来源："), 2)
            self.assertIn("# 2. 文章B-新版", text)
            self.assertNotIn("开头。", text)
            self.assertNotIn("小节内容。", text)
            self.assertIn("# 1. 文章A", text)

    def test_deduplicate_markdown_keeps_latest_per_url(self):
        from article_extractor import deduplicate_markdown

        parts = [
            self._sample_article(1, "甲", "https://a.com/1", extra="\n甲内容\n"),
            self._sample_article(2, "乙", "https://x.com/2", extra="\n乙-旧\n"),
            self._sample_article(3, "丙", "https://x.com/2", extra="\n丙-中\n"),
            self._sample_article(4, "丁", "https://x.com/2", extra="\n丁-新\n"),
            self._sample_article(5, "戊", "https://e.com/5", extra="\n戊内容\n"),
        ]
        markdown = "\n\n---\n\n".join(parts) + "\n"
        result = deduplicate_markdown(markdown)
        self.assertIsNotNone(result)
        self.assertEqual(result.count("> 来源："), 3)
        self.assertIn("# 1. 甲", result)
        self.assertIn("# 2. 丁", result)
        self.assertIn("# 3. 戊", result)
        self.assertNotIn("乙-旧", result)
        self.assertNotIn("丙-中", result)
        self.assertIn("丁-新", result)

    def test_deduplicate_markdown_returns_none_without_duplicates(self):
        from article_extractor import deduplicate_markdown

        markdown = (
            self._sample_article(1, "甲", "https://a.com/1")
            + "\n\n---\n\n"
            + self._sample_article(2, "乙", "https://b.com/2")
        )
        self.assertIsNone(deduplicate_markdown(markdown))

    def test_deduplicate_markdown_file_writes_backup(self):
        from article_extractor import deduplicate_markdown_file

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            # 直接写文件构造重复（写入口的 URL 替换逻辑会拦截同链接追加）
            markdown = (
                self._sample_article(1, "甲", "https://a.com/1", extra="\n甲内容\n")
                + "\n\n---\n\n"
                + self._sample_article(2, "乙", "https://x.com/2", extra="\n乙-旧\n")
                + "\n\n---\n\n"
                + self._sample_article(3, "丙", "https://x.com/2", extra="\n丙-新\n")
                + "\n"
            )
            target.write_text(markdown, encoding="utf-8", newline="")
            summary = deduplicate_markdown_file(target)
            self.assertIsNotNone(summary)
            self.assertEqual(summary.removed, 1)
            self.assertEqual(summary.remaining, 2)
            self.assertIsNotNone(summary.backup_path)
            self.assertTrue(summary.backup_path.is_file())
            text = target.read_text(encoding="utf-8")
            self.assertEqual(text.count("> 来源："), 2)
            self.assertIn("# 1. 甲", text)
            self.assertIn("# 2. 丙", text)
            self.assertNotIn("乙", text)

    def test_append_continues_image_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("已有内容\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())

            first = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(first.markdown, target, mode="append")
            first_image = Path(tmp) / "notes_assets" / "image-0001.png"
            self.assertTrue(first_image.is_file())
            self.assertIn("notes_assets/image-0001.png", first.markdown)

            second = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            self.assertIn("notes_assets/image-0002.png", second.markdown)
            self.assertTrue((Path(tmp) / "notes_assets" / "image-0002.png").is_file())

    def test_append_continues_index_from_existing_markdown_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text(
                "旧文章\n\n![](assets/image-0001.png)\n\n"
                "![](notes_assets/image-0003.jpg)\n",
                encoding="utf-8",
            )
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            self.assertIn("notes_assets/image-0004.png", result.markdown)
            self.assertTrue((Path(tmp) / "notes_assets" / "image-0004.png").is_file())

    def test_download_never_overwrites_existing_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "notes_assets"
            assets.mkdir()
            existing = assets / "image-0001.png"
            existing.write_bytes(PNG_BYTES)
            extractor = WeChatArticleExtractor(session=FakeSession())

            local_path = extractor._download_image(
                IMAGE_URL,
                assets,
                1,
                None,
                1,
            )

            self.assertEqual(local_path, assets / "image-0002.png")
            self.assertEqual(existing.read_bytes(), PNG_BYTES)

    def test_wechat_code_blocks_and_bold_headings(self):
        html = """
        <div id="js_content">
          <p><strong><span leaf="">1. data_buf</span></strong></p>
          <pre><section><span style="font-size:0">x</span></section><code>
            <section style="display:flex"><span leaf=""><br/></span>
              <section style="user-select:none">
                <section><span leaf="">1</span></section>
                <section><span leaf="">2</span></section>
              </section>
              <section><span leaf="">if ( src_hs &amp; ~rdy_dst)</span></section>
              <section><span leaf="">\xa0\xa0\xa0\xa0data_buf &lt;= data_src;</span></section>
            </section>
          </code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))

        self.assertIn("**1. data\\_buf**", markdown)
        self.assertNotIn("****", markdown)
        self.assertIn("```", markdown)
        self.assertIn("if ( src_hs & ~rdy_dst)", markdown)
        self.assertIn("    data_buf <= data_src;", markdown)
        self.assertNotIn("\n1\n", markdown)
        self.assertNotIn("\n2\n", markdown)


    def test_empty_heading_does_not_produce_bare_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=EmptyHeadingSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            self.assertNotRegex(result.markdown, r"(?m)^#\s*$")
            self.assertIn("第一段内容。", result.markdown)

    def test_empty_headings_are_dropped(self):
        html = """
        <div id="js_content">
          <h1><span leaf=""><br/></span></h1>
          <h2> </h2>
          <h3>有内容的标题</h3>
          <p>正文。</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertNotRegex(markdown, r"(?m)^#{1,6}\s*$")
        self.assertIn("有内容的标题", markdown)
        self.assertIn("正文。", markdown)


    def test_append_separator_has_blank_line_before_separator(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("最后一段文字\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("最后一段文字\n\n---\n\n# 1. 微信文章标题", appended)

    def test_append_never_creates_setext_heading(self):
        # 复现 debug.md 场景：第一篇文章以 '---' + 尾段结束，
        # 追加第二篇文章时分隔符不能紧贴尾段（否则会形成 Setext 标题）。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text(
                "最后一段内容。\n\n---\n\n*（文章末尾附注。）*\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("*（文章末尾附注。）*\n\n---\n\n# 1. 微信文章标题", appended)
            self.assertNotRegex(appended, r"(?m)^[^#>\n].*\n---\s*$")

    def test_append_after_trailing_horizontal_rule_uses_single_separator(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("已有内容\n\n---\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("已有内容\n\n---\n\n# 1. 微信文章标题", appended)
            self.assertNotIn("---\n\n---", appended)

    def test_wechat_strips_redundant_list_bullet(self):
        # 微信列表项常以字面 bullet 字符开头，markdownify 会输出 "- \u2022 text"，
        # 需要剥掉装饰 bullet，但代码围栏内的内容不能动。
        html = """
        <div id="js_content">
          <ul>
            <li><section><span leaf="">• </span><strong>本质目的</strong>：电源电压从0慢慢爬升过程中，MCU/FPGA内核、寄存器、RAM状态是<strong>随机不定态</strong>。</section></li>
            <li><section>• 电源刚上电。</section></li>
            <li><section>没有bullet的行。</section></li>
          </ul>
          <pre><code><span leaf="">- • keep this</span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("- **本质目的**：电源电压从0慢慢爬升过程中，MCU/FPGA内核、寄存器、RAM状态是**随机不定态**。", markdown)
        self.assertIn("- 电源刚上电。", markdown)
        self.assertNotIn("- \u2022 **本质目的**", markdown)
        self.assertNotIn("- \u2022 电源刚上电", markdown)
        self.assertIn("- \u2022 keep this", markdown)

    def test_wechat_preserves_textual_svg_blocks(self):
        html = """
        <div id="js_content">
          <svg xmlns="http://www.w3.org/2000/svg">
            <text>上电</text>
            <text>│</text>
            <text>├──100ms──┤ 电源/时钟稳定，PERST# 撤销</text>
            <text>│</text>
            <text>├──60ms───┤ LTSSM: Detect→Polling→Config，Gen1 L0 建立</text>
            <text>│</text>
            <text>└──1000ms─┘ 设备完全就绪，枚举完成（CRS 超时截止）</text>
          </svg>
          <svg><title>微信图标</title><path d="M0 0h10v10z"/></svg>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("上电", markdown)
        self.assertIn("├──100ms──┤ 电源/时钟稳定，PERST# 撤销", markdown)
        self.assertIn("└──1000ms─┘ 设备完全就绪，枚举完成（CRS 超时截止）", markdown)
        self.assertNotIn("微信图标", markdown)

    def test_wechat_unwraps_textual_svg_images(self):
        html = """
        <html>
          <head>
            <meta property="og:title" content="微信文章标题"/>
            <meta name="author" content="测试作者"/>
            <meta property="article:published_time" content="2026-08-03 10:00"/>
          </head>
          <body>
            <div id="js_article">
              <h1 class="rich_media_title" id="activity-name">微信文章标题</h1>
              <div class="rich_media_content" id="js_content">
                <h2>一张图总结</h2>
                <p><img data-src="{svg_url}" alt="时间轴图示"/></p>
                <p>每一个数字背后，都是物理电路对时间的真实需求。</p>
              </div>
            </div>
          </body>
        </html>
        """.format(svg_url=SVG_URL)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "article.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            with patch.object(FakeSession, "get", autospec=True) as mock_get:
                def _get(self, url, **kwargs):
                    if url == ARTICLE_URL:
                        return FakeResponse(html.encode("utf-8"), "text/html; charset=utf-8")
                    if url == SVG_URL:
                        return FakeResponse(SVG_BYTES, "image/svg+xml")
                    raise AssertionError(f"unexpected URL: {url}")

                mock_get.side_effect = _get
                result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
        self.assertIn("上电", result.markdown)
        self.assertIn("├──100ms──┤ 电源/时钟稳定，PERST# 撤销", result.markdown)
        self.assertIn("└──1000ms─┘ 设备完全就绪，枚举完成（CRS 超时截止）", result.markdown)
        self.assertIn("每一个数字背后，都是物理电路对时间的真实需求。", result.markdown)
        self.assertNotIn("![](", result.markdown)

    def test_wechat_merges_standalone_list_bullet_with_following_text(self):
        # 微信偶发输出 "- ·" 单独占一行，真正正文在下一行缩进。
        # 这种装饰点不是原文内容，应合并成一个正常列表项。
        html = """
        <div id="js_content">
          <ul>
            <li><p>·</p><p>固件负责配置寄存器</p></li>
          </ul>
          <pre><code><span leaf="">- ·</span><span leaf="">  keep this</span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("- 固件负责配置寄存器", markdown)
        self.assertNotIn("- ·\n\n  固件负责配置寄存器", markdown)
        self.assertIn("- ·\n  keep this", markdown)

    def test_wechat_strips_duplicated_ordered_list_number(self):
        # 微信 <ol> 列表项文本自带手写编号，markdownify 又加一遍序号，
        # 输出 "1. 1. 内容"，需要剥掉第二个编号；代码围栏内不处理。
        html = """
        <div id="js_content">
          <ol>
            <li><section><span leaf="">1.\u00a0</span><strong>上电瞬间</strong>：电容两端电压差值不能突变。</section></li>
            <li><section><span leaf="">2. </span>电源稳定后充电。</section></li>
            <li><section><span leaf="">1. </span>• 内容和bullet叠加。</section></li>
          </ol>
          <pre><code><span leaf="">1. 1. keep this</span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("1. **上电瞬间**：电容两端电压差值不能突变。", markdown)
        self.assertIn("2. 电源稳定后充电。", markdown)
        self.assertIn("3. 内容和bullet叠加。", markdown)
        self.assertNotIn("1. 1. **上电瞬间", markdown)
        self.assertIn("1. 1. keep this", markdown)

    def test_wechat_strips_standalone_repeated_order_number(self):
        # 微信排版偶发把手写编号单独输出成一行，后面又接 markdownify 生成的有序列表项。
        html = """
        <div id="js_content">
          <p>1</p>
          <ol><li>构建可信输入</li></ol>
          <p>2.</p>
          <ol start="2"><li>配置安全策略</li></ol>
          <pre><code><span leaf="">1</span><span leaf="">1. keep this</span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("1. 构建可信输入", markdown)
        self.assertIn("2. 配置安全策略", markdown)
        self.assertNotIn("1\n\n1. 构建可信输入", markdown)
        self.assertNotIn("2.\n\n2. 配置安全策略", markdown)
        self.assertIn("1\n1. keep this", markdown)

    def test_wechat_merges_standalone_order_number_with_plain_title(self):
        # 微信排版也会把手写编号拆成独立段落，后面接普通标题和说明。
        html = """
        <div id="js_content">
          <p>1</p>
          <p>Power / Clock</p>
          <p>电源与参考时钟稳定</p>
          <pre><code><span leaf="">1</span><span leaf="">Power / Clock</span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("1. Power / Clock\n\n   电源与参考时钟稳定", markdown)
        self.assertNotIn("1\n\nPower / Clock", markdown)
        self.assertIn("1\nPower / Clock", markdown)

    def test_wechat_order_item_continuation_stops_at_next_number(self):
        html = """
        <div id="js_content">
          <p>1</p>
          <p>Power / Clock</p>
          <p>电源与参考时钟稳定</p>
          <p>2</p>
          <p>Reset</p>
          <p>复位释放完成</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn("1. Power / Clock\n\n   电源与参考时钟稳定", markdown)
        self.assertIn("2. Reset\n\n   复位释放完成", markdown)
        self.assertNotIn("   2. Reset", markdown)

    def test_wechat_new_style_token_spans_no_duplication(self):
        # 新版微信编辑器把一行代码拆成多个 leaf token span，部分 token 还被
        # 彩色包裹 span 包住，行尾用 <span leaf=""><br/></span> 标记。
        # 旧实现 find_all(attrs={"leaf": ""}) 会把没有 leaf 属性的彩色包裹
        # span 也匹配进来，导致每个 token 文本重复两遍。
        html = """
        <div id="js_content">
          <h2>示例代码</h2>
          <pre><code><span style="color: #c678dd;"><span leaf="">class</span></span><span leaf=""> apb_write_test </span><span style="color: #c678dd;"><span leaf="">extends</span></span><span leaf=""> uvm_test;</span><span leaf=""><br/></span><span style="color: #61aeee;"><span leaf="">`uvm_component_utils(apb_write_test)</span></span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">function</span></span><span leaf=""> new(string name, uvm_component parent);</span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">endfunction</span></span><span leaf=""><br/></span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn(
            "```\nclass apb_write_test extends uvm_test;\n"
            "`uvm_component_utils(apb_write_test)\n"
            "function new(string name, uvm_component parent);\n"
            "endfunction\n```",
            markdown,
        )
        self.assertNotIn("class\nclass", markdown)
        self.assertNotIn("extends\nextends", markdown)
        self.assertNotIn("function\nfunction", markdown)
        self.assertNotIn('"req"\n"req"', markdown)

    def test_wechat_section_style_code_blocks_get_fenced(self):
        # 新版微信编辑器偶尔不用 <pre>，代码块直接写成带代码样式的
        # <section>（white-space: nowrap + Consolas/monospace + 深色背景），
        # 内部是高亮 token span，行尾用 <span leaf=""><br/></span> 切行。
        # 这类块之前会被 markdownify 当成普通段落，代码裸露在正文里。
        html = """
        <div id="js_content">
          <h2>示例代码</h2>
          <section style="white-space: nowrap; font-family: Consolas, Monaco, monospace; background-color: rgb(40, 44, 52);">
            <span style="color: #c678dd;"><span leaf="">class</span></span><span leaf=""> full_pipeline_driver </span><span style="color: #c678dd;"><span leaf="">extends</span></span><span leaf=""> uvm_driver #(my_transaction);</span><span leaf=""><br/></span>
            <span style="color: #61aeee;"><span leaf="">`uvm_component_utils(full_pipeline_driver)</span></span><span leaf=""><br/></span>
            <span style="color: #c678dd;"><span leaf="">virtual</span></span><span leaf=""> my_if vif;</span><span leaf=""><br/></span>
            <span leaf="">  my_config     cfg;</span><span leaf=""><br/></span>
          </section>
          <section style="display:flex"><span leaf="">这不是代码块</span></section>
          <p>正文段落。</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn(
            "```\nclass full_pipeline_driver extends uvm_driver #(my_transaction);\n"
            "`uvm_component_utils(full_pipeline_driver)\n"
            "virtual my_if vif;\n"
            "  my_config     cfg;\n```",
            markdown,
        )
        self.assertNotIn("class\nclass", markdown)
        self.assertIn("这不是代码块", markdown)
        self.assertIn("正文段落。", markdown)

    def test_append_to_empty_file_does_not_prepend_separator(self):
        # 续写到空/纯空白文件时不能再加 "---" 前缀，否则文件以 --- 开头，
        # 会被 Typora 等编辑器误识别为 YAML front matter 而吞掉后续内容。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            # 文件以自动生成的目录开头（HTML 注释标记，避免被识别为 YAML front matter），
            # 目录块之后才有 --- 分隔线
            self.assertTrue(appended.startswith("<!-- toc-start -->"), appended[:40])
            self.assertFalse(appended.startswith("---"), appended[:40])
            self.assertIn("# 1. 微信文章标题", appended)
            self.assertIn("[1. 微信文章标题](#", appended)
            self.assertNotRegex(appended, r"(?m)^\s*-\s+\[")


    def test_body_not_merged_into_quote_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            # 引用块（> update ...）与正文之间必须有空行，否则正文第一段会被
            # CommonMark/Typora 的 lazy continuation 并进引用块渲染
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}\n\n第一段内容。",
            )
            self.assertNotRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}\n[^\n>]",
            )

    def test_indented_list_heading_demoted_to_top_level(self):
        md = "  - 最优测试方案\n\n  摒弃冗余随机激励，内容。\n\n  1. 项目一\n"
        out = _normalize_indented_list_items(md)
        self.assertIn("- 最优测试方案\n\n  摒弃冗余随机激励，内容。", out)
        self.assertNotIn("  - ", out)

    def test_list_heading_content_merged_when_wrapped_in_section(self):
        html = (
            "<div>"
            "<ul><li><section><h3>最优测试方案</h3></section></li></ul>"
            "<section><p>摒弃冗余随机激励，内容。</p><ol><li>项目一</li><li>项目二</li></ol></section>"
            "<ul><li><h3>覆盖范围</h3></li></ul>"
            "<p>覆盖范围内容。</p>"
            "</div>"
        )
        extractor = WeChatArticleExtractor()
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find("div")
        extractor._merge_list_heading_content(node)
        md = extractor._convert_body(str(node))
        self.assertIn("- 最优测试方案\n\n  摒弃冗余随机激励，内容。", md)
        self.assertIn("  1. 项目一", md)
        self.assertIn("  2. 项目二", md)
        self.assertIn("- 覆盖范围\n\n  覆盖范围内容。", md)

    def test_list_heading_content_merged_into_list_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=ListHeadingSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            # 标题列表项后面的内容必须缩进到 `- ` 下面，与列表项同一层次
            self.assertIn(
                "- 最优测试方案\n\n  全局/模块复位后，第一段内容。",
                result.markdown,
            )
            self.assertIn("  1. 项目一", result.markdown)
            self.assertIn("  2. 项目二", result.markdown)
            self.assertIn("- 覆盖范围\n\n  覆盖范围内容。", result.markdown)

    def test_list_item_heading_demoted_to_plain_text(self):
        html = (
            "<div>"
            "<ul><li><h3>最优测试方案</h3></li></ul>"
            "<ul><li><h2>覆盖范围</h2></li></ul>"
            "</div>"
        )
        md = WeChatArticleExtractor._convert_body(html)
        self.assertIn("- 最优测试方案", md)
        self.assertIn("- 覆盖范围", md)
        self.assertNotIn("- ###", md)
        self.assertNotIn("- ##", md)

    def test_chinese_ordinal_paragraph_becomes_heading(self):
        html = (
            "<div>"
            "<p>一、寄存器复位值测试</p><p>内容。</p>"
            "<p>二、寄存器属性测试</p><p>内容。</p>"
            "<p>一、为什么我们最先想要按照前仿的划分来做？这个很朴素。</p>"
            "<ul><li>一、列表项不算标题</li></ul>"
            "</div>"
        )
        md = WeChatArticleExtractor._convert_body(html)
        self.assertIn("## 一、寄存器复位值测试", md)
        self.assertIn("## 二、寄存器属性测试", md)
        self.assertIn("一、为什么我们最先想要按照前仿的划分来做？这个很朴素。", md)
        self.assertIn("- 一、列表项不算标题", md)
        self.assertNotIn("## 一、为什么", md)
        self.assertNotIn("## - 一、", md)
        numbered = _number_headings("# 寄存器专项测试\n\n" + md)
        self.assertIn("## 1.1 寄存器复位值测试", numbered)
        self.assertIn("## 1.2 寄存器属性测试", numbered)

    def test_screenshot_flag_adds_marked_line(self):
        # 勾选「保存长截图」时，在 update 引用块内、紧跟 update 行之后加“已截图”标记
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(
                ARTICLE_URL,
                markdown_path=target,
                save_screenshot=True,
            )
            self.assertIn("> **已截图**", result.markdown)
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}\n> \*\*已截图\*\*",
            )

            # 未勾选时不出现该标记
            plain = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            self.assertNotIn("**已截图**", plain.markdown)

    def test_heading_numbering_first_and_second_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            first = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(first.markdown, target, mode="append")
            second = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(second.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            self.assertTrue(written.startswith("<!-- toc-start -->"), written[:40])
            self.assertIn("# 1. 微信文章标题", written)
            self.assertIn("# 2. 微信文章标题", written)
            self.assertIn("## 1.1 小节", written)
            self.assertIn("## 2.1 小节", written)
            # 重复编号时保持稳定，不会变成 1 1
            write_markdown_file(second.markdown, target, mode="append")
            again = target.read_text(encoding="utf-8")
            self.assertIn("# 3. 微信文章标题", again)
            self.assertNotIn("# 1. 1", again)

    def test_toc_added_on_first_write_without_hyphen_and_preserves_on_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            extractor = WeChatArticleExtractor(session=FakeSession())
            first = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(first.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            self.assertTrue(written.startswith("<!-- toc-start -->"), written[:40])
            self.assertIn("# 目录", written)
            self.assertIn("[1. 微信文章标题](#1-微信文章标题)", written)
            self.assertIn("　　[1.1 小节](#11-小节)", written)
            self.assertNotRegex(written, r"(?m)^\s*-\s+\[")
            self.assertEqual(written.count("toc-start"), 1)

            second = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(second.markdown, target, mode="append")
            again = target.read_text(encoding="utf-8")
            # 新文章追加后目录同步重建：全文件只有一份目录，且包含新旧两篇文章
            self.assertEqual(again.count("toc-start"), 1)
            self.assertEqual(again.count("toc-end"), 1)
            toc_part = again.split("<!-- toc-end -->", 1)[0]
            self.assertIn("[1. 微信文章标题](#1-微信文章标题)", toc_part)
            self.assertIn("[2. 微信文章标题](#2-微信文章标题)", toc_part)
            self.assertIn("　　[2.1 小节](#21-小节)", toc_part)
            self.assertNotRegex(toc_part, r"(?m)^\s*-\s+\[")
            self.assertIn("# 2. 微信文章标题", again)

    def test_toc_block_has_no_hyphen_and_keeps_hierarchy(self):
        block = _build_toc_block(
            "# 1. 标题\n\n## 1.1 小节\n\n### 1.1.1 子节\n"
        )
        self.assertIn("[1. 标题](#1-标题)", block)
        self.assertIn("　　[1.1 小节](#11-小节)", block)
        self.assertIn("　　　　[1.1.1 子节](#111-子节)", block)
        self.assertNotRegex(block, r"(?m)^\s*-\s+\[")

    def test_append_preserves_body_and_adds_current_toc(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            original = "# Old Custom Title\n\ncustom body without generated toc\n"
            target.write_text(original, encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            # 旧文件没有目录，续写时按当前格式补上目录；标题会重新编号
            self.assertTrue(written.startswith("<!-- toc-start -->"), written[:40])
            self.assertIn("[1. Old Custom Title](#1-old-custom-title)", written)
            self.assertIn(
                "# 1. Old Custom Title\n\ncustom body without generated toc",
                written,
            )
            self.assertIn("# 2. 微信文章标题", written)
            self.assertIn("## 2.1 小节", written)

    def test_append_renumbers_after_manual_heading_edit(self):
        # 模拟用户手动把一个二级标题改成正文后，再追加新文章；
        # 这时旧文章内剩余标题和 TOC 都应该按当前结构重新编号。
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            original = (
                "# 文章一\n\n"
                "> 来源：https://example.com/a\n"
                "> update 2026/08/22 10 : 00\n\n"
                "前言。\n\n"
                "## 小节甲\n\n"
                "甲内容。\n\n"
                "## 小节乙\n\n"
                "乙内容。\n"
            )
            extractor = WeChatArticleExtractor(session=FakeSession())
            write_markdown_file(original, target, mode="append", url="https://example.com/a")

            edited = target.read_text(encoding="utf-8")
            edited = edited.replace(
                "## 1.1 小节甲\n\n甲内容。\n\n",
                "小节甲已改成正文。\n\n",
            )
            target.write_text(edited, encoding="utf-8")

            second = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(second.markdown, target, mode="append")

            written = target.read_text(encoding="utf-8")
            toc_part = written.split("<!-- toc-end -->", 1)[0]
            self.assertIn("# 1. 文章一", written)
            self.assertIn("小节甲已改成正文。", written)
            self.assertIn("## 1.1 小节乙", written)
            self.assertIn("# 2. 微信文章标题", written)
            self.assertIn("## 2.1 小节", written)
            self.assertIn("[1. 文章一](#1-文章一)", toc_part)
            self.assertIn("　　[1.1 小节乙](#11-小节乙)", toc_part)
            self.assertIn("[2. 微信文章标题](#2-微信文章标题)", toc_part)

    def test_refresh_markdown_structure_file_rebuilds_toc_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            original = (
                "<!-- toc-start -->\n\n"
                "# 目录\n\n"
                "[1. 文章一](#1-文章一)  \n"
                "　　[1.1 小节甲](#11-小节甲)  \n"
                "　　[1.2 小节乙](#12-小节乙)  \n"
                "<!-- toc-end -->\n\n---\n\n"
                "# 1. 文章一\n\n"
                "> 来源：https://example.com/a\n"
                "> update 2026/08/22 10 : 00\n\n"
                "前言。\n\n"
                "## 1.1 小节甲\n\n"
                "甲内容。\n\n"
                "## 1.2 小节乙\n\n"
                "乙内容。\n"
            )
            edited = original.replace(
                "## 1.1 小节甲\n\n甲内容。\n\n",
                "小节甲已改成正文。\n\n",
            )
            target.write_text(edited, encoding="utf-8")

            summary = refresh_markdown_structure_file(target)

            self.assertIsNotNone(summary)
            written = target.read_text(encoding="utf-8")
            backup_files = list(target.parent.glob("notes.bak-*.md"))
            self.assertEqual(len(backup_files), 1)
            self.assertEqual(backup_files[0].read_text(encoding="utf-8"), edited)
            self.assertIn("# 1. 文章一", written)
            self.assertIn("小节甲已改成正文。", written)
            self.assertIn("## 1.1 小节乙", written)
            self.assertIn("[1. 文章一](#1-文章一)", written)
            self.assertIn("　　[1.1 小节乙](#11-小节乙)", written)
            self.assertNotIn("## 1.1 小节甲", written)

    def test_toc_skips_headings_inside_code_fences(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("# 旧标题\n\n```\n# code heading\n```\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            self.assertIn("# code heading", written)
            # 代码围栏里的标题不出现在目录里
            self.assertNotIn("code heading]", written)

    def test_heading_numbering_replaces_plain_number_prefix(self):
        html = """
        <div id="js_content">
          <h2>1. 小节</h2>
          <h3>2. 子节</h3>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        markdown = WeChatArticleExtractor._convert_body(str(content))
        numbered = __import__("article_extractor")._number_headings("# 标题\n\n" + markdown)
        self.assertIn("# 1. 标题", numbered)
        self.assertIn("## 1.1 小节", numbered)
        self.assertIn("### 1.1.1 子节", numbered)
        self.assertNotIn("1. 小节", numbered)
        self.assertNotIn("2. 子节", numbered)

    def test_heading_numbering_skips_fenced_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("# 旧标题\n\n## 旧小节\n\n```\n# code heading\n```\n", encoding="utf-8")
            extractor = WeChatArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)
            write_markdown_file(result.markdown, target, mode="append")
            written = target.read_text(encoding="utf-8")
            self.assertIn("# 1. 旧标题", written)
            self.assertIn("## 1.1 旧小节", written)
            self.assertIn("# code heading", written)
            self.assertIn("# 2. 微信文章标题", written)

    def test_heading_numbering_strips_chinese_ordinal(self):
        markdown = (
            "# 标题\n\n"
            "## 一、POR（上电复位 Power-On Reset）\n\n"
            "## 二、原因分析\n"
        )
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 POR（上电复位 Power-On Reset）", numbered)
        self.assertIn("## 1.2 原因分析", numbered)
        self.assertNotIn("一、", numbered)

    def test_heading_numbering_strips_roman_and_circled_ordinal(self):
        markdown = "# 标题\n\n## Ⅰ、引言\n\n## Ⅱ. 背景\n\n### ① 细节\n"
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 引言", numbered)
        self.assertIn("## 1.2 背景", numbered)
        self.assertIn("### 1.2.1 细节", numbered)
        self.assertNotIn("Ⅰ、", numbered)
        self.assertNotIn("①", numbered)

    def test_heading_numbering_strips_first_chapter_form(self):
        markdown = "# 标题\n\n## 第一章 POR\n\n## 第二章：复位电路\n"
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 POR", numbered)
        self.assertIn("## 1.2 复位电路", numbered)
        self.assertNotIn("第一章", numbered)
        self.assertNotIn("第二章", numbered)

    def test_heading_numbering_strips_existing_number_then_ordinal(self):
        # 续写后旧编号 + 原文章序号同时存在，也要一并清掉
        markdown = "# 标题\n\n## 1.1 一、POR\n"
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 POR", numbered)
        self.assertNotIn("一、", numbered)

    def test_heading_numbering_keeps_content_words_with_leading_char(self):
        # 一/两/十/壹 开头但属于正常词语，不能误删
        markdown = "# 标题\n\n## 一文读懂上电复位\n\n## 两个时钟域\n\n## 十种常见故障\n"
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 一文读懂上电复位", numbered)
        self.assertIn("## 1.2 两个时钟域", numbered)
        self.assertIn("## 1.3 十种常见故障", numbered)

    def test_heading_numbering_keeps_heading_when_only_ordinal(self):
        # 标题只剩序号（如“1、第一节”）时保留原文，避免生成空标题
        markdown = "# 标题\n\n## 1、第一节\n"
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("## 1.1 1、第一节", numbered)

    def test_heading_numbering_demotes_body_h1(self):
        # 文章正文自带的 # 一级标题应并入当前文章，而不是拆成新文章
        markdown = (
            "# 标题\n\n"
            "> 来源：https://example.com/a\n"
            "> update 2026/08/16 01 : 00\n\n"
            "# 正文里的一级标题一\n\n正文内容\n\n"
            "# 正文里的一级标题二\n\n更多内容\n"
        )
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("# 1. 标题", numbered)
        self.assertIn("## 1.1 正文里的一级标题一", numbered)
        self.assertIn("## 1.2 正文里的一级标题二", numbered)
        self.assertNotIn("# 2. ", numbered)

    def test_heading_numbering_skips_body_heading_identical_to_title(self):
        # 正文第一个标题与文章标题完全相同（微信文章常在正文开头重复标题）时，
        # 不生成重复的 4.1 小节标题，避免标题出现两次
        markdown = (
            "# CPU 读一个地址，数据到底是怎么从 DDR 回来的？\n\n"
            "> 来源：https://example.com/a\n"
            "> update 2026/08/16 01 : 00\n\n"
            "# CPU 读一个地址，数据到底是怎么从 DDR 回来的？\n\n"
            "# ——一次 Read，如何穿过整个 SoC？\n\n正文内容\n"
        )
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("# 1. CPU 读一个地址，数据到底是怎么从 DDR 回来的？", numbered)
        self.assertNotIn("## 1.1 CPU 读一个地址，数据到底是怎么从 DDR 回来的？", numbered)
        self.assertIn("## 1.1 ——一次 Read，如何穿过整个 SoC？", numbered)

    def test_heading_numbering_body_separator_does_not_start_new_article(self):
        # 正文里的 --- 分隔线不能当作文章边界；只有带 > 来源： 的 # 才算新文章
        markdown = (
            "# 标题一\n\n"
            "> 来源：https://example.com/a\n"
            "> update 2026/08/16 01 : 00\n\n"
            "# 正文小节\n\n内容\n\n---\n\n继续正文\n\n"
            "# 标题二\n\n"
            "> 来源：https://example.com/b\n"
            "> update 2026/08/16 01 : 01\n\n正文二\n"
        )
        numbered = __import__("article_extractor")._number_headings(markdown)
        self.assertIn("# 1. 标题一", numbered)
        self.assertIn("## 1.1 正文小节", numbered)
        self.assertIn("# 2. 标题二", numbered)
        self.assertIn("---", numbered)

if __name__ == "__main__":
    unittest.main()
