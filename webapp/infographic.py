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
        # 清理 markdown 代码块（兼容带/不带 trailing 空行的 LLM 输出）
        result = result.strip()
        if result.startswith("```"):
            lines = result.splitlines()
            lines = lines[1:]                          # 去掉 ```json 行
            if lines and lines[-1].strip() == "```":   # 去掉结尾 ``` 行（即使后有空格）
                lines = lines[:-1]
            result = "\n".join(lines)
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
            lines = result.splitlines()
            lines = lines[1:]                          # 去掉 ```json 行
            if lines and lines[-1].strip() == "```":   # 去掉结尾 ``` 行（即使后有空格）
                lines = lines[:-1]
            result = "\n".join(lines)
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


def normalize_group_scores(
    companies: list[dict],
    raw_keys: list[str],
    *,
    suffix: str = "_norm",
    neutral: float = 0.5,
) -> tuple[list[dict], dict]:
    """非破坏式归一化：为每个 raw_key 新增 _norm 字段 (0..1)，原始字段不覆盖。"""
    meta = {"ranges": {}, "all_equal_keys": []}
    out = [dict(c) for c in companies]
    for key in raw_keys:
        vals = [float(c[key]) for c in out if c.get(key) is not None]
        if not vals:
            meta["ranges"][key] = {"min": None, "max": None}
            for c in out:
                c[f"{key}{suffix}"] = None
            continue
        lo, hi = min(vals), max(vals)
        meta["ranges"][key] = {"min": lo, "max": hi}
        if hi == lo:
            meta["all_equal_keys"].append(key)
            for c in out:
                c[f"{key}{suffix}"] = neutral if c.get(key) is not None else None
            continue
        for c in out:
            raw = c.get(key)
            c[f"{key}{suffix}"] = round((float(raw) - lo) / (hi - lo), 3) if raw is not None else None
    return out, meta


def _truncate_label(name: str, max_chars: int = 6) -> str:
    name = (name or "").strip()
    return name if len(name) <= max_chars else f"{name[:max_chars]}…"


def _point_priority(points: list[dict], target_company: str, max_companies: int) -> list[dict]:
    """确保 target 排第一，并截断到 max_companies。按 company_name 去重。"""
    target_key = (target_company or "").strip().lower()
    seen = set()
    keep = []
    for p in points:
        key = (p.get("company_name") or "").strip().lower()
        if key == target_key:
            keep.append(p)
            seen.add(key)
            break
    for p in points:
        key = (p.get("company_name") or "").strip().lower()
        if key not in seen:
            seen.add(key)
            keep.append(p)
        if len(keep) >= max_companies:
            break
    return keep



def _echarts_inline_js() -> str:
    """读取并缓存本地 ECharts JS，供 srcdoc/file:// 渲染路径内联使用。"""
    with open(_ECHARTS_VENDOR_PATH, encoding="utf-8") as f:
        return f.read()


def _echarts_script_tag() -> str:
    """Always use vendored ECharts (CLAUDE.md: 散点图用本地 vendor echarts)."""
    return f"<script>{_echarts_inline_js()}</script>"

# ── 辅助函数 ──

