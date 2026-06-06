"""信息图渲染 — 增长飞轮 + 发展时间线

流程：LLM 生成结构化 JSON → SVG 模板确定性绘图 → Playwright 截成 PNG
"""
from __future__ import annotations
import functools
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
    <marker id="arrowhead" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
      <polygon points="0,0 10,4 0,8" fill="#29B8D4" opacity="0.6"/>
    </marker>
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
            # Wait for web fonts to load (Google Fonts for SVG; ECharts uses system fonts)
            try:
                page.wait_for_function("document.fonts && document.fonts.ready", timeout=5000)
            except Exception:
                pass
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
    # NOTE: Google Fonts require network access; domestic deployments may need HTTPS_PROXY
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
# ECharts 散点图 — 竞争格局矩阵 + 产业链生态位图
# ═══════════════════════════════════════════════════════════════

_ECHARTS_VENDOR_PATH = os.path.join(
    os.path.dirname(__file__), "static", "vendor", "echarts.min.js"
)


@functools.lru_cache(maxsize=1)
def _echarts_inline_js() -> str:
    """读取并缓存本地 ECharts JS，供 srcdoc/file:// 渲染路径内联使用。"""
    with open(_ECHARTS_VENDOR_PATH, encoding="utf-8") as f:
        return f.read()


def _echarts_script_tag() -> str:
    """Always use vendored ECharts (CLAUDE.md: 散点图用本地 vendor echarts)."""
    return f"<script>{_echarts_inline_js()}</script>"

_STACK_LABELS = ["基础设施", "基础模型", "中间件", "垂直应用", "分发渠道"]
_STACK_LAYER_COLORS = ["#4FC3F7", "#BA68C8", "#FFB74D", "#81C784", "#E57373"]


def _chart_empty_html(title: str, message: str = "暂无可用图表数据",
                      params: dict | None = None) -> str:
    p = params or {}
    theme = p.get("theme", "dark")
    bg = "#0B1629" if theme == "dark" else "#fff"
    text_color = "#fff" if theme == "dark" else "#1B2A4A"
    muted = "rgba(255,255,255,0.52)" if theme == "dark" else "#64748b"
    accent = p.get("accent_color", "#29B8D4")
    safe_title = _html_escape(p.get("title") or title)
    safe_message = _html_escape(message)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body{{margin:0;width:800px;height:600px;overflow:hidden;background:{bg};
    font-family:'Instrument Sans','Noto Sans SC','PingFang SC',sans-serif;color:{text_color}}}
  .wrap{{width:800px;height:600px;display:flex;align-items:center;justify-content:center;position:relative}}
  .grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(41,184,212,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(41,184,212,.08) 1px,transparent 1px);background-size:40px 40px;opacity:.35}}
  .panel{{position:relative;text-align:center;border:1px solid rgba(41,184,212,.28);border-radius:8px;padding:34px 48px;background:rgba(255,255,255,.035)}}
  h1{{margin:0 0 12px;font-size:22px;letter-spacing:0;color:{text_color}}}
  p{{margin:0;color:{muted};font-size:14px}}
  .bar{{width:72px;height:2px;background:{accent};margin:0 auto 18px}}
</style></head><body>
<div class="wrap"><div class="grid"></div><div class="panel"><div class="bar"></div><h1>{safe_title}</h1><p>{safe_message}</p></div></div>
</body></html>"""


def _html_escape(value: object) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _echarts_fit_style(bg: str) -> str:
    return f"""
  html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{bg}}}
  body{{display:flex;align-items:center;justify-content:center}}
  #chart-frame{{width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden;background:{bg}}}
  #chart{{width:800px;height:600px;flex:0 0 auto;transform-origin:center center}}
  #chart>div:first-child,#chart>div:first-child>canvas{{transform-origin:center center}}
  #chart>div:first-child>canvas{{display:block;width:100%!important;height:100%!important;object-fit:contain}}
"""


def _echarts_fit_script(chart_var: str = "chart") -> str:
    return f"""
