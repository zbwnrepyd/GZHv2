"""水平时间线 — 内置模板 B"""
META = {
    "id": "timeline_horizontal",
    "name": "水平时间线",
    "asset_key": "timeline",
    "builtin": True,
    "params": [
        {"key": "node_w", "label": "节点间距", "type": "range", "min": 120, "max": 260, "step": 10, "default": 180},
        {"key": "accent_color", "label": "强调色", "type": "color", "default": "#29B8D4"},
        {"key": "title_size", "label": "标题字号", "type": "range", "min": 14, "max": 22, "step": 1, "default": 16},
    ],
}


def build(data: dict, params: dict) -> str:
    events = data.get("events", [])
    if not events:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 200" width="800" height="200"><rect width="800" height="200" fill="#0B1629" rx="12"/><text x="400" y="100" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="16">暂无时间线数据</text></svg>'

    node_w = int(params.get("node_w", META["params"][0]["default"]))
    accent = params.get("accent_color", META["params"][1]["default"])
    title_size = int(params.get("title_size", META["params"][2]["default"]))

    n = len(events)
    total_w = max(800, 100 + n * node_w + 60)
    axis_y = 180
    top_pad = 40

    parts = []
    for i, ev in enumerate(events):
        x = 100 + i * node_w
        year = ev.get("year", "")
        title = ev.get("title", "")
        desc = ev.get("desc", "")
        if len(desc) > 40:
            desc = desc[:38] + "…"

        # 节点圆
        parts.append(f"""  <circle cx="{x}" cy="{axis_y}" r="8" fill="{accent}"/>
  <circle cx="{x}" cy="{axis_y}" r="18" fill="none" stroke="{accent}" stroke-opacity="0.2" stroke-width="1.5"/>""")
        # 年份（上方）
        parts.append(f"""  <text x="{x}" y="{axis_y - 30}" text-anchor="middle" font-family="'IBM Plex Mono',monospace" font-size="14" font-weight="700" fill="{accent}">{_esc(year)}</text>""")
        # 标题（下方）
        parts.append(f"""  <text x="{x}" y="{axis_y + 34}" text-anchor="middle" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{title_size}" font-weight="700" fill="#FFFFFF">{_esc(title)}</text>""")
        # 描述
        if desc:
            parts.append(f"""  <text x="{x}" y="{axis_y + 56}" text-anchor="middle" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="12" fill="rgba(255,255,255,0.5)">{_esc(desc)}</text>""")

    # 连接线
    if n > 1:
        x1 = 100
        x2 = 100 + (n - 1) * node_w
        parts.insert(0, f"""  <line x1="{x1}" y1="{axis_y}" x2="{x2}" y2="{axis_y}" stroke="{accent}" stroke-opacity="0.4" stroke-width="2" stroke-dasharray="6 4"/>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 320" width="{total_w}" height="320">
<rect width="{total_w}" height="320" fill="#0B1629" rx="12"/>
{chr(10).join(parts)}
</svg>"""


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
