"""Screenshot capture client with local Playwright validation hooks."""
from __future__ import annotations

import os
from dataclasses import dataclass


BAD_PAGE_KEYWORDS = [
    "login",
    "sign in",
    "captcha",
    "verify you are human",
    "access denied",
    "cloudflare",
    "enable javascript",
]

# 强信号：只要出现在页面中就基本可以确定为拦截页
STRONG_BAD_SIGNALS = [
    "captcha",
    "verify you are human",
    "access denied",
    "enable javascript",
]

# 弱信号：需要额外证据（如标题匹配或多信号共现）才能判定为拦截页
# 单独的 "login" / "sign in" / "cloudflare" 可能是页脚导航链接，不应误杀
WEAK_BAD_SIGNALS = [
    "login",
    "sign in",
    "cloudflare",
]

# 弱信号需要与以下至少一个表单专用词共现才判定为拦截页
# 注意：不用 "sign in to" / "log in to"（太泛，导航链接"Log in to X"不是表单）
AUTH_FORM_INDICATORS = [
    "password",
    "username",
    "forgot password",
    "forgot your password",
    "remember me",
    "keep me signed in",
]

DEFAULT_HIDE_SELECTORS = [
    '[id*=cookie]', '[class*=cookie]', '[class*=consent]',
    '[id*=consent]', '[class*=gdpr]', '[id*=gdpr]',
    '[class*=popup]', '[class*=overlay][style*=fixed]',
    '[class*=banner][class*=bottom]', '[class*=banner][class*=fixed]',
    '[aria-label*=cookie]', '[aria-label*=consent]',
]


@dataclass
class ScreenshotResult:
    ok: bool
    path: str = ""
    fail_reason: str = ""


def is_bad_page_text(text: str, page_title: str = "") -> bool:
    """检测页面是否为登录/验证码/拦截页。

    强信号（captcha、verify you are human 等）：命中即判定为拦截页。
    弱信号（login、sign in、cloudflare）：需要出现在页面标题中，或与表单词（password、username 等）共现，
    否则只是页脚导航链接，不误杀。
    """
    lower = (text or "").lower()
    title_lower = (page_title or "").lower()

    # 强信号：命中即拦截
    if any(keyword in lower for keyword in STRONG_BAD_SIGNALS):
        return True

    # 弱信号：需要额外证据
    for keyword in WEAK_BAD_SIGNALS:
        if keyword not in lower:
            continue
        # 页面标题中包含 → 强证据
        if keyword in title_lower:
            return True
        # 与表单指示词共现 → 强证据
        if any(indicator in lower for indicator in AUTH_FORM_INDICATORS):
            return True
        # 弱信号在极短文本中占比高 → 可能是拦截页
        # （真正的 Cloudflare 拦截页通常 < 300 字；正常页面即使简洁也 > 300 字）
        text_len = len(lower)
        if text_len < 300:
            return True

    return False


def capture(url: str, dest: str, provider: str = "local",
            viewport: tuple[int, int] = (1440, 1000),
            full_page: bool = False,
            hide_selectors: list[str] | None = None,
            full_viewport: bool = False) -> ScreenshotResult:
    if provider != "local":
        return ScreenshotResult(False, fail_reason=f"未配置截图服务 provider={provider}")
    return capture_with_playwright(url, dest, viewport=viewport, full_page=full_page,
                                   hide_selectors=hide_selectors, full_viewport=full_viewport)


def _hide_cookie_banners(page, hide_selectors: list[str] | None):
    """注入 CSS + JS 清理 cookie/consent/popup 元素"""
    if not hide_selectors:
        return
    # CSS 隐藏
    css_rules = ', '.join(f'{s}{{display:none!important}}' for s in hide_selectors)
    page.add_style_tag(content=css_rules)
    # JS 删除常见弹窗元素
    js_selectors = ', '.join(hide_selectors)
    page.evaluate(f"""
        (function() {{
            try {{
                document.querySelectorAll('{js_selectors}').forEach(function(el) {{ el.remove(); }});
                // 额外清理 fixed 定位的覆盖层
                document.querySelectorAll('[style*="position: fixed"], [style*="position:fixed"]').forEach(function(el) {{
                    var z = parseInt(getComputedStyle(el).zIndex) || 0;
                    if (z > 1000) el.remove();
                }});
            }} catch(e) {{}}
        }})()
    """)


def capture_with_playwright(url: str, dest: str,
                            viewport: tuple[int, int] = (1440, 1000),
                            full_page: bool = False,
                            hide_selectors: list[str] | None = None,
                            full_viewport: bool = False) -> ScreenshotResult:
    from playwright.sync_api import sync_playwright
    from asset_pipeline import _find_chromium

    exe = _find_chromium()
    if not exe:
        return ScreenshotResult(False, fail_reason="找不到 Chromium 可执行文件")

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=exe,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                # SPA / 重JS 站点 networkidle 可能永不触发 → 退而求其次
                try:
                    page.goto(url, wait_until="load", timeout=15000)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)
            _hide_cookie_banners(page, hide_selectors)
            page.wait_for_timeout(500)
            text = page.locator("body").inner_text(timeout=5000) if page.locator("body").count() else ""
            page_title = page.title() or ""
            if is_bad_page_text(text, page_title):
                return ScreenshotResult(False, fail_reason="页面疑似登录/验证码/Cloudflare")
            if page.evaluate("document.body ? document.body.scrollHeight : 0") < 300:
                return ScreenshotResult(False, fail_reason="页面主体内容过少")

            # 完整 viewport 模式：直接截整页（用于官网首页截图）
            if full_viewport:
                page.screenshot(path=dest, full_page=False)
                return _result_from_file(dest)

            # 元素模式：尝试选中 main/hero/section 区域
            for selector in ["main", "[data-testid]", ".product", ".hero", "section"]:
                loc = page.locator(selector).first
                try:
                    if loc.count() and loc.bounding_box():
                        loc.screenshot(path=dest)
                        return _result_from_file(dest)
                except Exception:
                    continue

            page.screenshot(path=dest, full_page=full_page)
            return _result_from_file(dest)
    except Exception as exc:
        return ScreenshotResult(False, fail_reason=str(exc))
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass


def _result_from_file(dest: str) -> ScreenshotResult:
    if os.path.exists(dest) and os.path.getsize(dest) > 512:
        return ScreenshotResult(True, path=dest)
    return ScreenshotResult(False, fail_reason="截图文件为空或过小")
