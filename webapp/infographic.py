"""信息图渲染 — 增长飞轮 + 发展时间线

流程：LLM 生成结构化 JSON → SVG 模板确定性绘图 → Playwright 截成 PNG
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from string import Template


# ═══════════════════════════════════════════════════════════════
# 增长飞轮 SVG 模板
# ═══════════════════════════════════════════════════════════════

FLYWHEEL_SVG = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0B1629"/>
      <stop offset="100%" stop-color="#162440"/>
    </linearGradient>
    <linearGradient id="arrowGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#29B8D4"/>
      <stop offset="100%" stop-color="#1A8FA8"/>
    </linearGradient>
  </defs>

  <!-- 背景 -->
  <rect width="800" height="800" fill="url(#bgGrad)" rx="12"/>

  <!-- 外圈虚线环 -->
  <circle cx="400" cy="380" r="260" fill="none" stroke="rgba(41,184,212,0.18)" stroke-width="1.5" stroke-dasharray="8 6"/>

  <!-- 飞轮箭头弧线（4段贝塞尔弧） -->
  $arrows

  <!-- 阶段节点 -->
  $stages

  <!-- 中心文字 -->
  $center_text
</svg>""")

# 单段箭头弧线（从角度 a1 到 a2，顺时针，在半径 r 处）
_ARROW_ARC = Template("""\
  <path d="$path_data"
        fill="none" stroke="url(#arrowGrad)" stroke-width="2.5"
        marker-end="url(#arrowhead)" opacity="0.7"/>""")

_FLYWHEEL_STAGE = Template("""\
  <!-- $label -->
  <circle cx="$cx" cy="$cy" r="48" fill="#162440" stroke="#29B8D4" stroke-width="2" filter="url(#glow)"/>
  <text x="$cx" y="$cy" text-anchor="middle" dominant-baseline="central"
        font-family="'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif"
        font-size="16" font-weight="700" fill="#FFFFFF">$label</text>
  <text x="$cx" y="${cy2}" text-anchor="middle" dominant-baseline="hanging"
        font-family="'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif"
        font-size="12" fill="rgba(255,255,255,0.55)" style="max-width:140px">
    $desc
  </text>""")


def _build_flywheel_svg(data: dict) -> str:
    """根据结构化 JSON 构建飞轮 SVG"""
    stages = data.get("stages", [])
    center_label = data.get("center", "增长飞轮")
    n = len(stages)
    if n < 2:
        raise ValueError("飞轮至少需要 2 个阶段")

    cx, cy, r = 400, 380, 200
    import math

    # 阶段节点位置
    stage_svgs = []
    for i, s in enumerate(stages):
        angle = -90 + (360 / n) * i  # 从顶部顺时针
        rad = math.radians(angle)
        sx = cx + r * math.cos(rad)
        sy = cy + r * math.sin(rad)
        label = s.get("label", f"阶段{i + 1}")
        desc = s.get("desc", "")
        # 截断过长的描述
        if len(desc) > 28:
            desc = desc[:26] + "…"
        stage_svgs.append(_FLYWHEEL_STAGE.substitute(
            cx=int(sx), cy=int(sy), cy2=int(sy) + 54,
            label=label, desc=desc,
        ))

    # 箭头弧线（相邻节点之间的顺时针弧）
    arrow_svgs = []
    for i in range(n):
        a1 = math.radians(-90 + (360 / n) * i - 10)
        a2 = math.radians(-90 + (360 / n) * ((i + 1) % n) + 10)
        r_arc = r - 4
        x1 = cx + r_arc * math.cos(a1)
        y1 = cy + r_arc * math.sin(a1)
        x2 = cx + r_arc * math.cos(a2)
        y2 = cy + r_arc * math.sin(a2)
        # 用二次贝塞尔逼近弧线
        mid_a = (a1 + a2) / 2
        r_mid = r_arc + 40  # 外凸
        mx = cx + r_mid * math.cos(mid_a)
        my = cy + r_mid * math.sin(mid_a)
        path = f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}"
        arrow_svgs.append(f"""  <path d="{path}" fill="none" stroke="rgba(41,184,212,0.45)" stroke-width="2" marker-end="url(#arrowhead)"/>""")

    # 中心文字
    center_svg = f"""  <circle cx="{cx}" cy="{cy}" r="56" fill="#0B1629" stroke="rgba(41,184,212,0.35)" stroke-width="1.5"/>
  <text x="{cx}" y="{cy - 10}" text-anchor="middle" dominant-baseline="central"
        font-family="'Bebas Neue','Noto Sans SC','PingFang SC',sans-serif"
        font-size="28" font-weight="400" fill="#29B8D4" letter-spacing="0.06em">{center_label}</text>
  <text x="{cx}" y="{cy + 18}" text-anchor="middle" dominant-baseline="central"
        font-family="'IBM Plex Mono','SF Mono',Menlo,monospace"
        font-size="11" fill="rgba(255,255,255,0.40)">{n} STAGES</text>"""

    return FLYWHEEL_SVG.substitute(
        arrows="\n".join(arrow_svgs),
        stages="\n".join(stage_svgs),
        center_text=center_svg,
    )


