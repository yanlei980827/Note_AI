# -*- coding: utf-8 -*-
import io, re, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor
from article_extractor import _number_headings, _ensure_toc

html = io.open(r"D:\sandbox\_wx_apb_sample.html", encoding="utf-8", errors="replace").read()
ext = WeChatArticleExtractor()
soup = ext._parse_html(html)
content_node = ext._find_content(soup)
ext._remove_noise(content_node)
ext._normalize_code_blocks(content_node)
ext._drop_empty_headings(content_node)
ext._merge_list_heading_content(content_node)
body_md = ext._convert_body(str(content_node))
body_md = body_md.replace("![]()", "![](debug_assets/image-0145.png)", 1)

header = (
    "# 握手 — 让 APB Master VIP 动起来\n\n"
    "> 来源：https://mp.weixin.qq.com/s/RpABSbuC-ysRU_tYugGIZw\n"
    "> 作者：福尔摩芯\n"
    "> update 2026/08/22 19 : 36\n\n"
)
full = header + body_md
numbered = _number_headings(full, start_article=13)

print("=== regenerated article-13 headings ===")
for l in numbered.splitlines():
    if re.match(r"^#{1,6} ", l):
        print(l[:80])
print("\nchar count:", len(numbered))
