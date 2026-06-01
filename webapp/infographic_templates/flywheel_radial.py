"""辐射飞轮 — 内置模板 C"""
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
    stages = data.get("stages", [])
    if len(stages) < 2:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800"><rect width="800" height="800" fill="#0B1629" rx="12"/><text x="400" y="400" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="16">飞轮至少需要 2 个阶段</text></svg>'

    r = int(params.get("radius", META["params"][0]["default"]))
    accent = params.get("accent_color", META["params"][1]["default"])
    label_size = int(params.get("label_size", META["params"][2]["default"]))
    center_label = data.get("center", "增长飞轮")
    n = len(stages)
    cx, cy = 400, 400

    # 外环
    outer_ring = f"""  <circle cx="{cx}" cy="{cy}" r="{r + 40}" fill="none" stroke="rgba(41,184,212,0.12)" stroke-width="1" stroke-dasharray="4 6"/>
  <circle cx="{cx}" cy="{cy}" r="{r + 80}" fill="none" stroke="rgba(41,184,212,0.06)" stroke-width="1"/>"""

    # 阶段节点 — 从中心辐射出去
    stage_svgs = []
    spoke_svgs = []
    for i, s in enumerate(stages):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        sx = cx + r * math.cos(rad)
        sy = cy + r * math.sin(rad)
        label = s.get("label", f"阶段{i + 1}")
        desc = s.get("desc", "")
        if len(desc) > 24:
            desc = desc[:22] + "…"

        # 从中心到节点的连接线
        mid_x = cx + (r * 0.38) * math.cos(rad)
        mid_y = cy + (r * 0.38) * math.sin(rad)
        spoke_svgs.append(f"""  <line x1="{int(mid_x)}" y1="{int(mid_y)}" x2="{int(sx) - 34 * math.cos(rad):.0f}" y2="{int(sy) - 34 * math.sin(rad):.0f}" stroke="{accent}" stroke-opacity="0.25" stroke-width="1.5"/>""")

        stage_svgs.append(f"""  <circle cx="{int(sx)}" cy="{int(sy)}" r="34" fill="#162440" stroke="{accent}" stroke-width="1.5"/>
  <text x="{int(sx)}" y="{int(sy)}" text-anchor="middle" dominant-baseline="central" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{label_size}" font-weight="700" fill="#FFFFFF">{_esc(label)}</text>
  <text x="{int(sx) + (44 * math.cos(rad)):.0f}" y="{int(sy) + (44 * math.sin(rad)):.0f}" text-anchor="middle" dominant-baseline="hanging" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="11" fill="rgba(255,255,255,0.45)">{_esc(desc)}</text>""")

    # 阶段间弧线箭头（顺时针）
    arc_svgs = []
    for i in range(n):
        a1 = math.radians(-90 + (360 / n) * i + 20)
        a2 = math.radians(-90 + (360 / n) * ((i + 1) % n) - 20)
        r_arc = r + 52
        x1 = cx + r_arc * math.cos(a1)
        y1 = cy + r_arc * math.sin(a1)
        x2 = cx + r_arc * math.cos(a2)
        y2 = cy + r_arc * math.sin(a2)
        # 二次贝塞尔近似弧
        mid_a = (a1 + a2) / 2
        r_mid = r_arc + 18
        mx = cx + r_mid * math.cos(mid_a)
        my = cy + r_mid * math.sin(mid_a)
        path = f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}"
        arc_svgs.append(f"""  <path d="{path}" fill="none" stroke="{accent}" stroke-opacity="0.4" stroke-width="2" marker-end="url(#arrowhead)"/>""")

    # 中心 hub
    hub_svg = f"""  <circle cx="{cx}" cy="{cy}" r="52" fill="#0B1629" stroke="{accent}" stroke-width="2"/>
  <circle cx="{cx}" cy="{cy}" r="60" fill="none" stroke="{accent}" stroke-opacity="0.15" stroke-width="1"/>
  <text x="{cx}" y="{cy - 8}" text-anchor="middle" dominant-baseline="central" font-family="'Bebas Neue','Noto Sans SC',sans-serif" font-size="24" font-weight="400" fill="{accent}" letter-spacing="0.05em">{_esc(center_label)}</text>
  <text x="{cx}" y="{cy + 20}" text-anchor="middle" dominant-baseline="central" font-family="'IBM Plex Mono',monospace" font-size="11" fill="rgba(255,255,255,0.35)">{n} STAGES</text>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
<defs>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#0B1629"/>
    <stop offset="100%" stop-color="#162440"/>
  </linearGradient>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="{accent}" stroke-width="1.5" stroke-linecap="round"/>
  </marker>
</defs>
<rect width="800" height="800" fill="url(#bgGrad)" rx="12"/>
{outer_ring}
{chr(10).join(spoke_svgs)}
{chr(10).join(arc_svgs)}
{chr(10).join(stage_svgs)}
{hub_svg}
</svg>"""


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
