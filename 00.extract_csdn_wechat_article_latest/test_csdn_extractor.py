"""Tests for the CSDN article extraction core logic (no live network)."""

import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from csdn_extractor import (
    CSDNArticleExtractor,
    validate_url,
    write_markdown_file,
)


ARTICLE_URL = "https://blog.csdn.net/test_author/article/details/123456789"
IMAGE_URL = "https://img-blog.csdnimg.cn/example.png"

FAKE_HTML = """<!doctype html>
<html>
  <head>
    <meta property="og:title" content="CSDN 文章标题"/>
    <meta property="article:published_time" content="2026-08-03 10:00:00"/>
    <meta name="author" content="测试作者"/>
    <title>页面标题</title>
  </head>
  <body>
    <div class="blog-content-box">
      <h1 class="title-article">CSDN 文章标题</h1>
      <div class="article-info-box">
        <a class="follow-nickName" href="https://blog.csdn.net/test_author">测试作者</a>
        <span class="time">2026-08-03 10:00:00</span>
      </div>
      <div id="article_content" class="article_content">
        <div id="content_views">
          <p>第一段内容。</p>
          <p><img data-src="{image_url}" alt="示意图"/></p>
          <h2>小节</h2>
          <pre><code class="language-python">print("hello")</code></pre>
          <div class="hide-article-box"><p>隐藏推广</p></div>
        </div>
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
        raise AssertionError(f"unexpected URL: {url}")


class CSDNExtractorTests(unittest.TestCase):
    def test_cookie_is_attached_to_session(self):
        extractor = CSDNArticleExtractor(cookie="a=1; b=2")
        self.assertEqual(
            extractor._session.headers.get("Cookie"),
            "a=1; b=2",
        )

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
            extractor = CSDNArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(
                ARTICLE_URL,
                markdown_path=markdown_path,
            )

            self.assertEqual(result.metadata.title, "CSDN 文章标题")
            self.assertEqual(result.metadata.author, "测试作者")
            self.assertEqual(result.metadata.publish_time, "2026-08-03 10:00:00")
            self.assertEqual(result.image_count, 1)
            self.assertEqual(result.markdown_path, markdown_path)
            self.assertIn("# CSDN 文章标题", result.markdown)
            self.assertIn(f"> 来源：{ARTICLE_URL}", result.markdown)
            self.assertIn("> 作者：测试作者", result.markdown)
            self.assertIn("> 发布时间：2026-08-03 10:00:00", result.markdown)
            self.assertIn("第一段内容。", result.markdown)
            self.assertIn("article_assets/image-0001.png", result.markdown)
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}",
            )
            self.assertNotIn("隐藏推广", result.markdown)
            self.assertNotIn("data-src", result.markdown)

            image_file = out_dir / "article_assets" / "image-0001.png"
            self.assertTrue(image_file.is_file())
            self.assertEqual(image_file.read_bytes(), PNG_BYTES)

    def test_append_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\n", encoding="utf-8")
            extractor = CSDNArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("旧文章内容", appended)
            self.assertIn("---", appended)
            self.assertIn("# 1. CSDN 文章标题", appended)
            self.assertIn("notes_assets/image-0001.png", appended)

            with self.assertRaises(ValueError):
                write_markdown_file(result.markdown, target, mode="replace")
            self.assertEqual(target.read_text(encoding="utf-8"), appended)

    def test_code_blocks_are_normalized(self):
        html = """
        <div id="content_views">
          <pre><code class="language-python">
            <span>print("hello")</span>
            <span>  print("world")</span>
          </code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="content_views")
        CSDNArticleExtractor._remove_noise(content)
        CSDNArticleExtractor._normalize_code_blocks(content)
        markdown = CSDNArticleExtractor._convert_body(str(content))

        self.assertIn("```", markdown)
        self.assertIn('print("hello")', markdown)
        self.assertIn('print("world")', markdown)


if __name__ == "__main__":
    unittest.main()
