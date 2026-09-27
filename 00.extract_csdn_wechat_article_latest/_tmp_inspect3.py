# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"test\page2.html", encoding="utf-8", errors="ignore").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
for pre in content.find_all("pre")[:2]:
    code = pre.find("code")
    if code is None: continue
    leafs = [sp for sp in code.find_all("span") if sp.has_attr("leaf")]
    brs = code.find_all("br")
    leaf_br = [sp for sp in leafs if sp.find("br") is not None]
    print("leafs:", len(leafs), "brs:", len(brs), "leaf-with-br:", len(leaf_br))
    print(repr(str(code)[:500]))
    print("---")
