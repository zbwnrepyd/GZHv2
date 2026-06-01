"""右轴时间线 — 内置模板 C"""
META = {
    "id": "timeline_right_axis",
    "name": "右轴时间线",
    "asset_key": "timeline",
    "builtin": True,
    "params": [
        {"key": "row_h", "label": "行高", "type": "range", "min": 60, "max": 140, "step": 5, "default": 90},
        {"key": "axis_x", "label": "时间轴位置", "type": "range", "min": 500, "max": 700, "step": 10, "default": 640},
        {"key": "accent_color", "label": "强调色", "type": "color", "default": "#29B8D4"},
        {"key": "title_size", "label": "标题字号", "type": "range", "min": 14, "max": 24, "step": 1, "default": 18},
    ],
}


def build(data: dict, params: dict) -> str:
    events = data.get("events", [])
    if not events:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 200" width="800" height="200"><rect width="800" height="200" fill="#0B1629" rx="12"/><text x="400" y="100" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="16">暂无时间线数据</text></svg>'

    row_h = int(params.get("row_h", META["params"][0]["default"]))
    axis_x = int(params.get("axis_x", META["params"][1]["default"]))
    accent = params.get("accent_color", META["params"][2]["default"])
    title_size = int(params.get("title_size", META["params"][3]["default"]))

    top_pad = 60
    bottom_pad = 40
    total_h = top_pad + len(events) * row_h + bottom_pad
    line_end = total_h - 20

    parts = []
    for i, ev in enumerate(events):
        y = top_pad + i * row_h + row_h // 2
        year = ev.get("year", "")
        title = ev.get("title", "")
        desc = ev.get("desc", "")
        if len(desc) > 60:
            desc = desc[:58] + "…"

        parts.append(f"""  <circle cx="{axis_x}" cy="{y}" r="6" fill="{accent}"/>
  <circle cx="{axis_x}" cy="{y}" r="14" fill="none" stroke="{accent}" stroke-opacity="0.25" stroke-width="1"/>
  <text x="{axis_x + 16}" y="{y + 5}" text-anchor="start" font-family="'IBM Plex Mono',monospace" font-size="15" font-weight="700" fill="{accent}">{_esc(year)}</text>
  <text x="{axis_x - 16}" y="{y - 8}" text-anchor="end" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{title_size}" font-weight="700" fill="#FFFFFF">{_esc(title)}</text>
  <text x="{axis_x - 16}" y="{y + 14}" text-anchor="end" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="13" fill="rgba(255,255,255,0.55)">{_esc(desc)}</text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {total_h}" width="800" height="{total_h}">
<defs>
  <linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{accent}"/>
    <stop offset="100%" stop-color="{accent}" stop-opacity="0.3"/>
  </linearGradient>
</defs>
<rect width="800" height="{total_h}" fill="#0B1629" rx="12"/>
<line x1="{axis_x}" y1="{top_pad}" x2="{axis_x}" y2="{line_end}" stroke="url(#lg)" stroke-width="2"/>
{chr(10).join(parts)}
</svg>"""


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
