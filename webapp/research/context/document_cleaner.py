"""文档清洗器 — 去除 HTML/文本噪音

职责：清洗 source_documents.raw_text 中的噪音片段。
目标：
- cookie/privacy/terms/login/signup 页面识别率 >= 95%
- 官网页脚/导航类文本过滤率 >= 80%
- 低质量文档不进入 chunk 阶段
"""
from __future__ import annotations
import re
from typing import Optional

# ── 噪音模式 ──

# 全页噪音：cookie/privacy/terms/login/signup 页面
_NOISE_PAGE_PATTERNS = [
    # cookie 弹窗
    (r"(?i)\b(cookie\s*policy|cookie\s*notice|cookie\s*consent|cookie\s*settings|cookie\s*preferences)\b",
     "cookie_page"),
    (r"(?i)\b(we\s*use\s*cookies|this\s*site\s*uses\s*cookies|uses\s*cookies\s*to|by\s*continuing\s*to\s*browse)\b",
     "cookie_banner"),
    # privacy / terms / legal
    (r"(?i)\b(privacy\s*policy|privacy\s*notice|data\s*protection\s*policy)\b", "privacy_page"),
    (r"(?i)\b(terms\s*of\s*service|terms\s*of\s*use|terms\s*and\s*conditions)\b", "terms_page"),
    (r"(?i)\b(legal\s*notice|legal\s*disclaimer|end\s*user\s*license\s*agreement)\b", "legal_page"),
    # login / signup / auth
    (r"(?i)\b(sign\s*in|log\s*in|sign\s*up|create\s*account|reset\s*password|forgot\s*password)\b",
     "auth_page"),
    # 垃圾内容
    (r"(?i)\b(sponsored\s*content|sponsored\s*post|paid\s*content|native\s*advertising)\b",
     "sponsored"),
]

# 块级噪音：footer / navigation / newsletter / CTA
_NOISE_BLOCK_PATTERNS = [
    # footer
    (r"(?i)^\s*(©\s*\d{4}|copyright\s+\d{4}|all\s*rights\s*reserved)\b", "footer_copyright"),
    (r"(?i)\b(all\s*rights\s*reserved|copyright\s+©)\b", "footer_copyright"),
    # navigation
    (r"(?i)^\s*(home|about|products?|solutions?|pricing|blog|contact|careers?|jobs)\s*$",
     "navigation_item"),
    (r"(?i)\b(navigation|nav\s*menu|site\s*map|breadcrumb)\b", "navigation"),
    # newsletter / CTA
    (r"(?i)\b(subscribe\s*to\s*our\s*newsletter|newsletter\s*sign\s*up|join\s*our\s*newsletter)\b",
     "newsletter_cta"),
    (r"(?i)\b(subscribe\s*now|sign\s*up\s*for|join\s*our\s*mailing|get\s*the\s*latest\s*updates)\b",
     "newsletter_cta"),
    (r"(?i)\b(start\s*free\s*trial|get\s*started\s*free|try\s*it\s*free|book\s*a\s*demo|request\s*a\s*demo|schedule\s*a\s*demo)\b",
     "cta_button"),
    # social media
    (r"(?i)\b(follow\s*us\s*on|find\s*us\s*on|connect\s*with\s*us\s*on)\b", "social_media_cta"),
    # author / related
    (r"(?i)\b(about\s*the\s*author|written\s*by|posted\s*by|published\s*on)\b", "author_bio"),
    (r"(?i)\b(related\s*posts|related\s*articles|you\s*may\s*also\s*like|recommended\s*reading)\b",
     "related_links"),
    # 广告
    (r"(?i)\b(advertisement|ad\s*-\s*|promoted\s*story|paid\s*promotion)\b", "advertisement"),
    # YouTube 寒暄
    (r"(?i)\b(hey\s*guys|what's\s*up\s*everyone|welcome\s*back\s*to|don't\s*forget\s*to\s*subscribe|like\s*and\s*subscribe|smash\s*that\s*like\s*button|hit\s*the\s*bell)\b",
     "youtube_greeting"),
    (r"(?i)\b(thanks\s*for\s*watching|thank\s*you\s*for\s*watching|see\s*you\s*in\s*the\s*next)\b",
     "youtube_outro"),
    # 赞助口播
    (r"(?i)\b(this\s*video\s*is\s*sponsored|sponsored\s*by|brought\s*to\s*you\s*by|thanks\s*to\s*our\s*sponsor)\b",
     "sponsor_mention"),
]