def _score(value, default=5.0) -> float:
    """安全读取评分值，钳制在 0–10。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(10.0, v))


def _map_stack_layer(value: str) -> str:
    """将 stack_layer 枚举值（英文/中文兼容）映射到 4 条泳道标签。"""
    mapping = {
        "vertical_app": "应用层",
        "distribution": "应用层",
        "middleware": "中间件层",
        "foundation_model": "模型层",
        "infrastructure": "基础设施层",
        "垂直应用": "应用层",
        "分发渠道": "应用层",
        "中间件": "中间件层",
        "基础模型": "模型层",
        "基础设施": "基础设施层",
        "应用层": "应用层",
        "中间件层": "中间件层",
        "模型层": "模型层",
        "基础设施层": "基础设施层",
    }
    return mapping.get(str(value or ""), "应用层")


# 产业链泳道（从上到下：应用→基础）
_STACK_LANE_LABELS = ["应用层", "中间件层", "模型层", "基础设施层"]

# 泳道层级说明文字（Y 轴左侧，空间不足时可省略）
_STACK_LANE_DESC = {
    "应用层": "直接面向终端用户",
    "中间件层": "连接模型与业务场景",
    "模型层": "提供核心智能能力",
    "基础设施层": "算力、数据与底层平台",
}


def _chart_empty_html(title: str, message: str = "暂无可用图表数据",
                      params: dict | None = None) -> str:
    p = params or {}
    theme = p.get("theme", "light")
    w = int(p.get("width") or 900)
    h = int(p.get("height") or 600)
    bg = "#0B1629" if theme == "dark" else "#FFFFFF"
    text_color = "#E8ECF1" if theme == "dark" else "#1B2A4A"
    muted = "rgba(255,255,255,0.52)" if theme == "dark" else "#64748b"
    accent = p.get("accent_color", "#29B8D4")
    safe_title = _html_escape(p.get("title") or title)
    safe_message = _html_escape(message)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg};
    font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;color:{text_color}}}
  .wrap{{width:{w}px;height:{h}px;display:flex;align-items:center;justify-content:center;position:relative}}
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


def _echarts_fit_style(bg: str, width: int = 900, height: int = 600) -> str:
    return f"""
  html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:{bg};
    font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;}}
  body{{position:relative}}
  #chart-frame{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden;background:{bg}}}
  #chart{{width:{width}px;height:{height}px;flex:0 0 auto;transform-origin:center center}}
  #chart>div:first-child,#chart>div:first-child>canvas{{transform-origin:center center}}
  #chart>div:first-child>canvas{{display:block;width:100%!important;height:100%!important;object-fit:contain}}
"""


def _echarts_fit_script(chart_var: str = "chart",
                        width: int = 900, height: int = 600) -> str:
    return f"""
