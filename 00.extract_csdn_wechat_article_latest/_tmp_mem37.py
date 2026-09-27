# -*- coding: utf-8 -*-
import io

path = r"D:\sandbox\extract_csdn_wechat_article_0815_fix\extract_csdn_wechat_article_memory.md"
src = io.open(path, "rb").read().decode("utf-8")

entry = """
37. 修复微信新版代码块 token 重复 bug（2026-08-22）：用户报告 debug.md 最新一篇（微信 APB Master VIP 文章）代码块每个 token 重复两遍、
    一行被拆成多个 token 行（如 `task\\ntask\\n body();`）。
    - 根因一：`BeautifulSoup.find_all("span", attrs={"leaf": ""})` 会过度匹配——把没有 `leaf=""` 属性的彩色包裹 span
      （`<span style="color:..."><span leaf="">class</span></span>` 的外层）也匹配进来，同一文本被抓两次 → 重复。
    - 根因二：新版微信编辑器把一行代码拆成多个 leaf token span（leaf 或被彩色 span 包裹的 leaf），行尾用
      `<span leaf=""><br/></span>` 标记；旧版每行是一个完整 leaf span。旧逻辑按 span 逐行 get_text → 行被拆散。
    - 修复：`WeChatArticleExtractor._normalize_code_blocks()` 改用 `span.has_attr("leaf")`（不过度匹配）；
      判定 `new_style = any(span.find("br") is not None for span in leaf_spans)`（有 br 行标记 → 新版：按 br 切行、
      行内 token 拼接；无 br → 旧版：每个 leaf 一整行、按行 join）。注意不能用 `parent.name == "code"` 判定，
      旧格式 leaf 也直接挂在 code 下（曾有 3 个测试失败）。后续统一做 `\\xa0`→空格、行尾 rstrip、连续空行压缩。
    - 测试：新增 `test_wechat_new_style_token_spans_no_duplication`（彩色包裹 token + br 切行，断言无重复、行拼接正确），
      全量 107 个测试通过。旧格式 page2.html 与新格式真实页面（_wx_apb_sample.html 11 个 pre）均验证无重复行。
    - debug.md 修复：文章 13 的 11 个坏代码块用修复后的提取器从原始 HTML 重转（字符级校验一致后替换）；
      因脚本索引过期曾误伤 debug.md，最终采用「保留 1-12 篇前缀 + 重建第 13 篇」方案并重跑 _ensure_toc 重建目录。
      注意：微信源码页面自身在 function/new、virtual/function/void 之间没有空格（如 functionnew），
      这是页面渲染结果，与提取逻辑无关，不是 bug。
"""

new = src.rstrip() + "\n" + entry + "\n"
io.open(path, "w", encoding="utf-8", newline="").write(new)
print("memory doc updated, new size:", len(new))
