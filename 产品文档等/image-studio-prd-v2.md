# 图片定稿台 v2 — 产品需求与技术文档

**项目**：GZHv2 / aistartups 知识卡片生产系统
**模块**：`/image-studio/`（新增）
**文档版本**：v2.0（取代 v1.0）
**日期**：2026-05-30

---

## 1. 核心策略调整

v1 把 AI 生图作为主路径，实践中质量难以控制。

v2 **翻转优先级**，参考 guizang-social-card-skill 的图源工作流：

```
主路径：网络图库搜索（真实照片 / 产品图 / 场景图）
备用路径：手动导入（本地上传 / 粘贴 URL）
例外路径：AI 生图（仅卡片 3/6，即 SVG 信息图）
```

| 卡片 | asset_key | v2 主路径 | 说明 |
|------|-----------|-----------|------|
| 1 封面 | logo | Clearbit → favicon（现有） | 已有，不动 |
| 2 公司形象 | office | **图库搜索**（Pexels 优先） | 办公室 / 团队 / 工作场景 |
| 3 发展时间线 | timeline | SVG 信息图（现有） | LLM → SVG，不变 |
| 4 主产品 | product_main | **图库搜索**（Pexels 优先） | 产品界面 / 使用场景 |
| 5 其他产品 | products_other | **图库搜索**（Pexels 优先） | 功能截图 / 产品组合 |
| 6 增长飞轮 | flywheel | SVG 信息图（现有） | LLM → SVG，不变 |
| 7 竞争格局 | competitors | **图库搜索**（Tavily 图片） | 行业竞品截图 / 赛道图 |

AI 生图（DALL-E 3）保留为**可选后备**，用户在定稿台底部可手动触发。

---

## 2. 图源优先级（采用 guizang 策略）

```
Pexels（支持中文关键词）
  → Unsplash（英文关键词，氛围图）
  → Tavily include_images（已集成，补漏）
  → 直接粘贴 URL / 本地上传
  [可选后备] → AI 生图（DALL-E 3）
```

### 2.1 Pexels 优先的理由

- **支持中文关键词**：`https://www.pexels.com/zh-cn/search/{关键词}/`
- 免费 API，200 次/小时
- 每次返回 `photos[].src.medium`（缩略图）+ `photos[].src.original`（高清），直接可用
- 不需要 Playwright，纯 HTTP

### 2.2 Tavily 图片的价值

- 项目已集成 Tavily，可直接在搜索时附带 `include_images: true`
- 返回的图片来自真实网页（竞品截图、产品新闻配图），适合卡片 7（竞争格局）
- 不额外消耗 API Key

### 2.3 版权处理原则

延用 guizang 策略：**先取图，后披露，用户决定**。

- 所有下载图片在 `image_variants.source_url` 记录来源
- 首次从外部取图后，前端展示来源信息（平台 + URL），询问是否在卡片中标注
- 用户选择写入数据库，不强制

---

## 3. 用户流程

```
进入图片定稿台（/image-studio/?company=Anthropic）
  └─ 总览面板：7 个有效槽位缩略图 + 状态角标
       └─ 点击某张卡片 → 槽位编辑视图
            ├─ 顶部：搜索栏（预填智能查询词，可编辑）+ [搜索] 按钮
            │         + 图库切换（Pexels / Unsplash / Tavily）
            ├─ 中部：候选图片网格（6-9 张，带来源标签）
            │    ├─ 点击任意张 → 下载到本地 → 加入变体库 → 进入定稿预览
            │    ├─ [更多] 按钮 → 翻页加载更多候选
            │    └─ [换词重搜] 链接
            ├─ 右侧：变体库（本次会话已保存的全部版本，可切换）
            └─ 底部：
                 ├─ 粘贴图片 URL → [下载并加入]
                 ├─ 上传本地文件 → [加入]
                 └─ [AI 生图（后备）] → 折叠面板，需要手动展开
```

---

## 4. 智能查询词生成

### 4.1 逻辑

进入槽位时，后端根据卡片的 `markdown_full` 调用 DeepSeek Flash 生成 **3 组搜索词**（英文 + 中文各一套）：

