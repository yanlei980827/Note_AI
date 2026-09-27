"""Tests for the Cnblogs (博客园) article extraction core logic (no live network)."""

import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from cnblogs_extractor import (
    CnblogsArticleExtractor,
    validate_url,
    write_markdown_file,
)


ARTICLE_URL = "https://www.cnblogs.com/xianyuIC/p/19356143"
IMAGE_URL = (
    "https://img2023.cnblogs.com/blog/1536533/202306/"
    "1536533-20230611221502810-262151781.png"
)

FAKE_HTML = """<!doctype html>
<html>
  <head>
    <meta property="og:title" content="博客园文章标题"/>
    <title>博客园文章标题 - 测试作者 - 博客园</title>
  </head>
  <body>
    <div id="post_detail">
      <div class="post">
        <h1 class="postTitle"><a id="cb_post_title_url" href="{url}">博客园文章标题</a></h1>
        <div class="postBody">
          <div id="cnblogs_post_body" class="blogpost-body">
            <p>第一段内容。</p>
            <p><img src="{image_url}" alt="示意图"/></p>
            <h2>小节</h2>
            <p>第二段内容。</p>
            <div class="cnblogs_code_toolbar">
              <span class="cnblogs_code_copy">复制代码</span>
            </div>
            <pre><code class="language-python"><span>print("hello")</span></code></pre>
          </div>
          <div class="postDesc">
            posted @ <span id="post-date">2026-08-03 10:00</span>
            <a href="https://www.cnblogs.com/test_author">测试作者</a>
            阅读(<span>1</span>) 评论(<span>0</span>)
            <a href="javascript:void(0)">收藏</a>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
""".format(url=ARTICLE_URL, image_url=IMAGE_URL)

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


class CnblogsExtractorTests(unittest.TestCase):
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
            extractor = CnblogsArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(
                ARTICLE_URL,
                markdown_path=markdown_path,
            )

            self.assertEqual(result.metadata.title, "博客园文章标题")
            self.assertEqual(result.metadata.author, "测试作者")
            self.assertEqual(result.metadata.publish_time, "2026-08-03 10:00")
            self.assertEqual(result.image_count, 1)
            self.assertEqual(result.markdown_path, markdown_path)
            self.assertIn("# 博客园文章标题", result.markdown)
            self.assertIn(f"> 来源：{ARTICLE_URL}", result.markdown)
            self.assertIn("> 作者：测试作者", result.markdown)
            self.assertIn("> 发布时间：2026-08-03 10:00", result.markdown)
            self.assertIn("第一段内容。", result.markdown)
            self.assertIn("article_assets/image-0001.png", result.markdown)
            self.assertRegex(
                result.markdown,
                r"> update \d{4}/\d{2}/\d{2} \d{2} : \d{2}",
            )
            self.assertNotIn("复制代码", result.markdown)
            self.assertNotIn("cnblogs_code_toolbar", result.markdown)
            self.assertNotIn("data-src", result.markdown)

            image_file = out_dir / "article_assets" / "image-0001.png"
            self.assertTrue(image_file.is_file())
            self.assertEqual(image_file.read_bytes(), PNG_BYTES)

    def test_append_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.md"
            target.write_text("旧文章内容\n", encoding="utf-8")
            extractor = CnblogsArticleExtractor(session=FakeSession())
            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)

            write_markdown_file(result.markdown, target, mode="append")
            appended = target.read_text(encoding="utf-8")
            self.assertIn("旧文章内容", appended)
            self.assertIn("---", appended)
            self.assertIn("# 1. 博客园文章标题", appended)
            self.assertIn("notes_assets/image-0001.png", appended)

            with self.assertRaises(ValueError):
                write_markdown_file(result.markdown, target, mode="replace")
            self.assertEqual(target.read_text(encoding="utf-8"), appended)

    def test_metadata_falls_back_to_title_tag(self):
        html = """<!doctype html>
        <html>
          <head><title>回退标题 - 某作者 - 博客园</title></head>
          <body>
            <div id="post_detail">
              <div class="postBody">
                <div id="cnblogs_post_body"><p>正文。</p></div>
                <div class="postDesc">
                  posted @ <span id="post-date">2026-08-01 09:30</span>
                  <a href="https://www.cnblogs.com/someone">某作者</a>
                </div>
              </div>
            </div>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = CnblogsArticleExtractor._extract_metadata(soup, ARTICLE_URL)
        self.assertEqual(metadata.title, "回退标题")
        self.assertEqual(metadata.author, "某作者")
        self.assertEqual(metadata.publish_time, "2026-08-01 09:30")

    def test_code_blocks_are_normalized(self):
        html = """
        <div id="cnblogs_post_body">
          <div class="cnblogs_code_toolbar"><span>复制代码</span></div>
          <pre><code class="language-python">
            <span>print("hello")</span>
            <span>  print("world")</span>
          </code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="cnblogs_post_body")
        CnblogsArticleExtractor._remove_noise(content)
        CnblogsArticleExtractor._normalize_code_blocks(content)
        markdown = CnblogsArticleExtractor._convert_body(str(content))

        self.assertIn("```", markdown)
        self.assertIn('print("hello")', markdown)
        self.assertIn('  print("world")', markdown)
        self.assertNotIn("复制代码", markdown)
        self.assertNotIn("cnblogs_code_toolbar", markdown)


if __name__ == "__main__":
    unittest.main()
