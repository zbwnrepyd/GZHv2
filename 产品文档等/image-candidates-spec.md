# 多候选图片采集方案

**覆盖**：截图多候选 + SVG 信息图多变体
**影响文件**：`asset_pipeline.py` / `infographic.py` / `image_variants` 表（已在定稿台方案中新建）

---

## 一、截图多候选

### 现状

每个槽位只截一张，逻辑是：找到第一个能用的 URL → 截图 → 直接 `upsert_asset`，没有候选池。

### 改动目标

每个槽位自动采集 **3 张候选**，写入 `image_variants`，不自动 select，等待人工在定稿台选定。

### 候选来源设计

**卡片 2 — office（公司真实照片）**

```
候选 1：About 页 hero 图（_scrape_page_hero_image(about_url)）
候选 2：Newsroom/Press 页第一张大图（_scrape_page_hero_image(newsroom_url)）
候选 3：Tavily 搜 "{company_name} office team photo" 的第一张图
```

**卡片 4 — product_main（主产品截图）**

```
候选 1：Playwright 截 main_product_img_src（LLM 推断的产品功能页）
候选 2：Playwright 截官网 website_url（首页完整截图）
候选 3：Tavily 搜 "{product_name} {company_name} interface screenshot" 第一张图
```

**卡片 5 — products_other（子产品截图，每产品一张，拼图前先多选）**

每个子产品各取 2 张候选：
```
候选 A：Playwright 截 product.url（产品页）
候选 B：Tavily 搜 "{product_name} {company_name}" 第一张图
```
定稿台展示时，每个产品的 2 张候选分别选一张，再拼图。

**卡片 7 — competitors（竞品截图）**

每个竞品各取 2 张候选：
```
候选 A：Playwright 截 competitor.url（竞品官网）
候选 B：Tavily 搜 "{competitor_name} product interface" 第一张图
兜底：Clearbit logo（仅当前两者都失败时）
```

### 代码改动

**`asset_pipeline.py`：新增 `_collect_candidates()` 通用函数**

```python
def _collect_candidates(
    db_path: str,
    images_root: str,
    company_name: str,
    asset_key: str,
    sources: list[dict],   # 每个 dict: {"type": "scrape|playwright|tavily", "url": str, "query": str}
    max_candidates: int = 3,
) -> int:
    """
    按 sources 列表依次尝试，每成功一次写入一条 image_variants 记录。
    返回实际写入的候选数量。
    不做 select，不写 company_assets。
    """
    from asset_store import insert_variant
    count = 0

    for src in sources:
        if count >= max_candidates:
            break

        dest = _variant_path(images_root, company_name, asset_key, count)
        success = False

        if src["type"] == "scrape":
            img_url = _scrape_page_hero_image(src["url"], company_name)
            if img_url:
                success = _download(img_url, dest)
                source_url = img_url

        elif src["type"] == "playwright":
            try:
                _playwright_screenshot(src["url"], dest)
                success = os.path.getsize(dest) > 512
                source_url = src["url"]
            except Exception:
                pass

        elif src["type"] == "tavily":
            img_url = _try_tavily_images(src["query"], dest)
            success = bool(img_url)
            source_url = img_url or ""

        elif src["type"] == "clearbit":
            img_url = f"https://logo.clearbit.com/{src['domain']}"
            success = _download(img_url, dest)
            source_url = img_url

        if success:
            insert_variant(
                db_path, company_name, asset_key,
                local_path=dest,
                source_type=src["type"],
                source_url=source_url,
            )
            count += 1

    return count


def _variant_path(images_root, company_name, asset_key, index):
    variants_dir = os.path.join(images_root, company_name, "variants")
    os.makedirs(variants_dir, exist_ok=True)
    return os.path.join(variants_dir, f"{asset_key}_{index}.png")
```

**各采集函数改为调用 `_collect_candidates()`**