# ═══════════════════════════════════════════════════════════════
# 发展时间线 SVG 模板
# ═══════════════════════════════════════════════════════════════

TIMELINE_SVG = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 $total_h" width="800" height="$total_h">
  <defs>
    <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#29B8D4"/>
      <stop offset="100%" stop-color="rgba(41,184,212,0.30)"/>
    </linearGradient>
  </defs>

  <!-- 背景 -->
  <rect width="800" height="$total_h" fill="#0B1629" rx="12"/>

  <!-- 中线 -->
  <line x1="160" y1="60" x2="160" y2="${line_end}" stroke="url(#lineGrad)" stroke-width="2"/>

  $events
</svg>""")

_TIMELINE_EVENT = Template("""\
  <!-- $year -->
  <circle cx="160" cy="$y" r="6" fill="#29B8D4"/>
  <circle cx="160" cy="$y" r="14" fill="none" stroke="rgba(41,184,212,0.25)" stroke-width="1"/>
  <text x="110" y="${y_label}" text-anchor="end"
        font-family="'IBM Plex Mono','SF Mono',Menlo,monospace"
        font-size="15" font-weight="700" fill="#29B8D4">$year</text>
  <text x="200" y="$y_title" dominant-baseline="hanging"
        font-family="'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif"
        font-size="18" font-weight="700" fill="#FFFFFF">$title</text>
  <text x="200" y="$y_desc" dominant-baseline="hanging"
        font-family="'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif"
        font-size="13" fill="rgba(255,255,255,0.55)">
    $desc
  </text>""")


def _build_timeline_svg(data: dict) -> str:
    """根据结构化 JSON 构建时间线 SVG"""
    events = data.get("events", [])
    if not events:
        raise ValueError("时间线至少需要 1 个事件")

    row_h = 90
    top_pad = 60
    bottom_pad = 40
    total_h = top_pad + len(events) * row_h + bottom_pad
    line_end = total_h - 20

    event_svgs = []
    for i, ev in enumerate(events):
        y = top_pad + i * row_h + 45
        year = ev.get("year", "")
        title = ev.get("title", "")
        desc = ev.get("desc", "")
        if len(desc) > 60:
            desc = desc[:58] + "…"
        event_svgs.append(_TIMELINE_EVENT.substitute(
            y=y, year=year, title=title, desc=desc,
            y_label=y + 5, y_title=y - 8, y_desc=y + 18,
        ))

    return TIMELINE_SVG.substitute(
        total_h=total_h,
        line_end=line_end,
        events="\n".join(event_svgs),
    )


# ═══════════════════════════════════════════════════════════════
# Markdown → JSON（LLM 提取结构化数据）
# ═══════════════════════════════════════════════════════════════

FLYWHEEL_EXTRACT_PROMPT = """从以下 Markdown 内容中提取增长飞轮的结构化数据，返回 JSON：

```json
{
  "center": "飞轮中心标题（简短，≤10字）",
  "stages": [
    {"label": "阶段1名（≤8字）", "desc": "阶段1简述（≤28字）"},
    ...
  ]
}
```

规则：
- center 取内容中飞轮的核心概念
- stages 取 3-5 个阶段，每个阶段的 label 简短、desc 精炼
- 只返回 JSON，不要其他文字

Markdown 内容：
"""

TIMELINE_EXTRACT_PROMPT = """从以下 Markdown 内容中提取发展沿袭时间线，返回 JSON：

```json
{
  "events": [
    {"year": "2020", "title": "事件标题（≤15字）", "desc": "简述（≤60字）"},
    ...
  ]
}
```

规则：
- 按时间从早到晚排列
- 每个事件 year/title 必填，desc 可选
- 提取 3-8 个关键事件
- 只返回 JSON，不要其他文字

