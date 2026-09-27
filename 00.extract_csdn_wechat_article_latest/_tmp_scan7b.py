# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_art7.html", encoding="utf-8", errors="replace").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)

secs = content.find_all("section")
print("total sections:", len(secs))
for idx, s in enumerate(secs):
    style = s.get("style") or ""
    leafs = [sp for sp in s.find_all("span") if sp.has_attr("leaf")]
    brs = s.find_all("br")
    nbsp = style.count("white-space")
    flags = []
    if "white-space: nowrap" in style: flags.append("nowrap")
    if "white-space: pre" in style: flags.append("pre")
    if "Consolas" in style or "monospace" in style: flags.append("mono")
    if "rgb(40, 44, 52)" in style: flags.append("bg-dark")
    if leafs: flags.append(f"leaf={len(leafs)}")
    if brs: flags.append(f"br={len(brs)}")
    if flags:
        print(idx, "|", ",".join(flags), "| text:", s.get_text()[:60].replace(chr(10), " "))
