"""Render an article HTML fragment into a full-page long screenshot.

The default backend uses a headless Chrome/Edge already installed on the
machine (no extra dependencies). Two passes are needed because Chrome's
``--screenshot`` only captures the viewport: pass 1 measures the real page
height via ``--dump-dom``, pass 2 captures with ``--window-size`` set to
that height.

An optional FastStone Capture backend can open a visible browser window,
trigger FastStone's scrolling-window capture hotkey, and then save either a
FastStone auto-saved file or an image copied to the clipboard.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import html
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)
BROWSER_NAMES = (
    "chrome",
    "msedge",
    "chromium",
    "google-chrome",
    "microsoft-edge",
)

DEFAULT_FSCAPTURE_EXE = Path(r"D:\install\_package\Google\_download\FSCapture97\FSCapture.exe")
FSCAPTURE_WINDOW_TOKEN_PREFIX = "A2MD"
FSCAPTURE_CAPTURE_TIMEOUT = 90.0
FSCAPTURE_FIND_WINDOW_TIMEOUT = 30.0
FSCAPTURE_READY_DELAY = 1.0
FSCAPTURE_CLICK_DELAY = 0.8
FSCAPTURE_POLL_INTERVAL = 0.5
FSCAPTURE_WAIT_BEFORE_CLIPBOARD = 1.5
FSCAPTURE_WINDOW_TITLE_PAD = " "
FSCAPTURE_SCROLL_HOTKEY = (0x11, 0x12, 0x2C)  # Ctrl + Alt + PrtSc
WM_CLOSE = 0x0010
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

SCREENSHOT_WIDTH = 800
VIRTUAL_TIME_BUDGET_MS = 3000
BROWSER_TIMEOUT = 90
HEIGHT_BUFFER = 40

PAGE_CSS = """
/* 微信等页面正文常带 visibility:hidden / opacity:0 的初始隐藏样式，依赖页面 JS 才显示。
   独立渲染时没有那些 JS，这里强制全部可见，避免长截图空白。 */
