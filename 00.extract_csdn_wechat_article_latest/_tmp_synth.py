# -*- coding: utf-8 -*-
import io, sys
sys.path.insert(0, r"D:\sandbox\extract_csdn_wechat_article_0815_fix")
from bs4 import BeautifulSoup
from wechat_extractor import WeChatArticleExtractor

html = """<div id="js_content">
  <h2>示例代码</h2>
  <pre><code><span style="color: #c678dd;"><span leaf="">class</span></span><span leaf=""> apb_write_test </span><span style="color: #c678dd;"><span leaf="">extends</span></span><span leaf=""> uvm_test;</span><span leaf=""><br/></span><span style="color: #61aeee;"><span leaf="">`uvm_component_utils(apb_write_test)</span></span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">function</span></span><span leaf=""> new(string name, uvm_component parent);</span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">endfunction</span></span><span leaf=""><br/></span></code></pre>
</div>"""
soup = BeautifulSoup(html, "html.parser")
content = soup.find(id="js_content")
WeChatArticleExtractor._remove_noise(content)
WeChatArticleExtractor._normalize_code_blocks(content)
WeChatArticleExtractor._drop_empty_headings(content)
md = WeChatArticleExtractor._convert_body(str(content))
print(repr(md))
