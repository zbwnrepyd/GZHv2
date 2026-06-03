# 图片定稿台 · 完整技术方案

**覆盖**：多候选采集 + SVG 参数编辑 + 模板导入  
**取代**：image-studio-prd-v2.md / image-candidates-spec.md（两份旧文档作废）

---

## 一、数据层

### 1.1 新增表 `image_variants`（追加到 `db/init_assets_db.sql`）

```sql
CREATE TABLE IF NOT EXISTS image_variants (
  id              INTEGER  PRIMARY KEY AUTOINCREMENT,
  company_name    TEXT     NOT NULL,
  asset_key       TEXT     NOT NULL,
  local_path      TEXT     NOT NULL,
  source_type     TEXT     NOT NULL,
  -- screenshot_scrape | screenshot_playwright | screenshot_tavily
  -- svg_render | import_upload | import_url
  source_url      TEXT,
  author          TEXT,
  license         TEXT,
  svg_template_id TEXT,    -- SVG类专用：使用的模板 ID
  svg_params_json TEXT,    -- SVG类专用：渲染时的参数快照（JSON）
  is_selected     INTEGER  DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_variants_co_key
  ON image_variants(company_name, asset_key);
```

### 1.2 `asset_store.py` 新增函数

```python
def list_variants(db_path, company_name, asset_key) -> list[dict]
def insert_variant(db_path, company_name, asset_key, local_path,
                   source_type, source_url="", author="", license="",
                   svg_template_id=None, svg_params_json=None) -> int
def select_variant(db_path, company_name, asset_key, variant_id) -> dict
    # 事务：清除同 key 其他 is_selected=1，设新 is_selected=1，
    # 同步 upsert_asset(local_path, status="ready")
def delete_variant(db_path, company_name, asset_key, variant_id) -> bool
    # 若删除的是 is_selected，同步 company_assets.status = "missing"
```

---

## 二、截图多候选采集

### 2.1 核心函数（`asset_pipeline.py`）

```python
def _variant_path(images_root, company_name, asset_key, suffix) -> str:
    d = os.path.join(images_root, company_name, "variants")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{asset_key}__{suffix}.png")


def _collect_candidates(
    db_path, images_root, company_name, asset_key,
    sources: list[dict],   # 每项: {type, url?, query?, domain?}
    max_candidates=3,
) -> int:
    """
    依次尝试 sources，成功则写 image_variants。
    不做 select，不写 company_assets.local_path。
    返回实际写入数量。
    """
    from asset_store import insert_variant
    count = 0
    for src in sources:
        if count >= max_candidates:
            break
        dest = _variant_path(images_root, company_name, asset_key, count)
        ok, source_url = False, ""

        if src["type"] == "scrape":
            img_url = _scrape_page_hero_image(src.get("url", ""))
            if img_url:
                ok = _download(img_url, dest)
                source_url = img_url

        elif src["type"] == "playwright":
            try:
                _playwright_screenshot(src["url"], dest)
                ok = os.path.getsize(dest) > 512
                source_url = src["url"]
            except Exception:
                pass

        elif src["type"] == "tavily":
            img_url = _try_tavily_images(src["query"], dest)
            ok = bool(img_url)
            source_url = img_url or ""

        elif src["type"] == "clearbit":
            url = f"https://logo.clearbit.com/{src['domain']}"
            ok = _download(url, dest)
            source_url = url

        if ok:
            insert_variant(db_path, company_name, asset_key,
                           local_path=dest,
                           source_type=f"screenshot_{src['type']}",
                           source_url=source_url)
            count += 1
    return count
```

### 2.2 各槽位候选来源

**卡片 2 — office**（3 候选）

```python
sources = [
    {"type": "scrape",      "url": about_url},
    {"type": "scrape",      "url": newsroom_url},
    {"type": "tavily",      "query": f'"{company_name}" office team photo'},
]
```

**卡片 4 — product_main**（3 候选）

