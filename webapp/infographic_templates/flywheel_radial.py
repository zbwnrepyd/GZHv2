"""辐射飞轮 — 内置模板 C（白色背景 + 纯闭环箭头 + 阶段标签）"""
import json as _json
import math

META = {
    "id": "flywheel_radial",
    "name": "辐射飞轮",
    "asset_key": "flywheel",
    "builtin": True,
    "params": [
        {"key": "radius", "label": "辐射半径", "type": "range", "min": 160, "max": 260, "step": 10, "default": 210},
        {"key": "accent_color", "label": "强调色", "type": "color", "default": "#29B8D4"},
        {"key": "label_size", "label": "阶段字号", "type": "range", "min": 13, "max": 20, "step": 1, "default": 16},
    ],
}


def build(data: dict, params: dict) -> str:
    stages = _parse_stages(params.get("stages_json", "")) or data.get("stages", [])
    if len(stages) < 2:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800"><rect width="800" height="800" fill="#FFFFFF" rx="12"/><text x="400" y="400" text-anchor="middle" fill="rgba(0,0,0,0.3)" font-size="16">飞轮至少需要 2 个阶段</text></svg>'

    r = int(params.get("radius", META["params"][0]["default"]))
    accent = params.get("accent_color", META["params"][1]["default"])
    label_size = int(params.get("label_size", META["params"][2]["default"]))
    n = len(stages)
    cx, cy = 400, 400

    # 阶段节点（白底小圆 + 标签，无描述文字）
    stage_svgs = []
    for i, s in enumerate(stages):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        sx = cx + r * math.cos(rad)
        sy = cy + r * math.sin(rad)
        label = s.get("label", f"阶段{i + 1}")
        stage_svgs.append(f"""  <circle cx="{int(sx)}" cy="{int(sy)}" r="34" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>
  <text x="{int(sx)}" y="{int(sy)}" text-anchor="middle" dominant-baseline="central" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{label_size}" font-weight="700" fill="#1B2A4A">{_esc(label)}</text>""")

    # 阶段间弧线箭头（顺时针闭环）
    arc_svgs = []
    for i in range(n):
        a1 = math.radians(-90 + (360 / n) * i + 20)
        a2 = math.radians(-90 + (360 / n) * ((i + 1) % n) - 20)
        r_arc = r + 52
        x1 = cx + r_arc * math.cos(a1)
        y1 = cy + r_arc * math.sin(a1)
        x2 = cx + r_arc * math.cos(a2)
        y2 = cy + r_arc * math.sin(a2)
        mid_a = (a1 + a2) / 2
        r_mid = r_arc + 18
        mx = cx + r_mid * math.cos(mid_a)
        my = cy + r_mid * math.sin(mid_a)
        path = f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}"
        arc_svgs.append(f"""  <path d="{path}" fill="none" stroke="{accent}" stroke-opacity="0.5" stroke-width="2.5" marker-end="url(#arrowhead)"/>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
<defs>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>
  </marker>
</defs>
<rect width="800" height="800" fill="transparent" rx="12"/>
{chr(10).join(arc_svgs)}
{chr(10).join(stage_svgs)}
</svg>"""


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _parse_stages(raw):
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, list) and len(parsed) >= 2:
            return parsed
    except (ValueError, TypeError):
        pass
    lines = [line.strip() for line in str(raw).split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    stages = []
    for line in lines:
        label = line.split("|", 1)[0].strip()
        if label:
            stages.append({"label": label, "desc": ""})
    return stages if len(stages) >= 2 else None
