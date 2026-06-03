# 图片搜索词改进方案 v2

**核心约束**：所有图片必须与目标公司直接相关，不允许行业通用图或占位图。

---

## 1. 问题重新定义

五张需要图片的卡片，诉求各不同：

| 卡片 | 需要的图片 | 正确来源 |
|------|-----------|---------|
| 2 office | 该公司真实照片（办公室/团队/创始人） | 新闻稿、LinkedIn、官网 About 页 |
| 4 product_main | 该公司主产品界面 | Playwright 截产品页 |
| 5 products_other | 该公司每个子产品界面 | Playwright 截各产品页（需 URL） |
| 7 competitors | 各竞品的产品界面 | Playwright 截竞品官网 |

**不允许的替代方案**：
- ❌ Pexels/Unsplash 通用图
- ❌ Lorem Flickr 随机图
- ❌ Picsum 占位图
- ❌ 没有该公司出现的任何图片

**允许的 fallback**：搜不到 → 该槽位标记 `failed`，进图片定稿台手动补。

---

## 2. 现有问题根因

### 问题一：搜索词没有锚定公司

```python
# 现在：行业词 + "office building"
queries = [f"{company_name} office building"]   # 只有公司名，Tavily 返回结果质量差

# 正确：多平台定向搜索
queries = [
    f'"{company_name}" office team photo',
    f'"{company_name}" headquarters',
    f'site:linkedin.com "{company_name}"',
    f'site:crunchbase.com "{company_name}"',
]
```

### 问题二：`other_products` 没有 URL 字段

当前 `other_products` JSON 结构：
```json
{"name": "产品A", "def": "...", "highlight": "..."}
```
没有产品页 URL，无法 Playwright 截图。

### 问题三：`competitors` 没有域名字段

当前 `competitors` JSON 结构：
```json
{"name": "OpenAI", "product": "ChatGPT", "data": "..."}
```
靠 `_guess_domain` 硬猜，准确率不稳定。

---

## 3. 两部分改动

### Part A：扩展 LLM 提取字段（`layer3-field-extraction.md`）

在 JSON schema 中补充 URL 字段：

```json
"other_products": [
  {
    "name": "产品名",
    "def": "一句话定义",
    "highlight": "亮点功能",
    "url": "产品独立页面URL，找不到填空字符串"
  }
],

"competitors": [
  {
    "name": "竞品名",
    "product": "核心产品",
    "data": "关键运营数据（含来源）",
    "url": "竞品官网URL，如 https://openai.com"
  }
]
```

同时补充 `office_photo_hints`：

```json
"office_photo_hints": {
  "newsroom_url": "公司新闻/媒体页URL，如 https://anthropic.com/news",
  "about_url": "公司About页URL，如 https://anthropic.com/about",
  "linkedin_url": "公司LinkedIn页URL（如已知）"
}
```

这三个字段 LLM 在研究阶段见过这些页面，有很高概率能填对。

---

### Part B：改写搜索词逻辑（`image_query.py`）

```python
def build_image_queries(record: dict) -> dict:
    company_name = record.get("company_name", "")
    website_url  = record.get("website_url", "")
    product_name = record.get("main_product_name", "")

    other_products = _json_array(record.get("other_products"))
    competitors    = _json_array(record.get("competitors"))
    office_hints   = record.get("office_photo_hints") or {}

    newsroom_url = office_hints.get("newsroom_url", "")
    about_url    = office_hints.get("about_url", "")
    linkedin_url = office_hints.get("linkedin_url", "")

    return {

        # ── 卡片2：公司真实照片 ──────────────────────────────
        "office": {
            # 策略：优先抓公司官方页面图，再 Tavily 搜新闻图
            "scrape_urls": [u for u in [about_url, newsroom_url] if u],
            "tavily_queries": [
                f'"{company_name}" office team photo',
                f'"{company_name}" headquarters building',
                f'"{company_name}" founders team',
            ],
            "allow_generic": False,   # 搜不到 → failed，不用通用图
        },

        # ── 卡片4：主产品截图 ────────────────────────────────
        "product_main": {
            # 策略：Playwright 截产品页（优先 main_product_img_src，其次官网）
            "playwright_urls": [
                u for u in [
                    record.get("main_product_img_src", ""),   # LLM 已推断的产品页 URL
                    website_url,
                ] if u and u.startswith("http")
            ],
            "tavily_queries": [
                f'"{product_name}" "{company_name}" interface screenshot',
                f'"{product_name}" app dashboard',
            ],
            "allow_generic": False,
        },

        # ── 卡片5：其他产品截图 ──────────────────────────────
        "products_other": {
            # 策略：对每个产品单独处理
            "per_product": [
                {
                    "name": p.get("name", ""),
                    "playwright_url": p.get("url", ""),          # 新字段
                    "tavily_queries": [
                        f'"{p.get("name")}" "{company_name}" interface',
                        f'"{company_name}" "{p.get("name")}" screenshot',
                    ],
                }
                for p in other_products[:4]
            ],
            "allow_generic": False,
        },

        # ── 卡片7：竞品产品截图 ──────────────────────────────
        "competitors": {
            # 策略：对每个竞品单独截图或搜图
            "per_comp": [
                {
                    "name": c.get("name", ""),
                    "playwright_url": c.get("url", ""),           # 新字段
                    "tavily_queries": [
                        f'"{c.get("name")}" product interface screenshot',
                        f'"{c.get("name")}" app UI',
                    ],
                }
                for c in competitors[:3]
            ],
            "fallback": "clearbit_logo",   # 只有竞品卡允许 logo 作为最后兜底
            "allow_generic": False,
        },
    }
```

---

