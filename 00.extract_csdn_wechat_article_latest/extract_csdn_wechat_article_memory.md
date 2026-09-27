# extract_csdn_wechat_article_0815_fix 代码记忆

> 用途：快速恢复本项目上下文，避免每次重新通读代码。
> 项目目录：`D:\sandbox\extract_csdn_wechat_article_0815_fix`
> 最近更新：2026-08-22

## 项目是什么

Windows 桌面应用（tkinter GUI），输入 CSDN / 微信公众号 / 知乎 / 博客园的文章链接，抓取正文并把图片下载到本地，
输出 Markdown 文件。支持续写（追加）和覆盖两种模式，可打包成单个 exe（PyInstaller）。

- 入口：`main.py` → `app_gui.py` 的 `ArticleMarkdownApp`
- 核心逻辑：`article_extractor.py` 的 `BaseArticleExtractor`（公共基类）
- 四个平台子类：`wechat_extractor.py` / `csdn_extractor.py` / `zhihu_extractor.py` / `cnblogs_extractor.py`
- 测试：`test_extractor.py`（微信）、`test_csdn_extractor.py`、`test_zhihu_extractor.py`、`test_cnblogs_extractor.py`（全部离线，用 FakeSession/FakeResponse）
- 依赖：beautifulsoup4、markdownify、requests、lxml（见 `requirements.txt`）

## 关键约定（易踩坑点）

1. **图片目录命名**：Markdown 文件 `X.md` 对应同目录下的 `X_assets`（`markdown_path.stem + "_assets"`），图片文件名 `image-0001.png` 这种 4 位序号格式。移动 md 时要连同 assets 一起移动。
2. **续写时图片序号续接**：`_existing_max_image_index()` 同时扫描 assets 目录文件名和已存在 markdown 里的图片引用，取最大序号 +1 作为新文章起始序号；下载时 `_download_image()` 若文件已存在则自动递增序号，绝不覆盖已有图片。
3. **Markdown 头格式**：
   ```
   # 标题
   > 来源：<url>
   > 作者：xxx        （可选，微信/CSDN/知乎子类 `_metadata_lines` 决定）
   > 发布时间：xxx    （可选，仅 CSDN/知乎输出，微信故意不输出发布时间）
   > update YYYY/MM/DD HH : MM
   ```
   提取时间用 `datetime.now()`，格式 `%Y/%m/%d %H : %M`（注意 `HH : MM` 中间有空格）。
   **引用块后必须有空行再接正文**：`_build_markdown` 返回 `"\n".join(lines) + "\n" + body_markdown`（lines 末尾有一个空串，
   join 后补一个 `\n` 形成空行），否则 CommonMark/Typora 的 lazy continuation 会把紧贴的正文第一段并进引用块渲染
   （debug.md「分层验证后仿思路」复现过：`> update` 后无空行，正文首段被吞进引用块）。
4. **续写分隔符**：已有内容 + `\n\n---\n\n` + 新文章。`write_markdown_file(markdown, target, mode)`，mode 只有 `append`/`replace`。append 时保留原文件换行风格（检测 `\r\n`）。
   **关键**：append 前会用 `_normalize_append_tail()` 去掉已有内容末尾的空行/孤立 `---`，并在分隔符 `---` 前保证有一个空行（`base + 两个换行 + separator`），否则前一篇的最后一段会紧贴 `---` 被 Markdown 渲染成 Setext 二级标题（debug.md 复现过的 bug）。
   空文件/纯空白文件续写时不加 `---` 前缀，直接写入新文章，避免文件以 `---` 开头被 Typora 等编辑器误识别为 YAML front matter（会把后续内容吞进隐藏块）。
5. **标题自动编号**：`write_markdown_file` 写入前会对整个文件做层级编号（`_number_headings`）：
   每篇 `# 标题` 是文章序号（第 1 篇=1、第 2 篇=2...），文章内 `##`→`1.1`、`###`→`1.1.1` 依次类推；
   已有工具编号和原文自带序号（`1、`/`一、`/`Ⅰ、`/`①`/`（一）`/`第一章` 等）会在重编前剥离
   （`_strip_heading_ordinal`，防止序号重叠影响阅读，如 `2.1 一、POR` → `2.1 POR`），代码围栏内不处理；
   标题只剩序号时保留原文，避免生成空标题；`一/两/十` 开头但属于正常词语的标题不会被误删。
   **正文里的 `#` 不算新文章**：`_is_article_start` 判断——只有文件里第一个 `#`、或后面紧跟 `> 来源：` 元数据的 `#` 才是新文章；
   文章正文自带的 `#`（微信长文常把章节写成 `<h1>`）会降级成 `##` 并入当前文章，避免一次提取被拆成多篇
   （debug.md 曾出现一篇被拆成 #4~#16 的 bug）。注意不能靠 `---` 判断文章边界，因为正文里也有 `---` 分隔线。
6. **原子写入**：`_atomic_write()` 先写临时文件再 `os.replace()`，失败清理临时文件。
7. **代码块规范化**：微信文章 `<pre><code>` 里常混有行号列（`user-select:none`）、装饰 span、`leaf` 空 span、`section` 结构。`WeChatArticleExtractor._normalize_code_blocks()` 会把这些剥掉，只保留文本行，去掉多余空行。CSDN/知乎用基类的 `_normalize_code_blocks`（只处理 `<pre><code>` 里连续空行压缩）。
8. **空标题处理**：`_drop_empty_headings()` 删除无可见文本的 h1-h6，避免 markdownify 输出裸 `#`。
9. **图片懒加载属性**：基类 `_image_source()` 依次取 `data-src` / `data-original` / `data-url` / `src`；知乎重写为 `data-actualsrc` / `data-original` / `data-src` / `src`。
10. **正文为空时报错**：找不到正文节点或转换后为空 md 时抛 `ValueError`（GUI 弹窗显示）。
11. **URL 域名与来源不匹配时** GUI 弹确认框（`SOURCE_HOSTS`：微信=mp.weixin.qq.com，CSDN=blog.csdn.net，知乎=zhihu.com，博客园=cnblogs.com）；粘贴 URL 时 `_detect_source()` 按域名自动切换来源下拉框。
12. **长截图（勾选「保存长截图」）**：提取成功后把**当前文章**正文渲染成整页 PNG，保存到该 md 同名的 `<md名>_assets` 图片目录下，文件名用文章标题（`<标题>.png`，经 `make_safe_filename` 清洗），实现见 `screenshot.py`。
    默认原理：Chrome/Edge `--screenshot` 只截视口，所以用两遍无头模式——第 1 遍 `--dump-dom` 读 JS 写入 `<title>H:高度</title>` 探测真实页面高度，第 2 遍按该高度设 `--window-size` 再截图；
    正文里的图片是相对 `base_dir` 的相对路径，所以临时 HTML 直接写在 `base_dir` 下（mkstemp），截图完即删除，不残留。
    **空白截图坑**：微信正文常带 `visibility:hidden`/`opacity:0` 的初始隐藏样式（依赖页面 JS 才显示），独立渲染没有那些 JS，
    `PAGE_CSS` 里加了 `html, body, body * { visibility: visible !important; opacity: 1 !important; }` 强制显示（debug.md 曾整页空白）。
    默认不依赖 Pillow 等第三方库，只需要本机有 Chrome/Edge（`find_browser()` 找固定路径 + PATH）；可选 `capture_article_screenshot_with_fscapture`
    会自动打开可视浏览器并触发 FSCapture，且只要选择 FSCapture 就会自动按“保存长截图”处理；若需走剪贴板兜底则会尝试用 Pillow 的 `ImageGrab`。
    失败抛 `ScreenshotError`，GUI 只记日志不影响 Markdown 提取。
    `ArticleExtraction` 新增 `body_html` 字段（清理后、图片已本地化的正文 HTML），worker 里 `result.body_html` 传给截图函数。
    **头部信息（2026-08-16 新增）**：`_build_article_html` / `capture_article_screenshot` 增加 `author`（公众号名/作者）与 `publish_time`（发布时间）参数，
    截图顶部按微信排版渲染「公众号名 → 标题 → 发布时间」三段头部（`.article-head` / `.article-account` / `.article-meta` 样式在 `PAGE_CSS` 里），
    GUI worker 从 `result.metadata.author` / `result.metadata.publish_time` 传入；无这些元数据时不渲染头部。
    **已截图标记（2026-08-16 新增）**：勾选「保存长截图」时，`save_screenshot=True` 从 GUI `_worker` 传给 `extract_article_html(..., save_screenshot)`，
    再传给 `_build_markdown`，在 md 头部 `> update ...` 行后加一行加粗 `**已截图**`（`_number_headings` 不处理普通段落，不受编号影响）。

