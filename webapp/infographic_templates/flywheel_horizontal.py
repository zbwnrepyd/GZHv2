"""水平飞轮 — 内置模板 B（白色背景 + 纯闭环箭头 + 阶段标签）"""
import json as _json

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
    stages = _parse_stages(params.get("stages_json", "")) or data.get("stages", [])
    if len(stages) < 2:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="800" height="400"><rect width="800" height="400" fill="#FFFFFF" rx="12"/><text x="400" y="200" text-anchor="middle" fill="rgba(0,0,0,0.3)" font-size="16">飞轮至少需要 2 个阶段</text></svg>'

    node_w = int(params.get("node_w", META["params"][0]["default"]))
    accent = params.get("accent_color", META["params"][1]["default"])
    label_size = int(params.get("label_size", META["params"][2]["default"]))
    n = len(stages)

    total_w = max(800, 120 + n * node_w + 120)
    cy = 200
    node_r = 34

    # 阶段节点（白底小圆 + 标签，无描述）
    stage_svgs = []
    for i, s in enumerate(stages):
        sx = 120 + i * node_w + node_w // 2
        label = s.get("label", f"阶段{i + 1}")
        stage_svgs.append(f"""  <circle cx="{sx}" cy="{cy}" r="{node_r}" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>
  <text x="{sx}" y="{cy}" text-anchor="middle" dominant-baseline="central" font-family="'Noto Sans SC','PingFang SC',sans-serif" font-size="{label_size}" font-weight="700" fill="#1B2A4A">{_esc(label)}</text>""")

    # 箭头（正向 + 回路）
    arrow_svgs = []
    for i in range(n - 1):
        x1 = 120 + i * node_w + node_w // 2 + node_r + 6
        x2 = 120 + (i + 1) * node_w + node_w // 2 - node_r - 6
        arrow_svgs.append(f"""  <line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" stroke="{accent}" stroke-opacity="0.6" stroke-width="2.5" marker-end="url(#arrowhead)"/>""")
    # 回路弧线（最后一个回到第一个）
    x_last = 120 + (n - 1) * node_w + node_w // 2 + node_r + 6
    x_first = 120 + node_w // 2 - node_r - 6
    y_loop = cy - node_r - 26
    loop_path = f"M{x_last},{cy} L{x_last},{y_loop} L{x_first},{y_loop} L{x_first},{cy}"
    arrow_svgs.append(f"""  <path d="{loop_path}" fill="none" stroke="{accent}" stroke-opacity="0.35" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 400" width="{total_w}" height="400">
<defs>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>
  </marker>
</defs>
<rect width="{total_w}" height="400" fill="transparent" rx="12"/>
{chr(10).join(stage_svgs)}
{chr(10).join(arrow_svgs)}
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