## 4. 采集逻辑改写（`asset_pipeline.py`）

### 卡片 2 — office

```python
def collect_office(db_path, images_root, company_name, query_config):
    dest = os.path.join(asset_dir(images_root, company_name), "office.png")
    
    # 1. 优先：抓官网 About/Newsroom 页，提取 <img> 最大图
    for url in query_config.get("scrape_urls", []):
        img_url = _scrape_page_hero_image(url, company_name)
        if img_url and _download(img_url, dest):
            upsert_asset(..., source_type="web_scrape", status="ready")
            return
    
    # 2. Tavily 搜新闻/媒体图（含公司名，真实照片）
    for query in query_config["tavily_queries"]:
        img_url = _try_tavily_images(query, dest)
        if img_url:
            upsert_asset(..., source_type="web_search", status="ready")
            return
    
    # 3. 搜不到 → failed（不用通用图）
    upsert_asset(db_path, company_name, "office", status="failed")
```

新增 `_scrape_page_hero_image`：

```python
def _scrape_page_hero_image(page_url: str, company_name: str) -> str | None:
    """
    抓取指定页面，找面积最大且非 logo/icon 的 <img>，返回其 src URL。
    用于 About / Newsroom 页提取公司真实照片。
    """
    from bs4 import BeautifulSoup
    try:
        resp = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        
        candidates = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if not src or src.startswith("data:"):
                continue
            # 跳过明显的 icon/logo/svg
            if any(x in src.lower() for x in ["icon", "logo", "favicon", ".svg"]):
                continue
            # 补全相对路径
            if src.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(page_url)
                src = f"{base.scheme}://{base.netloc}{src}"
            # 用宽高属性估面积（无则给默认分）
            w = int(img.get("width", 0) or 0)
            h = int(img.get("height", 0) or 0)
            score = w * h if w and h else 50000
            candidates.append((score, src))
        
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]   # 面积最大的图
    except Exception:
        return None
```

### 卡片 5 — products_other

```python
def collect_other_products(db_path, images_root, company_name, query_config):
    product_images = []
    
    for item in query_config["per_product"]:
        name = item["name"]
        tmp_dest = os.path.join(asset_dir(images_root, company_name),
                                f"_tmp_{name}.png")
        
        # 1. Playwright 截产品页（有 URL 时）
        if item["playwright_url"]:
            try:
                _playwright_screenshot(item["playwright_url"], tmp_dest)
                if os.path.getsize(tmp_dest) > 512:
                    product_images.append(tmp_dest)
                    continue
            except Exception:
                pass
        
        # 2. Tavily 搜产品界面图
        for query in item["tavily_queries"]:
            img_url = _try_tavily_images(query, tmp_dest)
            if img_url:
                product_images.append(tmp_dest)
                break
    
    if not product_images:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None
    
    # 水平拼接（现有逻辑不变）
    dest = os.path.join(asset_dir(images_root, company_name), "products_other.png")
    _composite_horizontal(product_images, dest)
    upsert_asset(..., status="ready")
```

### 卡片 7 — competitors

```python
def compose_competitors(db_path, images_root, company_name, query_config):
    comp_images = []
    
    for item in query_config["per_comp"]:
        tmp_dest = os.path.join(asset_dir(images_root, company_name),
                                f"_tmp_comp_{item['name']}.png")
        
        # 1. Playwright 截竞品官网（有 URL 时）
        if item["playwright_url"]:
            try:
                _playwright_screenshot(item["playwright_url"], tmp_dest)
                if os.path.getsize(tmp_dest) > 512:
                    comp_images.append(tmp_dest)
                    continue
            except Exception:
                pass
        
        # 2. Tavily 搜竞品产品截图
        for query in item["tavily_queries"]:
            img_url = _try_tavily_images(query, tmp_dest)
            if img_url:
                comp_images.append(tmp_dest)
                break
        
        # 3. 最终兜底：Clearbit logo（竞品卡专属）
        else:
            domain = _guess_domain(item["name"])
            if domain:
                logo_url = f"https://logo.clearbit.com/{domain}"
                if _download(logo_url, tmp_dest):
                    comp_images.append(tmp_dest)
    
    # 后续拼图逻辑不变
```

---

## 5. 变更汇总

| 文件 | 改动 |
|------|------|
| `prompts/layer3-field-extraction.md` | `other_products[]` 增加 `url` 字段；`competitors[]` 增加 `url` 字段；新增 `office_photo_hints` 对象 |
| `db/init_research_db.sql` | 无需改动（JSON 字段本来就是自由结构，新字段向后兼容） |
| `webapp/image_query.py` | 新建，实现 `build_image_queries()` |
| `webapp/asset_pipeline.py` | `collect_office` 改用 scrape + Tavily；`collect_other_products` / `compose_competitors` 改用 URL 优先 + Tavily；删除 Lorem Flickr 和 Picsum fallback |

**不改的**：下载工具函数、Playwright 截图、PIL 拼图、OSM 地图、upsert_asset 写库逻辑。

---

## 6. 预期结果

| 卡片 | 改进前 | 改进后 |
|------|-------|-------|
| 2 office | 随机办公楼/Picsum | 公司 About 页真实照片，或 Tavily 搜出的新闻配图 |
| 4 product_main | 营销落地页截图 | 产品功能页截图（LLM 提供的 `main_product_img_src`） |
| 5 products_other | 随机股票图拼接 | 各产品页 Playwright 截图拼接 |
| 7 competitors | 竞品 favicon 格子拼图 | 竞品官网截图拼图，兜底 Clearbit logo |
| 搜不到时 | Picsum 随机图 | `status=failed`，进图片定稿台手动补 |

