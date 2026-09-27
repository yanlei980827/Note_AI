# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"test\page2.html", encoding="utf-8", errors="ignore").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
pre = content.find_all("pre")[0]
code = pre.find("code")
leafs = [sp for sp in code.find_all("span") if sp.has_attr("leaf")]
for sp in leafs[:16]:
    print(repr(str(sp))[:160])
print("...")
print("parent chain of leafs:", [(sp.name, sp.parent.name if sp.parent else None) for sp in leafs[:6]])