```python
def collect_office(db_path, images_root, company_name, query_config):
    hints = query_config
    sources = [
        {"type": "scrape",     "url": hints.get("about_url", "")},
        {"type": "scrape",     "url": hints.get("newsroom_url", "")},
        {"type": "tavily",     "query": f'"{company_name}" office team photo'},
    ]
    sources = [s for s in sources if s.get("url") or s.get("query")]
    n = _collect_candidates(db_path, images_root, company_name, "office", sources)
    status = "ready" if n > 0 else "failed"
    upsert_asset(db_path, company_name, "office", status=status)
    # 注意：不写 local_path，等定稿台 select 后才写


def collect_product_main(db_path, images_root, company_name, query_config):
    sources = [
        {"type": "playwright", "url": query_config.get("product_page_url", "")},
        {"type": "playwright", "url": query_config.get("website_url", "")},
        {"type": "tavily",     "query": f'"{query_config["product_name"]}" "{company_name}" interface screenshot'},
    ]
    sources = [s for s in sources if s.get("url") or s.get("query")]
    n = _collect_candidates(db_path, images_root, company_name, "product_main", sources)
    upsert_asset(db_path, company_name, "product_main", status="ready" if n > 0 else "failed")


def collect_other_products(db_path, images_root, company_name, query_config):
    # 每个子产品单独采集 2 候选，存 asset_key = "products_other__{product_name}"
    for item in query_config["per_product"]:
        name = item["name"]
        asset_key = f"products_other__{name}"
        sources = [
            {"type": "playwright", "url": item.get("url", "")},
            {"type": "tavily",     "query": f'"{name}" "{company_name}" interface'},
        ]
        sources = [s for s in sources if s.get("url") or s.get("query")]
        _collect_candidates(db_path, images_root, company_name, asset_key, sources, max_candidates=2)
    # 主 asset_key 状态留给定稿台拼图后写入
    upsert_asset(db_path, company_name, "products_other", status="ready")


def compose_competitors(db_path, images_root, company_name, query_config):
    # 每个竞品单独采集 2 候选
    for item in query_config["per_comp"]:
        name = item["name"]
        asset_key = f"competitors__{name}"
        domain = _guess_domain(name)
        sources = [
            {"type": "playwright", "url": item.get("url", "")},
            {"type": "tavily",     "query": f'"{name}" product interface screenshot'},
            {"type": "clearbit",   "domain": domain},
        ]
        sources = [s for s in sources if s.get("url") or s.get("query") or s.get("domain")]
        _collect_candidates(db_path, images_root, company_name, asset_key, sources, max_candidates=2)
    upsert_asset(db_path, company_name, "competitors", status="ready")
```

---

## 二、SVG 信息图多变体

### 现状

`infographic.py` 的两个函数各只有**一套固定模板**：

- `_build_flywheel_svg()`：圆形阶段布局，固定深蓝背景，固定青色
- `_build_timeline_svg()`：左侧时间轴，固定垂直滚动

生成后 `_svg_to_png()` 直接覆盖写库，没有变体概念。

### 改动目标

每个 SVG 信息图自动生成 **3 套视觉变体**（相同数据，不同排版/配色），写入 `image_variants`，人工选定后写回 `company_assets`。

### 变体方案

**飞轮（card 6）— 3 套模板**

```
变体 A（现有）：圆形阶段布局，深蓝底，青色节点，弧线箭头
变体 B：水平流程图，同色系，方块→箭头→方块，更直观
变体 C：放射状布局，中心大圆，外圈阶段扇形展开
```

**时间线（card 3）— 3 套模板**

```
变体 A（现有）：左侧竖轴，右侧文字，顶到底滚动
变体 B：横向时间轴，从左到右，更适合宽图
变体 C：右侧竖轴（镜像），左侧文字，视觉层次不同
```

三套变体用相同的结构化 JSON 数据驱动，只改 SVG 模板本身，不重复调用 LLM。

### 代码改动

**`infographic.py`：新增多模板函数**