```python
# 查询词生成 prompt 模板
QUERY_GEN_PROMPT = """
根据以下知识卡片的 Markdown 内容，为该卡片的配图生成搜索词。

卡片主题：{card_topic}
公司名：{company_name}
Markdown 摘要：{markdown_summary}

要求：
1. 生成 3 组搜索词，每组包含：英文关键词（适合 Unsplash）、中文关键词（适合 Pexels）
2. 聚焦图片视觉内容，不要包含公司名（通用场景图效果更好）
3. 不要生成涉及人脸识别的词，不要生成版权敏感词
4. 返回 JSON 格式：[{"en": "...", "zh": "..."}, ...]
"""
```

### 4.2 各卡片默认查询词模板（无 LLM 时的 fallback）

| 卡片 | 英文 fallback | 中文 fallback |
|------|--------------|--------------|
| 2 office | `{company} office team workspace` | `科技公司 办公室 团队` |
| 4 product_main | `{company} app interface technology` | `科技 产品 界面 手机` |
| 5 products_other | `software product feature technology` | `软件 功能 科技 工具` |
| 7 competitors | `{industry} technology startup competition` | `科技 创业公司 行业 竞争` |

### 4.3 前端可编辑

搜索词在前端展示为可编辑输入框，用户可以：
- 直接修改关键词后重新搜索
- 切换"英文模式"/"中文模式"（决定优先走 Unsplash 还是 Pexels）
- 点击 3 组 LLM 生成词的任意一个快速填入

---

## 5. 后端新增功能

### 5.1 新增 API 端点

#### `GET /api/image-studio/<company>`
返回全部槽位概览（同 v1）。

#### `GET /api/image-studio/<company>/<asset_key>`
返回单个槽位的变体库（同 v1）。

---

#### `POST /api/image-studio/<company>/<asset_key>/search`
图库搜索，返回候选图片列表。

**Request**
```json
{
  "query": "SaaS office workspace technology",
  "source": "pexels",    // pexels | unsplash | tavily
  "lang": "zh",          // zh = 中文模式（走 pexels zh-cn），en = 英文模式
  "page": 1,
  "per_page": 9
}
```

**Response**
```json
{
  "results": [
    {
      "id": "pexels_3184339",
      "thumbnail_url": "https://images.pexels.com/photos/.../medium.jpeg",
      "full_url": "https://images.pexels.com/photos/.../large.jpeg",
      "source": "pexels",
      "source_page": "https://www.pexels.com/photo/...",
      "author": "Fauxels",
      "license": "Pexels License"
    }
  ],
  "total": 80,
  "page": 1,
  "query_used": "SaaS office workspace technology"
}
```

**实现**（`webapp/image_search.py` 新建）：

```python
def search_pexels(query: str, lang: str = "en", page: int = 1, per_page: int = 9) -> dict:
    """
    Pexels 图片搜索。
    lang="zh" 时走 https://www.pexels.com/zh-cn/search/{query}/
    lang="en" 时走 https://api.pexels.com/v1/search?query={query}
    """
    api_key = config.PEXELS_API_KEY
    if not api_key:
        return {"results": [], "error": "PEXELS_API_KEY not configured"}

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "page": page, "per_page": per_page,
              "locale": "zh-CN" if lang == "zh" else "en-US"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return {
        "results": [
            {
                "id": f"pexels_{p['id']}",
                "thumbnail_url": p["src"]["medium"],
                "full_url": p["src"]["large2x"],
                "source": "pexels",
                "source_page": p["url"],
                "author": p["photographer"],
                "license": "Pexels License",
            }
            for p in data.get("photos", [])
        ],
        "total": data.get("total_results", 0),
    }


def search_unsplash(query: str, page: int = 1, per_page: int = 9) -> dict:
    """Unsplash 图片搜索（英文关键词效果最佳）"""
    access_key = config.UNSPLASH_ACCESS_KEY
    if not access_key:
        return {"results": [], "error": "UNSPLASH_ACCESS_KEY not configured"}

    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "page": page, "per_page": per_page,
              "orientation": "landscape"}
    headers = {"Authorization": f"Client-ID {access_key}"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return {
        "results": [
            {
                "id": f"unsplash_{p['id']}",
                "thumbnail_url": p["urls"]["small"],
                "full_url": p["urls"]["regular"],
                "source": "unsplash",
                "source_page": p["links"]["html"],
                "author": p["user"]["name"],
                "license": "Unsplash License",
            }
            for p in data.get("results", [])
        ],
        "total": data.get("total", 0),
    }


def search_tavily_images(query: str, company_name: str = "") -> dict:
    """
    复用已有 Tavily 集成，增加 include_images=True。
    适合搜索真实产品截图、竞品界面图。
    """
    from pipeline import _search_tavily_query
    result = _search_tavily_query(query, include_images=True)
    images = result.get("images", [])

    return {
        "results": [
            {
                "id": f"tavily_{i}",
                "thumbnail_url": img if img.startswith("http") else "",
                "full_url": img,
                "source": "tavily",
                "source_page": img,
                "author": "",
                "license": "未知，请核实版权",
            }
            for i, img in enumerate(images)
            if img and img.startswith("http")
        ],
        "total": len(images),
    }


def search_images(query: str, source: str = "pexels",
                  lang: str = "en", page: int = 1, per_page: int = 9) -> dict:
    """统一图片搜索入口"""
    if source == "pexels":
        return search_pexels(query, lang=lang, page=page, per_page=per_page)
    elif source == "unsplash":
        return search_unsplash(query, page=page, per_page=per_page)
    elif source == "tavily":
        return search_tavily_images(query)
    else:
        return {"results": [], "error": f"未知 source: {source}"}
```

