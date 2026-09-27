# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_art7.html", encoding="utf-8", errors="replace").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)

node = content.find(string=lambda s: s and "full_pipeline_driver" in s)
cur = node
chain = []
while cur is not None and getattr(cur, "name", None) != "div":
    chain.append((getattr(cur, "name", None), (getattr(cur, "get", lambda k, d="": d)("style") or "")[:120]))
    cur = cur.parent
for c in reversed(chain):
    print(c)
