# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from wechat_extractor import WeChatArticleExtractor

html = io.open(r"D:\sandbox\_wx_apb_sample.html", encoding="utf-8", errors="replace").read()
ext = WeChatArticleExtractor()
soup = ext._parse_html(html)
content_node = ext._find_content(soup)
assert content_node is not None, "content node not found"
ext._remove_noise(content_node)
ext._normalize_code_blocks(content_node)
ext._drop_empty_headings(content_node)
ext._merge_list_heading_content(content_node)
body_html = str(content_node)
md = ext._convert_body(body_html)

print("=== checks ===")
for token in ["task body();", '"req"', "req = apb_transaction::type_id::create(", "start_item(req);", "class apb_write_test extends uvm_test;"]:
    print(f"{token!r}: {md.count(token)}")

idx = md.find("apb_write_test")
start = md.rfind("```", 0, idx)
end = md.find("```", idx)
print("\n=== code block around apb_write_test ===")
print(md[start:end+3])