Markdown 内容：
"""


def extract_flywheel_json(markdown: str, deepseek_call) -> dict | None:
    """用 LLM 从 Markdown 提取飞轮结构化 JSON"""
    try:
        result = deepseek_call(
            system_prompt=FLYWHEEL_EXTRACT_PROMPT,
            user_message=markdown,
            temperature=0.1,
            max_tokens=2048,
        )
        # 清理 markdown 代码块
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result[:-3]
        return json.loads(result.strip())
    except Exception:
        return None


def extract_timeline_json(markdown: str, deepseek_call) -> dict | None:
    """用 LLM 从 Markdown 提取时间线结构化 JSON"""
    try:
        result = deepseek_call(
            system_prompt=TIMELINE_EXTRACT_PROMPT,
            user_message=markdown,
            temperature=0.1,
            max_tokens=2048,
        )
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result[:-3]
        return json.loads(result.strip())
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Playwright 渲染 SVG → PNG
# ═══════════════════════════════════════════════════════════════

def _html_to_png(html: str, dest: str, width: int = 800, height: int = 600, scale: int = 2):
    """用 Playwright 将 HTML 渲染为高清 PNG"""
    tmp = dest + ".html"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)

    try:
        from playwright.sync_api import sync_playwright
        from asset_pipeline import _find_chromium
        with sync_playwright() as p:
            exe = _find_chromium()
            if not exe:
                raise RuntimeError("找不到 Chromium。执行 'playwright install chromium'")
            browser = p.chromium.launch(
                headless=True, executable_path=exe,
                args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-gpu"],
            )
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
            )
            page.goto(f"file://{tmp}", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            page.screenshot(path=dest, full_page=False, clip={
                "x": 0, "y": 0, "width": width, "height": height,
            })
            browser.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _svg_to_png(svg_content: str, dest: str, width: int = 800, height: int = 800, scale: int = 2):
    """用 Playwright 将 SVG 渲染为高清 PNG"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@500;700&family=Noto+Sans+SC:wght@400;700;900&display=swap');
  body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; background: #0B1629; }}
  svg {{ display: block; }}
</style></head><body>{svg_content}</body></html>"""
    _html_to_png(html, dest, width, height, scale)


# ═══════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════

def render_with_template(
    data: dict, params: dict,
    template_id: str,
    dest: str,
) -> bool:
    """用指定模板 + 参数渲染 SVG → PNG"""
    from infographic_templates import get as get_template
    m = get_template(template_id)
    if not m:
        raise ValueError(f"模板 {template_id!r} 不存在")
    svg = m.build(data, params)
    card_w, card_h = 800, 800
    if "viewBox" in svg:
        import re
        m2 = re.search(r'viewBox="\d+\s+\d+\s+(\d+)\s+(\d+)"', svg)
        if m2:
            card_w, card_h = int(m2.group(1)), int(m2.group(2))
    _svg_to_png(svg, dest, width=card_w, height=card_h)
    return os.path.getsize(dest) > 512


def render_flywheel(data: dict, dest: str) -> bool:
    """从 JSON 渲染飞轮 SVG → PNG，返回是否成功"""
    try:
        svg = _build_flywheel_svg(data)
        _svg_to_png(svg, dest, width=800, height=800)
        return os.path.getsize(dest) > 512
    except Exception:
        return False


def render_timeline(data: dict, dest: str) -> bool:
    """从 JSON 渲染时间线 SVG → PNG，返回是否成功"""
    try:
        svg = _build_timeline_svg(data)
        n = len(data.get("events", []))
        total_h = 60 + n * 90 + 40
        _svg_to_png(svg, dest, width=800, height=total_h)
        return os.path.getsize(dest) > 512
    except Exception:
        return False


def generate_flywheel_from_markdown(markdown: str, dest: str, deepseek_call) -> bool:
    """从 Markdown 提取 → 渲染飞轮 PNG"""
    data = extract_flywheel_json(markdown, deepseek_call)
    if not data:
        return False
    return render_flywheel(data, dest)


def generate_timeline_from_markdown(markdown: str, dest: str, deepseek_call) -> bool:
    """从 Markdown 提取 → 渲染时间线 PNG"""
    data = extract_timeline_json(markdown, deepseek_call)
    if not data:
        return False
    return render_timeline(data, dest)


# ═══════════════════════════════════════════════════════════════
# Frappe Charts 散点图（竞争格局 + 生态位）
# ═══════════════════════════════════════════════════════════════

_FRAPPE_CDN_CSS = "https://unpkg.com/frappe-charts@1.6.2/dist/frappe-charts.min.css"
_FRAPPE_CDN_JS = "https://unpkg.com/frappe-charts@1.6.2/dist/frappe-charts.min.iife.js"

_STACK_LABELS = ["Infrastructure", "Foundation Model", "Middleware", "Vertical App", "Distribution"]


def _build_scatter_html(title: str, x_label: str, y_label: str,
                        datasets: list[dict], height: int = 560,
                        params: dict | None = None) -> str:
    """生成 Frappe Charts 散点图 HTML"""
    p = params or {}
    accent = p.get("accent_color", "#29B8D4")
    point_size = p.get("point_size", 5)
    title_size = p.get("title_size", 14)
    axis_size = p.get("axis_size", 11)
    data_json = json.dumps({"datasets": datasets}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="{_FRAPPE_CDN_CSS}">
<style>
  body {{ margin: 0; width: 780px; height: 580px; overflow: hidden;
         background: #0B1629; display: flex; align-items: center; justify-content: center; }}
  #chart {{ width: 760px; height: {height}px; }}
  .frappe-chart .title {{ fill: {accent} !important; font-size: {title_size}px !important; font-weight: 700 !important; }}
  .frappe-chart text {{ fill: rgba(255,255,255,0.55) !important; font-size: {axis_size}px !important; }}
  .frappe-chart .line-vertical, .frappe-chart .line-horizontal {{ stroke: rgba(255,255,255,0.08) !important; }}
  .frappe-chart .dataset-units {{ display: none; }}
  .frappe-chart circle {{ r: {point_size}px; }}
</style></head><body>
<div id="chart"></div>
<script src="{_FRAPPE_CDN_JS}"></script>
<script>
  var data = {data_json};
  data.datasets.forEach(function(ds) {{
    ds.values = ds.values.filter(function(v) {{ return v.x != null && v.y != null; }});
  }});
  new frappe.Chart("#chart", {{
    title: "{title}",
    type: "scatter",
    height: {height},
    data: data,
    axisOptions: {{ xAxisMode: "tick", yAxisMode: "tick", xIsSeries: true }},
    colors: ["{accent}","#7DD3FC","#F9E2AF","#A7F3D0","#C4B5FD","#FDA4AF",
             "rgba(255,255,255,0.25)","rgba(255,255,255,0.20)","rgba(255,255,255,0.18)","rgba(255,255,255,0.15)"],
    maxSlices: 20
  }});
</script></body></html>"""


