# -*- coding: utf-8 -*-
import io, re, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor
from article_extractor import _number_headings, _ensure_toc

# 1) regenerated article 13 body from the FIXED extractor
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
numbered = _number_headings(header + body_md, start_article=13)

# 2) keep intact prefix of current debug.md (articles 1-12 + separator before # 13.)
dbg_path = r"D:\sandbox\debug.md"
raw = io.open(dbg_path, "rb").read().decode("utf-8")
lines = raw.split("\r\n")
title_idx = next(i for i, l in enumerate(lines) if l.startswith("# 13."))
keep = lines[:title_idx]
print("keeping lines 1..", title_idx, "| last kept:", keep[-3:])

# 3) combine and rebuild TOC
combined = "\r\n".join(keep) + "\r\n" + numbered.replace("\n", "\r\n")
final = _ensure_toc(combined, "\r\n")

io.open(dbg_path, "w", encoding="utf-8", newline="").write(final)
print("debug.md rebuilt OK, final lines:", final.count("\r\n") + 1)
