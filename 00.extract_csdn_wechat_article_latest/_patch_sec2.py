# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
wx = BASE / "wechat_extractor.py"

text = wx.read_text(encoding="utf-8")

old = '''        for list_node in content_node.find_all(["ul", "ol"]):
            items = list_node.find_all("li", recursive=False)
            if len(items) != 1:
                continue
            li = items[0]
            children = [
                child
                for child in li.children
                if getattr(child, "name", None)
                or (getattr(child, "string", None) or "").strip()
            ]
            if len(children) != 1 or getattr(children[0], "name", None) not in (
                "h1", "h2", "h3", "h4", "h5", "h6",
            ):
                continue
            siblings = []'''
new = '''        for list_node in content_node.find_all(["ul", "ol"]):
            items = list_node.find_all("li", recursive=False)
            if len(items) != 1:
                continue
            li = items[0]
            if _single_heading_element(li) is None:
                continue
            siblings = []'''
assert text.count(old) == 1, f"count={text.count(old)}"
text = text.replace(old, new, 1)
wx.write_text(text, encoding="utf-8")
print("patched wechat_extractor.py: use _single_heading_element in merge loop")
