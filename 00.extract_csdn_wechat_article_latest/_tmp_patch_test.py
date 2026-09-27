# -*- coding: utf-8 -*-
import io

path = r"D:\sandbox\extract_csdn_wechat_article_0815_fix\test_extractor.py"
src = io.open(path, "rb").read().decode("utf-8")

anchor = '''        self.assertNotIn("   2. Reset", markdown)

    def test_append_to_empty_file_does_not_prepend_separator(self):'''

new_test = '''        self.assertNotIn("   2. Reset", markdown)

    def test_wechat_new_style_token_spans_no_duplication(self):
        # 新版微信编辑器把一行代码拆成多个 leaf token span，部分 token 还被
        # 彩色包裹 span 包住，行尾用 <span leaf=""><br/></span> 标记。
        # 旧实现 find_all(attrs={"leaf": ""}) 会把没有 leaf 属性的彩色包裹
        # span 也匹配进来，导致每个 token 文本重复两遍。
        html = """
        <div id="js_content">
          <h2>示例代码</h2>
          <pre><code><span style="color: #c678dd;"><span leaf="">class</span></span><span leaf=""> apb_write_test </span><span style="color: #c678dd;"><span leaf="">extends</span></span><span leaf=""> uvm_test;</span><span leaf=""><br/></span><span style="color: #61aeee;"><span leaf="">`uvm_component_utils(apb_write_test)</span></span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">function</span></span><span leaf=""> new(string name, uvm_component parent);</span><span leaf=""><br/></span><span style="color: #c678dd;"><span leaf="">endfunction</span></span><span leaf=""><br/></span></code></pre>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        WeChatArticleExtractor._remove_noise(content)
        WeChatArticleExtractor._normalize_code_blocks(content)
        WeChatArticleExtractor._drop_empty_headings(content)
        markdown = WeChatArticleExtractor._convert_body(str(content))
        self.assertIn(
            "```\\nclass apb_write_test extends uvm_test;\\n"
            "`uvm_component_utils(apb_write_test)\\n"
            "function new(string name, uvm_component parent);\\n"
            "endfunction\\n```",
            markdown,
        )
        self.assertNotIn("class\\nclass", markdown)
        self.assertNotIn("extends\\nextends", markdown)
        self.assertNotIn("function\\nfunction", markdown)
        self.assertNotIn('"req"\\n"req"', markdown)

    def test_append_to_empty_file_does_not_prepend_separator(self):'''

assert anchor in src, "anchor not found"
src = src.replace(anchor, new_test, 1)
io.open(path, "w", encoding="utf-8", newline="").write(src)
print("test added OK")
