"""圆形飞轮 — 内置模板 A（白色背景 + 闭环箭头 + 可编辑阶段标签）"""
import json as _json
import math

META = {
    "id": "flywheel_circular",
    "name": "圆形飞轮",
    "asset_key": "flywheel",
    "builtin": True,
    "params": [
        {"key": "accent_color", "label": "强调色", "type": "color", "default": "#29B8D4"},
        {"key": "label_size", "label": "阶段字号", "type": "range", "min": 18, "max": 34, "step": 1, "default": 25},
        {"key": "show_desc", "label": "显示描述", "type": "checkbox", "default": False},
        {"key": "stages_json", "label": "阶段数据", "type": "textarea", "default": ""},
    ],
}


def build(data: dict, params: dict) -> str:
    # -- 阶段数据：优先从 params.stages_json 解析，回退到 data.stages --
    stages = _parse_stages(params.get("stages_json", "")) or data.get("stages", [])
    if len(stages) < 2:
        w = int(float(params.get("width", 800)))
        h = int(float(params.get("height", 800)))
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="#FFFFFF" rx="12"/><text x="{w//2}" y="{h//2}" text-anchor="middle" fill="rgba(0,0,0,0.3)" font-size="16">飞轮至少需要 2 个阶段</text></svg>'

    accent = params.get("accent_color", "#29B8D4")
    label_size = int(float(params.get("label_size", 25)))
    show_desc = _is_truthy(params.get("show_desc", False))
    n = len(stages)

    w = int(float(params.get("width", 800)))
    h = int(float(params.get("height", 800)))
    cx, cy = w / 2, h / 2

    # 箭头环半径与文字长度解耦；文字用 tspan 换行，避免长字段把环挤到中心。
    text_box_w = max(150, min(280, w * 0.34))
    top_bottom_text_w = max(180, min(360, w * 0.46))
    # 根据实际最长文字估算所需水平空间，确保不超出 viewBox
    actual_texts = [_stage_display_text(s, show_desc) for s in stages]
    max_text_px = max((_est_text_px(t, label_size, text_box_w) for t in actual_texts), default=label_size * 3)
    text_margin = max(text_box_w / 2, max_text_px / 2 + 20)
    ring_margin_x = max(120, label_size * 3.1, text_margin)
    ring_margin_y = max(120, label_size * 3.4)
    a = max((w / 2) - ring_margin_x, 70)
    b = max((h / 2) - ring_margin_y, 70)

    # -- 阶段节点（先算位置，再按 Y 分组错开防重叠）--
    positions = []
    for i, s in enumerate(stages):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        sx = cx + a * math.cos(rad)
        sy = cy + b * math.sin(rad)
        positions.append({"s": s, "sx": sx, "sy": sy, "idx": i})

    # 同 Y 层（± label_size*1.2）的阶段上下错开
    y_band = label_size * 1.2
    for i, p in enumerate(positions):
        same_band = [q for q in positions if abs(q["sy"] - p["sy"]) < y_band]
        if len(same_band) > 1:
            band_idx = same_band.index(p)
            offset_y = (band_idx - (len(same_band) - 1) / 2) * label_size * 0.7
            p["sy"] += offset_y

    stage_svgs = []
    for p in positions:
        sx, sy = p["sx"], p["sy"]
        label = p["s"].get("label", f"阶段{p['idx'] + 1}")
        desc = p["s"].get("desc", "").strip()
        # 合并为一行：label | desc 或纯 label
        text = f"{label} | {desc}" if (show_desc and desc) else label
        max_width = top_bottom_text_w if abs(sx - cx) < a * 0.35 else text_box_w
        stage_svgs.append(_stage_text_svg(text, sx, sy, label_size, max_width))

    # -- 箭头弧线 —
    arrow_svgs = []
    for i in range(n):
        a1_deg = -90 + (360 / n) * i + 18
        a2_deg = -90 + (360 / n) * ((i + 1) % n) - 18
        a1 = math.radians(a1_deg)
        a2 = math.radians(a2_deg)
        x1 = cx + a * math.cos(a1)
        y1 = cy + b * math.sin(a1)
        x2 = cx + a * math.cos(a2)
        y2 = cy + b * math.sin(a2)
        span = (a2_deg - a1_deg) % 360
        large = 1 if span > 180 else 0
        path = f"M{x1:.1f},{y1:.1f} A{a:.1f},{b:.1f} 0 {large} 1 {x2:.1f},{y2:.1f}"
        arrow_svgs.append(
            f'<path d="{path}" fill="none" stroke="{accent}" stroke-width="5"'
            f' stroke-opacity="0.85" marker-end="url(#arrowhead)"/>',
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs>
  <marker id="arrowhead" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M2 2L9 6L2 10" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>
  </marker>
</defs>
<rect width="{w}" height="{h}" fill="transparent" rx="12"/>
{chr(10).join(arrow_svgs)}
{chr(10).join(stage_svgs)}
</svg>"""


def _parse_stages(raw):
    """从 JSON 字符串解析阶段数组"""
    if not raw or not raw.strip():
        return None
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, list) and len(parsed) >= 2:
            return parsed
    except (ValueError, TypeError):
        pass
    # 尝试按行解析 alt 格式:  label|desc
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    if len(lines) >= 2:
        stages = []
        for line in lines:
            parts = line.split("|", 1)
            stages.append({"label": parts[0].strip(), "desc": parts[1].strip() if len(parts) > 1 else ""})
        return stages
    return None


def _is_truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes", "on")
    return bool(v)


def _stage_text_svg(text, x, y, label_size, max_width):
    lines = _wrap_text(text, max_width, label_size, max_lines=3)
    line_h = label_size * 1.12
    y0 = y - ((len(lines) - 1) * line_h / 2)
    tspans = []
    for i, line in enumerate(lines):
        tspans.append(f'<tspan x="{x:.1f}" y="{y0 + i * line_h:.1f}">{_esc(line)}</tspan>')
    return (
        f'<text class="flywheel-stage-label" x="{x:.1f}" y="{y:.1f}" text-anchor="middle"'
        f' font-family="\'Noto Sans SC\',\'PingFang SC\',sans-serif"'
        f' font-size="{label_size}" font-weight="700" fill="#1B2A4A">'
        f'{"".join(tspans)}</text>'
    )


def _wrap_text(text, max_width, label_size, max_lines=3):
    text = " ".join(str(text or "").split())
    if not text:
        return [""]
    max_units = max(4, int(max_width / max(label_size * 0.62, 1)))
    lines = []
    current = ""
    current_units = 0
    for ch in text:
        unit = 0.5 if ch.isascii() and ch not in "|，。；：、" else 1
        if current and current_units + unit > max_units:
            lines.append(current.rstrip())
            current = ch.lstrip()
            current_units = unit
            if len(lines) == max_lines - 1:
                break
        else:
            current += ch
            current_units += unit
    consumed = "".join(lines) + current
    rest = text[len(consumed):].strip()
    if rest:
        keep_units = max(2, max_units - 1)
        trimmed = ""
        total = 0
        for ch in current:
            unit = 0.5 if ch.isascii() and ch not in "|，。；：、" else 1
            if total + unit > keep_units:
                break
            trimmed += ch
            total += unit
        current = trimmed.rstrip() + "…"
    if current:
        lines.append(current.rstrip())
    return lines[:max_lines] or [text]


def _stage_display_text(s, show_desc):
    """构建阶段在 SVG 中的显示文本"""
    label = s.get("label", "")
    desc = s.get("desc", "").strip()
    if show_desc and desc:
        return f"{label} | {desc}"
    return label


def _est_text_px(text, label_size, max_width):
    """估算文本渲染后的实际宽度（px），考虑换行"""
    # 先计算是否需要换行
    # 中文字符宽度 ≈ label_size * 0.62, ASCII ≈ label_size * 0.31
    chars = list(text or "")
    # 最大单行字符数
    max_chars = max(1, int(max_width / (label_size * 0.62)))
    if len(chars) <= max_chars:
        # 单行
        total = 0
        for ch in chars:
            total += label_size * 0.31 if (ch.isascii() and ch not in "|，。；：、") else label_size * 0.62
        return max(label_size, total)
    # 多行：取第一行宽度（最长的行）
    line_width = 0
    current = 0
    for ch in chars:
        w = label_size * 0.31 if (ch.isascii() and ch not in "|，。；：、") else label_size * 0.62
        if current + w > max_width:
            line_width = max(line_width, current)
            current = w
        else:
            current += w
    line_width = max(line_width, current)
    return max(label_size, line_width)


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
