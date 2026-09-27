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
    return chr(10).join(f.splitlines()[1:-1])

new_bodies = [fence_body(f) for f in re.findall(r"```.*?```", md, flags=re.S)]

dbg_path = r"D:\sandbox\debug.md"
raw = io.open(dbg_path, "rb").read().decode("utf-8")
lines = raw.split("\r\n")
start_idx = next(i for i, l in enumerate(lines) if l.startswith("# 13."))
fence_ranges = []
open_line = None
for i in range(start_idx, len(lines)):
    if re.match(r"^\s*(```|~~~)", lines[i]):
        if open_line is None:
            open_line = i
        else:
            fence_ranges.append((open_line, i))
            open_line = None

def strip_ws(s):
    return re.sub(r"\s+", "", s)

assert len(fence_ranges) == len(new_bodies)
for (a, b), nb in zip(fence_ranges, new_bodies):
    old_body = "\n".join(lines[a+1:b])
    old_lines = old_body.split("\n")
    deduped = []
    for l in old_lines:
        if deduped and deduped[-1] == l:
            continue
        deduped.append(l)
    assert strip_ws("\n".join(deduped)) == strip_ws(nb), f"mismatch at {a+1}"

for (a, b), nb in zip(fence_ranges, new_bodies):
    lines[a+1:b] = nb.split("\n")
out = "\r\n".join(lines)
io.open(dbg_path, "w", encoding="utf-8", newline="").write(out)
print("debug.md repaired OK, article-13 fences replaced:", len(fence_ranges))