13. **覆盖模式自动备份（2026-08-16 新增）**：`write_markdown_file(markdown, target, mode, progress=None)` 在 `mode="replace"`
    且目标文件已存在时，覆盖写入前先调 `_backup_before_replace()`，把原 md 和对应 `<stem>_assets` 图片目录整体复制到
    `<stem>_assets\backup\<YYYYmmdd_HHMMSS>`（同秒重复自动加 `_1` 后缀；复制 assets 时用
    `ignore_patterns("backup")` 排除 backup 自身，避免递归复制）；备份路径经 `_notify(progress, ...)` 上报，
    GUI `_worker` 传 `progress=self._progress_hook`，日志会显示「覆盖前已备份原文件到：...」。append 模式不触发备份。
    **注意**：backup 目录在 assets 内，`_existing_max_image_index` 只扫 assets 顶层 `image-*.ext`，不受 backup 影响；
    但 `_download_image` 也不会扫 backup 里的图片，所以备份不会污染新文章的图片序号。

14. **微信中文序号伪标题（2026-08-16 新增）**：微信正文常把「一、」「二、」这类中文序号的章节名写成普通段落（非 h2 标签），
    markdownify 转出的纯文本行既不是标题也没有强调标记。`WeChatArticleExtractor._convert_body` 用
    `CHINESE_ORDINAL_HEADING_RE`（`^[一二三四五六七八九十]{1,3}、[^。！？；：，]{1,40}$`）把「中文序号 + 短句 +
    无句末标点」的独立段落升级为 `## ` 标题，再由 `_number_headings` 统一编号（剥序后如 `## 3.2 寄存器属性测试`）。
    带句号/问号/冒号/逗号或过长的行不转换；列表项（`- 一、…`）不转换（行首不是中文序号）。
    debug.md「寄存器专项测试」一文曾因原文段落化出现 5 个「应为标题却是段落」的小节（二~六），已修。

15. **微信列表项里的标题标记（2026-08-16 新增）**：微信正文把「加粗小标题」写成 `<li><h3>xxx</h3></li>`，
    markdownify 输出 `- ### xxx`。`_convert_body` 用 `LIST_ITEM_HEADING_RE`
    （`^(\s*[-*+]\s+)#{1,6}[ \t]+(.*)$` → `\1\2`）去掉 `- ` 后面的 `#` 标记，列表项文字按普通段落处理，
    不参与标题编号（代码围栏内不处理）。

16. **微信标题列表项内容合并（2026-08-16 新增）**：基类 `extract_article_html` 在 `_drop_empty_headings` 后调用
    `_merge_list_heading_content(content_node)` 钩子（基类空实现）。微信覆写：把「`<ul>/<ol>` 内只有一个 `<li>` 且 li 内容是
    单个 h1-h6」的列表（`_is_single_heading_list` 判断）后面紧邻的 `<p>`/`<ol>`/非标题 `<ul>`/`<ol>` 兄弟节点移入该 `<li>`，
    遇到下一个标题列表项即停止；markdownify 输出 `- 标题` + 缩进 2 空格的内容（同一列表层次，含嵌套有序列表）。
    真实微信 HTML 中标题可能被 `<section>/<div>` 包裹（`<li><section><h3>…`）、内容也在 `<section>` 里，
    `_single_heading_element` 递归穿透包装层找唯一标题，兄弟收集同样接受 `<section>/<div>`（遇到独立标题块停止）。
    CSDN/知乎不覆写，行为不变。
17. **微信 2 空格缩进列表项兜底（2026-08-16 新增）**：markdownify 偶尔把「- 标题」输出成 2 空格缩进的列表项
    （`  - 标题`），而其后的内容也只缩进 2 空格（不足嵌套列表项内容列 4 空格），CommonMark/Typora 会把内容
    渲染成列表项外的独立段落。`_convert_body` 末尾调用 `_normalize_indented_list_items()`：检测
    「`^  [-*+]\s+(.+)` 列表项 + 其后首个非空行以 2 空格开头且不是列表项」→ 把该项降为顶格 `- 内容`，
    内容缩进正好匹配 `- ` 的内容列；跳过代码围栏。该函数是文本层兜底，与第 16 条的结构层合并互补。
18. **PDF 输出（2026-08-16 新增）**：勾选「输出 PDF（需 Chrome/Edge）」后，提取完成时把当前文章用本机 Chrome/Edge 无头
    模式 `--print-to-pdf` 输出为 PDF，保存到 markdown 同目录的 `PDF` 文件夹，文件名与 md 同名
    （`markdown_name.pdf`）。实现见 `pdf_export.py`：`export_article_pdf()` 复用
    `screenshot._build_article_html`（新增 `css` 参数）与 `_run_browser`（新增 `label` 参数），用 `PRINT_CSS`
    （`PAGE_CSS` + A4/分页规则叠加）渲染文章 HTML 后打印；临时 HTML 写在 markdown 目录下以解析相对图片路径，
    用完即删。无浏览器或失败时不影响 markdown 提取（GUI 日志提示，不中断）。

## 文件结构与职责

- `main.py`：tkinter 入口，创建 `ArticleMarkdownApp`。
- `app_gui.py`：
  - 界面：来源下拉（微信/CSDN/知乎）、Cookie（可选）、文章链接（粘贴/清空）、Markdown 路径（浏览文件/选目录/打开）、写入方式（续写/覆盖）、开始提取、日志区、进度条、状态栏。
  - 写入方式下拉是 `tk.OptionMenu`（2026-08-16 由 ttk.Combobox 更换，因为 Combobox 下拉不支持单项着色）：
    「覆盖（替换）」菜单项用 `entryconfig(foreground="red", font=bold)` 红字加粗，选中后旁边显示红色加粗警示
    「⚠ 覆盖会替换原文件并覆盖之前的所有备份，请谨慎选择！」（`_on_mode_change` 切换，按钮文字同步变红）。
  - 后台线程 `_worker` + `queue.Queue` + `root.after` 轮询（`_poll_queue`），消息类型：`progress` / `done` / `log` / `error`（`log` 用于 worker 里不能直接碰 tkinter 的提示）。
  - `_worker` 参数新增 `save_screenshot`；把它传给 `extract_article_html(..., save_screenshot=...)`（控制 md 头部「已截图」标记），
    截图时把 `result.metadata.author/publish_time` 传给 `capture_article_screenshot`（控制截图头部公众号名/发布时间）；完成后 `("done", saved, result, screenshot_path, screenshot_error)`。
  - `_open_markdown()` 用 `os.startfile` 打开 md。
