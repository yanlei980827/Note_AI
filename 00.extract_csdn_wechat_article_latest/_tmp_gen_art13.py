# -*- coding: utf-8 -*-
import io, re, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_apb_sample.html", encoding="utf-8", errors="replace").read()
ext = WeChatArticleExtractor()
soup = ext._parse_html(html)
content_node = ext._find_content(soup)
ext._remove_noise(content_node)
ext._normalize_code_blocks(content_node)
ext._drop_empty_headings(content_node)
ext._merge_list_heading_content(content_node)
body_md = ext._convert_body(str(content_node))

# save for later
io.open(r"D:\sandbox\_tmp_art13_body.md", "w", encoding="utf-8", newline="").write(body_md)
print("body chars:", len(body_md))
print("=== headings ===")
for l in body_md.splitlines():
    if re.match(r"^#{1,6} ", l):
        print(l[:80])