---

#### `POST /api/image-studio/<company>/<asset_key>/fetch`
下载候选图片到本地，写入变体库。

**Request**
```json
{
  "full_url": "https://images.pexels.com/photos/3184339/...",
  "thumbnail_url": "https://images.pexels.com/photos/3184339/.../medium.jpeg",
  "source": "pexels",
  "source_page": "https://www.pexels.com/photo/3184339",
  "author": "Fauxels",
  "license": "Pexels License",
  "attribution": false    // 用户选择是否在卡片中标注来源
}
```

**Response**
```json
{
  "id": 15,
  "local_path": "/images/Anthropic/variants/pexels_3184339.jpg",
  "source_type": "web_pexels",
  "thumbnail_url": "https://...",
  "source_page": "https://..."
}
```

**实现**：
- 复用 `asset_pipeline._download()` 下载到 `images/{company}/variants/{slug}.jpg`
- 写入 `image_variants` 表（`source_type` 区分来源：`web_pexels` / `web_unsplash` / `web_tavily` / `import_upload` / `import_url` / `api_generate`）
- 记录 `source_url`、`author`、`license`、`attribution_required`（布尔）

---

#### `POST /api/image-studio/<company>/<asset_key>/query`
（可选）调用 DeepSeek Flash 生成智能搜索词。

**Request**
```json
{ "card_markdown": "..." }
```

**Response**
```json
{
  "queries": [
    { "en": "SaaS workspace collaboration", "zh": "在线协作 工具 团队" },
    { "en": "productivity software interface", "zh": "效率工具 界面 软件" },
    { "en": "remote work technology", "zh": "远程办公 科技" }
  ]
}
```

调用成本低（DeepSeek Flash 极便宜），调用一次，缓存到 `localStorage`，不反复调。

---

#### `POST /api/image-studio/<company>/<asset_key>/import`
手动导入（本地文件上传 / 粘贴 URL）。同 v1，不变。

#### `PATCH /api/image-studio/<company>/<asset_key>/select`
选定变体，写回 `company_assets`。同 v1，不变。

#### `DELETE /api/image-studio/<company>/<asset_key>/variants/<id>`
删除变体。同 v1，不变。

---

### 5.2 Tavily 改造（最小改动）

在 `pipeline._search_tavily_query` 加可选参数：

```python
def _search_tavily_query(query: str, include_images: bool = False):
    body = {
        "query": query,
        "max_results": 10,
    }
    if include_images:
        body["include_images"] = True
    ...
```

不影响现有调用（`include_images` 默认 False）。

---

### 5.3 环境变量（新增 2 个，均为免费 API）

```bash
# .env.example 追加
PEXELS_API_KEY=...           # https://www.pexels.com/api/ 免费申请
UNSPLASH_ACCESS_KEY=...      # https://unsplash.com/developers 免费申请
```

两者均可选；如果都不配置，定稿台降级到 Tavily 图片搜索（已在项目中）+ 手动导入。

---

## 6. 数据模型

### 6.1 新增表 `image_variants`（与 v1 一致，新增版权字段）