```python
sources = [
    {"type": "playwright",  "url": main_product_img_src},  # LLM推断的产品页
    {"type": "playwright",  "url": website_url},            # 官网首页
    {"type": "tavily",      "query": f'"{product_name}" "{company_name}" interface screenshot'},
]
```

**卡片 5 — products_other**（每产品 2 候选，asset_key=`products_other__<name>`）

```python
for p in other_products[:4]:
    sources = [
        {"type": "playwright", "url": p.get("url","")},
        {"type": "tavily",     "query": f'"{p["name"]}" "{company_name}" interface'},
    ]
    _collect_candidates(..., asset_key=f"products_other__{p['name']}", sources=sources, max_candidates=2)
```

**卡片 7 — competitors**（每竞品 2 候选，asset_key=`competitors__<name>`，兜底 clearbit）

```python
for c in competitors[:3]:
    sources = [
        {"type": "playwright", "url": c.get("url","")},
        {"type": "tavily",     "query": f'"{c["name"]}" product interface screenshot'},
        {"type": "clearbit",   "domain": _guess_domain(c["name"])},
    ]
    _collect_candidates(..., asset_key=f"competitors__{c['name']}", sources=sources, max_candidates=2)
```

所有槽位采集完成后统一调用 `upsert_asset(status="ready")`，不写 `local_path`（等定稿台 select）。

---

## 三、SVG 信息图模板系统

### 3.1 模板目录

```
webapp/
  infographic_templates/       ← 新目录
    __init__.py
    timeline_left_axis.py      ← 现有逻辑迁移（变体 A）
    timeline_horizontal.py     ← 新增（变体 B）
    timeline_right_axis.py     ← 新增（变体 C）
    flywheel_circular.py       ← 现有逻辑迁移（变体 A）
    flywheel_horizontal.py     ← 新增（变体 B）
    flywheel_radial.py         ← 新增（变体 C）
    _user_uploaded/            ← 用户上传的模板存放在此
      .gitignore
```

### 3.2 模板文件规范

每个模板是一个独立 `.py` 文件，必须导出两个名称：`META` 和 `build`。