- `article_extractor.py`（核心，约 641 行）：
  - 工具函数：`validate_url`、`make_safe_filename`（Windows 保留名 CON/PRN/AUX/NUL/COM1.. 加下划线前缀）、`guess_extension`（优先 `wx_fmt` 查询参数 → 路径后缀 → Content-Type，默认 .jpg）、`write_markdown_file`（mode=append/replace，replace 前自动备份）、`_backup_before_replace`（覆盖前把原 md+assets 复制到 assets\backup\<时间戳>）、`_normalize_append_tail`（append 前清理尾部、防止 Setext 标题）、`_atomic_write`。
  - `BaseArticleExtractor.extract_article_html(url, markdown_path, progress, save_screenshot=False)` 主流程：
    1. `validate_url`；记录 `extraction_time`
    2. `_fetch_page`（requests，编码兜底 apparent_encoding）
    3. `_parse_html`（优先 lxml，失败回退 html.parser）
    4. `_extract_metadata`（子类实现）→ 得到标题/作者/发布时间/url
    5. `_resolve_markdown_path`（None→cwd/标题.md；目录→目录/标题.md；否则按给定路径）
    6. `assets_dir = 父目录/<stem>_assets`；`image_start = 已有最大序号+1`
    7. `_find_content`（子类实现）→ 正文节点
    8. `_remove_noise` → `_normalize_code_blocks` → `_drop_empty_headings`
    9. `_localize_images`：逐 img 下载、替换 src 为相对路径（`os.path.relpath`，`/` 分隔）
    10. `_convert_body`：markdownify（heading_style=ATX，bullets=-），清理行尾空格和 3+ 空行
    11. `_build_markdown`：头 + 正文
  - `ArticleExtraction` dataclass：metadata / markdown / image_count / markdown_path / body_html（新增，供长截图使用）。
- `wechat_extractor.py`：
  - 正文选择器：`#js_content` / `#js_article` / `.rich_media_content` / `#js_content_area`。
  - 标题：`h1#activity-name` / `h1.rich_media_title` / og:title meta / title。
  - 作者：meta author / og:article:author / `#js_name`（span 或 a）。
  - 发布时间：`em#publish_time` / `span#publish_time` / article:published_time / weibo:article:create_at。
  - 丢弃类：js_media_tip / js_media_tail / js_media_qr / js_media_warning / rich_media_tool / rich_media_meta_list。
  - `_metadata_lines` 只输出作者，**不输出发布时间**（需求要求把发布时间改成提取时间）。
  - 注意：`WeChatArticleExtractor._remove_noise` 是重写的（基类 + DROP_CLASSES），`_normalize_code_blocks` 也是重写的。
  - `_convert_body` 也是重写的：先调基类转换，再剥掉列表项行首装饰 bullet（`- • 文本` → `- 文本`，支持 `•◦▪●○◆◇·・‣⁃` 及 `\xa0`），且跳过代码围栏内的内容。
- `csdn_extractor.py`：
  - 正文选择器：`#content_views` / `#article_content` / `.markdown_views`。
  - 标题：`h1.title-article` / `h1.article-title` / og:title / title（去掉尾部 `- CSDN博客` 等）。
  - 作者：`a.follow-nickName` / `a.nick-name` / meta author。
  - 时间：article:published_time meta / `span.time`。
  - 丢弃类：hide-article-box / article-copyright / more-toolbox / recommend-box / toolbox-list / follow-text / person-info / subscribe-comment / article-info-box。
  - `_metadata_lines` 输出作者 + 发布时间。
- `zhihu_extractor.py`：
  - 正文选择器：`.Post-RichTextContainer` / `.Post-RichText` / `.RichText` / `.RichContent-inner` / `<article>`。
  - `_fetch_page` 重写：401/403 直接抛中文提示（先登录再贴 Cookie）。
  - 标题：`h1.Post-Title` / h1 / og:title / title（去掉尾部 `- 知乎`）。
  - 作者：meta author / `a.UserLink-link` / `span.UserLink-link`。
  - 时间：article:published_time / itemprop=datePublished / `span.ContentItem-time`。
  - 丢弃类：Post-SideActions / Post-Actions / Post-Footer / Post-Header / Post-Author / Post-Topics / ContentItem-actions / RichContent-actions。
  - `_metadata_lines` 输出作者 + 发布时间。
- `cnblogs_extractor.py`（博客园）：
  - 正文选择器：`#cnblogs_post_body` / `.blogpost-body` / `.postBody`。
  - 标题：`h1.postTitle` / `a#cb_post_title_url` / og:title / title（去掉尾部 ` - 作者 - 博客园` / ` - 博客园`）。
  - 作者：`div.postDesc` 内第一个指向 `cnblogs.com/` 的链接文本，meta author 兜底。
  - 时间：`span#post-date` / article:published_time / publishdate meta。
  - 丢弃类：cnblogs_code_toolbar / cnblogs_code_copy（复制按钮装饰；不能删 cnblogs_code，它包裹着 <pre> 代码）。
  - `_metadata_lines` 输出作者 + 发布时间。
- `screenshot.py`（长截图模块，无第三方依赖）：
  - `find_browser()`：Chrome/Edge 固定路径 + PATH 查找。
  - `capture_article_screenshot(title, body_html, output_png, base_dir, width=800, author="", publish_time="")`：两遍 headless 截图，返回 output_png 或抛 `ScreenshotError`。
  - `_run_browser` 用文件重定向 stdout/stderr（避免 Chrome 子进程继承管道句柄导致 communicate 卡死），`CREATE_NO_WINDOW`，超时 90s。
  - `_build_article_html(title, body_html, author="", publish_time="")`：按原页面排版渲染顶部——公众号名/作者行（标题前内容）+ 标题 + 原创/作者/发布时间；
    内联 CSS（中文字体/代码块换行/图片 max-width/`.article-head` 头部样式）+ 注入高度探测 JS（DOMContentLoaded/load/200ms 定时器三重触发）。
- `test_screenshot.py`：HTML 构建、高度解析、无浏览器报错、以及本机有 Chrome/Edge 时自动跑的端到端截图测试。

## 打包

- `build.bat`：装依赖 → `PyInstaller --noconfirm --clean --windowed --onefile --name Article2Markdown --hidden-import markdownify --hidden-import bs4 --hidden-import lxml main.py`，产物 `dist\Article2Markdown.exe`。
- 目录下还有旧的 `WechatArticle2Markdown.spec` / `Article2Markdown.spec`（gitignore 忽略 *.spec、build/、dist/）。
- 修复 bug 后一般需要重新打包 exe（用户会要求）。

## 测试与 fixture

- `test/test.md`：真实微信文章样例，含两篇文章（第一篇「基于 ICG + 三级同步电路的无毛刺时钟切换方案」，第二篇「83：后向寄存器切片（backword register slice）」），第二篇曾出现 markdown 格式混乱的 bug，修复依据。
- `test/test.md.bak`：旧版本备份（25KB，当前 test.md 约 46KB）。
- `test/page2.html`：微信文章原始 HTML 快照（约 3.2MB，第二篇 83 后向寄存器切片 的页面）。
- `test/test_assets/`：与 test.md 对应的图片目录（image-0000 ~ image-0029，含 png/jpg/gif）。
- `test/assets_old/`：旧 assets 目录。
- 测试用例覆盖的关键行为：
  - 图片下载为 `image-0001.png` 且 md 中引用 `article_assets/image-0001.png`
  - append 分隔符 `旧内容\n\n---\n\n# 标题`（`---` 前必须空行，避免 Setext 标题）
  - 续写图片序号从 md 引用/目录文件续接（如 `image-0003` → 新图 `image-0004`）
  - 已存在图片不被覆盖（`_download_image` 自动 +1）
  - 空标题不产生裸 `#`
  - 微信代码块无行号、无 `****`，保留 `if ( src_hs & ~rdy_dst)` 等原始代码
  - 微信 md 中 `assertNotIn("发布时间")`（微信不输出发布时间）
  - 微信列表项多余 `•` 被剥离（`- • 文本` → `- 文本`），代码围栏内不剥离