function fitChartCanvas(){{
  var frame=document.getElementById('chart-frame');
  var chartEl=document.getElementById('chart');
  if(!frame||!chartEl) return;
  var scale=Math.min(frame.clientWidth/800, frame.clientHeight/600);
  if(!isFinite(scale)||scale<=0) scale=1;
  chartEl.style.transform='scale('+scale+')';
  if({chart_var}&&{chart_var}.resize) {chart_var}.resize();
}}
window.addEventListener('resize', fitChartCanvas);
fitChartCanvas();
"""


def _build_competitive_landscape_html(
    companies: list[dict], highlight: str,
    params: dict | None = None,
) -> str:
    """竞争格局矩阵 HTML — 四象限 + 气泡大小按融资阶段缩放 + 主公司高亮"""
    p = params or {}
    accent = p.get("accent_color", "#29B8D4")
    pt_base = p.get("point_size", 14)
    t_size = p.get("title_size", 22)
    a_size = p.get("axis_size", 15)
    theme = p.get("theme", "dark")
    show_label = p.get("show_label", False)

    hi_data, ot_data = [], []
    for c in companies:
        n = str(c.get("company_name", ""))
        dx = float(c.get("score_defensibility") or 0)
        dy = float(c.get("score_incumbent_attention") or 0)
        if dx == 0 and dy == 0:
            continue
        fs = float(c.get("funding_stage_score") or 0)
        sz = max(6, fs * 4 + 6) if fs > 0 else pt_base
        (hi_data if n == highlight else ot_data).append({
            "name": n, "value": [dx, dy, sz, n],
        })
    ds_json = json.dumps([
        {"name": highlight, "data": hi_data},
        {"name": "其他公司", "data": ot_data},
    ], ensure_ascii=False)
    no_data_graphic = "" if (hi_data or ot_data) else f""",
    {{type:'text',left:'center',top:'middle',style:{{text:{json.dumps("暂无可用图表数据", ensure_ascii=False)},fill:'{accent}',fontSize:18,fontWeight:700,textAlign:'center'}}}}"""

    bg = "#0B1629" if theme == "dark" else "#fff"
    text_color = "#fff" if theme == "dark" else "#333"
    muted = "rgba(255,255,255,0.5)" if theme == "dark" else "#999"
    line_color = "rgba(255,255,255,0.12)" if theme == "dark" else "#e0e0e0"
    quad_label_color = "rgba(255,255,255,0.18)" if theme == "dark" else "rgba(0,0,0,0.08)"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_echarts_fit_style(bg)}
</style></head><body>
<div id="chart-frame"><div id="chart"></div></div>
{_echarts_script_tag()}
<script>
var ds={ds_json};
var hiName={json.dumps(highlight, ensure_ascii=False)};
var series=ds.map(function(d){{
  return{{
    name:d.name, type:'scatter', data:d.data,
    symbolSize:function(val){{return val[2]||{pt_base};}},
    label:{{
      show:function(p){{return p.value[3]===hiName;}},
      formatter:function(p){{return p.value[3]||'';}},
      fontSize:{p.get("label_size", 16)},
      fontWeight:700,
      color:'{accent}',
      position:'right',
      distance:8,
    }},
    labelLayout:{{hideOverlap:true}},
    emphasis:{{focus:'series'}},
    itemStyle:{{borderColor:'rgba(0,0,0,0.3)',borderWidth:0.5}},
  }};
}});
// 主公司用 accent 色，其他用灰色系
series[0].itemStyle=series[0].itemStyle||{{}};
series[0].itemStyle.color='{accent}';
if(series[1]) series[1].itemStyle.color='rgba(255,255,255,0.25)';

var opt={{
  title:{{text:{json.dumps(p.get("title") or "竞争格局矩阵", ensure_ascii=False)},subtext:{json.dumps(p.get("subtitle") or "", ensure_ascii=False)},left:'center',textStyle:{{color:'{text_color}',fontSize:{t_size},fontWeight:700}},subtextStyle:{{color:'{muted}',fontSize:13}}}},
  tooltip:{{
    formatter:function(p){{return p.value[3]+'<br/>Defensibility: '+p.value[0]+'<br/>Incumbent Attention: '+p.value[1];}}
  }},
  legend:{{show:false}},
  grid:{{left:70,right:40,top:60,bottom:50}},
  xAxis:{{
    name:'Defensibility', min:0, max:10,
    nameTextStyle:{{color:'{muted}',fontSize:{a_size}}},
    axisLine:{{lineStyle:{{color:'{line_color}'}}}},
    splitLine:{{lineStyle:{{color:'rgba(255,255,255,0.06)'}}}},
    splitNumber:10,
  }},
  yAxis:{{
    name:'Incumbent Attention', min:0, max:10,
    nameTextStyle:{{color:'{muted}',fontSize:{a_size}}},
    axisLine:{{lineStyle:{{color:'{line_color}'}}}},
    splitLine:{{lineStyle:{{color:'rgba(255,255,255,0.06)'}}}},
    splitNumber:10,
  }},
  backgroundColor:'{bg}',
  color:["{accent}","#7DD3FC","#F9E2AF","#A7F3D0","#C4B5FD","#FDA4AF"],
  series: series,
  graphic:[
    {{type:'text',left:62,top:52,style:{{text:{json.dumps(p.get("quadrant_tl") or "Sweet Spot", ensure_ascii=False)},fill:'{quad_label_color}',fontSize:13,fontWeight:600}}}},
    {{type:'text',right:32,top:52,style:{{text:{json.dumps(p.get("quadrant_tr") or "Kill Zone", ensure_ascii=False)},fill:'{quad_label_color}',fontSize:13,fontWeight:600}}}},
    {{type:'text',left:62,bottom:42,style:{{text:{json.dumps(p.get("quadrant_bl") or "Waiting Room", ensure_ascii=False)},fill:'{quad_label_color}',fontSize:13,fontWeight:600}}}},
    {{type:'text',right:32,bottom:42,style:{{text:{json.dumps(p.get("quadrant_br") or "Battlefield", ensure_ascii=False)},fill:'{quad_label_color}',fontSize:13,fontWeight:600}}}}{no_data_graphic},
  ],
}};
// 四象限分割线：加在首个 series 上（ECharts markLine 必须在 series 内，不能在 opt 顶层）
if (series[0]) {{
  series[0].markLine = {{
    silent:true, symbol:'none',
    lineStyle:{{color:'rgba(255,255,255,0.15)',type:'dashed',width:1}},
    data:[
      {{xAxis:5,label:{{show:false}}}},
      {{yAxis:5,label:{{show:false}}}},
    ],
  }};
}}
var chart=echarts.init(document.getElementById('chart'));
chart.setOption(opt);
{_echarts_fit_script("chart")}
</script></body></html>"""


