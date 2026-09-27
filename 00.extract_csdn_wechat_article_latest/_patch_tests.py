import io

path = r"test_extractor.py"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

newline = "\r\n" if "\r\n" in text else "\n"

tests = (
    "    def test_append_never_creates_setext_heading(self):" + newline
    + "        # 复现 debug.md 场景：第一篇文章以 '---' + 尾段结束，" + newline
    + "        # 追加第二篇文章时分隔符不能紧贴尾段（否则会形成 Setext 标题）。" + newline
    + "        with tempfile.TemporaryDirectory() as tmp:" + newline
    + "            target = Path(tmp) / \"notes.md\"" + newline
    + "            target.write_text(" + newline
    + "                \"最后一段内容。\\n\\n---\\n\\n\""
    + "\\n*（文章末尾附注。）*\\n\", encoding=\"utf-8\")" + newline
    + "            extractor = WeChatArticleExtractor(session=FakeSession())" + newline
    + "            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)" + newline
    + "            write_markdown_file(result.markdown, target, mode=\"append\")" + newline
    + "            appended = target.read_text(encoding=\"utf-8\")" + newline
    + "            self.assertIn(\"*（文章末尾附注。）*\\n\\n---\\n\\n# 微信文章标题\", appended)" + newline
    + "            self.assertNotRegex(appended, r\"(?m)^[^#>\\n].*\\n---\\s*$\")" + newline
    + newline
    + "    def test_append_after_trailing_horizontal_rule_uses_single_separator(self):" + newline
    + "        with tempfile.TemporaryDirectory() as tmp:" + newline
    + "            target = Path(tmp) / \"notes.md\"" + newline
    + "            target.write_text(\"已有内容\\n\\n---\\n\", encoding=\"utf-8\")" + newline
    + "            extractor = WeChatArticleExtractor(session=FakeSession())" + newline
    + "            result = extractor.extract_article_html(ARTICLE_URL, markdown_path=target)" + newline
    + "            write_markdown_file(result.markdown, target, mode=\"append\")" + newline
    + "            appended = target.read_text(encoding=\"utf-8\")" + newline
    + "            self.assertIn(\"已有内容\\n\\n---\\n\\n# 微信文章标题\", appended)" + newline
    + "            self.assertNotIn(\"---\\n\\n---\", appended)" + newline
    + newline
)

anchor = "if __name__ == \"__main__\":" + newline
assert anchor in text, "main guard not found"
text = text.replace(anchor, tests + anchor, 1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("patched test_extractor.py:", "test_append_never_creates_setext_heading" in text)
