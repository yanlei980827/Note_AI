"""Extract a Zhihu article into Markdown with local image files."""

from __future__ import annotations

import re

from article_extractor import (
    ArticleMetadata,
    BaseArticleExtractor,
    validate_url,
    write_markdown_file,
)


ZHIHU_ORIGIN = "https://www.zhihu.com"

CONTENT_SELECTORS = (
    ("div", {"class": "Post-RichTextContainer"}),
    ("div", {"class": "Post-RichText"}),
    ("div", {"class": "RichText"}),
    ("div", {"class": "RichContent-inner"}),
    ("article", {}),
)

DROP_CLASSES = (
    "Post-SideActions",
    "Post-Actions",
    "Post-Footer",
    "Post-Header",
    "Post-Author",
    "Post-Topics",
    "ContentItem-actions",
    "RichContent-actions",
)


class ZhihuArticleExtractor(BaseArticleExtractor):
    """Fetch a Zhihu article page and convert its body to Markdown."""

    source_label = "知乎"
    referer = ZHIHU_ORIGIN

    def _fetch_page(self, url: str) -> str:
        response = self._session.get(url, timeout=self.timeout)
        if response.status_code in (401, 403):
            raise ValueError(
                "知乎拒绝了匿名访问（HTTP 403/401）。请先在浏览器登录知乎，"
                "再按 F12 复制 Network 请求里的 Cookie，"
                "粘贴到「Cookie（可选）」后重试。"
            )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    @staticmethod
    def _extract_metadata(soup, url: str) -> ArticleMetadata:
        title_node = (
            soup.find("h1", class_="Post-Title")
            or soup.find("h1")
            or soup.find("meta", property="og:title")
            or soup.find("title")
        )
        title = ""
        if title_node is not None:
            if title_node.name == "meta":
                title = title_node.get("content", "")
            else:
                title = title_node.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"\s*-\s*知乎\s*$", "", title).strip()
        if not title:
            title = "未命名知乎文章"

        author_node = (
            soup.find("meta", attrs={"name": "author"})
            or soup.find("a", class_="UserLink-link")
            or soup.find("span", class_="UserLink-link")
        )
        author = ""
        if author_node is not None:
            author = (author_node.get("content") or author_node.get_text(" ", strip=True) or "").strip()
        author = re.sub(r"\s+", " ", author).strip()

        time_node = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"itemprop": "datePublished"})
            or soup.find("span", class_="ContentItem-time")
        )
        publish_time = ""
        if time_node is not None:
            publish_time = (time_node.get("content") or time_node.get_text(" ", strip=True) or "").strip()
        publish_time = re.sub(r"\s+", " ", publish_time).strip()

        return ArticleMetadata(title=title, author=author, publish_time=publish_time, url=url)

    @staticmethod
    def _find_content(soup):
        for name, attrs in CONTENT_SELECTORS:
            node = soup.find(name, attrs=attrs)
            if node is not None:
                return node
        return None

    @staticmethod
    def _remove_noise(content_node) -> None:
        BaseArticleExtractor._remove_noise(content_node)
        for class_name in DROP_CLASSES:
            for tag in content_node.find_all(class_=class_name):
                tag.decompose()

    @staticmethod
    def _image_source(img) -> str:
        return (
            img.get("data-actualsrc")
            or img.get("data-original")
            or img.get("data-src")
            or img.get("src")
            or ""
        )

    def _metadata_lines(self, metadata: ArticleMetadata):
        lines = []
        if metadata.author:
            lines.append(f"> 作者：{metadata.author}")
        if metadata.publish_time:
            lines.append(f"> 发布时间：{metadata.publish_time}")
        return lines
