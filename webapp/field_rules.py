"""层1：规则层 — 不碰 LLM，用关键词+网页抓取确定枚举字段"""

from __future__ import annotations
import re
from firecrawl_local import scrape_url

# stack_layer：从 company_type 关键词推断
STACK_KEYWORDS: list[tuple[str, str]] = [
    # infrastructure — 底层算力/存储
    ("基础设施", "infrastructure"), ("infrastructure", "infrastructure"),
    ("infra", "infrastructure"), ("cloud", "infrastructure"), ("compute", "infrastructure"),
    ("serverless", "infrastructure"), ("gpu", "infrastructure"), ("vector_db", "infrastructure"),
    ("vector database", "infrastructure"), ("embedding", "infrastructure"),
    # foundation_model — 模型层
    ("基础模型", "foundation_model"), ("foundation model", "foundation_model"),
    ("foundation_model", "foundation_model"), ("大模型", "foundation_model"),
    ("llm", "foundation_model"), ("large language model", "foundation_model"),
    ("开源模型", "foundation_model"), ("open source model", "foundation_model"),
    ("api", "foundation_model"),  # LLM API 提供商
    # middleware — 中间件/工具链
    ("中间件", "middleware"), ("middleware", "middleware"),
    ("mlops", "middleware"), ("orchestrat", "middleware"),
    ("agent", "middleware"), ("rag", "middleware"), ("pipeline", "middleware"),
    ("fine-tun", "middleware"), ("fine_tun", "middleware"), ("训练", "middleware"),
    ("observability", "middleware"), ("monitoring", "middleware"),
    ("安全", "middleware"), ("security", "middleware"), ("guard", "middleware"),
    # vertical_app — 垂直应用
    ("coding", "vertical_app"), ("code", "vertical_app"),
    ("design", "vertical_app"), ("marketing", "vertical_app"),
    ("视频", "vertical_app"), ("video", "vertical_app"),
    ("搜索", "vertical_app"), ("search", "vertical_app"),
    ("音频", "vertical_app"), ("audio", "vertical_app"), ("voice", "vertical_app"),
    ("图像", "vertical_app"), ("image", "vertical_app"), ("图片", "vertical_app"),
    ("3d", "vertical_app"), ("avatar", "vertical_app"),
    ("写作", "vertical_app"), ("writing", "vertical_app"), ("内容", "vertical_app"),
    ("法律", "vertical_app"), ("legal", "vertical_app"),
    ("医疗", "vertical_app"), ("medical", "vertical_app"), ("health", "vertical_app"),
    ("金融", "vertical_app"), ("finance", "vertical_app"),
    ("教育", "vertical_app"), ("education", "vertical_app"),
    ("客服", "vertical_app"), ("customer service", "vertical_app"),
    ("sales", "vertical_app"), ("销售", "vertical_app"),
    ("助手", "vertical_app"), ("assistant", "vertical_app"), ("copilot", "vertical_app"),
    ("chat", "vertical_app"), ("chatbot", "vertical_app"), ("生成", "vertical_app"),
    ("generator", "vertical_app"), ("generation", "vertical_app"),
    # distribution — 分发/平台
    ("分发", "distribution"), ("distribution", "distribution"),
    ("marketplace", "distribution"), ("directory", "distribution"),
    ("浏览器", "distribution"), ("browser", "distribution"),
    ("搜索引擎", "distribution"), ("search engine", "distribution"),
    ("平台", "distribution"),  # 注意：此关键词靠后，避免覆盖垂直应用
]


def infer_stack_layer(company_type: str) -> str | None:
    """从 company_type 文本推断 stack_layer 枚举。未命中返回 None。"""
    if not company_type:
        return None
    text = str(company_type).lower()
    # 按顺序匹配，先命中的优先
    for keyword, layer in STACK_KEYWORDS:
        if keyword in text:
            return layer
    return None


# pricing 页关键词 → customer_segment_type
CUSTOMER_KEYWORDS: list[tuple[str, str]] = [
    ("enterprise", "b2b_enterprise"),
    ("企业", "b2b_enterprise"),
    ("team", "b2b_smb"),
    ("团队", "b2b_smb"),
    ("small business", "b2b_smb"),
    ("startup", "b2b_smb"),
    ("api", "developer_api"),
    ("developer", "developer_api"),
    ("开发", "developer_api"),
    ("b2b2c", "b2b2c"),
    ("consumer", "b2c"),
    ("个人", "b2c"),
    ("individual", "b2c"),
]

# pricing 页关键词 → pricing_model
PRICING_KEYWORDS: list[tuple[str, str]] = [
    ("contact sales", "enterprise_contract"),
    ("联系销售", "enterprise_contract"),
    ("talk to sales", "enterprise_contract"),
    ("outcome", "outcome_based"),
    ("按效果", "outcome_based"),
    ("per token", "usage_based"),
    ("per call", "usage_based"),
    ("per request", "usage_based"),
    ("按量", "usage_based"),
    ("usage", "usage_based"),
]


def scrape_pricing_signals(website: str, timeout: int = 15) -> dict:
    """爬取 /pricing 页，返回 {'customer_segment_type': ..., 'pricing_model': ...}。
    未命中返回 None，交给 LLM 层。"""
    result = {}
    if not website:
        return result

    url = website.rstrip('/') + '/pricing'
    try:
        resp = scrape_url(url, timeout=timeout)
    except Exception:
        return result

    if resp.get('error'):
        return result

    html = (resp.get('markdown', '') + ' ' + resp.get('title', '')).lower()
    if len(html) < 100:
        return result

    # customer_segment_type
    for keyword, value in CUSTOMER_KEYWORDS:
        if keyword in html:
            result['customer_segment_type'] = value
            break

    # pricing_model
    for keyword, value in PRICING_KEYWORDS:
        if keyword in html:
            result['pricing_model'] = value
            break

    # subscription 兜底检测（放在 pricing 后面，优先级最低）
    if 'pricing_model' not in result:
        if '/mo' in html or '/month' in html or '/年' in html or 'monthly' in html:
            if 'free' in html:
                result['pricing_model'] = 'freemium'
            else:
                result['pricing_model'] = 'subscription'

    # freemium 兜底
    if 'pricing_model' not in result and ('free' in html or '免费' in html):
        result['pricing_model'] = 'freemium'

    return result


def run_rule_layer(website: str, company_type: str = '') -> dict:
    """执行规则层，返回命中的字段 dict。未命中的 key 不在 dict 中。"""
    hits: dict = {}

    # stack_layer
    stack = infer_stack_layer(company_type)
    if stack:
        hits['stack_layer'] = stack

    # customer + pricing from pricing page
    if website:
        pricing_hits = scrape_pricing_signals(website)
        for k, v in pricing_hits.items():
            if v and k not in hits:
                hits[k] = v

    return hits