```python
# ── 飞轮变体 B：水平流程图 ──────────────────────────────────

FLYWHEEL_HORIZONTAL_SVG = Template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 320" width="900" height="320">
  <rect width="900" height="320" fill="#0B1629" rx="12"/>
  $stages
  $arrows
  <text x="450" y="300" text-anchor="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="14"
        fill="rgba(255,255,255,0.45)">$center_label</text>
</svg>""")

def _build_flywheel_horizontal(data: dict) -> str:
    """水平流程图变体：阶段横向排列，箭头连接"""
    stages = data.get("stages", [])
    n = len(stages)
    if n == 0:
        raise ValueError("stages 为空")
    step_w = 900 / n
    cx_base = step_w / 2
    cy = 150
    stage_svgs, arrow_svgs = [], []
    for i, s in enumerate(stages):
        cx = cx_base + i * step_w
        stage_svgs.append(f"""
  <rect x="{cx-70}" y="{cy-45}" width="140" height="90" rx="8"
        fill="#0F2040" stroke="rgba(41,184,212,0.5)" stroke-width="1.5"/>
  <text x="{cx}" y="{cy-10}" text-anchor="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="15" font-weight="700"
        fill="#29B8D4">{s['label']}</text>
  <text x="{cx}" y="{cy+14}" text-anchor="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="11"
        fill="rgba(255,255,255,0.65)">{s['desc'][:22]}</text>""")
        if i < n - 1:
            ax = cx + 70
            arrow_svgs.append(
                f'<line x1="{ax}" y1="{cy}" x2="{ax+step_w-140}" y2="{cy}" '
                f'stroke="rgba(41,184,212,0.6)" stroke-width="2" marker-end="url(#ah)"/>')
    return FLYWHEEL_HORIZONTAL_SVG.substitute(
        stages="\n".join(stage_svgs),
        arrows="\n".join(arrow_svgs),
        center_label=data.get("center", ""),
    )


# ── 飞轮变体 C：放射状布局 ──────────────────────────────────

def _build_flywheel_radial(data: dict) -> str:
    """放射状变体：中心标题，外圈均匀分布阶段扇形"""
    import math
    stages = data.get("stages", [])
    n = len(stages)
    cx, cy, r = 400, 400, 260
    stage_svgs = []
    for i, s in enumerate(stages):
        angle = 2 * math.pi * i / n - math.pi / 2
        sx = cx + r * math.cos(angle)
        sy = cy + r * math.sin(angle)
        stage_svgs.append(f"""
  <circle cx="{sx:.0f}" cy="{sy:.0f}" r="55"
          fill="#0F2040" stroke="rgba(41,184,212,0.55)" stroke-width="1.5"/>
  <line x1="{cx}" y1="{cy}" x2="{sx:.0f}" y2="{sy:.0f}"
        stroke="rgba(41,184,212,0.25)" stroke-width="1.5"/>
  <text x="{sx:.0f}" y="{sy:.0f}" text-anchor="middle" dominant-baseline="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="14" font-weight="700"
        fill="#29B8D4">{s['label']}</text>""")
    center_svg = f"""
  <circle cx="{cx}" cy="{cy}" r="65" fill="#0B1629" stroke="rgba(41,184,212,0.4)" stroke-width="2"/>
  <text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="16" font-weight="900"
        fill="#FFFFFF">{data.get('center','')}</text>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
  <rect width="800" height="800" fill="#0B1629" rx="12"/>
  {chr(10).join(stage_svgs)}
  {center_svg}
</svg>"""


# ── 时间线变体 B：横向时间轴 ────────────────────────────────

def _build_timeline_horizontal(data: dict) -> str:
    """横向时间轴变体"""
    events = data.get("events", [])
    n = len(events)
    if n == 0:
        raise ValueError("events 为空")
    w, h = 900, 320
    step = (w - 100) / max(n - 1, 1)
    svgs = []
    for i, ev in enumerate(events):
        x = 50 + i * step
        svgs.append(f"""
  <circle cx="{x:.0f}" cy="160" r="8" fill="#29B8D4"/>
  <line x1="{x:.0f}" y1="160" x2="{x:.0f}" y2="{'110' if i%2==0 else '210'}"
        stroke="rgba(41,184,212,0.4)" stroke-width="1.5"/>
  <text x="{x:.0f}" y="{'95' if i%2==0 else '240'}" text-anchor="middle"
        font-family="'IBM Plex Mono',monospace" font-size="13" font-weight="700"
        fill="#29B8D4">{ev.get('year','')}</text>
  <text x="{x:.0f}" y="{'75' if i%2==0 else '260'}" text-anchor="middle"
        font-family="'Noto Sans SC',sans-serif" font-size="12"
        fill="rgba(255,255,255,0.8)">{ev.get('title','')[:12]}</text>""")
    axis = f'<line x1="50" y1="160" x2="{w-50}" y2="160" stroke="url(#lineGrad)" stroke-width="2"/>'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs><linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#29B8D4"/>
    <stop offset="100%" stop-color="rgba(41,184,212,0.3)"/>
  </linearGradient></defs>
  <rect width="{w}" height="{h}" fill="#0B1629" rx="12"/>
  {axis}
  {''.join(svgs)}
</svg>"""


# ── 时间线变体 C：右侧竖轴（镜像） ─────────────────────────

def _build_timeline_right_axis(data: dict) -> str:
    """右侧竖轴变体：时间轴在右，文字在左，与变体A形成对称视觉"""
    events = data.get("events", [])
    row_h, top_pad, bottom_pad = 90, 60, 40
    total_h = top_pad + len(events) * row_h + bottom_pad
    line_end = total_h - 20
    axis_x = 640   # 轴在右侧 640px 处
    event_svgs = []
    for i, ev in enumerate(events):
        y = top_pad + i * row_h + 45
        title = ev.get("title", "")
        desc = ev.get("desc", "")[:58]
        year = ev.get("year", "")
        event_svgs.append(f"""
  <circle cx="{axis_x}" cy="{y}" r="6" fill="#29B8D4"/>
  <text x="{axis_x+20}" y="{y+5}" font-family="'IBM Plex Mono',monospace"
        font-size="15" font-weight="700" fill="#29B8D4">{year}</text>
  <text x="{axis_x-20}" y="{y-8}" text-anchor="end"
        font-family="'Noto Sans SC',sans-serif" font-size="18" font-weight="700"
        fill="#FFFFFF">{title}</text>
  <text x="{axis_x-20}" y="{y+18}" text-anchor="end"
        font-family="'Noto Sans SC',sans-serif" font-size="13"
        fill="rgba(255,255,255,0.55)">{desc}</text>""")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {total_h}" width="800" height="{total_h}">
  <defs><linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#29B8D4"/>
    <stop offset="100%" stop-color="rgba(41,184,212,0.3)"/>
  </linearGradient></defs>
  <rect width="800" height="{total_h}" fill="#0B1629" rx="12"/>
  <line x1="{axis_x}" y1="60" x2="{axis_x}" y2="{line_end}"
        stroke="url(#lineGrad)" stroke-width="2"/>
  {''.join(event_svgs)}
</svg>"""
```

