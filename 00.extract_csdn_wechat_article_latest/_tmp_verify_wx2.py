# -*- coding: utf-8 -*-
import io, sys, re
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
md = ext._convert_body(str(content_node))

# extract all code fences
fences = re.findall(r"```.*?```", md, flags=re.S)
print(f"total fences: {len(fences)}")
bad = 0
for fi, f in enumerate(fences):
    lines = [l for l in f.splitlines() if l.strip()]
    dups = [(i, lines[i], lines[i+1]) for i in range(len(lines)-1) if lines[i] == lines[i+1]]
    if dups:
        bad += 1
        print(f"--- fence {fi} has consecutive dup lines: {dups[:4]}")
        print(f[:400])
print(f"fences with consecutive duplicate lines: {bad}")
# Also count raw duplicate token pattern: same non-space token twice in a row within one line is fine; check line pairs