function fitChartCanvas(){{
  var frame=document.getElementById('chart-frame');
  var chartEl=document.getElementById('chart');
  if(!frame||!chartEl) return;
  var scale=Math.min(frame.clientWidth/{width}, frame.clientHeight/{height});
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
    """竞争格局定位图 HTML — markArea 象限背景 + 目标公司高亮 + 中文轴名 + 归一化 0-1 轴。

    X 轴 = score_incumbent_attention_norm（巨头竞争压力，组内 0-1）
    Y 轴 = score_defensibility_norm（护城河强度，组内 0-1）
    Tooltip 同时显示归一化 (0-1) 与原始 (0-10) 分数。
    """
    p = dict(params or {})
    p.setdefault("title", "竞争格局定位图")
    p.setdefault("subtitle", "组内相对排名，Tooltip 保留原始 0–10 分")
    p.setdefault("max_companies", 12)
    p.setdefault("show_all_labels_threshold", 12)
    accent = p.get("accent_color", "#29B8D4")
    width = int(p.get("width") or 900)
    height = int(p.get("height") or 600)
    t_size = int(p.get("title_size") or 16)
    a_size = int(p.get("axis_size") or 12)
    l_size = int(p.get("label_size") or 13)
    theme = p.get("theme", "light")
    max_cos = int(p.get("max_companies", 12))
    label_threshold = int(p.get("show_all_labels_threshold", 12))

    bg = "#FFFFFF" if theme == "light" else "#0B1629"
    text_color = "#1B2A4A" if theme == "light" else "#E8ECF1"
    muted = "#6B7280" if theme == "light" else "rgba(255,255,255,0.55)"
    line_color = "#E5E7EB" if theme == "light" else "rgba(255,255,255,0.10)"
    q_bg_alpha = "0.12" if theme == "light" else "0.10"
    q_label_color = "rgba(0,0,0,0.35)" if theme == "light" else "rgba(255,255,255,0.28)"

    # 域过滤 + 归一化
    domain = [
        c for c in companies
        if c.get("score_defensibility") is not None
        and c.get("score_incumbent_attention") is not None
    ]
    domain = _point_priority(domain, highlight, max_cos)
    normed, _norm_meta = normalize_group_scores(
        domain, ["score_defensibility", "score_incumbent_attention"],
    )

    # 构建数据点（is_highlight + raw/norm 双字段）
    points = []
    for c in normed:
        n = str(c.get("display_name") or c.get("company_name") or "")
        is_hi = (c.get("company_name") or "").strip().lower() == highlight.strip().lower()
        x_norm = c.get("score_incumbent_attention_norm")
        y_norm = c.get("score_defensibility_norm")
        x_raw = c.get("score_incumbent_attention")
        y_raw = c.get("score_defensibility")
        fs = _score(c.get("funding_stage_score"))
        show_label = is_hi or (len(points) < label_threshold)
        points.append({
            "name": n,
            "value": [x_norm if x_norm is not None else 0.5, y_norm if y_norm is not None else 0.5, fs],
            "x_raw": x_raw, "y_raw": y_raw,
            "is_highlight": is_hi,
            "show_label": show_label,
        })

    no_data = not points
    ds_json = json.dumps(points, ensure_ascii=False)
    title_text = json.dumps(p.get("title"), ensure_ascii=False)
    subtitle_text = json.dumps(p.get("subtitle", ""), ensure_ascii=False)
    highlight_json = json.dumps(highlight, ensure_ascii=False)

    result = '<!DOCTYPE html>\n'
    result += '<html><head><meta charset="utf-8">\n<style>\n'
    result += _echarts_fit_style(bg, width, height)
    result += '\n</style></head><body>\n'
    result += '<div id="chart-frame"><div id="chart"></div></div>\n'
    result += _echarts_script_tag() + '\n<script>\n'
    result += 'var points=' + ds_json + ';\n'
    result += 'var hiName=' + highlight_json + ';\n'
    result += 'var series=[{\n'
    result += '  type:"scatter", data:points,\n'
    result += '  symbolSize:function(val,params){\n'
    result += '    var base=10+val[2]*2;\n'
    result += '    return params.data&&params.data.is_highlight?base*1.5:base;\n'
    result += '  },\n'
    result += '  itemStyle:{\n'
    result += '    color:function(params){return params.data&&params.data.is_highlight?"' + accent + '":"#1B2A4A";},\n'
    result += '    opacity:function(params){return params.data&&params.data.is_highlight?1:0.5;},\n'
    result += '    borderColor:function(params){return params.data&&params.data.is_highlight?"#FFFFFF":"transparent";},\n'
    result += '    borderWidth:function(params){return params.data&&params.data.is_highlight?2:0;},\n'
    result += '  },\n'
    result += '  label:{\n'
    result += '    show:true,\n'
    result += '    formatter:function(params){return params.data&&params.data.show_label?params.data.name:"";},\n'
    result += '    fontSize:' + str(l_size) + ',fontWeight:"bold",color:"#1B2A4A",\n'
    result += '    backgroundColor:"rgba(255,255,255,0.92)",borderRadius:4,padding:[3,6],\n'
    result += '    position:"right",\n'
    result += '  },\n'
    result += '  labelLayout:{hideOverlap:true,moveOverlap:"shiftY"},\n'
    result += '  markLine:{\n'
    result += '    silent:true,symbol:"none",\n'
    result += '    lineStyle:{type:"dashed",color:"rgba(27,42,74,0.18)",width:1},\n'
    result += '    data:[{xAxis:0.5,label:{show:false}},{yAxis:0.5,label:{show:false}}],\n'
    result += '  },\n'
    result += '  markArea:{\n'
    result += '    silent:true,\n'
    result += '    data:[\n'
    result += '      [{xAxis:0,yAxis:0.5,itemStyle:{color:"rgba(40,200,120,' + q_bg_alpha + ')"}},{xAxis:0.5,yAxis:1}],\n'
    result += '      [{xAxis:0.5,yAxis:0.5,itemStyle:{color:"rgba(255,140,0,' + q_bg_alpha + ')"}},{xAxis:1,yAxis:1}],\n'
    result += '      [{xAxis:0.5,yAxis:0,itemStyle:{color:"rgba(220,50,50,' + q_bg_alpha + ')"}},{xAxis:1,yAxis:0.5}],\n'
    result += '      [{xAxis:0,yAxis:0,itemStyle:{color:"rgba(180,180,180,' + q_bg_alpha + ')"}},{xAxis:0.5,yAxis:0.5}],\n'
    result += '    ],\n'
    result += '  },\n'
    result += '}];\n\n'
    result += 'var opt={\n'
    result += '  animation:false,\n'
    result += '  backgroundColor:"' + bg + '",\n'
    result += '  title:{text:' + title_text + ',subtext:' + subtitle_text + ',left:24,top:18,\n'
    result += '    textStyle:{color:"' + text_color + '",fontSize:' + str(t_size) + ',fontWeight:"bold"},\n'
    result += '    subtextStyle:{color:"' + muted + '",fontSize:10}},\n'
    result += '  tooltip:{trigger:"item",\n'
    result += '    formatter:function(p){\n'
    result += '      var d=p.data||{};\n'
    result += '      var rm=10;\n'
    result += '      return "<b>"+d.name+"</b><br/>"\n'
    result += '        +"护城河（相对）："+(d.y_raw!=null?p.value[1].toFixed(3):"-")+"<br/>"\n'
    result += '        +"护城河（原始）："+(d.y_raw!=null?(d.y_raw+" / "+rm):"-")+"<br/>"\n'
    result += '        +"巨头竞争压力（相对）："+(d.x_raw!=null?p.value[0].toFixed(3):"-")+"<br/>"\n'
    result += '        +"巨头竞争压力（原始）："+(d.x_raw!=null?(d.x_raw+" / "+rm):"-");\n'
    result += '    }\n'
    result += '  },\n'
    result += '  legend:{show:false},\n'
    result += '  grid:{left:68,right:28,top:70,bottom:80},\n'
    result += '  xAxis:{\n'
    result += '    type:"value",min:0,max:1,scale:false,boundaryGap:false,\n'
    result += '    name:"巨头竞争压力 →",nameLocation:"middle",nameGap:32,\n'
    result += '    nameTextStyle:{color:"' + text_color + '",fontSize:15,fontWeight:"bold"},\n'
    result += '    axisLine:{lineStyle:{color:"' + line_color + '"}},\n'
    result += '    axisLabel:{color:"' + muted + '",fontSize:9},\n'
    result += '    splitLine:{lineStyle:{color:"' + line_color + '",type:"dashed"}},\n'
    result += '    splitNumber:5,\n'
    result += '  },\n'
    result += '  yAxis:{\n'
    result += '    type:"value",min:0,max:1,scale:false,boundaryGap:false,\n'
    result += '    name:"护城河强度 ↑",nameLocation:"middle",nameGap:44,\n'
    result += '    nameTextStyle:{color:"' + text_color + '",fontSize:15,fontWeight:"bold"},\n'
    result += '    axisLine:{lineStyle:{color:"' + line_color + '"}},\n'
    result += '    axisLabel:{color:"' + muted + '",fontSize:9},\n'
    result += '    splitLine:{lineStyle:{color:"' + line_color + '",type:"dashed"}},\n'
    result += '    splitNumber:5,\n'
    result += '  },\n'
    # quadrant labels — computed from grid to scale with any width/height
    grid_left, grid_right, grid_top, grid_bottom = 68, 28, 70, 80
    px_start = grid_left
    px_end = width - grid_right
    py_start = grid_top
    py_end = height - grid_bottom
    q_left = int(px_start + (px_end - px_start) * 0.25)
    q_right = int(px_start + (px_end - px_start) * 0.75)
    q_top = int(py_start + (py_end - py_start) * 0.25)
    q_bottom = int(py_start + (py_end - py_start) * 0.75)
    result += '  series:series,\n'
    result += '  graphic:[\n'
    result += '    {type:"text",left:' + str(q_left) + ',top:' + str(q_top) + ',style:{text:"战略机会区",fill:"' + q_label_color + '",fontSize:15,fontWeight:"bold",textAlign:"center",textVerticalAlign:"middle"}},\n'
    result += '    {type:"text",left:' + str(q_right) + ',top:' + str(q_top) + ',style:{text:"竞争激烈区",fill:"' + q_label_color + '",fontSize:15,fontWeight:"bold",textAlign:"center",textVerticalAlign:"middle"}},\n'
    result += '    {type:"text",left:' + str(q_right) + ',top:' + str(q_bottom) + ',style:{text:"高压险境区",fill:"' + q_label_color + '",fontSize:15,fontWeight:"bold",textAlign:"center",textVerticalAlign:"middle"}},\n'
    result += '    {type:"text",left:' + str(q_left) + ',top:' + str(q_bottom) + ',style:{text:"边缘观望区",fill:"' + q_label_color + '",fontSize:15,fontWeight:"bold",textAlign:"center",textVerticalAlign:"middle"}},\n'
    result += '    {type:"text",left:84,bottom:18,style:{text:"● 目标公司    ○ 竞争对手",fill:"' + muted + '",fontSize:13}},\n'
    if no_data:
        result += '    {type:"text",left:"center",top:"middle",style:{text:"暂无可用图表数据",fill:"' + muted + '",fontSize:18,fontWeight:700,textAlign:"center"}}\n'
    result += '  ],\n'
    result += '};\n'
    result += "var chart=echarts.init(document.getElementById('chart'));\n"
    result += "chart.setOption(opt);\n"
    result += _echarts_fit_script("chart", width, height) + '\n'
    result += "</script></body></html>"

    return result



def _score_level(score: float) -> str:
    """将原始 0-10 评分映射为低/中/高。"""
    if score is None:
        return "?"
    if score < 4:
        return "低"
    if score < 7:
        return "中"
    return "高"


def _find_highlight_point(points: list[dict], highlight: str) -> dict | None:
    """在 points 列表中查找目标公司数据点。"""
    hl = (highlight or "").strip().lower()
    for p in points:
        if p.get("is_highlight"):
            return p
    for p in points:
        if (p.get("name") or "").strip().lower() == hl:
            return p
    return None


def _build_ecosystem_positioning_html(
    companies: list[dict], highlight: str,
    params: dict | None = None,
) -> str:
    """AI 栈生态位图 HTML — 动态结论标题 + 归一化 0-1 X 轴 + category Y 轴泳道。

    X 轴 = score_value_capture_norm（价值捕获率，组内 0-1）
    Y 轴 = stack_layer 映射到 4 条泳道（category）
    """
    p = dict(params or {})
    p.setdefault("title", "AI 栈生态位图")
    p.setdefault("max_companies", 12)
    accent = p.get("accent_color", "#29B8D4")
    width = int(p.get("width") or 1440)
    height = int(p.get("height") or 900)
    t_size = int(p.get("title_size") or 26)
    a_size = int(p.get("axis_size") or 15)
    l_size = int(p.get("label_size") or 17)
    theme = p.get("theme", "light")
    max_cos = int(p.get("max_companies", 12))

    bg = "#FFFFFF" if theme == "light" else "#0B1629"
    text_color = "#1B2A4A" if theme == "light" else "#E8ECF1"
    muted = "#6B7280" if theme == "light" else "rgba(255,255,255,0.55)"
    line_color = "#E5E7EB" if theme == "light" else "rgba(255,255,255,0.10)"

    # -- 数据：归一化 0-1 --
    domain = [
        c for c in companies
        if c.get("score_value_capture") is not None
        and c.get("stack_layer") is not None
    ]
    domain = _point_priority(domain, highlight, max_cos)
    normed, _norm_meta = normalize_group_scores(domain, ["score_value_capture"])

    points = []
    for c in normed:
        n = str(c.get("display_name") or c.get("company_name") or "")
        sx_norm = c.get("score_value_capture_norm")
        sx_raw = c.get("score_value_capture")
        sl = _map_stack_layer(c.get("stack_layer"))
        is_hi = (c.get("company_name") or "").strip().lower() == highlight.strip().lower()
        points.append({
            "name": n,
            "value": [sx_norm if sx_norm is not None else 0.5, sl, 5.0],
            "x_raw": sx_raw,
            "is_highlight": is_hi,
            "show_label": is_hi,
        })

    # -- 动态标题 --
    target = _find_highlight_point(points, highlight)
    if target:
        raw_x = target.get("x_raw")
        level = _score_level(raw_x) if raw_x is not None else "?"
        layer = target["value"][1]
        title_text = f"{target['name']}：{layer} / {level}价值捕获"
        target_layer = layer
        target_level = level
        target_coord = [float(target["value"][0]), layer]
    else:
        title_text = p.get("title")
        target_layer = ""
        target_level = ""
        target_coord = None

    subtitle = p.get("subtitle") or "越往右，越能在产业链里赚到钱"

    no_data = not points
    ds_json = json.dumps(points, ensure_ascii=False)
    title_json = json.dumps(title_text, ensure_ascii=False)
    subtitle_json = json.dumps(subtitle, ensure_ascii=False)
    lanes_json = json.dumps(_STACK_LANE_LABELS, ensure_ascii=False)
    highlight_json = json.dumps(highlight, ensure_ascii=False)

    # -- ECharts JS 组件 --
    # splitArea
    split_area_js = (
        'splitArea:{show:true,areaStyle:{color:["rgba(27,42,74,0.02)","rgba(27,42,74,0.05)"]}},'
        if theme == "light" else "")

    # series
    target_coord_json = json.dumps(target_coord or [0.5, "应用层"])
    target_layer_js = json.dumps(target_layer, ensure_ascii=False)
    target_level_js = json.dumps(target_level + "捕获", ensure_ascii=False)
    series_js = (
        'var tl=' + target_layer_js + ';'
        'var tll=' + target_level_js + ';'
        'var series=[{'
        'type:"scatter", data:points,'
        'symbolSize:function(val,params){return params.data&&params.data.is_highlight?28:12;},'
        'itemStyle:{'
        'color:function(params){return params.data&&params.data.is_highlight?"' + accent + '":"rgba(27,42,74,0.22)";},'
        'opacity:function(params){return params.data&&params.data.is_highlight?1:0.55;},'
        'borderColor:function(params){return params.data&&params.data.is_highlight?"#FFFFFF":"transparent";},'
        'borderWidth:function(params){return params.data&&params.data.is_highlight?3:0;},'
        '},'
        'label:{'
        'show:true,'
        'formatter:function(params){if(!params.data||!params.data.is_highlight)return"";return params.data.name+"\\n"+tl+" / "+tll+"捕获";},'
        'fontSize:' + str(l_size) + ',fontWeight:"bold",color:"#1B2A4A",'
        'backgroundColor:"rgba(255,255,255,0.92)",borderRadius:6,padding:[4,8],'
        'position:"right",distance:10,'
        '},'
        'labelLayout:{hideOverlap:true,moveOverlap:"shiftY"},'
        'markPoint:{silent:true,symbol:"pin",symbolSize:48,'
        'itemStyle:{color:"' + accent + '"},'
        'data:[{coord:' + target_coord_json + '}],'
        '},'
        '}];'
    )

    # xAxis — 0-1 归一化，只显示低/中/高
    xaxis_js = (
        'xAxis:{'
        'type:"value",min:0,max:1,scale:false,boundaryGap:false,'
        'name:"",'
        'axisLine:{lineStyle:{color:"' + line_color + '",width:1.5}},'
        'axisLabel:{'
        'color:"' + text_color + '",fontSize:' + str(a_size) + ',fontWeight:600,'
        'formatter:function(v){if(v===0)return"低";if(v>=0.98)return"高";return"";}'
        '},'
        'axisTick:{show:true,inside:true,length:5},'
        'splitLine:{lineStyle:{color:"' + line_color + '",type:"dashed"}},'
        'splitNumber:4,'
        '},'
    )

    # yAxis — category 泳道
    yaxis_js = (
        'yAxis:{'
        'type:"category",inverse:true,'
        'data:' + lanes_json + ','
        + split_area_js + '\n    '
        'nameTextStyle:{color:"' + muted + '",fontSize:' + str(a_size) + '},'
        'axisLine:{lineStyle:{color:"' + line_color + '",width:1.5}},'
        'axisLabel:{color:"' + text_color + '",fontSize:16,fontWeight:700},'
        'splitLine:{show:false},'
        '},'
    )

    grid_js = 'grid:{left:160,right:80,top:100,bottom:100},'

    title_js = (
        'title:{text:' + title_json + ',subtext:' + subtitle_json + ',left:"center",top:32,'
        'textStyle:{color:"' + text_color + '",fontSize:' + str(t_size) + ',fontWeight:"bold"},'
        'subtextStyle:{color:"' + muted + '",fontSize:14}},'
    )

    if no_data:
        graphic_js = (
            'graphic:[{type:"text",left:"center",top:"middle",'
            'style:{text:"暂无可用图表数据",fill:"' + muted + '",fontSize:22,fontWeight:700,textAlign:"center"}}],'
        )
    else:
        graphic_js = (
            'graphic:[{type:"text",left:"center",bottom:42,'
            'style:{text:"价值捕获：低 → 中 → 高",fill:"rgba(0,0,0,0.35)",fontSize:16,fontWeight:"bold",textAlign:"center"}}],'
        )

    # -- 完整 HTML --
    result = '<!DOCTYPE html>\n'
    result += '<html><head><meta charset="utf-8">\n<style>\n'
    result += _echarts_fit_style(bg, width, height)
    result += '\n</style></head><body>\n'
    result += '<div id="chart-frame"><div id="chart"></div></div>\n'
    result += _echarts_script_tag() + '\n<script>\n'
    result += 'var points=' + ds_json + ';\n'
    result += 'var hiName=' + highlight_json + ';\n'
    result += series_js + '\n\n'
    result += 'var opt={\n'
    result += '  animation:false,\n'
    result += '  backgroundColor:"' + bg + '",\n'
    result += '  ' + title_js + '\n'
    result += '  tooltip:{trigger:"item",\n'
    result += '    formatter:function(p){\n'
    result += '      var d=p.data||{};\n'
    result += '      var rm=10;\n'
    result += '      return "<b>"+d.name+"</b><br/>"\n'
    result += '        +"层级: "+p.value[1]+"<br/>"\n'
    result += '        +"价值捕获率（相对）："+(d.x_raw!=null?p.value[0].toFixed(3):"-")+"<br/>"\n'
    result += '        +"价值捕获率（原始）："+(d.x_raw!=null?(d.x_raw+" / "+rm):"-");\n'
    result += '    }\n'
    result += '  },\n'
    result += '  legend:{show:false},\n'
    result += '  ' + grid_js + '\n'
    result += '  ' + xaxis_js + '\n'
    result += '  ' + yaxis_js + '\n'
    result += '  series:series,\n'
    result += '  ' + graphic_js + '\n'
    result += '};\n'
    result += "var chart=echarts.init(document.getElementById('chart'));\n"
    result += "chart.setOption(opt);\n"
    result += _echarts_fit_script("chart", width, height) + '\n'
    result += "</script></body></html>"

    return result



def build_stack_positioning_svg(companies: list[dict], highlight: str,
                                 params: dict | None = None) -> str:
    """产业链生态位图 HTML（ECharts 离散轴散点图）"""
    return _build_ecosystem_positioning_html(companies, highlight, params)



def build_competitive_landscape_svg(companies: list[dict], highlight: str,
                                     params: dict | None = None) -> str:
    """竞争格局矩阵 HTML（ECharts 四象限散点图）"""
    return _build_competitive_landscape_html(companies, highlight, params)


def render_competitive_landscape(companies: list[dict], highlight: str, dest: str,
                                  params: dict | None = None) -> bool:
    try:
        p = params or {}
        w = int(p.get("width") or 900)
        h = int(p.get("height") or 600)
        html = build_competitive_landscape_svg(companies, highlight, params)
        _html_to_png(html, dest, width=w, height=h, scale=2)
        return os.path.getsize(dest) > 1024
    except Exception:
        return False


def render_stack_positioning(companies: list[dict], highlight: str, dest: str,
                              params: dict | None = None) -> bool:
    try:
        p = params or {}
        w = int(p.get("width") or 1440)
        h = int(p.get("height") or 900)
        html = build_stack_positioning_svg(companies, highlight, params)
        _html_to_png(html, dest, width=w, height=h, scale=2)
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