html, body, body * {
  visibility: visible !important;
  opacity: 1 !important;
}
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  margin: 0 auto;
  padding: 48px 28px 64px;
  max-width: 760px;
  color: #2c3e50;
  background: #ffffff;
  font-size: 16px;
  line-height: 1.9;
}
h1 { font-size: 24px; line-height: 1.45; margin: 0 0 24px; }
h2 { font-size: 21px; margin: 30px 0 12px; line-height: 1.45; }
h3 { font-size: 18px; margin: 24px 0 10px; }
h4, h5, h6 { font-size: 16px; margin: 18px 0 8px; }
p { margin: 12px 0; }
img { max-width: 100%; height: auto; }
pre {
  background: #f6f8fa;
  border-radius: 6px;
  padding: 14px;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
code {
  font-family: Consolas, "Courier New", monospace;
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.92em;
}
pre code { background: transparent; padding: 0; }
blockquote {
  border-left: 4px solid #d0d7de;
  margin: 12px 0;
  padding: 2px 16px;
  color: #57606a;
}
table { border-collapse: collapse; margin: 12px 0; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; }
a { color: #3370ff; text-decoration: none; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 24px 0; }

.article-head {
  border-bottom: 1px solid #eaeaea;
  padding-bottom: 18px;
  margin-bottom: 22px;
}
.account-row {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
}
.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #3c8dff;
  color: #ffffff;
  font-size: 17px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  flex: 0 0 auto;
}
.account-name {
  font-size: 15px;
  color: #576b95;
  font-weight: 500;
}
.article-title {
  font-size: 23px;
  line-height: 1.45;
  margin: 0 0 12px;
  font-weight: 600;
}
.article-meta {
  font-size: 13px;
  color: #888;
}
.article-meta span {
  margin-right: 8px;
}
.article-meta .badge {
  display: inline-block;
  border: 1px solid #576b95;
  color: #576b95;
  border-radius: 3px;
  font-size: 12px;
  padding: 0 4px;
}
"""



class ScreenshotError(RuntimeError):
    """Raised when a long screenshot cannot be produced."""


def find_browser() -> Optional[str]:
    """Locate a Chrome/Edge executable, or return None."""
    for candidate in BROWSER_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    for name in BROWSER_NAMES:
        path = shutil.which(name)
        if path:
            return path
    return None


def find_fscapture() -> Optional[str]:
    """Locate the FastStone Capture executable, or return None."""
    candidates = [
        os.environ.get("FSCAPTURE_EXE", ""),
        str(DEFAULT_FSCAPTURE_EXE),
        shutil.which("FSCapture.exe") or "",
        shutil.which("FSCapture") or "",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _build_article_html(
    title: str,
    body_html: str,
    author: str = "",
    publish_time: str = "",
    css: str = PAGE_CSS,
    title_suffix: str = "",
    include_height_probe: bool = True,
) -> str:
    """Render the article page with the original-style top (公众号名/标题/发布时间)."""
    safe_title = html.escape(title or "", quote=False)
    safe_suffix = html.escape(title_suffix or "", quote=False)
    safe_author = html.escape(author or "", quote=False)
    safe_time = html.escape(publish_time or "", quote=False)
    script = ""
    if include_height_probe:
        script = (
            "(function(){function report(){"
            "document.title='H:'+Math.ceil(document.documentElement.scrollHeight);}"
            "document.addEventListener('DOMContentLoaded',report);"
            "window.addEventListener('load',report);"
            "setTimeout(report,200);})();"
        )
    head_lines = []
    if safe_author:
        # 文章标题前面的内容：公众号名/作者行（原页面顶部）
        head_lines.append(
            '<div class="account-row">'
            f'<span class="avatar">{safe_author[:1]}</span>'
            f'<span class="account-name">{safe_author}</span>'
            "</div>"
        )
    head_lines.append(f'<h1 class="article-title">{safe_title}</h1>')
    meta_parts = []
    if safe_author:
        meta_parts.append('<span class="badge">原创</span><span>' + safe_author + "</span>")
    if safe_time:
        meta_parts.append(f"<span>{safe_time}</span>")
    if meta_parts:
        head_lines.append('<div class="article-meta">' + " ".join(meta_parts) + "</div>")
    head_html = "\n".join(head_lines)
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{safe_title}{safe_suffix}</title>\n"
        f"<script>{script}</script>\n"
        f"<style>{css}</style>\n"
        "</head>\n<body>\n"
        f'<div class="article-head">\n{head_html}\n</div>\n'
        f"{body_html}\n"
        "</body>\n</html>\n"
    )


def _parse_page_height(dom_text: str) -> int:
    match = re.search(r"<title>H:(\d+)</title>", dom_text)
    if not match:
        raise ScreenshotError("浏览器未能返回页面高度（可能页面加载异常）")
    height = int(match.group(1))
    if height <= 0:
        raise ScreenshotError("浏览器返回的页面高度无效")
    return height


def _run_browser(browser: str, args: List[str], label: str = "截图") -> str:
    """Run headless browser with file-redirected output (avoids pipe deadlock
    from Chrome child processes inheriting stdout/stderr handles)."""
    tmp = tempfile.mkdtemp(prefix=".article2md_browser_")
    stdout_path = os.path.join(tmp, "stdout.txt")
    stderr_path = os.path.join(tmp, "stderr.txt")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
            try:
                result = subprocess.run(
                    [browser] + args,
                    stdout=out,
                    stderr=err,
                    timeout=BROWSER_TIMEOUT,
                    creationflags=flags,
                )
            except FileNotFoundError as exc:
                raise ScreenshotError(f"未找到浏览器程序：{browser}") from exc
            except subprocess.TimeoutExpired as exc:
                raise ScreenshotError(f"生成{label}超时（浏览器无响应）") from exc
        if result.returncode != 0:
            try:
                with open(stderr_path, "r", encoding="utf-8", errors="ignore") as handle:
                    stderr_text = handle.read()
            except OSError:
                stderr_text = ""
            detail = stderr_text.strip()[-500:] or "未知错误"
            raise ScreenshotError(f"浏览器{label}失败（退出码 {result.returncode}）：{detail}")
        try:
            with open(stdout_path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except OSError as exc:
            raise ScreenshotError(f"读取浏览器输出失败：{exc}") from exc
    finally:
        _best_effort_rmtree(tmp)


def _best_effort_rmtree(path: str) -> None:
    for _ in range(3):
        try:
            shutil.rmtree(path, ignore_errors=True)
            return
        except OSError:
            time.sleep(0.3)


def _launch_visible_browser(browser: str, page_url: str) -> subprocess.Popen:
    """Open a visible browser window for manual or FastStone-driven capture."""
    args = [
        "--app=%s" % page_url,
        "--start-maximized",
        "--allow-file-access-from-files",
        "--no-first-run",
        "--disable-extensions",
        "--disable-background-networking",
        "--force-device-scale-factor=1",
    ]
    return subprocess.Popen([browser] + args)


def _window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _wait_for_window_with_token(token: str, timeout: float = FSCAPTURE_FIND_WINDOW_TIMEOUT) -> int:
    user32 = ctypes.windll.user32
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            try:
                if user32.IsWindowVisible(hwnd):
                    title = _window_text(hwnd)
                    if token in title:
                        found.append(hwnd)
            except Exception:
                pass
            return True

        try:
            user32.EnumWindows(enum_proc, 0)
        except Exception:
            pass
        if found:
            return int(found[-1])
        time.sleep(0.2)
    raise ScreenshotError(f"未找到浏览器窗口（标题标记：{token}）")


def _focus_window(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    if not hwnd:
        return
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
    except Exception:
        pass
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _send_scroll_capture_hotkey() -> None:
    user32 = ctypes.windll.user32
    for vk in FSCAPTURE_SCROLL_HOTKEY:
        try:
            user32.keybd_event(vk, 0, 0, 0)
        except Exception:
            pass
    for vk in reversed(FSCAPTURE_SCROLL_HOTKEY):
        try:
            user32.keybd_event(vk, 0, 2, 0)
        except Exception:
            pass


def _click_window_center(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ScreenshotError("无法获取浏览器窗口大小")
    point = wintypes.POINT()
    point.x = (rect.right - rect.left) // 2
    point.y = (rect.bottom - rect.top) // 2
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise ScreenshotError("无法计算浏览器窗口坐标")
    try:
        user32.SetCursorPos(point.x, point.y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    except Exception as exc:
        raise ScreenshotError(f"无法模拟鼠标点击：{exc}") from exc


def _save_clipboard_image(output_png: Path) -> bool:
    try:
        from PIL import ImageGrab
    except Exception:
        return False
    try:
        image = ImageGrab.grabclipboard()
    except Exception:
        return False
    if hasattr(image, "save"):
        image.save(output_png)
        return True
    return False


def _clear_clipboard() -> None:
    user32 = ctypes.windll.user32
    try:
        if user32.OpenClipboard(0):
            try:
                user32.EmptyClipboard()
            finally:
                user32.CloseClipboard()
    except Exception:
        pass


def _wait_for_fscapture_result(output_png: Path, timeout: float = FSCAPTURE_CAPTURE_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    clipboard_armed = False
    while time.time() < deadline:
        if output_png.is_file() and output_png.stat().st_size > 0:
            return True
        if clipboard_armed:
            if _save_clipboard_image(output_png):
                return True
        else:
            time.sleep(FSCAPTURE_WAIT_BEFORE_CLIPBOARD)
            clipboard_armed = True
            continue
        time.sleep(FSCAPTURE_POLL_INTERVAL)
    return False


def _close_window(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    if hwnd:
        try:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass


def capture_article_screenshot_with_fscapture(
    title: str,
    body_html: str,
    output_png: Path,
    base_dir: Optional[Path] = None,
    width: int = SCREENSHOT_WIDTH,
    author: str = "",
    publish_time: str = "",
    fscapture_exe: Optional[str] = None,
) -> Path:
    """Render the article through a visible browser and FastStone Capture.

    This backend opens a visible browser window, asks FastStone Capture to
    start a scrolling-window capture, and waits for either an auto-saved file
    or an image copied to the clipboard. It is Windows-only and expects
    FastStone Capture to be installed locally.
    """
    if os.name != "nt":
        raise ScreenshotError("FSCapture 截图模式仅支持 Windows")

    browser = find_browser()
    if not browser:
        raise ScreenshotError(
            "未找到 Chrome/Edge 浏览器，无法生成长截图。请安装 Chrome 或 Edge 后重试。"
        )

    fscapture = fscapture_exe or find_fscapture()
    if not fscapture:
        raise ScreenshotError(
            "未找到 FSCapture.exe。请确认 FastStone Capture 已安装，"
            "或把路径配置到 FSCAPTURE_EXE。"
        )

    output_png = Path(output_png).expanduser()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    if output_png.parent.is_dir() is False:
        raise ScreenshotError(f"长截图保存目录不可用：{output_png.parent}")

    base_dir = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    capture_token = f"{FSCAPTURE_WINDOW_TOKEN_PREFIX}-{uuid.uuid4().hex[:8]}"
    html_doc = _build_article_html(
        title,
        body_html,
        author=author,
        publish_time=publish_time,
        title_suffix=f" {capture_token}",
        include_height_probe=False,
    )

    fd = None
    html_path = None
    browser_hwnd = 0
    browser_proc = None
    fscapture_proc = None
    try:
        fd, raw_path = tempfile.mkstemp(
            prefix=".article2md_page_", suffix=f".{capture_token}.html", dir=str(base_dir)
        )
        html_path = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(html_doc)
        fd = None
        page_url = html_path.resolve().as_uri()

        browser_proc = _launch_visible_browser(browser, page_url)
        fscapture_proc = subprocess.Popen([fscapture])

        browser_hwnd = _wait_for_window_with_token(capture_token)
        _focus_window(browser_hwnd)
        time.sleep(FSCAPTURE_READY_DELAY)
        _clear_clipboard()
        _send_scroll_capture_hotkey()
        time.sleep(FSCAPTURE_CLICK_DELAY)
        _click_window_center(browser_hwnd)

        if _wait_for_fscapture_result(output_png):
            return output_png
        raise ScreenshotError(
            "FSCapture 未自动输出截图文件。请确认它已设置为“到文件(自动保存)” "
            "或“复制到剪贴板”，然后重试。"
        )
    finally:
        _close_window(browser_hwnd)
        for proc in (fscapture_proc, browser_proc):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if html_path is not None:
            try:
                html_path.unlink()
            except OSError:
                pass


def capture_article_screenshot(
    title: str,
    body_html: str,
    output_png: Path,
    base_dir: Optional[Path] = None,
    width: int = SCREENSHOT_WIDTH,
    author: str = "",
    publish_time: str = "",
) -> Path:
    """Render ``body_html`` (images relative to ``base_dir``) to a full-page PNG.

    Returns ``output_png`` on success; raises :class:`ScreenshotError` when no
    browser is available or the capture fails.
    """
    browser = find_browser()
    if not browser:
        raise ScreenshotError(
            "未找到 Chrome/Edge 浏览器，无法生成长截图。请安装 Chrome 或 Edge 后重试。"
        )

    output_png = Path(output_png).expanduser()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    if output_png.parent.is_dir() is False:
        raise ScreenshotError(f"长截图保存目录不可用：{output_png.parent}")

    base_dir = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    html_doc = _build_article_html(title, body_html, author=author, publish_time=publish_time)

    fd = None
    html_path = None
    profile_dir = tempfile.mkdtemp(prefix=".article2md_profile_")
    try:
        fd, raw_path = tempfile.mkstemp(
            prefix=".article2md_page_", suffix=".html", dir=str(base_dir)
        )
        html_path = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(html_doc)
        fd = None
        page_url = html_path.resolve().as_uri()
        target = str(output_png.resolve())

        common = [
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-background-networking",
            "--force-device-scale-factor=1",
            "--window-size=%d,%d" % (width, width),
            "--virtual-time-budget=%d" % VIRTUAL_TIME_BUDGET_MS,
            "--user-data-dir=%s" % profile_dir,
        ]

        dom_text = _run_browser(browser, common + ["--dump-dom", page_url])
        height = _parse_page_height(dom_text) + HEIGHT_BUFFER

        shot_args = [
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-sandbox",
            "--disable-extensions",
            "--force-device-scale-factor=1",
            "--window-size=%d,%d" % (width, height),
            "--virtual-time-budget=%d" % VIRTUAL_TIME_BUDGET_MS,
            "--user-data-dir=%s" % profile_dir,
            "--screenshot=%s" % target,
            page_url,
        ]
        _run_browser(browser, shot_args)

        if not output_png.is_file() or output_png.stat().st_size == 0:
            raise ScreenshotError("浏览器未生成截图文件")
        return output_png
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if html_path is not None:
            try:
                html_path.unlink()
            except OSError:
                pass
        _best_effort_rmtree(profile_dir)
