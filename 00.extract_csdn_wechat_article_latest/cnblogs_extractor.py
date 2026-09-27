"""Extract a Cnblogs (博客园) article into Markdown with local image files."""

from __future__ import annotations

import re

from article_extractor import (
    ArticleMetadata,
    BaseArticleExtractor,
    validate_url,
    write_markdown_file,
)


CNBLOGS_ORIGIN = "https://www.cnblogs.com"

CONTENT_SELECTORS = (
    ("div", {"id": "cnblogs_post_body"}),
    ("div", {"class": "blogpost-body"}),
    ("div", {"class": "postBody"}),
)

# 博客园代码块外层的装饰元素（复制按钮/工具栏），不包含正文；
# 注意不能删 cnblogs_code 本身，它包裹着 <pre> 代码。
DROP_CLASSES = (
    "cnblogs_code_toolbar",
    "cnblogs_code_copy",
)


class CnblogsArticleExtractor(BaseArticleExtractor):
    """Fetch a Cnblogs blog article page and convert its body to Markdown."""

    source_label = "博客园"
    referer = CNBLOGS_ORIGIN

    @staticmethod
    def _extract_metadata(soup, url: str) -> ArticleMetadata:
        title_node = (
            soup.find("h1", class_="postTitle")
            or soup.find("a", id="cb_post_title_url")
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
        # <title> 通常是「标题 - 作者 - 博客园」，去掉作者和站点后缀
        title = re.sub(r"\s*-\s*[^-]*-\s*博客园\s*$", "", title).strip()
        title = re.sub(r"\s*[-_|]\s*博客园\s*$", "", title).strip()
        if not title:
            title = "未命名博客园文章"

        author = ""
        post_desc = soup.find("div", class_="postDesc")
        if post_desc is not None:
            author_link = post_desc.find(
                "a", href=re.compile(r"https?://[^/]*cnblogs\.com/")
            )
            if author_link is not None:
                author = author_link.get_text(" ", strip=True)
        if not author:
            author_node = soup.find("meta", attrs={"name": "author"})
            if author_node is not None:
                author = author_node.get("content") or ""
        author = re.sub(r"\s+", " ", author or "").strip()

        publish_time = ""
        time_node = (
            soup.find("span", id="post-date")
            or soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "publishdate"})
        )
        if time_node is not None:
            publish_time = (
                time_node.get("content") or time_node.get_text(" ", strip=True) or ""
            ).strip()
        publish_time = re.sub(r"\s+", " ", publish_time).strip()

        return ArticleMetadata(
            title=title, author=author, publish_time=publish_time, url=url
        )

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
