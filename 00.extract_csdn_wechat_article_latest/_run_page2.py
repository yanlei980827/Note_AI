import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from bs4 import BeautifulSoup
from wechat_extractor import WeChatArticleExtractor

html = open(r"test\page2.html", encoding="utf-8", errors="ignore").read()
soup = WeChatArticleExtractor._parse_html(html)
content = WeChatArticleExtractor._find_content(soup)
WeChatArticleExtractor._remove_noise(content)
WeChatArticleExtractor._normalize_code_blocks(content)
WeChatArticleExtractor._drop_empty_headings(content)
md = WeChatArticleExtractor._convert_body(str(content))
print(md[:3000])