```sql
-- db/init_assets_db.sql 追加
CREATE TABLE IF NOT EXISTS image_variants (
  id              INTEGER  PRIMARY KEY AUTOINCREMENT,
  company_name    TEXT     NOT NULL,
  asset_key       TEXT     NOT NULL,
  local_path      TEXT     NOT NULL,
  source_type     TEXT     NOT NULL,  -- web_pexels|web_unsplash|web_tavily|
                                       -- import_upload|import_url|api_generate
  source_url      TEXT,               -- 原始图片 URL
  source_page     TEXT,               -- 图片所在网页（用于标注）
  author          TEXT,               -- 图片作者
  license         TEXT,               -- 版权说明
  attribution_req INTEGER DEFAULT 0,  -- 1=用户选择标注来源
  prompt          TEXT,               -- AI 生图时使用的 prompt
  is_selected     INTEGER DEFAULT 0,  -- 1=当前选定版本
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_variants_company_asset
  ON image_variants(company_name, asset_key);
```

### 6.2 `company_assets` 无需修改字段

`upsert_asset` 写入时补充 `source_url` 字段（现有字段，已存在）。

---

## 7. 前端布局

### 7.1 总览面板（同 v1）

7 个槽位网格，卡片 8 置灰，状态角标，顶部工具栏，「全局搜索词偏好」（替代 v1 的「全局风格锁」）。

### 7.2 槽位编辑面板（重新设计）

```
┌──────────────────────────────────────────────────────────┬──────────────┐
│ 搜索区（上方全宽）                                         │              │
│  [ 搜索词输入框，预填 LLM 生成词 ]  [ Pexels ▾ ]  [搜索]  │ 变体库       │
│  快选词：[SaaS workspace]  [productivity tool]  [更换]    │（已下载版本） │
├──────────────────────────────────────────────────────────│              │
│ 候选图片网格（3列 × 3行 = 9张）                            │ 选定预览     │
│  [图1] [图2] [图3]                                        │ + 定稿按钮   │
│  [图4] [图5] [图6]                                        │              │
│  [图7] [图8] [图9]                                        │              │
│  [←前一页]  第 1/9 页  [下一页→]                          │              │
├──────────────────────────────────────────────────────────│              │
│ 其他导入：[粘贴 URL]  [上传本地图片]                        │              │
│ ▼ AI 生图（后备）——点击展开                                │              │
└──────────────────────────────────────────────────────────┴──────────────┘
```

**候选图片格**：

- 鼠标悬停显示：作者、图库来源角标（Pexels P / Unsplash U / Tavily T）
- 点击图片触发 `fetch` 接口 → 下载到本地 → 出现在变体库 → 进入右侧选定预览
- 版权提示（Tavily 来源图片显示"⚠️ 版权未核实"）

**AI 生图折叠面板（后备路径）**：

- 收起状态：一行灰色文字「AI 生图（后备，质量不稳定）▼」
- 展开后：prompt 输入框 + 生成按钮（调用现有 `/api/generate-image`）
- 展开状态在 localStorage 记住（默认收起）

### 7.3 版权披露弹窗

首次从 Pexels/Unsplash 取图后弹出（之后本会话不再重复）：

```
已从 Pexels 取图：
  assets/photo.jpg — Fauxels — https://www.pexels.com/photo/...
  
⚠️ 请自行判断版权是否适用于你的发布场景。

是否在卡片中标注来源？
  [标注来源：Photo · Pexels · @Fauxels]   [不标注，仅本地记录]
```

用户选择写入 `image_variants.attribution_req`，不影响图片下载和使用流程。

---

## 8. 文件结构变更

```
# 新建
webapp/image_search.py          # Pexels / Unsplash / Tavily 图片搜索
image-studio/
  index.html
  js/
    studio-app.js               # 主控制器
    search-panel.js             # 图库搜索 + 候选网格
    variant-sidebar.js          # 变体库 + 定稿预览
    query-gen.js                # 智能查询词生成 + 缓存
    studio-api.js               # fetch 封装
  css/
    studio.css

# 改动
db/init_assets_db.sql           # 追加 image_variants 表
webapp/asset_store.py           # 追加 list_variants / insert_variant /
                                #   select_variant / delete_variant
webapp/pipeline.py              # _search_tavily_query 加 include_images 参数
webapp/config.py                # 追加 PEXELS_API_KEY / UNSPLASH_ACCESS_KEY
webapp/app.py                   # 追加 /image-studio/ 静态路由 +
                                #   /api/image-studio/* 路由
.env.example                    # 追加两个新 key 说明
```

