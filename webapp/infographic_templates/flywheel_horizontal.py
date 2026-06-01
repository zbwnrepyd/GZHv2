"""水平飞轮 — 内置模板 B"""
META = {
    "id": "flywheel_horizontal",
    "name": "水平飞轮",
    "asset_key": "flywheel",
    "builtin": True,
    "params": [
        {"key": "node_w", "label": "节点间距", "type": "range", "min": 150, "max": 260, "step": 10, "default": 200},
        {"key": "accent_color", "label": "强调色", "type": "color", "default": "#29B8D4"},
        {"key": "label_size", "label": "阶段字号", "type": "range", "min": 13, "max": 20, "step": 1, "default": 16},
    ],
}


def build(data: dict, params: dict) -> str:
    stages = data.get("stages", [])
    if len(stages) < 2:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="800" height="400"><rect width="800" height="400" fill="#0B1629" rx="12"/><text x="400" y="200" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="16">飞轮至少需要 2 个阶段</text></svg>'

    node_w = int(params.get("node_w", META["params"][0]["default"]))
    accent = params.get("accent_color", META["params"][1]["default"])
    label_size = int(params.get("label_size", META["params"][2]["default"]))
    center_label = data.get("center", "增长飞轮")
    n = len(stages)

    total_w = max(800, 120 + n * node_w + 120)
    cx, cy = total_w // 2, 220
    node_r = 42

    # 阶段节点
    stage_svgs = []
    for i, s in enumerate(stages):
        sx = 120 + i * node_w + node_w // 2
        label = s.get("label", f"阶段{i + 1}")
        desc = s.get("desc", "")
        if len(desc) > 24:
            desc = desc[:22] + "…"
        stage_svgs.append(f"""  <circle cx="{sx}" cy="{cy}" r="{node_r}" fill="#162440" stroke="{accent}" stroke-width="2"/>
  <text x="{sx}" y="{cy}" text-anchor="middle" dominant-baseline="central" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{label_size}" font-weight="700" fill="#FFFFFF">{_esc(label)}</text>
  <text x="{sx}" y="{cy + node_r + 20}" text-anchor="middle" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="12" fill="rgba(255,255,255,0.5)">{_esc(desc)}</text>""")

    # 箭头
    arrow_svgs = []
    for i in range(n - 1):
        x1 = 120 + i * node_w + node_w // 2 + node_r + 6
        x2 = 120 + (i + 1) * node_w + node_w // 2 - node_r - 6
        arrow_svgs.append(f"""  <line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" stroke="{accent}" stroke-opacity="0.5" stroke-width="2" marker-end="url(#arrowhead)"/>""")
    # 回路弧线（最后一个回到第一个）
    x_last = 120 + (n - 1) * node_w + node_w // 2 + node_r + 6
    x_first = 120 + node_w // 2 - node_r - 6
    y_loop = cy - node_r - 30
    loop_path = f"M{x_last},{cy} Q{x_last},{y_loop} {x_first},{y_loop} Q{x_first - 20},{y_loop} {x_first},{cy}"
    arrow_svgs.append(f"""  <path d="{loop_path}" fill="none" stroke="{accent}" stroke-opacity="0.3" stroke-width="1.5" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>""")

    # 上方中心标题
    title_y = cy - node_r - 58
    title_svg = f"""  <text x="{cx}" y="{title_y}" text-anchor="middle" font-family="'Bebas Neue','Noto Sans SC',sans-serif" font-size="26" font-weight="400" fill="{accent}" letter-spacing="0.06em">{_esc(center_label)}</text>
  <text x="{cx}" y="{title_y + 22}" text-anchor="middle" font-family="'IBM Plex Mono',monospace" font-size="11" fill="rgba(255,255,255,0.35)">{n} STAGES</text>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 400" width="{total_w}" height="400">
<defs>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#0B1629"/>
    <stop offset="100%" stop-color="#162440"/>
  </linearGradient>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="{accent}" stroke-width="1.5" stroke-linecap="round"/>
  </marker>
</defs>
<rect width="{total_w}" height="400" fill="url(#bgGrad)" rx="12"/>
{title_svg}
{chr(10).join(stage_svgs)}
{chr(10).join(arrow_svgs)}
</svg>"""


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