## 已记录的历史 bug（需求文档 extract_wechat_article_requirment.md 与 README）

1. 第二篇微信文章提取后 markdown 格式混乱（正文选择器/代码块问题）→ 已修。
2. 需求从"发布"时间改为"提取"时间，引用块加 `update year/month/day`，并加"打开 markdown"按钮 → 已实现。
3. 图片目录必须按 markdown 文件名生成 `X_assets`（曾没按文件名生成）→ 已修。
4. 续写时图片索引在原基础上累加，不从 0 开始，不覆盖已有图片 → 已修。
5. 续写第二篇后，第一篇的最后一段被渲染成标题（`debug.md` 场景：尾段直接紧贴追加的 `---`，形成 Setext 二级标题）→ 已修：`write_markdown_file` 追加时先 `_normalize_append_tail()` 清理尾部，再以 `base + \n\n + ---\n\n + 新文章` 拼接，保证分隔符前有空行；新增 `test_append_never_creates_setext_heading` 等 3 个测试。
6. 微信列表项行首多一个装饰 `•`（markdownify 输出 `- • 文本`，debug.md 两篇文章共 71 处）→ 已修：`WeChatArticleExtractor._convert_body` 覆写中剥离行首 bullet（含 `\xa0`），代码围栏内不处理；新增 `test_wechat_strips_redundant_list_bullet`。
7. 续写模式写入空/纯空白文件时，文件开头多了一个 `---`，会被 Typora 等编辑器当作 YAML front matter，把
   “## 二、STM32 RC外部复位电路”之前的所有章节吞进隐藏块（用户描述为“前面章节内容都在引用块里”）→ 已修：
   `write_markdown_file` 空文件续写时不再加 `---` 前缀；新增 `test_append_to_empty_file_does_not_prepend_separator`。
8. 微信 `<ol>` 列表项文本自带手写编号（如 `1. 内容`），markdownify 又加一遍序号，输出 `1. 1. 内容` → 已修：
   `_convert_body` 中先剥重复编号（`^\d+\.\s+\d+\.`）再剥 bullet，代码围栏内不处理；新增
   `test_wechat_strips_duplicated_ordered_list_number`。
9. 微信列表项行首装饰 bullet（`- • 文本`）与重复编号（`1. 1. 文本`）已通过 `_convert_body` 覆写统一剥离（先编号后 bullet，跳过代码围栏）。
10. 新功能：标题层级编号（文章=1/2/3...，二级=1.1/2.1...，三级=1.1.1...）→ `write_markdown_file` 写文件前用 `_number_headings` 重编整个文件；
    新增 `test_heading_numbering_first_and_second_article`、`test_heading_numbering_replaces_plain_number_prefix`、
    `test_heading_numbering_skips_fenced_code` 3 个测试；既有 append/分隔符相关测试的断言改为 `# 1 微信文章标题` 形式。
11. 编号与原文序号重叠：文章标题里自带 `1`、`一`、`Ⅰ`、`①`、`（一）`、`第一章` 等序号时，软件编号后再拼原文会变成
    `2.1 一、POR` 这种重复序号 → 已修：`HEADING_NUMBER_STRIP_RE` 扩展为同时剥离阿拉伯/中文/罗马/圈号/括号/第X章前缀
    （`_strip_heading_ordinal` 循环剥离，剥离后残留的引导分隔符如 `：` 一并清掉）；空标题回退原文；
    `一/两/十` 开头但属于正常词语（如 `一文读懂`、`两个时钟域`）不误删；新增
    `test_heading_numbering_strips_chinese_ordinal` 等 6 个测试。
12. 新功能：保存文章长截图（防公众号链接失效后无法看原文）→ 勾选「保存长截图」后，用本机 Chrome/Edge 无头模式把当前文章正文渲染成整页 PNG，保存到 `<md名>_assets\文章标题.png`；
    `--screenshot` 只截视口，所以两遍：`--dump-dom` 探测高度 → 按高度 `--window-size` 截图；临时 HTML 写在文章目录（图片相对路径才能解析），截图后删除；
    无浏览器/失败抛 `ScreenshotError`，不影响 Markdown 提取；新增 `test_screenshot.py`（7 个测试，含浏览器可用时的端到端用例）。
13. 长截图空白 bug：文章正文带 `visibility:hidden`/`opacity:0`（微信初始隐藏、靠 JS 显示）时，两遍截图的页面只有标题可见、正文区域全白
    → 已修：`PAGE_CSS` 强制 `visibility: visible !important; opacity: 1 !important`；用真实图片 + 隐藏样式复现验证（修复前后 22KB → 629KB）。
14. 一次提取被拆成多篇文章 bug：微信长文正文里自带 `<h1>`（如「CPU 读一个地址」那篇的章节全是 h1），`_number_headings` 把每个 `#` 都当新文章，
    debug.md 一次提取被拆成 #4~#16 → 已修：`_is_article_start` 只在「文件首个 `#`」或「`#` 后紧跟 `> 来源：`」时开新文章，
    正文 `#` 降级为 `##` 并入当前文章（不能用 `---` 判断，正文里也有 `---`）；新增 `test_heading_numbering_demotes_body_h1`、
    `test_heading_numbering_body_separator_does_not_start_new_article` 2 个测试。
15. 新功能：勾选「保存长截图」时在 md 文章头部 `> update` 行后加加粗「已截图」标记 → `save_screenshot` 参数从 GUI 传入
    `extract_article_html` → `_build_markdown`，未勾选不出现；新增 `test_screenshot_flag_adds_marked_line`。
16. 新功能：长截图顶部一并截下公众号名/作者与发布时间（微信排版：公众号名 → 标题 → 发布时间）→ `capture_article_screenshot` /
    `_build_article_html` 增加 `author`、`publish_time` 参数，GUI worker 传 `result.metadata.author/publish_time`；
    新增 `test_includes_account_and_publish_time` / `test_omits_header_when_no_metadata` / `test_escapes_metadata` 3 个测试。

17. 「已截图」标记位置修正：由 update 行后独立一行改为放进 update 所在的引用块（`> **已截图**`，紧跟 `> update` 行之后）。
18. 长截图头部还原：不再手动添加公众号名/标题/发布时间（第 16 条功能回退）→ `capture_article_screenshot` / `_build_article_html`
    移除 `author`、`publish_time` 参数，正文 HTML 从顶部到底部原封不动渲染；`BuildArticleHtmlHeaderTest` 删除，
    新增 `test_renders_body_without_manual_header`；GUI worker 不再传 author/publish_time。

19. 长截图顶部还原（第 18 条修正）：用户澄清「文章标题前面的内容也要截图」——原页面标题上方有公众号名/作者行、标题下方有
    「原创 公众号名 发布时间」信息行；`capture_article_screenshot` / `_build_article_html` 恢复 `author`、`publish_time` 参数，
    GUI worker 重新传 `result.metadata.author/publish_time`；`.article-head` 渲染 公众号名行(圆形头像占位) + 标题 + meta 行；
    `BuildArticleHtmlHeaderTest` 恢复并适配。