```python
# 示例：webapp/infographic_templates/timeline_left_axis.py

META = {
    "id":        "timeline_left_axis",
    "name":      "左轴时间线",
    "asset_key": "timeline",           # "timeline" 或 "flywheel"
    "builtin":   True,                 # 用户上传的设为 False
    "params": [
        {
            "key":     "row_h",
            "label":   "行高",
            "type":    "range",
            "min":     60,
            "max":     140,
            "step":    5,
            "default": 90,
        },
        {
            "key":     "axis_x",
            "label":   "时间轴位置",
            "type":    "range",
            "min":     100,
            "max":     300,
            "step":    10,
            "default": 160,
        },
        {
            "key":     "accent_color",
            "label":   "强调色",
            "type":    "color",
            "default": "#29B8D4",
        },
        {
            "key":     "title_size",
            "label":   "标题字号",
            "type":    "range",
            "min":     14,
            "max":     24,
            "step":    1,
            "default": 18,
        },
    ],
}


def build(data: dict, params: dict) -> str:
    """
    data:   LLM 提取的结构化 JSON
            timeline → {"events": [{"year","title","desc"}, ...]}
            flywheel → {"center": "...", "stages": [{"label","desc"}, ...]}
    params: 用户在定稿台设定的参数值（key 同 META.params[].key）
    返回:   SVG 字符串
    """
    events     = data.get("events", [])
    row_h      = int(params.get("row_h",      META["params"][0]["default"]))
    axis_x     = int(params.get("axis_x",     META["params"][1]["default"]))
    accent     = params.get("accent_color",   META["params"][2]["default"])
    title_size = int(params.get("title_size", META["params"][3]["default"]))

    top_pad    = 60
    bottom_pad = 40
    total_h    = top_pad + len(events) * row_h + bottom_pad

    event_svgs = []
    for i, ev in enumerate(events):
        y     = top_pad + i * row_h + row_h // 2
        year  = ev.get("year", "")
        title = ev.get("title", "")
        desc  = ev.get("desc", "")
        if len(desc) > 60:
            desc = desc[:58] + "…"

        event_svgs.append(f"""
  <circle cx="{axis_x}" cy="{y}" r="6" fill="{accent}"/>
  <circle cx="{axis_x}" cy="{y}" r="14" fill="none"
          stroke="{accent}" stroke-opacity="0.25" stroke-width="1"/>
  <text x="{axis_x - 16}" y="{y + 5}" text-anchor="end"
        font-family="'IBM Plex Mono',monospace"
        font-size="15" font-weight="700" fill="{accent}">{year}</text>
  <text x="{axis_x + 16}" y="{y - 8}"
        font-family="'Noto Sans SC','PingFang SC',sans-serif"
        font-size="{title_size}" font-weight="700" fill="#FFFFFF">{title}</text>
  <text x="{axis_x + 16}" y="{y + 14}"
        font-family="'Noto Sans SC','PingFang SC',sans-serif"
        font-size="13" fill="rgba(255,255,255,0.55)">{desc}</text>""")

    line_end = total_h - 20
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 800 {total_h}" width="800" height="{total_h}">
  <defs>
    <linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.3"/>
    </linearGradient>
    <marker id="ah" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="5" markerHeight="5" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="{accent}"
            stroke-width="1.5" stroke-linecap="round"/>
    </marker>
  </defs>
  <rect width="800" height="{total_h}" fill="#0B1629" rx="12"/>
  <line x1="{axis_x}" y1="{top_pad}" x2="{axis_x}" y2="{line_end}"
        stroke="url(#lg)" stroke-width="2"/>
  {''.join(event_svgs)}
</svg>"""
```

### 3.3 模板管理器（`infographic_templates/__init__.py`）

```python
"""SVG 模板加载 / 注册 / 上传管理"""
import importlib.util
import os
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent
_USER_DIR     = _TEMPLATE_DIR / "_user_uploaded"
_USER_DIR.mkdir(exist_ok=True)

_registry: dict[str, object] = {}   # id → module


def _load_file(path: Path):
    spec   = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_all():
    """扫描内置目录 + 用户目录，注册全部模板"""
    for path in sorted(_TEMPLATE_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        _register(path)
    for path in sorted(_USER_DIR.glob("*.py")):
        _register(path)


def _register(path: Path):
    try:
        m = _load_file(path)
        if hasattr(m, "META") and hasattr(m, "build"):
            _registry[m.META["id"]] = m
    except Exception as e:
        print(f"[templates] 加载失败 {path.name}: {e}")


def get_all() -> list[dict]:
    """返回全部模板的 META 列表（用于 API 返回给前端）"""
    return [m.META for m in _registry.values()]


def get(template_id: str):
    """获取模板 module；未找到返回 None"""
    return _registry.get(template_id)


def upload(filename: str, content: bytes) -> dict:
    """
    保存用户上传的模板文件，验证后注册。
    返回 META 或抛出 ValueError。
    """
    if not filename.endswith(".py"):
        raise ValueError("只接受 .py 文件")
    dest = _USER_DIR / filename
    dest.write_bytes(content)
    try:
        m = _load_file(dest)
        if not hasattr(m, "META") or not hasattr(m, "build"):
            dest.unlink()
            raise ValueError("模板文件缺少 META 或 build 函数")
        _registry[m.META["id"]] = m
        return m.META
    except Exception as e:
        if dest.exists():
            dest.unlink()
        raise ValueError(f"模板解析失败：{e}")


def delete(template_id: str) -> bool:
    """删除用户上传的模板（内置模板不可删）"""
    m = _registry.get(template_id)
    if not m or m.META.get("builtin"):
        return False
    path = _USER_DIR / f"{template_id}.py"
    if path.exists():
        path.unlink()
    del _registry[template_id]
    return True


# 模块加载时自动注册
load_all()
```

