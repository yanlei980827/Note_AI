# -*- coding: utf-8 -*-
import io, sys, re
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"test\page2.html", encoding="utf-8", errors="ignore").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
WeChatArticleExtractor._remove_noise(content)
WeChatArticleExtractor._normalize_code_blocks(content)
WeChatArticleExtractor._drop_empty_headings(content)
md = WeChatArticleExtractor._convert_body(str(content))

print("=== old-format checks ===")
for token in ["if ( src_hs & ~rdy_dst)", "data_buf <= data_src;", "if ( src_vld & ~src_hs )"]:
    print(f"{token!r}: {md.count(token)}")

fences = re.findall(r"```.*?```", md, flags=re.S)
print(f"total fences: {len(fences)}")
bad = 0
for fi, f in enumerate(fences):
    lines = [l for l in f.splitlines() if l.strip()]
    dups = [(i, lines[i], lines[i+1]) for i in range(len(lines)-1) if lines[i] == lines[i+1]]
    if dups:
        bad += 1
        print(f"--- fence {fi} dup: {dups[:4]}")
print(f"fences with consecutive dup lines: {bad}")