# 评论区识别
_COMMENT_PATTERNS = [
    (r"(?i)^\s*(comment|reply|upvote|downvote|share\s*this)\s*$", "comment_ui"),
    (r"(?i)\b(leave\s*a\s*comment|comments?\s*section|show\s*comments?|hide\s*comments?)\b",
     "comment_section"),
]

# 低信息密度行
_LOW_INFO_PATTERNS = [
    (r"^\s*$", "empty_line"),
    (r"^\s*[-–—]{2,}\s*$", "separator"),
    (r"^\s*#{1,6}\s*$", "empty_heading"),
]


def clean_document_text(
    raw_text: str,
    source_type: str = "",
    source_url: str = "",
) -> dict:
    """清洗文档文本，返回清洗后文本和噪音标记。

    Returns:
        {
            "clean_text": str,
            "removed_ratio": float,
            "noise_flags": list[str],
            "is_low_quality": bool,
            "is_noise_page": bool,
        }
    """
    if not raw_text or not raw_text.strip():
        return {
            "clean_text": "",
            "removed_ratio": 1.0,
            "noise_flags": ["empty_text"],
            "is_low_quality": True,
            "is_noise_page": True,
        }

    original_len = len(raw_text)
    noise_flags: list[str] = []
    is_noise_page = False

    # 1. 检查是否整页噪音（cookie/privacy/terms/login/signup）
    text_lower = raw_text.lower()
    for pattern, flag in _NOISE_PAGE_PATTERNS:
        if re.search(pattern, raw_text):
            noise_flags.append(flag)
            # 如果是 cookie/privacy/terms/login/signup 页面，整页标记
            if flag in ("cookie_page", "cookie_banner", "privacy_page",
                        "terms_page", "legal_page", "auth_page"):
                is_noise_page = True

    # 如果标题占比过高（>30% 是这些关键词），全页标记为低质量
    if is_noise_page:
        noise_keyword_count = sum(
            len(re.findall(p, raw_text)) for p, _ in _NOISE_PAGE_PATTERNS
        ) if _NOISE_PAGE_PATTERNS else 0
        # 简短页面（<500 字符且全是噪音关键字）直接丢弃
        if original_len < 500 and noise_keyword_count >= 3:
            return {
                "clean_text": "",
                "removed_ratio": 1.0,
                "noise_flags": noise_flags,
                "is_low_quality": True,
                "is_noise_page": True,
            }

    # 2. 逐行过滤
    lines = raw_text.split("\n")
    cleaned_lines = []
    removed_count = 0

    for line in lines:
        stripped = line.strip()

        # 空行保留（用于段落分隔），但连续空行合并
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            else:
                removed_count += len(line) + 1
            continue

        # 检查低信息密度
        is_low_info = False
        for pattern, flag in _LOW_INFO_PATTERNS:
            if re.match(pattern, stripped):
                noise_flags.append(flag)
                is_low_info = True
                break
        if is_low_info:
            removed_count += len(line) + 1
            continue

        # 检查评论
        is_comment = False
        for pattern, flag in _COMMENT_PATTERNS:
            if re.search(pattern, stripped):
                noise_flags.append(flag)
                is_comment = True
                break
        if is_comment:
            removed_count += len(line) + 1
            continue

        # 检查噪音块（footer/navigation/newsletter/CTA/广告/YouTube寒暄/赞助）
        is_noise = False
        for pattern, flag in _NOISE_BLOCK_PATTERNS:
            if re.search(pattern, stripped):
                noise_flags.append(flag)
                is_noise = True
                break
        if is_noise:
            removed_count += len(line) + 1
            continue

        cleaned_lines.append(stripped)

    # 3. 后处理
    clean_text = "\n".join(cleaned_lines).strip()
    # 合并连续空行为单个空行
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

    clean_len = len(clean_text)
    removed_ratio = (original_len - clean_len) / max(original_len, 1)
    is_low_quality = (
        is_noise_page
        or clean_len < 100
        or removed_ratio > 0.95
    )

    return {
        "clean_text": clean_text,
        "removed_ratio": removed_ratio,
        "noise_flags": list(set(noise_flags)),
        "is_low_quality": is_low_quality,
        "is_noise_page": is_noise_page,
    }