### 3.4 渲染入口（`infographic.py` 改造）

原有 `render_flywheel` / `render_timeline` 保留，新增：

```python
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
    card_h = 800  # flywheel 固定 800；timeline 从 svg viewBox 读高度
    if 'viewBox' in svg:
        import re
        m2 = re.search(r'viewBox="[^"]*\s(\d+)"', svg)
        if m2:
            card_h = int(m2.group(1))
    _svg_to_png(svg, dest, width=800, height=card_h)
    return os.path.getsize(dest) > 512
```

---

## 四、新增 API 路由（`app.py`）

### SVG 模板管理

```
GET  /api/svg-templates
     → [{id, name, asset_key, builtin, params:[...]}, ...]

POST /api/svg-templates/upload
     multipart: file=<.py>
     → {meta: {...}} | {error: "..."}

DELETE /api/svg-templates/<template_id>
     → {deleted: true} | {error: "..."}
```

### 图片定稿台

```
GET  /image-studio/
     → 静态入口页

GET  /api/image-studio/<company>
     → 全部槽位概览（status / variant_count / selected_path）

GET  /api/image-studio/<company>/<asset_key>
     → 单槽位全部 variants

POST /api/image-studio/<company>/<asset_key>/render-svg
     {template_id, params: {key:val,...}}
     → 渲染 PNG → insert_variant → {variant_id, local_path}

PATCH /api/image-studio/<company>/<asset_key>/select
     {variant_id}
     → select_variant() 写回 company_assets → {ok}

DELETE /api/image-studio/<company>/<asset_key>/variants/<id>
     → delete_variant() → {deleted}

POST /api/image-studio/<company>/<asset_key>/import
     multipart file 或 JSON {url}
     → insert_variant → {variant_id, local_path}
```

**`render-svg` 实现**：

```python
@app.route("/api/image-studio/<company>/<asset_key>/render-svg", methods=["POST"])
def render_svg_variant(company, asset_key):
    if asset_key not in ("flywheel", "timeline"):
        return jsonify({"error": "仅支持 flywheel / timeline"}), 400

    body        = request.get_json()
    template_id = body.get("template_id")
    params      = body.get("params", {})

    # 取结构化数据（LLM 已提取，存在 final DB 对应卡片 markdown 里）
    card_index = 6 if asset_key == "flywheel" else 3
    markdown   = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
    if not markdown:
        return jsonify({"error": "未找到定稿内容"}), 404

    # LLM 提取结构化 JSON（复用现有函数，结果可缓存）
    def ds_call(sys, usr, **kw):
        return call_deepseek(config.DEEPSEEK_API_KEY, sys, usr, **kw)

    data = (extract_flywheel_json if asset_key == "flywheel"
            else extract_timeline_json)(markdown, ds_call)
    if not data:
        return jsonify({"error": "结构化数据提取失败"}), 500

    # 渲染
    suffix = f"{template_id}_{int(time.time())}"
    dest   = _variant_path(config.IMAGES_DIR, company, asset_key, suffix)

    try:
        from infographic import render_with_template
        ok = render_with_template(data, params, template_id, dest)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not ok:
        return jsonify({"error": "SVG 渲染失败"}), 500

    vid = insert_variant(
        config.DB_PATH_ASSETS, company, asset_key,
        local_path=f"/images/{company}/variants/{os.path.basename(dest)}",
        source_type="svg_render",
        svg_template_id=template_id,
        svg_params_json=json.dumps(params),
    )
    return jsonify({"variant_id": vid,
                    "local_path": f"/images/{company}/variants/{os.path.basename(dest)}"})
```

---

## 五、定稿台前端——SVG 槽位专属 UI

点击 flywheel 或 timeline 槽位时，三栏布局调整为：