20. 标题重复 bug：微信文章「CPU 读一个地址…」正文开头自带与文章标题完全相同的 `<h1>`，自动编号后标题出现两次
    （`# 4 …` + `## 4.1 …`）→ 已修：`_number_headings` 跟踪当前文章标题，正文第一个标题（忽略全部空白比较）与
    标题相同时跳过不编号（新增辅助函数 `_heading_text_key` 和测试 `test_heading_numbering_skips_body_heading_identical_to_title`）；
    已有 debug.md 里的重复标题会在下次追加提取时被自动重编号清除。

21. 新功能：覆盖模式的危险警示与保护 → 写入方式下拉框的「覆盖（替换）」项改为红色加粗（ttk.Combobox 无法给单项着色，
    换成 `tk.OptionMenu` 并对菜单项 `entryconfig` foreground/font），选中后旁边显示红色加粗警示「⚠ 覆盖会替换原文件并覆盖之前的所有备份，请谨慎选择！」；
    覆盖写入前把原 md + `<stem>_assets` 备份到 `<stem>_assets\backup\<时间戳>`（`_backup_before_replace`，同秒去重、排除 backup 自身），
    GUI 日志显示备份路径；新增 `test_replace_creates_backup_of_markdown_and_assets` / `test_replace_without_existing_file_skips_backup` /
    `test_append_does_not_create_backup` 3 个测试。

22. 正文首段被吞进文章头部引用块 bug：微信文章「分层验证后仿思路」提取到 debug.md 后，正文第一段「不像RTL功能仿真，后仿，…」
    被渲染进 `> update ...` 引用块 → 已修：`_build_markdown` 生成 md 时引用块与正文之间只拼了一个 `\n`（`"> update ...\n" + body_markdown`），
    CommonMark/Typora 的 lazy continuation 会把紧贴的正文第一段并入引用块；改为 `"\n".join(lines) + "\n" + body_markdown` 保证空行分隔；
    新增 `test_body_not_merged_into_quote_block`；debug.md 中该处（update 后无空行）已直接补空行修正。

23. 中文序号章节名被当作段落 bug：debug.md「【验证专项】寄存器专项测试」中「二、寄存器属性测试」「三、地址粘连测试」
    「四、数据粘连测试」「五、地址边界测试」「六、全地址遍历测试」都是纯段落（应为 `##` 标题，与「一、→ 3.1」同级）
    → 已修：微信正文把这类中文序号章节名写成普通段落（非 h2），`_convert_body` 新增 `CHINESE_ORDINAL_HEADING_RE`
    （`^[一二三四五六七八九十]{1,3}、[^。！？；：，]{1,40}$`）把「中文序号 + 短句 + 无句末标点」的独立行升级为 `## ` 标题；
    新增 `test_chinese_ordinal_paragraph_becomes_heading`；debug.md 中 5 处改为 `## 3.2~3.6`，并统一 3.2 下
    「- 最优测试方案」为 `- ### 最优测试方案`（与 3.1 一致）。

24. 列表项里误带标题等级 bug：微信正文把「加粗小标题」写成 `<li><h3>xxx</h3></li>`，markdownify 输出 `- ### xxx`，
    用户要求「·」后面不要标题等级，列表项文字按段落 → 已修：`_convert_body` 新增 `LIST_ITEM_HEADING_RE`
    （`^(\s*[-*+]\s+)#{1,6}[ \t]+(.*)$`），把 `- ### 标题` 降为 `- 标题`；新增
    `test_list_item_heading_demoted_to_plain_text`；debug.md 12 处已改为 `- 标题`。
    注：debug.md 在用户重建后为 4 篇新文章，「寄存器专项测试」为 #4，小节 4.1~4.6 由中文序号标题修复自动生成。

25. 列表项内容层次 bug：微信「加粗小标题」写成 `<ul><li><h3>xxx</h3></li></ul>`，标题下面的内容在 `<ul>` 外的独立
    `<p>/<ol>` 节点，markdownify 输出 `- 标题` 后接顶格段落（内容与 `-` 不在同一层次）→ 已修：基类 `extract_article_html`
    新增钩子 `_merge_list_heading_content`（默认空），微信覆写把「单标题 li 列表」后面紧邻的 `<p>`/`<ol>`/非标题列表兄弟
    移入 `<li>`（遇到下一个标题列表项停止），markdownify 输出时内容自然缩进 2 空格；新增
    `test_list_heading_content_merged_into_list_item`；debug.md #4 文章 21 行内容已缩进修正。

26. 列表项内容合并漏掉 section 包裹结构 bug：debug.md 4.2「最优测试方案」内容仍顶格（同文 4.1/4.3 等已缩进）
    → 已修：真实微信 HTML 中部分标题是 `<li><section><h3>…`（标题被 section 包裹）、内容在 `<section>` 里，
    旧合并逻辑只认 li 内直接 h1-h6 → 直接跳过；新增 `_single_heading_element`（递归穿透 section/div 找唯一标题），
    `_merge_list_heading_content` 复用该判断，兄弟收集接受 `<section>/<div>`（遇独立标题块停止）；新增
    `test_list_heading_content_merged_when_wrapped_in_section`；debug.md 4.2 的 5 行内容已手动缩进修正。
27. 「最优测试方案」内容不在同一层级 bug（第 5 篇文章 5.2 节）：debug.md 出现 `  - 最优测试方案`（2 空格缩进列表项），
    其后内容 `  摒弃…` 也是 2 空格，CommonMark 渲染成列表项外的独立段落 → 已修：`wechat_extractor.py` 新增
    `INDENTED_LIST_ITEM_RE` + `_normalize_indented_list_items()` 文本层兜底（见约定 17），把 2 空格缩进列表项
    降为顶格 `- `；新增 `test_indented_list_heading_demoted_to_top_level`；debug.md 全部「最优测试方案」
    均改为顶格 `- `；已重新打包 `dist\Article2Markdown.exe`（59 个测试全过）。
28. 新功能：输出 PDF → 勾选「输出 PDF」后生成 `<markdown 目录>/PDF/<markdown_name>.pdf`，用 Chrome/Edge 无头
    `--print-to-pdf`，内容与长截图同源（文章 HTML + 公众号名/标题/发布时间头部），打印 CSS 分页；
    新增 `pdf_export.py` 与 `test_pdf_export.py`（6 个测试）；`screenshot._build_article_html` 增加 `css` 参数、
    `_run_browser` 增加 `label` 参数（错误消息更通用）；`app_gui.py` 增加「输出 PDF」勾选框与完成提示；
    65 个测试全过，已重新打包 `dist\Article2Markdown.exe`。
29. 整份 Markdown 输出 PDF + 完成弹窗修复：
    - 需求澄清：勾选「输出 PDF」要导出的是**整份 markdown**（含之前追加的所有文章），不是仅当前文章
      → `pdf_export.py` 新增 `export_markdown_pdf(markdown_path, output_pdf, base_dir)`：读取整个 `.md`
      文件 → 内置轻量 `markdown_to_html()` 转换器渲染全文（无第三方 markdown 库依赖；支持 ATX 标题、
      引用块、有序/无序/嵌套列表+缩进续行、围栏与缩进代码块、管道表格、图片、链接、行内 code/bold/
      italic/strike、`---` 分隔线、段落与两空格硬换行）→ `_build_markdown_pdf_html`（复用 PRINT_CSS，
      不叠加单篇文章的公众号头部）→ Chrome/Edge `--print-to-pdf`；图片相对路径相对 markdown 目录解析。
      原 `export_article_pdf` 保留兼容（测试仍覆盖）。
    - GUI：`app_gui.py` worker 改用 `export_markdown_pdf(saved, pdf_target, base_dir=saved.parent)`；
      `_finish_ok` 之前签名缺 `pdf_path`/`pdf_error` 两个参数，worker 的 done 消息传了 6 个参数 →
      `TypeError` 导致完成后不弹窗 → 已补上签名（这是「提取完成后没有弹窗」的根因）。
    - 测试：`test_pdf_export.py` 扩展到 20 个（转换器 10 个 + 整份导出/无浏览器/缺文件等）；全项目 79 个
      测试全过；真实 Chrome 端到端验证 `debug.md` → `PDF\debug.pdf` 30 页、图片正常、临时 HTML 清理；
      已重新打包 `dist\Article2Markdown.exe`。

