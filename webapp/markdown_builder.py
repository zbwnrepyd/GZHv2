from __future__ import annotations

import json

import db as database


CARD_TITLES = {
    1: "首页",
    2: "公司介绍",
    3: "发展沿袭",
    4: "主产品",
    5: "其他产品",
    6: "商业模式",
    7: "竞争格局",
    8: "总结",
}


def _missing(value) -> bool:
    return value is None or str(value).strip() == "" or str(value).strip() == "暂缺"


def _value(record: dict, key: str) -> str:
    value = record.get(key)
    return "暂缺" if _missing(value) else str(value)


def _json_array(value) -> list:
    if _missing(value):
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _format_timeline(value) -> str:
    events = _json_array(value)
    if not events:
        return f"**发展沿袭时间线**：{value if not _missing(value) else '暂缺'}"
    lines = []
    for event in events:
        date = event.get("date") or event.get("time") or event.get("year") or "暂缺"
        title = event.get("event") or event.get("title") or event.get("description") or "暂缺"
        impact = event.get("impact") or event.get("result") or ""
        suffix = f" — *{impact}*" if impact else ""
        lines.append(f"- **{date}** {title}{suffix}")
    return "\n".join(lines)


def _format_other_products(value) -> str:
    products = _json_array(value)
    if not products:
        return "**其他产品**：暂缺" if _missing(value) else str(value)
    return "\n".join(
        f"- **{p.get('name', '暂缺')}**：{p.get('def') or p.get('description') or '暂缺'}"
        f"（{p.get('highlight') or p.get('feature') or '暂缺'}）"
        for p in products
    )


def _format_competitors(value) -> str:
    competitors = _json_array(value)
    if not competitors:
        return f"**竞争格局**：{value if not _missing(value) else '暂缺'}"
    lines = []
    for idx, competitor in enumerate(competitors, start=1):
        name = competitor.get("name") or competitor.get("company") or f"竞品{idx}"
        product = competitor.get("product") or competitor.get("description") or "暂缺"
        data = competitor.get("data") or competitor.get("metric") or competitor.get("evidence") or "暂缺"
        lines.append(f"**TOP{idx}**：{name} — {product}（{data}）")
    return "\n".join(lines)


def build_card_markdown(db_path: str, company_name: str, card_index: int, version: str) -> str:
    """Build one card's editable Markdown from the latest research record."""
    record = database.get_research(db_path, company_name, version)
    if not record:
        return ""

    title = CARD_TITLES.get(card_index, f"卡片{card_index}")
    lines = [f"## 卡片{card_index}：{title}", ""]

    if card_index == 1:
        lines += [f"# {company_name}", "", f"**{_value(record, 'company_type')}**"]
    elif card_index == 2:
        lines += [
            f"**位置**：{_value(record, 'location')}",
            "",
            _value(record, "company_def"),
            "",
            f"**创始人**：{_value(record, 'founder_name')}",
            f"**学历背景**：{_value(record, 'founder_edu')}",
            f"**工作背景**：{_value(record, 'founder_bg')}",
            f"**过往成就**：{_value(record, 'founder_achievement')}",
            f"**团队规模**：{_value(record, 'team_size')}",
            f"**团队亮点**：{_value(record, 'team_highlight')}",
            f"**融资**：{_value(record, 'funding_info')}",
            f"**客户群体**：{_value(record, 'customer_segment')}",
            f"**官网**：{_value(record, 'website_url')}",
        ]
    elif card_index == 3:
        lines.append(_format_timeline(record.get("timeline_events")))
    elif card_index == 4:
        lines += [
            f"## {_value(record, 'main_product_name')}",
            "",
            _value(record, "main_product_def"),
            "",
            f"**亮点**：{_value(record, 'main_product_highlight')}",
            f"**成就**：{_value(record, 'main_product_achievement')}",
        ]
        image = record.get("main_product_img_src")
        if not _missing(image):
            lines += ["", f"![产品图片]({image})"]
    elif card_index == 5:
        lines.append(_format_other_products(record.get("other_products")))
    elif card_index == 6:
        lines += [
            f"**盈利**：{_value(record, 'revenue_model')}",
            f"**冷启动**：{_value(record, 'cold_start')}",
            f"**GTM**：{_value(record, 'gtm_strategy')}",
            f"**飞轮**：{_value(record, 'growth_flywheel')}",
        ]
    elif card_index == 7:
        moat_text = _value(record, 'moat')
        # 拆分壁垒和生态位（若 moat 字段中包含"生态位分析"标记则拆分，否则生态位留空）
        moat_part = moat_text
        niche_part = record.get('ecosystem_niche') or ''
        if not niche_part:
            for sep in ['- 生态位分析', '●生态位分析', '生态位分析', '- 生态位', '●生态位', '\n\n生态位']:
                idx = moat_text.find(sep)
                if idx > 0:
                    moat_part = moat_text[:idx].strip()
                    niche_part = moat_text[idx:].strip()
                    break
        lines += [
            f"**壁垒**：{moat_part if moat_part and moat_part != '暂缺' else '暂缺'}",
        ]
        if niche_part and niche_part != '暂缺':
            lines.append(f"**生态位**：{niche_part}")
        lines.append(_format_competitors(record.get("competitors")))
    elif card_index == 8:
        lines += [
            f"**机遇**：{_value(record, 'market_opportunity')}",
        ]

    return "\n".join(lines).rstrip() + "\n"
