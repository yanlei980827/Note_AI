"""Tests for the Zhihu article extraction core logic (no live network)."""

import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from zhihu_extractor import (
    ZhihuArticleExtractor,
    validate_url,
    write_markdown_file,
)


ARTICLE_URL = "https://zhuanlan.zhihu.com/p/357258757"
IMAGE_URL = "https://pic1.zhimg.com/v2-example_720w.jpg"

FAKE_HTML = """<!doctype html>
<html>
  <head>
    <meta property="og:title" content="知乎文章标题"/>
    <meta name="author" content="测试作者"/>
    <meta property="article:published_time" content="2026-08-03 10:00:00"/>
    <title>页面标题</title>
  </head>
  <body>
    <h1 class="Post-Title">知乎文章标题</h1>
    <div class="Post-Header">
      <a class="UserLink-link" href="https://www.zhihu.com/people/test">测试作者</a>
    </div>
    <div class="Post-RichTextContainer">
      <div class="RichText ztext Post-RichText">
        <p>第一段内容。</p>
        <p><img data-actualsrc="{image_url}" alt="示意图"/></p>
        <h2>小节</h2>
        <pre><code class="language-python">print("hello")</code></pre>
        <div class="Post-Footer"><p>页脚推荐</p></div>
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
    def __init__(self, content, content_type, status=200):
        self._content = content
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.status_code = status
        self.text = content.decode("utf-8", errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("should not be reached")
        return None

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]


class FakeSession:
    def __init__(self, status=200):
        self.status = status

    def get(self, url, **kwargs):
        if url == ARTICLE_URL:
            if self.status == 403:
                return FakeResponse(b"forbidden", "text/plain", status=403)
            return FakeResponse(FAKE_HTML.encode("utf-8"), "text/html; charset=utf-8")
        if url == IMAGE_URL:
            return FakeResponse(PNG_BYTES, "image/jpeg")
        raise AssertionError(f"unexpected URL: {url}")


class ZhihuExtractorTests(unittest.TestCase):
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
            extractor = ZhihuArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(
                ARTICLE_URL,
                markdown_path=markdown_path,
            )

            self.assertEqual(result.metadata.title, "知乎文章标题")
            self.assertEqual(result.metadata.author, "测试作者")
            self.assertEqual(result.metadata.publish_time, "2026-08-03 10:00:00")
            self.assertEqual(result.image_count, 1)
            self.assertEqual(result.markdown_path, markdown_path)
            self.assertIn("# 知乎文章标题", result.markdown)
            self.assertIn(f"> 来源：{ARTICLE_URL}", result.markdown)
            self.assertIn("> 作者：测试作者", result.markdown)
            self.assertIn("> 发布时间：2026-08-03 10:00:00", result.markdown)
            self.assertIn("第一段内容。", result.markdown)
            self.assertIn("article_assets/image-0001.jpg", result.markdown)
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}",
            )
            self.assertNotIn("页脚推荐", result.markdown)
            self.assertNotIn("data-actualsrc", result.markdown)

            image_file = out_dir / "article_assets" / "image-0001.jpg"
            self.assertTrue(image_file.is_file())
            self.assertEqual(image_file.read_bytes(), PNG_BYTES)

    def test_append_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\n", encoding="utf-8")
            extractor = ZhihuArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("旧文章内容", appended)
            self.assertIn("---", appended)
            self.assertIn("# 1. 知乎文章标题", appended)
            self.assertIn("notes_assets/image-0001.jpg", appended)

            with self.assertRaises(ValueError):
                write_markdown_file(result.markdown, target, mode="replace")
            self.assertEqual(target.read_text(encoding="utf-8"), appended)

    def test_forbidden_raises_helpful_error(self):
        extractor = ZhihuArticleExtractor(session=FakeSession(status=403))
        with self.assertRaises(ValueError) as ctx:
            extractor.extract_article_html(ARTICLE_URL, markdown_path=Path(tempfile.gettempdir()) / "x.md")
        self.assertIn("Cookie", str(ctx.exception))

    def test_cookie_is_attached_to_session(self):
        extractor = ZhihuArticleExtractor(cookie="a=1; b=2")
        self.assertEqual(
            extractor._session.headers.get("Cookie"),
            "a=1; b=2",
        )

    def test_code_blocks_are_normalized(self):
        html = """
        <div class="Post-RichTextContainer">
          <pre><code class="language-python">
            <span>print("hello")</span>
            <span>  print("world")</span>
          </code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", class_="Post-RichTextContainer")
        ZhihuArticleExtractor._remove_noise(content)
        ZhihuArticleExtractor._normalize_code_blocks(content)
        markdown = ZhihuArticleExtractor._convert_body(str(content))

        self.assertIn("```", markdown)
        self.assertIn('print("hello")', markdown)
        self.assertIn('print("world")', markdown)


if __name__ == "__main__":
    unittest.main()
