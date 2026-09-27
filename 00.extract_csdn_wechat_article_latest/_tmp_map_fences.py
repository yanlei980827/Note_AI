# -*- coding: utf-8 -*-
import io, re, sys
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

fences = re.findall(r"```.*?```", md, flags=re.S)
print("regenerated fences:", len(fences))

dbg = io.open(r"D:\sandbox\debug.md", encoding="utf-8", errors="replace").read()
dbg_lines = dbg.split(chr(10))
# debug.md article 13 fences: lines 2285-3122
dbg_fences = []
open_line = None
for i, l in enumerate(dbg_lines):
    if 2284 <= i <= 3121:
        if re.match(r"^\s*```", l):
            if open_line is None:
                open_line = i
            else:
                dbg_fences.append((open_line+1, i+1))
                open_line = None
print("debug.md article-13 fences:", len(dbg_fences))

# For each regenerated fence, print first content line; for each dbg fence print first content line
def first_content(f):
    for l in f.splitlines():
        if l.strip():
            return l.strip()
    return ""

print("\nregenerated first lines:")
for i, f in enumerate(fences):
    print(i, "|", first_content(f))
print("\ndebug.md article-13 first lines:")
for i, (a, b) in enumerate(dbg_fences):
    block = chr(10).join(dbg_lines[a:b])
    print(i, "|", first_content(block))
