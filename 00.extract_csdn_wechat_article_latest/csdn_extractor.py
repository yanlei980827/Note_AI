"""Extract a CSDN blog article into Markdown with local image files."""

from __future__ import annotations

import re

from article_extractor import (
    ArticleMetadata,
    BaseArticleExtractor,
    validate_url,
    write_markdown_file,
)


CSDN_ORIGIN = "https://blog.csdn.net"

CONTENT_SELECTORS = (
    ("div", {"id": "content_views"}),
    ("div", {"id": "article_content"}),
    ("div", {"class": "markdown_views"}),
)

DROP_CLASSES = (
    "hide-article-box",
    "article-copyright",
    "more-toolbox",
    "recommend-box",
    "toolbox-list",
    "follow-text",
    "person-info",
    "subscribe-comment",
    "article-info-box",
)


class CSDNArticleExtractor(BaseArticleExtractor):
    """Fetch a CSDN blog article page and convert its body to Markdown."""

    source_label = "CSDN"
    referer = CSDN_ORIGIN

    @staticmethod
    def _extract_metadata(soup, url: str) -> ArticleMetadata:
        title_node = (
            soup.find("h1", class_="title-article")
            or soup.find("h1", class_="article-title")
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
        title = re.sub(r"\s*[-_|]\s*CSDN博客\s*$", "", title).strip()
        if not title:
            title = "未命名 CSDN 文章"

        author_node = (
            soup.find("a", class_="follow-nickName")
            or soup.find("a", class_="nick-name")
            or soup.find("meta", attrs={"name": "author"})
        )
        author = ""
        if author_node is not None:
            author = (author_node.get("content") or author_node.get_text(" ", strip=True) or "").strip()
        author = re.sub(r"\s+", " ", author).strip()

        time_node = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("span", class_="time")
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

    def _metadata_lines(self, metadata: ArticleMetadata):
        lines = []
        if metadata.author:
            lines.append(f"> 作者：{metadata.author}")
        if metadata.publish_time:
            lines.append(f"> 发布时间：{metadata.publish_time}")
        return lines
