# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_art7.html", encoding="utf-8", errors="replace").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
print("content node:", content.name, content.get("id") or content.get("class"))

pres = content.find_all("pre")
codes = content.find_all("code")
print("pres:", len(pres), "codes:", len(codes))

# find the full_pipeline_driver code block
node = content.find(string=lambda s: s and "full_pipeline_driver" in s)
print("text node found:", node is not None)
if node is not None:
    # walk up to find code block container
    cur = node
    chain = []
    while cur is not None and cur.name != "body":
        chain.append((cur.name, (cur.get("style") or "")[:120]))
        cur = cur.parent
    for c in reversed(chain):
        print(c)

# check all section-based code candidates: sections with nowrap style inside content
secs = content.find_all("section")
print("sections in content:", len(secs))
nowrap = [s for s in secs if s.get("style") and "white-space: nowrap" in s.get("style")]
print("nowrap sections:", len(nowrap))
for s in nowrap[:3]:
    print("  section style:", (s.get("style") or "")[:150])
    leafs = s.find_all("span", attrs={"leaf": ""})
    print("  direct leaf spans:", len([sp for sp in s.find_all("span") if sp.has_attr("leaf")]), "br:", len(s.find_all("br")))
