# -*- coding: utf-8 -*-
import io, re

path = r"D:\sandbox\extract_csdn_wechat_article_0815_fix\wechat_extractor.py"
src = io.open(path, "rb").read().decode("utf-8")

old = re.compile(
    r"            if leaf_spans:\r?\n"
    r"                new_style = any\(\r?\n"
    r"                    span\.parent is not None and span\.parent\.name == \"code\"\r?\n"
    r"                    for span in leaf_spans\r?\n"
    r"                \)\r?\n"
    r"                if new_style:"
)
new = (
    "            if leaf_spans:\r\n"
    "                new_style = any(span.find(\"br\") is not None for span in leaf_spans)\r\n"
    "                if new_style:"
)
assert old.search(src), "anchor not found"
src = old.sub(lambda m: new, src, count=1)
io.open(path, "w", encoding="utf-8", newline="").write(src)
print("patched OK")