def build_competitive_landscape_svg(companies: list[dict], highlight: str,
                                     params: dict | None = None) -> str:
    """竞争格局散点图 HTML：Defensibility × Incumbent Attention"""
    highlight_data, other_data = [], []
    for c in companies:
        name = str(c.get("company_name", ""))
        dx = float(c.get("score_defensibility") or 0)
        dy = float(c.get("score_incumbent_attention") or 0)
        if dx == 0 and dy == 0: continue
        (highlight_data if name == highlight else other_data).append({"x": dx, "y": dy, "name": name})
    datasets = []
    if highlight_data: datasets.append({"name": highlight, "values": highlight_data})
    if other_data: datasets.append({"name": "其他公司", "values": other_data})
    return _build_scatter_html("竞争格局矩阵", "Defensibility", "Incumbent Attention", datasets, params=params)


def build_stack_positioning_svg(companies: list[dict], highlight: str,
                                 params: dict | None = None) -> str:
    """生态位散点图 HTML：Stack Layer × Value Capture"""
    highlight_data, other_data = [], []
    st_map = {"infrastructure": 1, "foundation_model": 2, "middleware": 3,
              "vertical_app": 4, "distribution": 5}
    for c in companies:
        name = str(c.get("company_name", ""))
        sx = st_map.get(str(c.get("stack_layer") or "vertical_app"), 3)
        dy = float(c.get("score_value_capture") or 0)
        if dy == 0: continue
        (highlight_data if name == highlight else other_data).append({"x": sx, "y": dy, "name": name})
    datasets = []
    if highlight_data: datasets.append({"name": highlight, "values": highlight_data})
    if other_data: datasets.append({"name": "其他公司", "values": other_data})
    return _build_scatter_html("AI Stack 定位图", "Stack Layer", "Value Capture", datasets, params=params)


def render_competitive_landscape(companies: list[dict], highlight: str, dest: str,
                                  params: dict | None = None) -> bool:
    try:
        html = build_competitive_landscape_svg(companies, highlight, params)
        _html_to_png(html, dest, width=780, height=580, scale=2)
        return os.path.getsize(dest) > 1024
    except Exception:
        return False


def render_stack_positioning(companies: list[dict], highlight: str, dest: str,
                              params: dict | None = None) -> bool:
    try:
        html = build_stack_positioning_svg(companies, highlight, params)
        _html_to_png(html, dest, width=780, height=580, scale=2)
        return os.path.getsize(dest) > 1024
    except Exception:
        return False
