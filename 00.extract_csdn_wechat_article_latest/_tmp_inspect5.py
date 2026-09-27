# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"test\page2.html", encoding="utf-8", errors="ignore").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
pre = content.find_all("pre")[0]
code = pre.find("code")
print("code children:", [(getattr(c,'name',None)) for c in code.children])
for sec in code.find_all("section"):
    cols = sec.find_all("span", recursive=False)
    print("section spans:", [repr(str(s))[:80] for s in cols][:6])
    break