30. 新功能：Markdown 自动目录 + PDF 书签 + 引用块绿色：
    - 自动目录：`write_markdown_file`（append/replace 都会）先 `_strip_toc_block` 去掉旧目录块，`_number_headings`
      重编号后由 `_ensure_toc` 在文件顶部生成新目录（`<!-- toc-start -->` ~ `<!-- toc-end -->` 标记包裹，
      `# 目录` + 1~3 级标题链接 `[标题](#slug)`，后接 `---` 分隔线）；`heading_slug()` 生成 GitHub 风格锚点
      （小写、去标点、空白转 `-`），目录链接与 PDF 标题 id 共用保证跳转一致；代码围栏里的 `#` 不进目录。
    - PDF 书签：`export_markdown_pdf` 打印后用内置 pypdf（vendor 到项目根 `pypdf/`，随 exe 打包）
      `_add_pdf_bookmarks` 注入层级书签（outline）：逐页提取文本、取标题最后出现页定位页号，h1/h2/h3 构建父子书签；
      注入失败静默兜底，PDF 仍保留可点击目录页（Chrome 会把 `#锚点` 链接写成 PDF 内部链接，pypdf 重写后保留）。
      注意 Chrome `--print-to-pdf` 本身不生成书签（outline 为空），必须靠 pypdf 注入。
    - 引用块绿色：`PRINT_CSS` 增加 `blockquote { border-left:#2f9e44; background:#f0f8ef; color:#2e6b34; }`（仅 PDF）。
    - `markdown_to_html` 改动：标题输出 `<hN id="slug">`、跳过 `<!-- ... -->` 注释行、`_starts_new_block` 识别注释行。
    - 测试：新增 TOC 更新/围栏跳过、注释跳过+标题 id、绿色 CSS、书签注入兜底、真实 Chrome 书签 E2E（无 Chrome 时跳过）；
      86 个测试全过；已重新打包 `dist\Article2Markdown.exe`。

31. PDF 修复两处渲染问题（2026-08-16）：
    - 多行段落/引用块被压成一行：`markdown_to_html` 的 `_render_paragraph` 之前把段落内多行用空格拼接
      （`<br>` 仅当行尾有两个空格时插入），导致 markdown 里同一引用块内
      `> 来源：https://...` 与 `> update 2026/08/16 14 : 45` 两行（无空行）在 PDF 里变成一行。
      → 改为段落内多行一律用 `<br>` 拼接（`"<br>".join(...)`），PDF 与 markdown 源文件行结构一致。
    - 目录前出现圆点：生成的 TOC 是 `- [标题](#slug)` 列表，PDF 里被浏览器渲染成带项目符号（·）的 `<ul>`。
      → `markdown_to_html` 用 `TOC_START_MARKER`/`TOC_END_MARKER` 跟踪目录区域，区域内列表用
      `<ul class="toc">` 渲染（`_render_list_region` 增加 `toc` 参数），`PRINT_CSS` 增加
      `ul.toc, ul.toc ul { list-style: none; }` 隐藏圆点（仅目录，正文列表保留符号）。
    - 验证：`test_pdf_export.py` 新增 3 个测试（多行段落保留换行、多行引用块保留换行、目录无圆点）；
      89 个测试全过；真实 debug.md → PDF 36 页，pypdf 提取确认目录页无任何圆点字符、第 30 页
      「来源/update 14 : 45」为两行；已重新打包 `dist\Article2Markdown.exe`。

32. PDF 修复：NBSP 误判代码块 + 目录层级丢失（2026-08-16）：
    - 代码块误判：debug.md 里 `- 覆盖范围` 后的正文行以 `  \xa0 \xa0`（ASCII 空格 + NBSP）开头，
      `_INDENTED_CODE_RE` 原用 `\s{4,}` 匹配缩进，Python 的 `\s` 包含 NBSP/全角空格，而 CommonMark
      只把 ASCII 空格当代码缩进 → 同一行 Typora 显示段落、PDF 显示代码块。
      → 改为 `^( {4,}|\t)(.*)$`（只认 ASCII 空格和制表符），NBSP 行落入列表续行
      `<li>覆盖范围<br>所有寄存器…</li>`；真实 debug.md 7 处全部生效（PDF 第 28 页验证）。
    - 目录层级丢失：`ul.toc { padding-left: 0 }` 对嵌套 `ul.toc` 同样生效，把子级缩进清零，
      目录只剩圆点没了、但层级也没了。→ 增加 `ul.toc ul { padding-left: 1.5em; }`，
      Chrome 实测 1 级=1px、2 级=22px、3 级=43px，层级恢复。
    - 验证：新增 3 个测试（NBSP 行非代码块、ASCII 4 空格仍为代码、目录嵌套保留缩进）；92 个测试全过；
      因原 exe 正在运行（两个实例，审批服务 503 未能结束），打包为 `dist\Article2Markdown_v2.exe`，
      待用户关闭旧 exe 后替换回 `Article2Markdown.exe` 原名。

33. 一级标题编号格式调整（2026-08-16）：`# 1 标题` → `# 1. 标题`（数字后加 `.` 和一个空格）。
    `_number_headings` 中原来 `if level > 1:` 才拼点号后缀，改为对 level>=1 统一拼
    `str(article) + "." + ".".join(...)`：一级 `# 1. 标题`，二级 `## 1.1`，三级 `### 1.1.1` 不变。
    `_strip_heading_ordinal` 已能剥离新的 `1. ` 前缀（重排不会重复编号）；目录条目同步为
    `- [1. 标题](#1-标题)`（heading_slug 会去掉点号，锚点不变）；PDF 书签用规范化文本匹配，不受点号影响。
    92 个测试全过（更新了 test_extractor/test_csdn_extractor/test_zhihu_extractor 的编号断言）；
    已重新打包 `dist\Article2Markdown.exe`（保留原名）。

## 常见调试命令

```powershell
cd D:\sandbox\extract_csdn_wechat_article_0815_fix
python -m pytest test_extractor.py test_csdn_extractor.py test_zhihu_extractor.py test_cnblogs_extractor.py -q
# 或
python test_extractor.py
```

```powershell
# 用真实页面快照验证微信提取：
# 把 test/page2.html 喂给 BeautifulSoup，调用 WeChatArticleExtractor._find_content / _convert_body
```

## 给未来修复 bug 的提示

- 先跑三个测试文件确认现状；改动核心逻辑时注意保持 `image-xxxx` 序号、`update` 时间格式、append 分隔符等既有约定不变。
- 涉及微信文章格式的 bug，优先检查 `_normalize_code_blocks` 与 `_remove_noise` 对 `section`/`leaf`/行号列的处理。
- 涉及图片路径的 bug，检查 `_resolve_markdown_path`、`_existing_max_image_index`、`_localize_images` 三者的配合。
- GUI 线程安全：worker 里不能直接碰 tkinter，必须通过 `self.queue.put`。

