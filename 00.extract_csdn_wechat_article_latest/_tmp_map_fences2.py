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

def fence_body(f):
    lines = f.splitlines()
    return chr(10).join(lines[1:-1])

fences = [fence_body(f) for f in re.findall(r"```.*?```", md, flags=re.S)]

dbg = io.open(r"D:\sandbox\debug.md", encoding="utf-8", errors="replace").read()
dbg_lines = dbg.split(chr(10))
dbg_fences = []
open_line = None
for i, l in enumerate(dbg_lines):
    if 2284 <= i <= 3121:
        if re.match(r"^\s*```", l):
            if open_line is None:
                open_line = i
            else:
                dbg_fences.append(chr(10).join(dbg_lines[open_line+1:i]))
                open_line = None

# dedupe helper: compress consecutive identical lines
def dedupe(b):
    lines = b.split(chr(10))
    out = []
    for l in lines:
        if out and out[-1] == l:
            continue
        out.append(l)
    return chr(10).join(out)

print("=== compare regenerated vs debug.md article-13 fences ===")
for i, (rf, df) in enumerate(zip(fences, dbg_fences)):
    rfirst = [l for l in rf.split(chr(10)) if l.strip()][0] if rf.strip() else "(empty)"
    dfirst = [l for l in df.split(chr(10)) if l.strip()][0] if df.strip() else "(empty)"
    # match check: is regenerated first line's token sequence a superset of debug's first line?
    print(f"fence {i}: reg={rfirst!r} dbg={dfirst!r}")