**`infographic.py`：新增批量生成入口**

```python
FLYWHEEL_BUILDERS = [
    ("A_circular",    _build_flywheel_svg),           # 现有
    ("B_horizontal",  _build_flywheel_horizontal),    # 新增
    ("C_radial",      _build_flywheel_radial),        # 新增
]

TIMELINE_BUILDERS = [
    ("A_left_axis",   _build_timeline_svg),           # 现有
    ("B_horizontal",  _build_timeline_horizontal),    # 新增
    ("C_right_axis",  _build_timeline_right_axis),    # 新增
]


def generate_flywheel_variants(
    db_path: str, images_root: str, company_name: str,
    markdown: str, deepseek_call
) -> int:
    """
    生成飞轮 3 个变体，写入 image_variants，返回成功数量。
    数据只提取一次，三个模板共用。
    """
    from asset_store import insert_variant

    data = extract_flywheel_json(markdown, deepseek_call)
    if not data:
        return 0

    count = 0
    for variant_id, builder in FLYWHEEL_BUILDERS:
        try:
            svg = builder(data)
            dest = _variant_path(images_root, company_name, "flywheel", variant_id)
            _svg_to_png(svg, dest)
            if os.path.getsize(dest) > 512:
                insert_variant(
                    db_path, company_name, "flywheel",
                    local_path=dest,
                    source_type="svg_render",
                    prompt=f"flywheel_variant_{variant_id}",
                )
                count += 1
        except Exception as e:
            print(f"[infographic] flywheel 变体 {variant_id} 失败: {e}")

    upsert_asset(db_path, company_name, "flywheel",
                 status="ready" if count > 0 else "failed")
    return count


def generate_timeline_variants(
    db_path: str, images_root: str, company_name: str,
    markdown: str, deepseek_call
) -> int:
    """生成时间线 3 个变体，写入 image_variants"""
    from asset_store import insert_variant

    data = extract_timeline_json(markdown, deepseek_call)
    if not data:
        return 0

    count = 0
    for variant_id, builder in TIMELINE_BUILDERS:
        try:
            svg = builder(data)
            dest = _variant_path(images_root, company_name, "timeline", variant_id)
            _svg_to_png(svg, dest)
            if os.path.getsize(dest) > 512:
                insert_variant(
                    db_path, company_name, "timeline",
                    local_path=dest,
                    source_type="svg_render",
                    prompt=f"timeline_variant_{variant_id}",
                )
                count += 1
        except Exception as e:
            print(f"[infographic] timeline 变体 {variant_id} 失败: {e}")

    upsert_asset(db_path, company_name, "timeline",
                 status="ready" if count > 0 else "failed")
    return count
```