34. 非空文件续写时目录与标题序号重整（2026-08-29）：需求「手动改过标题层级后，下一次追加时要把标题序号和目录一起刷新」。
    - 之前：append 到非空文件只会把新文章贴到末尾，旧标题编号不会重新计算，目录虽然重建但可能和手动编辑后的标题层级不一致。
    - 现在：`write_markdown_file` 在 append / replace 写回前都会先追加或替换，再调用 `_refresh_numbering_and_toc(...)`；
      这一步会先去掉旧 `toc-start/toc-end` 块，再用 `_number_headings` 按当前文档结构重新编号整个文件，最后用 `_build_toc_block`
      重建目录。这样用户手动把某个二级标题改成正文后，下次追加新文章时，前面剩余的标题号会自动补齐，目录也会同步刷新。
      空文件/新文件分支也走同一套刷新流程，保证首写和后续追加行为一致。
    - 测试：`test_toc_added_on_first_write_without_hyphen_and_preserves_on_append` 改为断言续写后
      目录含新旧两篇文章；`test_append_preserves_nonempty_file_prefix_byte_for_byte` 改为
      `test_append_preserves_body_and_adds_current_toc`；新增 `test_append_replaces_old_toc_format_with_current_format`。

35. 重排标题/目录按钮（2026-08-29）：新增 GUI 按钮「重排标题/目录」，用于只对当前 Markdown 文件执行标题重编号和目录重建。
    - 点击前会检查 Markdown 路径是否存在、是否为文件，并在确认后调用 `refresh_markdown_structure_file(...)`。
    - 该动作会在原文件旁生成 `.bak-YYYYMMDD_HHMMSS.md` 备份，然后用当前标题层级重写整个文件；若文件已经是最新结构，则提示“没有发现需要调整的标题或目录”。
    - 测试：新增 `test_refresh_markdown_structure_file_rebuilds_toc_and_backs_up`，确认备份内容与重排结果。

36. 链接备份 backup.md（2026-08-22）：需求「每次添加的文章链接，都保存到当前 Markdown 同级目录的 backup.md，
     保存文章链接和对应写入的 Markdown 文件一一对应」。
    - `article_extractor.py` 新增常量 `ARTICLE_BACKUP_FILE = Path("backup.md")`
      与函数 `log_article_backup(url, markdown_path)`：成功后以 UTF-8 追加一行到
      `markdown_path` 同级目录的 `backup.md`
      `<序号> | <日期时间 YYYY/MM/DD HH:MM:SS> | <文章链接> | <markdown 绝对路径>`，
      序号通过 `_next_backup_number` 统计已有非空行数 + 1 持续累加（旧格式行不改写，仅续号）；
      目录不存在自动创建；url 为空或写失败返回 None，不阻断提取。
    - `write_markdown_file(..., url="")` 新增 `url` 参数，三条成功路径（新文件/空文件/非空续写）最后统一调用
      `log_article_backup` 并 `_notify` 日志；GUI `app_gui.py` worker 传 `url=result.metadata.url`。
      若显式 `url` 为空，则回退读取当前 `markdown` 里的首个 `> 来源：` 行再写入备份；
      若两者都没有则跳过。注意非空续写分支的提前 `return` 会跳过日志，已移除。
    - 测试：`test_backup_logs_url_and_markdown_path`（新文件+非空续写两次都记录，断言 2 行）、
      `test_backup_uses_markdown_source_when_url_empty`（不传 url 但 markdown 里有 `> 来源：` 时仍记录）、
      `test_backup_is_written_next_to_markdown_file`（备份总是写到当前 markdown 同级目录）、
      `test_backup_skipped_when_url_and_source_empty`（url 和来源行都为空时不写备份文件）；
      测试通过覆盖模块级
      `ARTICLE_BACKUP_FILE` 指向临时文件名，避免污染真实路径。

36. 新增博客园（cnblogs）提取（2026-08-22）：需求「新增一个网站文章的提取，该网站是博客园，按照之前的要求加入软件里」。
    - 新增 `cnblogs_extractor.py`（`CnblogsArticleExtractor`，继承 BaseArticleExtractor，模式同 CSDN/知乎）：
      正文 `#cnblogs_post_body`；标题 `h1.postTitle`；作者取 `div.postDesc` 内指向 `cnblogs.com/` 的链接；
      时间 `span#post-date`；输出 `> 作者：` + `> 发布时间：`；丢弃复制按钮装饰类（不删 cnblogs_code 包裹）。
    - `app_gui.py`：来源下拉加「博客园」，`SOURCE_HOSTS` 加 `cnblogs.com`，`_detect_source` 粘贴自动识别，
      `_make_extractor` 返回 `CnblogsArticleExtractor`。
    - 真实页面验证：`https://www.cnblogs.com/xianyuIC/p/19356143` → 标题 Verdi学习笔记 / 作者 咸鱼IC /
      发布时间 2025-12-16 11:10，正文与代码块转换正常（沙箱无网络，图片数 0，本机可正常下载）。
    - 测试：新增 `test_cnblogs_extractor.py` 5 个测试（元数据/图片/追加/标题回退/代码块+去噪），106 个测试全过。

37. 修复微信新版代码块 token 重复 bug（2026-08-22）：用户报告 debug.md 最新一篇（微信 APB Master VIP 文章）代码块每个 token 重复两遍、
    一行被拆成多个 token 行（如 `task\ntask\n body();`）。
    - 根因一：`BeautifulSoup.find_all("span", attrs={"leaf": ""})` 会过度匹配——把没有 `leaf=""` 属性的彩色包裹 span
      （`<span style="color:..."><span leaf="">class</span></span>` 的外层）也匹配进来，同一文本被抓两次 → 重复。
    - 根因二：新版微信编辑器把一行代码拆成多个 leaf token span（leaf 或被彩色 span 包裹的 leaf），行尾用
      `<span leaf=""><br/></span>` 标记；旧版每行是一个完整 leaf span。旧逻辑按 span 逐行 get_text → 行被拆散。
    - 修复：`WeChatArticleExtractor._normalize_code_blocks()` 改用 `span.has_attr("leaf")`（不过度匹配）；
      判定 `new_style = any(span.find("br") is not None for span in leaf_spans)`（有 br 行标记 → 新版：按 br 切行、
      行内 token 拼接；无 br → 旧版：每个 leaf 一整行、按行 join）。注意不能用 `parent.name == "code"` 判定，
      旧格式 leaf 也直接挂在 code 下（曾有 3 个测试失败）。后续统一做 `\xa0`→空格、行尾 rstrip、连续空行压缩。
    - 测试：新增 `test_wechat_new_style_token_spans_no_duplication`（彩色包裹 token + br 切行，断言无重复、行拼接正确），
      全量 107 个测试通过。旧格式 page2.html 与新格式真实页面（_wx_apb_sample.html 11 个 pre）均验证无重复行。
    - debug.md 修复：文章 13 的 11 个坏代码块用修复后的提取器从原始 HTML 重转（字符级校验一致后替换）；
      因脚本索引过期曾误伤 debug.md，最终采用「保留 1-12 篇前缀 + 重建第 13 篇」方案并重跑 _ensure_toc 重建目录。
      注意：微信源码页面自身在 function/new、virtual/function/void 之间没有空格（如 functionnew），
      这是页面渲染结果，与提取逻辑无关，不是 bug。

