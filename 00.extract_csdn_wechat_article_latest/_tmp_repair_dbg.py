# -*- coding: utf-8 -*-
import io, re, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

# 1) regenerate article 13 fences from the sample HTML with the FIXED extractor
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

new_bodies = [fence_body(f) for f in re.findall(r"```.*?```", md, flags=re.S)]
print("regenerated bodies:", len(new_bodies))

# 2) read debug.md preserving CRLF
dbg_path = r"D:\sandbox\debug.md"
raw = io.open(dbg_path, "rb").read().decode("utf-8")
lines = raw.split("\r\n")
has_crlf = "\r\n" in raw
print("crlf:", has_crlf, "lines:", len(lines))

# 3) locate article 13 heading and fences after it
start_idx = None
for i, l in enumerate(lines):
    if l.startswith("# 13. ") or l.startswith("# 13."):
        start_idx = i
        break
assert start_idx is not None, "article 13 heading not found"
print("article 13 starts at line:", start_idx + 1)

fence_ranges = []
open_line = None
for i in range(start_idx, len(lines)):
    if re.match(r"^\s*(```|~~~)", lines[i]):
        if open_line is None:
            open_line = i
        else:
            fence_ranges.append((open_line, i))
            open_line = None
print("article-13 fences found:", len(fence_ranges))
assert len(fence_ranges) == len(new_bodies), "fence count mismatch"

# 4) verify token consistency: dedup consecutive dup lines in broken body, then
#    compare whitespace token sequence with regenerated body
def tokens(s):
    return s.split()

problems = 0
for (a, b), nb in zip(fence_ranges, new_bodies):
    old_body = "\n".join(lines[a+1:b])
    # collapse consecutive identical lines in the broken body
    old_lines = old_body.split("\n")
    deduped = []
    for l in old_lines:
        if deduped and deduped[-1] == l:
            continue
        deduped.append(l)
    deduped_body = "\n".join(deduped)
    ot = tokens(deduped_body)
    nt = tokens(nb)
    # compare ignoring the formatting-only tokens like \xa0->space changes are fine
    if ot != nt:
        problems += 1
        print(f"MISMATCH fence a={a+1}: old_tokens={ot[:12]}... new_tokens={nt[:12]}...")
print("token mismatches:", problems)

if problems == 0:
    # 5) replace bodies
    for (a, b), nb in zip(fence_ranges, new_bodies):
        lines[a+1:b] = nb.split("\n")
    out = "\r\n".join(lines) if has_crlf else "\n".join(lines)
    io.open(dbg_path, "w", encoding="utf-8", newline="").write(out)
    print("debug.md repaired OK")
else:
    print("ABORT: not writing")