---

## 9. 实施计划

### Phase 1 — 数据层（1.5 小时）

1. `db/init_assets_db.sql` 追加 `image_variants` 表（含版权字段）。
2. `asset_store.py` 新增 4 个函数。
3. 运行现有 Python 测试确认无回归。

### Phase 2 — 图片搜索后端（2 小时）

4. `webapp/image_search.py` 实现 `search_pexels` / `search_unsplash` / `search_tavily_images` / `search_images`。
5. `pipeline._search_tavily_query` 加 `include_images` 参数。
6. `config.py` 追加 2 个字段；`.env.example` 更新说明。
7. `app.py` 新增路由：`/image-studio/` 静态、`/api/image-studio/*` 6 条。
8. `curl` 冒烟测试：搜索 Pexels、fetch 一张图、写入变体库。

### Phase 3 — 前端（4 小时）

9. `studio-api.js` 封装全部 fetch。
10. `studio-app.js` 总览网格，读取 `GET /api/image-studio/:company`。
11. `query-gen.js` 调用 `POST /query`，结果缓存到 `localStorage`。
12. `search-panel.js` 搜索框 + 图库切换 + 9 宫格候选 + 翻页 + 点击 fetch 下载。
13. `variant-sidebar.js` 变体库 + 定稿预览 + [定稿写回] 按钮。
14. 版权披露弹窗（session 级，不重复弹）。
15. AI 生图折叠面板（调用现有接口）。

### Phase 4 — 联调（1 小时）

16. 完整走一遍：进入定稿台 → Pexels 搜索 → 选图 → 下载 → 定稿 → 制作台验证。
17. 验证 Tavily 图片路径（竞争格局卡片）。
18. 验证 Unsplash fallback（PEXELS_API_KEY 为空时）。

---

## 10. 验收标准

| # | 验收项 | 验证方法 |
|---|--------|----------|
| 1 | 搜索词自动预填（Pexels 中文词 + Unsplash 英文词各一套） | 打开槽位编辑查看 |
| 2 | Pexels 搜索返回 9 张候选图，带缩略图和来源标签 | 操作验证 |
| 3 | 点击候选图片 → 自动下载到本地 variants 目录 | 文件系统检查 |
| 4 | 候选图出现在变体库，选定后写回 `company_assets.local_path` | `sqlite3` 查询 |
| 5 | 制作台图片已更新为选定变体（无需重启） | 制作台预览 |
| 6 | 版权披露弹窗在首次取图后出现，用户选择写入 DB | DB 查询 `attribution_req` |
| 7 | Tavily 图片搜索可用于卡片 7（竞争格局） | 操作验证 |
| 8 | 手动粘贴 URL 下载并加入变体库 | 操作验证 |
| 9 | AI 生图面板默认折叠，展开后可生成并加入变体库 | 操作验证 |
| 10 | PEXELS_API_KEY 为空时，自动降级到 Unsplash / Tavily | 删除 Key 测试 |
| 11 | `python3 -m py_compile webapp/*.py` 通过 | 命令行 |
| 12 | 既有 Python 测试全部通过 | `unittest discover` |

---

## 附录 A — 与 v1 的主要差异

| 维度 | v1 | v2 |
|------|----|----|
| 主路径 | AI 生图（DALL-E 3） | 图库搜索（Pexels → Unsplash → Tavily） |
| 提示词工程 | 结构化面板，5 个字段 | 取消，改为搜索词编辑框 |
| 全局风格锁 | 有 | 无（不同卡片用不同搜索词，风格由图库图决定） |
| 图源数量 | 1 张生成 → 选 | 每次搜索 9 张候选 → 翻页可到 80+ |
| AI 生图 | 主路径 | 折叠面板，可选后备 |
| 版权管理 | 无 | `attribution_req` 字段 + 披露弹窗 |
| 新增 API Key | 无 | PEXELS_API_KEY + UNSPLASH_ACCESS_KEY（均免费） |
| 卡片 3/6 | AI 生图（错误） | SVG 信息图（正确，维持现有） |

## 附录 B — Pexels / Unsplash 申请

**Pexels API**：https://www.pexels.com/api/
- 注册账号后即可申请，免审核，200 次/小时

**Unsplash Developer**：https://unsplash.com/developers
- Developer 应用申请，免费 50 次/小时（Demo 模式），足够本地使用