38. 同一链接文章再次添加时原地替换（2026-08-22）：需求「如果新加的文章之前在该 markdown 里添加过，以最新添加的这一次为准直接替换掉原来的文章」。
    - `article_extractor.py` 新增 `_article_url_from_line(line)`（从 `> 来源：` 行取 URL）与
      `_replace_article_by_url(raw, markdown, url, newline)`：遍历现有文件（跳过目录区和代码围栏），
      找第一个 `# N.` 标题后跟 `> 来源：{url}` 的文章，解析其编号 N；从标题行到下一个独立 `---`
      （或 EOF）之间替换为新 markdown 并按 `start_article=N` 重编号，其余文章逐字保留；
      返回新文本，找不到匹配返回 None（调用方回退为普通追加）。
    - `write_markdown_file` 非空续写分支先尝试 `_replace_article_by_url`，命中则覆盖更新并提示
      「检测到该文章链接已存在，已用最新内容覆盖更新原文章」；未命中才走原追加逻辑。
      backup.md 仍然每次写入都记一条（含更新时间戳与序号）。
    - 边界处理：首篇前面无 `---`、末篇后面无 `---` 均可替换；代码围栏内的 `---` 不算文章分隔符
      （扫描时维护 in_fence/in_toc 状态）；url 为空或未匹配时不替换。
    - 测试：新增 `test_replace_existing_article_by_url_in_place`（三篇中替换中间篇，编号/位置不变、
      围栏内 --- 不误判）、`test_append_when_url_not_in_file`（未匹配时普通追加）、
      `test_replace_first_and_last_article`（首末篇边界）。全量 110 个测试通过。

39. 重复文章去重功能（2026-08-22）：需求「写个去重逻辑把重复文章清理成一篇」（debug.md 中同一链接的寄存器专项文章被追加了 9 次）。
    - `article_extractor.py` 新增 `_collect_articles(lines)`（按 ``# N.`` 标题 + ``> 来源：`` 切分文章，跳过目录区/代码围栏，
      边界以下一个文章标题为准，正文里的 --- 分隔线不会把文章切断，尾部 --- 分隔符通过 `_trim_article_tail` 去掉）、
      `_article_update_time`（解析 ``> update YYYY/MM/DD HH : MM`` 时间戳）、
      `deduplicate_markdown(markdown)`（同一 URL 只保留 ``> update`` 最新的一篇，时间戳相同保留最后追加的，
      其余删除，全部文章重编号 1..N，重建目录；无重复返回 None）与
      `deduplicate_markdown_file(target, backup=True)`（写盘前自动生成 `文件.bak-YYYYMMDD_HHMMSS` 备份，
      返回 `DedupSummary(removed, remaining, backup_path)`）。
    - 顺带修复 `_replace_article_by_url` 的边界 bug：原用「下一个独立 ---」当文章结尾，会把正文里的分隔线（微信常见）误判为文章边界，
      导致替换时截断文章；改为「下一个 ``# N.`` 文章标题」作边界，替换区间为 `文章内容 + ["", "---", ""] + 下一篇`。
    - GUI `app_gui.py`：Markdown 路径行新增「去重」按钮 → `_deduplicate()`（确认弹窗 → 调
      `deduplicate_markdown_file` → 提示删除/保留数量与备份路径）。
    - 测试：新增 `test_replace_article_with_internal_separator_keeps_whole_article`、
      `test_deduplicate_markdown_keeps_latest_per_url`、`test_deduplicate_markdown_returns_none_without_duplicates`、
      `test_deduplicate_markdown_file_writes_backup`（直接写文件构造重复，因为写入口的同 URL 替换逻辑会拦截重复追加）。
      全量 114 个测试通过。
    - debug.md 已实际去重：14 篇 → 6 篇（删除 8 篇重复的寄存器专项，保留 update 22:58 最新一篇），
      备份 `D:\sandbox\debug.bak-20260822_203057.md`；27 个代码块全部无重复行。

40. 微信 section 式代码块（无 <pre> 包裹）裸露正文 bug（2026-08-22）：用户报告 debug.md 最新一篇
    （微信「乱序 — 响应乱序处理与完整 Driver」）代码全部裸露在正文里、没有代码围栏，
    例如 `class full_pipeline_driver extends uvm_driver #(my_transaction);`。
    - 根因：该文代码块不是 `<pre><code>`，而是微信编辑器的另一种结构：`<section>` 带
      `white-space: nowrap` + `font-family: Consolas/monospace` + 深色背景 `rgb(40,44,52)`，
      内部是彩色包裹 + `<span leaf=""><br/></span>` 切行的高亮 token span。`_normalize_code_blocks`
      只遍历 `find_all("pre")`，完全没处理这种 section 代码块 → markdownify 把 token span 当普通行 → 代码成正文。
    - 修复：`wechat_extractor.py` 重构出共享的 `_extract_code_text(node)`（leaf 含 br → 按 br 切行拼接；
      无 br → 每 leaf 一行；`\xa0`→空格、行尾 rstrip、连续空行压缩；无有效文本返回 None）。
      `_normalize_code_blocks` 先处理 `<pre><code>`，再遍历 `content_node.find_all("section")`，
      用 `_is_code_section`（style 含 `white-space: nowrap` 且 Consolas/monospace 且存在 leaf span）判定，
      跳过已在 `<pre>` 内的（`section.find_parent("pre")`），用
      `_TAG_FACTORY = BeautifulSoup("", "html.parser")`（`section.new_tag` 不存在）创建 `<pre><code>`
      并 `section.replace_with(new_pre)`；bs4 4.12.3 允许跨树插入。
    - 注意：旧格式测试里的 `<section style="display:flex">`（无 nowrap/mono 特征）不会被误判；
      `_remove_noise` 的 DROP_CLASSES 也不会删这些 section。
    - 测试：新增 `test_wechat_section_style_code_blocks_get_fenced`（彩色包裹 + br 切行，断言进 ```、
      无 `\_` 转义、行拼接正确，且无代码特征的 section 不被转换）。全量 115 个测试通过。
    - debug.md 修复：用修复后的提取器从保存的 `D:\sandbox\_wx_art7.html` 重新生成第 7 篇，
      图片按现有 debug_assets 顺序回填（image-0154..0157），保留原头部（标题/来源/作者/
      update 2026/08/22 20 : 41），`_replace_article_by_url` 原地替换 + `_ensure_toc` 重建目录；
      写入前自动备份 `debug.bak-20260822_205552.md`。修复后 4 个代码块全部进围栏，
      全文仅 1 处 `\`uvm_fatal\`` 内联反引号正文（非代码块）。注意 `_atomic_write` 需要 `Path` 对象
      （传 str 会 AttributeError: str has no attribute parent）。

41. 微信文本型 SVG 图示/时间轴保留（2026-08-29）：用户报告公众号文章中
    “上电 / 100ms / CRS 超时截止” 这类多行流程图式内容被遗漏。根因是通用清洗里把
    所有 `<svg>` 一刀切 `decompose()`，若正文把这类时间轴/图示做成 SVG 文本节点就会直接消失，
    另有一类是把文本型 SVG 直接放进 `<img src="...svg">` 或 `data:image/svg+xml`。
    - 修复：`BaseArticleExtractor._remove_noise()` 先遍历 `svg`，用 `_svg_text_content(svg)` 判断是否为
      “可见文本块”（至少 3 行可见文本，且含明显的箱线/时间轴字符如 `│├└─`）；命中则保留文本，
      未命中才删除该 SVG。`_localize_images()` 也会在遇到文本型 SVG 图片时把它展开成 `<pre><code>`，
      这样正文里的时间轴/流程图可保留，纯装饰 SVG 仍会过滤。
    - 测试：新增 `test_wechat_preserves_textual_svg_blocks` 和
      `test_wechat_unwraps_textual_svg_images`，分别覆盖 inline SVG 和 SVG 图片两种形态，
      断言正文中的 `100ms` / `CRS 超时截止` 保留，同时装饰性 SVG 图标会被过滤。

