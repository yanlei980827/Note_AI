# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_apb_sample.html", encoding="utf-8", errors="replace").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
pres = content.find_all("pre")
print("pres:", len(pres))
for pre in pres:
    code = pre.find("code")
    if code is None:
        continue
    txt = code.get_text()
    if "apb_write_test" in txt:
        print("found target pre")
        leafs = [sp for sp in code.find_all("span") if sp.has_attr("leaf")]
        print("leaf spans:", len(leafs))
        direct = [sp for sp in leafs if sp.parent is not None and sp.parent.name == "code"]
        print("leaf directly under code:", len(direct))
        brs = code.find_all("br")
        print("br count:", len(brs))
        leaf_br = [sp for sp in leafs if sp.find("br") is not None]
        print("leaf spans containing br:", len(leaf_br))
        # print structure of first 3 spans
        import re
        print(repr(str(code)[:600]))
        break