def _build_ecosystem_positioning_html(
    companies: list[dict], highlight: str,
    params: dict | None = None,
) -> str:
    """产业链生态位图 HTML — 离散X轴中文标签 + 层级颜色 + 高价值截留区"""
    p = params or {}
    accent = p.get("accent_color", "#29B8D4")
    pt_base = p.get("point_size", 14)
    t_size = p.get("title_size", 22)
    a_size = p.get("axis_size", 15)
    theme = p.get("theme", "dark")
    show_label = p.get("show_label", False)

    st_map = {"infrastructure": 0, "foundation_model": 1, "middleware": 2, "vertical_app": 3, "distribution": 4}
    st_labels = _STACK_LABELS
    st_colors = _STACK_LAYER_COLORS

    # 按 stack_layer 分组
    groups = {label: [] for label in st_labels}
    for c in companies:
        n = str(c.get("company_name", ""))
        sl = str(c.get("stack_layer") or "vertical_app")
        sx = st_map.get(sl, 3)
        dy = float(c.get("score_value_capture") or 0)
        if dy == 0:
            continue
        fs = float(c.get("funding_stage_score") or 0)
        sz = max(6, fs * 4 + 6) if fs > 0 else pt_base
        label = st_labels[sx] if 0 <= sx < len(st_labels) else st_labels[3]
        groups[label].append({
            "name": n, "value": [sx, dy, sz, n],
            "is_highlight": n == highlight,
        })
    ds = []
    for idx, label in enumerate(st_labels):
        items = groups[label]
        if not items:
            continue
        ds.append({
            "name": label,
            "data": items,
            "color": st_colors[idx] if idx < len(st_colors) else "#81C784",
        })

    ds_json = json.dumps(ds, ensure_ascii=False)
    no_data_graphic = "" if ds else f"{{type:'text',left:'center',top:'middle',style:{{text:{json.dumps('暂无可用图表数据', ensure_ascii=False)},fill:'{accent}',fontSize:18,fontWeight:700,textAlign:'center'}}}}"
    bg = "#0B1629" if theme == "dark" else "#fff"
    text_color = "#fff" if theme == "dark" else "#333"
    muted = "rgba(255,255,255,0.5)" if theme == "dark" else "#999"
    line_color = "rgba(255,255,255,0.12)" if theme == "dark" else "#e0e0e0"
    hi_color = accent
    hi_border = "rgba(255,255,255,0.6)"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_echarts_fit_style(bg)}