```
┌──────────────────────┬─────────────────┬──────────────────┐
│ 模板选择（左栏）       │ 参数调整（中栏）  │ 变体库 + 定稿（右）│
└──────────────────────┴─────────────────┴──────────────────┘
```

**左栏 — 模板列表**

- 从 `GET /api/svg-templates` 拉取，按 `asset_key` 过滤显示
- 内置模板带 `built-in` 角标，用户上传的带 `custom` 角标
- 底部「上传模板 .py」按钮 → `<input type=file accept=".py">` → `POST /api/svg-templates/upload`
- 选中模板后，中栏自动更新为对应 `params` 的控件

**中栏 — 参数控件（根据 META.params 动态渲染）**

```js
function renderParamControls(params) {
  return params.map(p => {
    if (p.type === "range") return `
      <div class="ctrl-row">
        <label>${p.label}</label>
        <input type="range" min="${p.min}" max="${p.max}" step="${p.step}"
               value="${p.default}" data-key="${p.key}"
               oninput="onParamChange(this)">
        <span class="val" id="pv-${p.key}">${p.default}</span>
      </div>`;
    if (p.type === "color") return `
      <div class="ctrl-row">
        <label>${p.label}</label>
        <input type="color" value="${p.default}" data-key="${p.key}"
               oninput="onParamChange(this)">
      </div>`;
  }).join("");
}
```

底部「生成并加入变体库」按钮 → `POST /api/image-studio/<co>/<key>/render-svg` → 新变体追加到右栏

**右栏 — 变体库 + 定稿**（与截图槽位共用同一组件，无需单独实现）

---

## 六、自动初始化（文字生成完成后触发）

```python
# 在 _collect_assets_silently() 末尾追加：

# 飞轮：用全部内置模板各生成一张候选
for tpl_id in ["flywheel_circular", "flywheel_horizontal", "flywheel_radial"]:
    try:
        suffix = f"{tpl_id}_{int(time.time())}"
        dest   = _variant_path(images_root, company_name, "flywheel", suffix)
        ok     = render_with_template(flywheel_data, {}, tpl_id, dest)
        if ok:
            insert_variant(db_path, company_name, "flywheel",
                           local_path=dest, source_type="svg_render",
                           svg_template_id=tpl_id, svg_params_json="{}")
    except Exception:
        pass

# 时间线：同上
for tpl_id in ["timeline_left_axis", "timeline_horizontal", "timeline_right_axis"]:
    ...
```

`flywheel_data` / `timeline_data` 在文字生成后 LLM 已提取一次，复用即可，不重复调 LLM。

---

## 七、文件变更汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `db/init_assets_db.sql` | 追加 | `image_variants` 表 |
| `webapp/asset_store.py` | 追加 4 函数 | list / insert / select / delete variant |
| `webapp/asset_pipeline.py` | 新增 + 改写 | `_variant_path` / `_collect_candidates` / `_scrape_page_hero_image`；各采集函数改为写 variants |
| `webapp/infographic.py` | 新增 | `render_with_template()` |
| `webapp/infographic_templates/` | 新建目录 | `__init__.py` + 6 个内置模板 + `_user_uploaded/` |
| `webapp/app.py` | 追加路由 | `/image-studio/` 静态 + `/api/image-studio/*` + `/api/svg-templates/*` |
| `image-studio/` | 新建 | `index.html` + `js/` + `css/` |

---

## 八、建议实施顺序

1. `init_assets_db.sql` + `asset_store.py` 4 函数（数据层先行）
2. `infographic_templates/` 目录 + 内置 6 模板（迁移现有逻辑 + 新增 4 套）
3. `infographic.py` 新增 `render_with_template()`
4. `asset_pipeline.py` 改写（截图多候选）
5. `app.py` 追加全部路由
6. `image-studio/` 前端（总览 → 截图槽位 → SVG 槽位）
7. 联调：截图候选 → SVG 参数调整 → 模板上传 → 定稿写回