---

## 三、`asset_store.py` 补充函数

上面的代码调用了 `_variant_path()`，需要在 `asset_store.py` 或 `asset_pipeline.py` 中补充：

```python
def _variant_path(images_root: str, company_name: str,
                  asset_key: str, suffix) -> str:
    """生成变体文件路径，suffix 可以是数字或字符串"""
    variants_dir = os.path.join(images_root, company_name, "variants")
    os.makedirs(variants_dir, exist_ok=True)
    return os.path.join(variants_dir, f"{asset_key}__{suffix}.png")
```

---

## 四、变更汇总

| 文件 | 改动内容 |
|------|---------|
| `webapp/asset_pipeline.py` | 新增 `_collect_candidates()` / `_variant_path()` / `_scrape_page_hero_image()`；改写 `collect_office` / `collect_product_main` / `collect_other_products` / `compose_competitors`，均改为写 `image_variants` 而不直接 select |
| `webapp/infographic.py` | 新增 3 套飞轮模板（现有 + B + C）、3 套时间线模板（现有 + B + C）；新增 `generate_flywheel_variants()` / `generate_timeline_variants()` 批量入口；LLM 提取调用从 1 次改为共用（不增加 token 消耗） |
| `db/init_assets_db.sql` | 已在定稿台方案中新建 `image_variants` 表，本方案无需再改 |
| `webapp/asset_store.py` | `insert_variant()` 已在定稿台方案中定义，本方案直接调用 |

---

## 五、最终各槽位候选数量

| 卡片 | asset_key | 自动候选数 | 候选来源 |
|------|-----------|-----------|---------|
| 2 | office | 3 | About 页 + Newsroom 页 + Tavily |
| 3 | timeline | **3** | 竖轴A + 横向B + 右轴C（SVG 变体） |
| 4 | product_main | 3 | 产品功能页 + 官网首页 + Tavily |
| 5 | products_other | 每产品 2 | 产品页 + Tavily（各产品独立） |
| 6 | flywheel | **3** | 圆形A + 水平B + 放射C（SVG 变体） |
| 7 | competitors | 每竞品 2 | 官网截图 + Tavily（兜底 Clearbit logo） |