</style></head><body>
<div id="chart-frame"><div id="chart"></div></div>
{_echarts_script_tag()}
<script>
var ds={ds_json};
var hiName={json.dumps(highlight, ensure_ascii=False)};
var series=ds.map(function(d){{
  return{{
    name:d.name, type:'scatter', data:d.data,
    symbolSize:function(val){{return val[2]||{pt_base};}},
    label:{{
      show:true,
      formatter:function(p){{return (p.data&&p.data.is_highlight)?(p.value[3]||''):'';}},
      fontSize:{p.get("label_size", 16)},
      fontWeight:700,
      color:'{accent}',
      position:'top',
      distance:10,
    }},
    labelLayout:{{hideOverlap:true}},
    emphasis:{{focus:'series'}},
    itemStyle:{{
      color:d.color,
      borderColor:function(p){{return p.dataIndex!=null&&d.data[p.dataIndex]&&d.data[p.dataIndex].is_highlight?'{hi_border}':'rgba(0,0,0,0.3)';}},
      borderWidth:function(p){{return p.dataIndex!=null&&d.data[p.dataIndex]&&d.data[p.dataIndex].is_highlight?2.5:0.5;}},
    }},
  }};
}});

var opt={{
  title:{{text:{json.dumps(p.get("title") or "AI Stack 定位图", ensure_ascii=False)},subtext:{json.dumps(p.get("subtitle") or "", ensure_ascii=False)},left:'center',textStyle:{{color:'{text_color}',fontSize:{t_size},fontWeight:700}},subtextStyle:{{color:'{muted}',fontSize:13}}}},
  tooltip:{{
    formatter:function(p){{return p.value[3]+'<br/>Stack: '+p.seriesName+'<br/>Value Capture: '+p.value[1];}}
  }},
  legend:{{show:false}},
  grid:{{left:70,right:40,top:60,bottom:50}},
  xAxis:{{
    name:'Stack Layer', type:'category',
    data:{json.dumps(st_labels, ensure_ascii=False)},
    nameTextStyle:{{color:'{muted}',fontSize:{a_size}}},
    axisLine:{{lineStyle:{{color:'{line_color}'}}}},
    axisLabel:{{color:'{muted}',fontSize:11}},
    splitLine:{{show:false}},
  }},
  yAxis:{{
    name:'Value Capture', min:0, max:10,
    nameTextStyle:{{color:'{muted}',fontSize:{a_size}}},
    axisLine:{{lineStyle:{{color:'{line_color}'}}}},
    splitLine:{{lineStyle:{{color:'rgba(255,255,255,0.06)'}}}},
    splitNumber:10,
  }},
  backgroundColor:'{bg}',
  series: series,
  graphic:[{no_data_graphic}],
}};
// 高价值截留区（y≥阈值）：markLine + markArea 加在首个 series 上
if (series[0]) {{
  series[0].markLine = {{
    silent:true, symbol:'none',
    data:[
      {{yAxis:{float(p.get("value_threshold") or 7)},label:{{show:true,formatter:{json.dumps("高价值截留区 ≥" + str(p.get("value_threshold") or 7), ensure_ascii=False)},position:'end',color:'{muted}',fontSize:10}},lineStyle:{{color:'rgba(129,199,132,0.3)',type:'dashed',width:1.5}}}},
    ],
  }};
  series[0].markArea = {{
    silent:true,
    data:[[
      {{yAxis:{float(p.get("value_threshold") or 7)},itemStyle:{{color:'rgba(129,199,132,0.05)'}}}},
      {{yAxis:10}},
    ]],
  }};
}};
var chart=echarts.init(document.getElementById('chart'));
chart.setOption(opt);
{_echarts_fit_script("chart")}
</script></body></html>"""


def build_competitive_landscape_svg(companies: list[dict], highlight: str,
                                     params: dict | None = None) -> str:
    """竞争格局矩阵 HTML（ECharts 四象限散点图）"""
    return _build_competitive_landscape_html(companies, highlight, params)


def build_stack_positioning_svg(companies: list[dict], highlight: str,
                                 params: dict | None = None) -> str:
    """产业链生态位图 HTML（ECharts 离散轴散点图）"""
    return _build_ecosystem_positioning_html(companies, highlight, params)


def render_competitive_landscape(companies: list[dict], highlight: str, dest: str,
                                  params: dict | None = None) -> bool:
    try:
        html = build_competitive_landscape_svg(companies, highlight, params)
        _html_to_png(html, dest, width=800, height=600, scale=2)
        return os.path.getsize(dest) > 1024
    except Exception:
        return False


def render_stack_positioning(companies: list[dict], highlight: str, dest: str,
                              params: dict | None = None) -> bool:
    try:
        html = build_stack_positioning_svg(companies, highlight, params)
        _html_to_png(html, dest, width=800, height=600, scale=2)
        return os.path.getsize(dest) > 1024
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 飞轮 / 时间线渲染（SVG 模板 → Playwright PNG）
# ═══════════════════════════════════════════════════════════════

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
